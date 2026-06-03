from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alumina_sol_extractor.stage5.dataset_fusion.semantic_validation import run_semantic_validation


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_semantic_v1_1_validation_reports_clean_candidate(tmp_path: Path) -> None:
    previous_dir = tmp_path / "semantic_v1"
    candidate_dir = tmp_path / "semantic_v1_1_candidate"
    validation_dir = tmp_path / "validation"

    _write_csv(
        previous_dir / "all_papers_final_parameters_linked.csv",
        [
            {"paper_id": "paper-1", "qualified_paper_id": "mechanism/paper-1", "paper_category": "mechanism", "paper_category_status": "official", "paper_dir": "x", "canonical_key": "unit", "parameter_id": "p-old"},
            {"paper_id": "paper-1", "qualified_paper_id": "mechanism/paper-1", "paper_category": "mechanism", "paper_category_status": "official", "paper_dir": "x", "canonical_key": "pH", "parameter_id": "p-1"},
        ],
    )
    _write_csv(
        candidate_dir / "all_papers_final_parameters_linked.csv",
        [
            {"paper_id": "paper-1", "qualified_paper_id": "mechanism/paper-1", "paper_category": "mechanism", "paper_category_status": "official", "paper_dir": "x", "category": "mechanism", "canonical_key": "pH", "parameter_id": "p-1", "source_scope": "data_point", "source_file": "final_dataset/parameters.jsonl"},
        ],
    )
    _write_csv(
        candidate_dir / "all_papers_excluded_parameters.csv",
        [
            {
                "paper_id": "paper-1",
                "qualified_paper_id": "mechanism/paper-1",
                "paper_category": "mechanism",
                "paper_category_status": "official",
                "paper_dir": "x",
                "canonical_key": "unit",
                "canonical_name": "unit",
                "parameter_family": "other",
                "raw_value": "C",
                "numeric_value": "",
                "unit": "",
                "source_file": "final_dataset/parameters.jsonl",
                "source_stage": "stage5.materialization",
                "source_scope": "extended_data.unclassified_results.unit",
                "parameter_semantic_role": "metadata_or_bookkeeping",
                "included_in_main_parameter_landscape": False,
                "exclusion_reason": "metadata_like_key",
            }
        ],
    )
    _write_csv(
        candidate_dir / "all_papers_parameter_semantic_qa.csv",
        [
            {
                "paper_id": "paper-1",
                "qualified_paper_id": "mechanism/paper-1",
                "paper_category": "mechanism",
                "paper_category_status": "official",
                "paper_dir": "x",
                "parameter_id": "p-1",
                "canonical_key": "pH",
                "parameter_semantic_role": "synthesis_process_property",
                "included_in_main_parameter_landscape": True,
                "exclusion_reason": "",
            },
            {
                "paper_id": "paper-1",
                "qualified_paper_id": "mechanism/paper-1",
                "paper_category": "mechanism",
                "paper_category_status": "official",
                "paper_dir": "x",
                "parameter_id": "p-meta",
                "canonical_key": "unit",
                "parameter_semantic_role": "metadata_or_bookkeeping",
                "included_in_main_parameter_landscape": False,
                "exclusion_reason": "metadata_like_key",
            },
        ],
    )
    _write_json(
        candidate_dir / "all_papers_link_aware_summary.json",
        {
            "official_paper_count": 343,
            "non_primary_paper_count": 4,
            "missing_identity_row_count": 0,
            "category_mismatch_rows": 0,
        },
    )

    summary = run_semantic_validation(
        previous_export_dir=previous_dir,
        candidate_export_dir=candidate_dir,
        validation_dir=validation_dir,
        per_paper_raw_outputs_modified=False,
    )

    assert summary["residual_metadata_key_count"] == 0
    assert summary["category_mismatch_rows"] == 0
    assert summary["missing_identity_row_count"] == 0
    assert summary["acceptance"]["residual_metadata_zero"] is True
    assert (validation_dir / "semantic_v1_1_validation_summary.json").exists()
    assert (validation_dir / "residual_metadata_keys_in_final.csv").exists()
