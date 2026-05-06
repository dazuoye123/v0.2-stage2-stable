from __future__ import annotations

from alumina_sol_extractor.vision_spectra.io import parse_json_payload


def test_parse_json_payload_accepts_code_fence_wrapped_json() -> None:
    payload = parse_json_payload("```json\n{\"figure_id\": \"fig-1\", \"peaks\": []}\n```")
    assert payload["figure_id"] == "fig-1"
    assert payload["peaks"] == []
