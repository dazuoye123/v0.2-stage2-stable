"""OpenAI-compatible VLM client skeleton for Stage 4."""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class VLMRequest:
    image_path: str
    prompt: str
    model: str | None = None


class VisionLanguageModelClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        dry_run: bool = True,
        timeout_s: int = 120,
    ) -> None:
        env_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        self.api_key = api_key or env_api_key
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or (
            "https://dashscope.aliyuncs.com/compatible-mode/v1" if os.getenv("DASHSCOPE_API_KEY") else None
        )
        self.model_name = model_name or os.getenv("VLM_MODEL_NAME") or "qwen-vl-max"
        self.dry_run = dry_run
        self.timeout_s = timeout_s

    def extract(self, request: VLMRequest) -> dict[str, Any]:
        if self.dry_run:
            return {
                "dry_run": True,
                "model": request.model or self.model_name,
                "image_path": request.image_path,
                "prompt": request.prompt,
                "response_text": None,
            }
        if not self.api_key:
            raise RuntimeError("Live VLM mode requires OPENAI_API_KEY or DASHSCOPE_API_KEY.")
        if not self.base_url:
            raise RuntimeError("Live VLM mode requires OPENAI_BASE_URL or a DashScope-compatible default.")
        if not Path(request.image_path).exists():
            raise RuntimeError(f"Image not found for VLM request: {request.image_path}")
        image_path = Path(request.image_path).resolve()
        image_url = self._image_path_to_data_url(image_path)

        payload = {
            "model": request.model or self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        }
        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_s,
        )
        if response.status_code >= 400:
            message = response.text.strip()
            raise RuntimeError(
                f"VLM request failed with status {response.status_code}: {message[:1000]}"
            )
        response_payload = response.json()
        response_text = self._coerce_response_text(
            response_payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        return {
            "dry_run": False,
            "model": request.model or self.model_name,
            "image_path": request.image_path,
            "prompt": request.prompt,
            "response_text": response_text,
            "response_payload": response_payload,
        }

    @staticmethod
    def _image_path_to_data_url(image_path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type:
            mime_type = "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _coerce_response_text(content: Any) -> str | None:
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(part for part in text_parts if part) or None
        return str(content)
