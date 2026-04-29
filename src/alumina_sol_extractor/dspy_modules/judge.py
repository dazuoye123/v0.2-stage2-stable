"""Optional judge wrapper for Stage 3 DSPy extraction."""

from __future__ import annotations

from typing import Any

from .modules import JudgeExtractionModule, ModuleResult, to_json_text


def run_judge(
    paper_text: str,
    extraction_json: dict[str, Any],
    ontology_keys: list[str],
    schema_hint: dict[str, Any],
) -> ModuleResult:
    """Run the Stage 3 judge module."""
    module = JudgeExtractionModule()
    return module.run(
        paper_text=paper_text,
        extraction_json=to_json_text(extraction_json),
        ontology_keys=to_json_text(ontology_keys),
        schema_hint=to_json_text(schema_hint),
    )
