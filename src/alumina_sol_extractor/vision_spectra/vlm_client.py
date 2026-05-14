"""OpenAI-compatible VLM client for Stage 4 vision extraction."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class VLMRequest:
    image_path: str
    prompt: str
    model: str | None = None


class VLMRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str,
        is_transient: bool,
        retry_attempts: int,
        max_retries: int,
        timeout_seconds: int,
        attempt_errors: list[dict[str, Any]] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.is_transient = is_transient
        self.retry_attempts = retry_attempts
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.attempt_errors = attempt_errors or []
        self.status_code = status_code


class VisionLanguageModelClient:
    DEFAULT_TIMEOUT_SECONDS = 300
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BACKOFF_SECONDS = 5.0

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        dry_run: bool = True,
        timeout_s: int | None = None,
        max_retries: int | None = None,
        retry_backoff_s: float | None = None,
    ) -> None:
        env_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        self.api_key = api_key or env_api_key
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or (
            "https://dashscope.aliyuncs.com/compatible-mode/v1" if os.getenv("DASHSCOPE_API_KEY") else None
        )
        self.model_name = model_name or os.getenv("VLM_MODEL_NAME") or "qwen-vl-max"
        self.dry_run = dry_run
        self.config_warnings: list[str] = []
        self.timeout_s = timeout_s or self._read_positive_int_env(
            "VLM_TIMEOUT_SECONDS",
            default=self.DEFAULT_TIMEOUT_SECONDS,
        )
        self.max_retries = max_retries or self._read_positive_int_env(
            "VLM_MAX_RETRIES",
            default=self.DEFAULT_MAX_RETRIES,
        )
        self.retry_backoff_s = retry_backoff_s or self._read_positive_float_env(
            "VLM_RETRY_BACKOFF_SECONDS",
            default=self.DEFAULT_RETRY_BACKOFF_SECONDS,
        )

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
        response_payload = self._post_with_retry(payload=payload)
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
            "timeout_seconds": self.timeout_s,
        }

    def _post_with_retry(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        attempt_errors: list[dict[str, Any]] = []
        max_attempts = max(1, self.max_retries)
        last_error: VLMRequestError | None = None
        for attempt_index in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=self.timeout_s,
                )
                if response.status_code >= 400:
                    message = response.text.strip()
                    error_type, is_transient = self._classify_http_failure(response.status_code, message)
                    if is_transient and attempt_index < max_attempts:
                        attempt_errors.append(
                            {
                                "attempt_index": attempt_index,
                                "error_type": error_type,
                                "error_message": message[:1000],
                                "status_code": response.status_code,
                            }
                        )
                        time.sleep(self._backoff_for_attempt(attempt_index))
                        continue
                    raise VLMRequestError(
                        f"VLM request failed with status {response.status_code}: {message[:1000]}",
                        error_type=error_type,
                        is_transient=is_transient,
                        retry_attempts=attempt_index,
                        max_retries=max_attempts,
                        timeout_seconds=self.timeout_s,
                        attempt_errors=[*attempt_errors, {
                            "attempt_index": attempt_index,
                            "error_type": error_type,
                            "error_message": message[:1000],
                            "status_code": response.status_code,
                        }],
                        status_code=response.status_code,
                    )
                return response.json()
            except requests.exceptions.ReadTimeout as exc:
                last_error = self._build_request_exception(
                    exc,
                    error_type="read_timeout",
                    is_transient=True,
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    attempt_errors=attempt_errors,
                )
            except requests.exceptions.ConnectTimeout as exc:
                last_error = self._build_request_exception(
                    exc,
                    error_type="connect_timeout",
                    is_transient=True,
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    attempt_errors=attempt_errors,
                )
            except requests.exceptions.ConnectionError as exc:
                last_error = self._build_request_exception(
                    exc,
                    error_type="connection_error",
                    is_transient=True,
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    attempt_errors=attempt_errors,
                )
            except requests.exceptions.Timeout as exc:
                last_error = self._build_request_exception(
                    exc,
                    error_type="timeout",
                    is_transient=True,
                    attempt_index=attempt_index,
                    max_attempts=max_attempts,
                    attempt_errors=attempt_errors,
                )
            if last_error is None:
                break
            if attempt_index < max_attempts and last_error.is_transient:
                time.sleep(self._backoff_for_attempt(attempt_index))
                continue
            raise last_error
        if last_error is not None:
            raise last_error
        raise RuntimeError("VLM request failed without a captured error.")

    def _build_request_exception(
        self,
        exc: Exception,
        *,
        error_type: str,
        is_transient: bool,
        attempt_index: int,
        max_attempts: int,
        attempt_errors: list[dict[str, Any]],
    ) -> VLMRequestError:
        message = str(exc)
        current_attempt_errors = [*attempt_errors, {
            "attempt_index": attempt_index,
            "error_type": error_type,
            "error_message": message,
        }]
        return VLMRequestError(
            message or error_type,
            error_type=error_type,
            is_transient=is_transient,
            retry_attempts=attempt_index,
            max_retries=max_attempts,
            timeout_seconds=self.timeout_s,
            attempt_errors=current_attempt_errors,
        )

    def _backoff_for_attempt(self, attempt_index: int) -> float:
        return float(self.retry_backoff_s) * max(1, 2 ** (attempt_index - 1))

    @staticmethod
    def _classify_http_failure(status_code: int, message: str) -> tuple[str, bool]:
        if status_code == 429:
            return "http_429", True
        if status_code in {500, 502, 503, 504}:
            return f"http_{status_code}", True
        if status_code in {401, 403}:
            return f"http_{status_code}", False
        return f"http_{status_code}", False

    def _read_positive_int_env(self, env_name: str, *, default: int) -> int:
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value.strip() == "":
            return default
        try:
            value = int(raw_value)
        except ValueError:
            self.config_warnings.append(f"{env_name}_invalid_using_default:{raw_value}")
            return default
        if value <= 0:
            self.config_warnings.append(f"{env_name}_non_positive_using_default:{raw_value}")
            return default
        return value

    def _read_positive_float_env(self, env_name: str, *, default: float) -> float:
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value.strip() == "":
            return default
        try:
            value = float(raw_value)
        except ValueError:
            self.config_warnings.append(f"{env_name}_invalid_using_default:{raw_value}")
            return default
        if value <= 0:
            self.config_warnings.append(f"{env_name}_non_positive_using_default:{raw_value}")
            return default
        return value

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
