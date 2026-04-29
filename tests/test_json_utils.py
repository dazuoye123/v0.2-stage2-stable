from __future__ import annotations

from alumina_sol_extractor.dspy_modules.json_utils import extract_json_from_markdown, safe_json_loads


def test_safe_json_loads_parses_plain_json() -> None:
    payload, error = safe_json_loads('{"a": 1, "b": null}')
    assert error is None
    assert payload == {"a": 1, "b": None}


def test_safe_json_loads_parses_fenced_json() -> None:
    payload, error = safe_json_loads("Here is output\n```json\n{\"a\": [1, 2]}\n```")
    assert error is None
    assert payload == {"a": [1, 2]}


def test_extract_json_from_markdown_strips_wrapper() -> None:
    assert extract_json_from_markdown("```json\n[1,2,3]\n```") == "[1,2,3]"
