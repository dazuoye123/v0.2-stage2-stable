from __future__ import annotations

import requests

from alumina_sol_extractor.vision_spectra.vlm_client import VLMRequestError, VisionLanguageModelClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_read_timeout_retries_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.ReadTimeout("Read timed out")
        return _FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.requests.post", fake_post)
    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.time.sleep", lambda *_args, **_kwargs: None)

    client = VisionLanguageModelClient(
        dry_run=False,
        api_key="key",
        base_url="https://example.com/v1",
        timeout_s=300,
        max_retries=3,
        retry_backoff_s=0.01,
    )
    payload = client._post_with_retry(payload={"model": "x"})

    assert payload["choices"][0]["message"]["content"] == "{}"
    assert calls["count"] == 3


def test_http_429_retries(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(429, text="rate limited")
        return _FakeResponse(200, {"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.requests.post", fake_post)
    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.time.sleep", lambda *_args, **_kwargs: None)

    client = VisionLanguageModelClient(
        dry_run=False,
        api_key="key",
        base_url="https://example.com/v1",
        timeout_s=300,
        max_retries=3,
        retry_backoff_s=0.01,
    )
    payload = client._post_with_retry(payload={"model": "x"})

    assert payload["choices"][0]["message"]["content"] == "{}"
    assert calls["count"] == 2


def test_http_401_does_not_retry(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return _FakeResponse(401, text="unauthorized")

    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.requests.post", fake_post)
    monkeypatch.setattr("alumina_sol_extractor.vision_spectra.vlm_client.time.sleep", lambda *_args, **_kwargs: None)

    client = VisionLanguageModelClient(
        dry_run=False,
        api_key="key",
        base_url="https://example.com/v1",
        timeout_s=300,
        max_retries=3,
        retry_backoff_s=0.01,
    )

    try:
        client._post_with_retry(payload={"model": "x"})
    except VLMRequestError as exc:
        assert exc.error_type == "http_401"
        assert exc.retry_attempts == 1
    else:
        raise AssertionError("Expected VLMRequestError")
    assert calls["count"] == 1
