"""MinerU PDF to Markdown converter.

The implementation follows the MinerU precise API local-file flow:

1. Request a signed upload URL with ``/api/v4/file-urls/batch``.
2. Upload the local PDF to that URL with HTTP PUT.
3. Poll ``/api/v4/extract-results/batch/{batch_id}`` until the job is done.
4. Download and unzip MinerU's result package.
5. Save raw Markdown, rewrite image paths, normalize chemistry text, and save
   the cleaned Markdown.

Only MinerU is used here. There is no Docling or Mistral fallback.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any

import requests

from alumina_sol_extractor.utils.chemical_text_normalizer import (
    normalize_mineru_markdown_chemistry,
)
from alumina_sol_extractor.utils.figure_utils import rewrite_mineru_image_paths


class MinerUAPIError(RuntimeError):
    """Raised when the MinerU API returns an error or times out."""


@dataclass
class MinerUPDFToMarkdown:
    """Convert one PDF file to cleaned Markdown with MinerU."""

    project_root: Path
    mineru_raw_dir: Path
    markdown_output_dir: Path
    output_dir: Path
    api_key_env: str = "MINERU_API_KEY"
    base_url_env: str = "MINERU_BASE_URL"
    poll_interval_seconds: int = 3
    max_wait_seconds: int = 600
    save_raw: bool = True
    save_cleaned: bool = True
    chemistry_enabled: bool = True
    unicode_subscript: bool = False
    model_version: str = "vlm"
    language: str = "ch"
    is_ocr: bool = True
    enable_formula: bool = True
    enable_table: bool = True
    request_timeout_seconds: int = 120
    last_outputs: dict[str, Path] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self._load_env_file(self.project_root / ".env")
        self.mineru_raw_dir = self._resolve_path(self.mineru_raw_dir)
        self.markdown_output_dir = self._resolve_path(self.markdown_output_dir)
        self.output_dir = self._resolve_path(self.output_dir)

        self.api_key = os.environ.get(self.api_key_env)
        if not self.api_key:
            raise MinerUAPIError(
                f"Missing MinerU API key. Please set environment variable "
                f"{self.api_key_env}."
            )

        base_url = os.environ.get(self.base_url_env, "https://mineru.net")
        self.base_url = base_url.rstrip("/")

    def convert_file(self, input_pdf: Path, output_md: Path) -> Path:
        """Convert a local PDF to cleaned Markdown and return the Markdown path."""
        input_pdf = Path(input_pdf).resolve()
        if not input_pdf.exists():
            raise FileNotFoundError(f"Input PDF does not exist: {input_pdf}")

        paper_id = input_pdf.stem
        raw_dir = self.mineru_raw_dir / paper_id
        figures_dir = self.output_dir / paper_id / "figures_all"
        output_md = self._resolve_path(output_md)
        raw_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)
        output_md.parent.mkdir(parents=True, exist_ok=True)

        batch_id, upload_url, create_response = self._create_upload_task(
            input_pdf=input_pdf,
            paper_id=paper_id,
        )
        self._write_json(raw_dir / "mineru_create_response.json", create_response)

        self._upload_pdf(input_pdf=input_pdf, upload_url=upload_url)
        poll_response = self._poll_until_done(batch_id=batch_id)
        self._write_json(raw_dir / "mineru_poll_response.json", poll_response)

        result = self._select_result(poll_response, input_pdf.name)
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise MinerUAPIError("MinerU finished but did not return full_zip_url.")

        zip_path = raw_dir / "mineru_result.zip"
        self._download_file(zip_url, zip_path)
        extracted_dir = raw_dir / "extracted"
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)
        extracted_dir.mkdir(parents=True, exist_ok=True)
        self._extract_zip(zip_path, extracted_dir)

        mineru_md = self._find_markdown(extracted_dir)
        raw_markdown = mineru_md.read_text(encoding="utf-8")
        raw_mineru_md = raw_dir / "raw_mineru.md"
        if self.save_raw:
            raw_mineru_md.write_text(raw_markdown, encoding="utf-8")

        cleaned = rewrite_mineru_image_paths(
            markdown=raw_markdown,
            markdown_dir=mineru_md.parent,
            project_root=self.project_root,
            paper_id=paper_id,
        )
        if self.chemistry_enabled:
            cleaned = normalize_mineru_markdown_chemistry(
                cleaned,
                unicode_subscript=self.unicode_subscript,
            )
        if self.save_cleaned:
            output_md.write_text(cleaned, encoding="utf-8")

        self.last_outputs = {
            "input_pdf": input_pdf,
            "raw_dir": raw_dir,
            "raw_mineru_md": raw_mineru_md,
            "mineru_zip": zip_path,
            "extracted_dir": extracted_dir,
            "figures_all_dir": figures_dir,
            "cleaned_markdown": output_md,
        }
        return output_md

    def _create_upload_task(self, input_pdf: Path, paper_id: str) -> tuple[str, str, dict]:
        url = f"{self.base_url}/api/v4/file-urls/batch"
        payload = {
            "files": [
                {
                    "name": input_pdf.name,
                    "data_id": self._safe_data_id(paper_id),
                    "is_ocr": self.is_ocr,
                }
            ],
            "model_version": self.model_version,
            "language": self.language,
            "enable_formula": self.enable_formula,
            "enable_table": self.enable_table,
        }
        response = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.request_timeout_seconds,
        )
        data = self._checked_json(response)
        result = data["data"]
        file_urls = result.get("file_urls") or []
        if not file_urls:
            raise MinerUAPIError(f"MinerU did not return file_urls: {data}")
        return result["batch_id"], file_urls[0], data

    def _upload_pdf(self, input_pdf: Path, upload_url: str) -> None:
        with input_pdf.open("rb") as file_obj:
            response = requests.put(
                upload_url,
                data=file_obj,
                timeout=self.request_timeout_seconds,
            )
        if response.status_code not in (200, 201):
            raise MinerUAPIError(
                f"MinerU file upload failed: HTTP {response.status_code} "
                f"{response.text[:500]}"
            )

    def _poll_until_done(self, batch_id: str) -> dict:
        url = f"{self.base_url}/api/v4/extract-results/batch/{batch_id}"
        started = time.time()
        while time.time() - started <= self.max_wait_seconds:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.request_timeout_seconds,
            )
            data = self._checked_json(response)
            result = self._select_result(data, expected_name=None)
            state = result.get("state")
            if state == "done":
                return data
            if state == "failed":
                raise MinerUAPIError(
                    f"MinerU parsing failed: {result.get('err_msg', 'unknown error')}"
                )
            time.sleep(self.poll_interval_seconds)

        raise MinerUAPIError(
            f"MinerU polling timed out after {self.max_wait_seconds} seconds. "
            f"batch_id={batch_id}"
        )

    @staticmethod
    def _select_result(data: dict, expected_name: str | None) -> dict:
        results = data.get("data", {}).get("extract_result", [])
        if isinstance(results, dict):
            results = [results]
        if not results:
            raise MinerUAPIError(f"MinerU response has no extract_result: {data}")
        if expected_name:
            for item in results:
                if item.get("file_name") == expected_name:
                    return item
        return results[0]

    def _download_file(self, url: str, output_path: Path) -> None:
        with requests.get(url, stream=True, timeout=self.request_timeout_seconds) as r:
            r.raise_for_status()
            with output_path.open("wb") as file_obj:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)

    @staticmethod
    def _extract_zip(zip_path: Path, output_dir: Path) -> None:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(output_dir)

    @staticmethod
    def _find_markdown(extracted_dir: Path) -> Path:
        preferred = list(extracted_dir.rglob("full.md"))
        if preferred:
            return preferred[0]
        markdown_files = list(extracted_dir.rglob("*.md"))
        if markdown_files:
            return markdown_files[0]
        raise MinerUAPIError(f"No Markdown file found in MinerU zip: {extracted_dir}")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @staticmethod
    def _checked_json(response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise MinerUAPIError(
                f"MinerU returned non-JSON response: HTTP {response.status_code} "
                f"{response.text[:500]}"
            ) from exc

        if response.status_code != 200:
            raise MinerUAPIError(
                f"MinerU HTTP error {response.status_code}: "
                f"{json.dumps(data, ensure_ascii=False)}"
            )
        if data.get("code") != 0:
            raise MinerUAPIError(
                f"MinerU API error: {json.dumps(data, ensure_ascii=False)}"
            )
        return data

    def _resolve_path(self, path: str | Path) -> Path:
        path = Path(path)
        if path.is_absolute():
            return path
        return self.project_root / path

    @staticmethod
    def _safe_data_id(value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
        digest = sha1(value.encode("utf-8")).hexdigest()[:10]
        safe = safe or "paper"
        return f"{safe[:110]}-{digest}"[:128]

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _load_env_file(env_path: Path) -> None:
        """Load simple KEY=VALUE pairs from .env without adding a dependency."""
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
