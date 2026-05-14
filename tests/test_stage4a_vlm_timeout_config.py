from __future__ import annotations

from alumina_sol_extractor.vision_spectra.vlm_client import VisionLanguageModelClient


def test_vlm_timeout_defaults(monkeypatch) -> None:
    monkeypatch.delenv("VLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("VLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("VLM_RETRY_BACKOFF_SECONDS", raising=False)

    client = VisionLanguageModelClient(dry_run=True)

    assert client.timeout_s == 300
    assert client.max_retries == 3
    assert client.retry_backoff_s == 5.0


def test_vlm_timeout_invalid_env_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("VLM_TIMEOUT_SECONDS", "abc")
    monkeypatch.setenv("VLM_MAX_RETRIES", "-1")
    monkeypatch.setenv("VLM_RETRY_BACKOFF_SECONDS", "oops")

    client = VisionLanguageModelClient(dry_run=True)

    assert client.timeout_s == 300
    assert client.max_retries == 3
    assert client.retry_backoff_s == 5.0
    assert any("VLM_TIMEOUT_SECONDS_invalid_using_default" in item for item in client.config_warnings)
    assert any("VLM_MAX_RETRIES_non_positive_using_default" in item for item in client.config_warnings)
    assert any("VLM_RETRY_BACKOFF_SECONDS_invalid_using_default" in item for item in client.config_warnings)
