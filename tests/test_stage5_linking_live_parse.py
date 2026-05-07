from __future__ import annotations

import pytest

from alumina_sol_extractor.linking.llm_linker import EvidenceSpectraParameterLinker, extract_json_payload


def test_extract_json_payload_from_markdown_wrapped_list():
    raw = """```json
[
  {"candidate_id": "cand-1", "decision": "accept", "link_type": "supports", "confidence": "high", "reasoning": "match"}
]
```"""
    parsed = extract_json_payload(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["candidate_id"] == "cand-1"


def test_extract_json_payload_from_prefixed_text():
    raw = 'Here is the result:\n{"links":[{"candidate_id":"cand-1","decision":"unmatched","link_type":"weak_supports","confidence":"low","reasoning":"uncertain"}]}'
    parsed = extract_json_payload(raw)
    assert isinstance(parsed, dict)
    assert parsed["links"][0]["decision"] == "unmatched"


def test_live_mode_without_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LINKING_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    linker = EvidenceSpectraParameterLinker(dry_run=False)
    with pytest.raises(RuntimeError, match="requires LINKING_API_KEY, OPENAI_API_KEY, or DASHSCOPE_API_KEY"):
        linker.run(
            [
                {
                    "candidate_id": "cand-1",
                    "paper_id": "paper-1",
                    "source_type": "spectra_peak",
                    "source_id": "peak-1",
                    "target_type": "parameter",
                    "target_id": "param-1",
                    "candidate_reason": "test",
                    "deterministic_score": 0.5,
                    "needs_llm": True,
                    "candidate_status": "needs_llm",
                }
            ]
        )


def test_prompt_lists_allowed_candidate_ids():
    linker = EvidenceSpectraParameterLinker(dry_run=True)
    prompt = linker.build_prompt(
        [
            {
                "candidate_id": "cand-1",
                "paper_id": "paper-1",
                "source_type": "evidence_object",
                "source_id": "图2.2",
                "source_text": "NMR evidence",
                "source_value": None,
                "source_unit": None,
                "source_figure_id": "图2.2",
                "target_type": "parameter",
                "target_id": "param-1",
                "target_text": "nmr_27Al_peak_position_ppm",
                "target_value": 62.5,
                "target_unit": "ppm",
                "target_figure_id": None,
                "candidate_reason": "linked_figure_or_spectra_overlap",
                "deterministic_score": 0.55,
                "needs_llm": True,
                "candidate_status": "needs_llm",
            }
        ],
        paper_context={"title": "Test Paper"},
    )
    assert "Allowed candidate_ids" in prompt
    assert "cand-1" in prompt
    assert "Allowed decision values: accept, reject, unmatched." in prompt
    assert "Allowed link_type values: supports, weak_supports, describes, derived_from, same_figure, conflicts." in prompt
