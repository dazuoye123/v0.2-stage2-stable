from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from alumina_sol_extractor.stage5.dataset_fusion.semantics import (
    METADATA_OR_BOOKKEEPING_KEYS,
    OFFICIAL_PAPER_CATEGORIES,
    is_metadata_or_bookkeeping_key,
    is_true_parameter_key,
)


FORBIDDEN_METADATA_KEYS = {
    "unit",
    "context",
    "key",
    "source_text",
    "evidence_ref",
    "evidence_reference",
    "variables",
    "series_name",
    "parameter",
    "condition",
    "experiment_series",
    "series",
    "series_ref",
    "evidence",
    "material_system",
    *METADATA_OR_BOOKKEEPING_KEYS,
}


def run_semantic_validation(
    *,
    previous_export_dir: Path,
    candidate_export_dir: Path,
    validation_dir: Path,
    per_paper_raw_outputs_modified: bool = False,
) -> dict[str, Any]:
    validation_dir.mkdir(parents=True, exist_ok=True)
    previous_dir = Path(previous_export_dir)
    candidate_dir = Path(candidate_export_dir)

    previous_final = _read_csv(previous_dir / "all_papers_final_parameters_linked.csv")
    candidate_final = _read_csv(candidate_dir / "all_papers_final_parameters_linked.csv")
    candidate_excluded = _read_csv(candidate_dir / "all_papers_excluded_parameters.csv")
    candidate_semantic = _read_csv(candidate_dir / "all_papers_parameter_semantic_qa.csv")
    summary = _read_json(candidate_dir / "all_papers_link_aware_summary.json")

    category_validation = _build_category_validation(candidate_final, candidate_excluded, candidate_semantic)
    identity_validation = _build_identity_validation(candidate_final, candidate_excluded, candidate_semantic)
    canonical_before_after = _build_canonical_before_after(previous_final, candidate_final)
    residual_metadata = _build_residual_metadata(candidate_final)
    excluded_metadata = _build_excluded_metadata(candidate_excluded)
    overfiltering = _build_overfiltering_audit(candidate_excluded)
    role_distribution = _build_semantic_role_distribution(candidate_semantic)
    paper_delta = _build_paper_level_delta(previous_final, candidate_final)

    summary_payload = {
        "semantic_repair_version": "v1.1",
        "official_paper_count": int(summary.get("official_paper_count", 0)),
        "non_primary_paper_count": int(summary.get("non_primary_paper_count", 0)),
        "main_parameter_count": int(len(candidate_final.index)),
        "excluded_parameter_count": int(len(candidate_excluded.index)),
        "residual_metadata_key_count": int(len(residual_metadata.index)),
        "category_mismatch_rows": int(category_validation["category_mismatch_rows"].sum()) if not category_validation.empty else 0,
        "missing_identity_row_count": int(identity_validation["missing_identity_rows"].sum()) if not identity_validation.empty else 0,
        "per_paper_raw_outputs_modified": bool(per_paper_raw_outputs_modified),
    }
    summary_payload["acceptance"] = {
        "official_paper_count_343": bool(summary_payload["official_paper_count"] == 343),
        "non_primary_paper_count_4": bool(summary_payload["non_primary_paper_count"] == 4),
        "category_mismatch_zero": bool(summary_payload["category_mismatch_rows"] == 0),
        "missing_identity_zero": bool(summary_payload["missing_identity_row_count"] == 0),
        "official_categories_only": bool(_official_categories_only(candidate_final)),
        "residual_metadata_zero": bool(summary_payload["residual_metadata_key_count"] == 0),
        "excluded_metadata_traceable": bool(not excluded_metadata.empty),
        "main_parameter_count_in_range": bool(7500 <= summary_payload["main_parameter_count"] <= 11000),
        "overfiltering_not_severe": bool(overfiltering.empty or int(overfiltering["overfiltering_risk_count"].fillna(0).sum()) <= 200),
        "per_paper_raw_outputs_untouched": bool(not per_paper_raw_outputs_modified),
    }
    summary_payload["passed"] = all(bool(value) for value in summary_payload["acceptance"].values())

    _write_frame(validation_dir / "canonical_key_before_after.csv", canonical_before_after)
    _write_frame(validation_dir / "residual_metadata_keys_in_final.csv", residual_metadata)
    _write_frame(validation_dir / "excluded_metadata_audit.csv", excluded_metadata)
    _write_frame(validation_dir / "overfiltering_risk_audit.csv", overfiltering)
    _write_frame(validation_dir / "semantic_role_distribution.csv", role_distribution)
    _write_frame(validation_dir / "category_semantics_validation.csv", category_validation)
    _write_frame(validation_dir / "identity_column_validation.csv", identity_validation)
    _write_frame(validation_dir / "paper_level_parameter_count_delta.csv", paper_delta)
    _write_json(validation_dir / "semantic_v1_1_validation_summary.json", summary_payload)
    (validation_dir / "semantic_v1_1_validation_report.md").write_text(
        _build_report(summary_payload, residual_metadata, excluded_metadata, overfiltering),
        encoding="utf-8",
    )
    return summary_payload


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _build_category_validation(final_frame: pd.DataFrame, excluded_frame: pd.DataFrame, semantic_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in {
        "all_papers_final_parameters_linked.csv": final_frame,
        "all_papers_excluded_parameters.csv": excluded_frame,
        "all_papers_parameter_semantic_qa.csv": semantic_frame,
    }.items():
        paper_category = frame["paper_category"].fillna("").astype(str) if "paper_category" in frame.columns else pd.Series("", index=frame.index)
        category = frame["category"].fillna("").astype(str) if "category" in frame.columns else paper_category
        rows.append(
            {
                "table_name": name,
                "row_count": int(len(frame.index)),
                "official_category_rows": int(paper_category.isin(OFFICIAL_PAPER_CATEGORIES).sum()),
                "non_primary_category_rows": int((~paper_category.isin(OFFICIAL_PAPER_CATEGORIES) & paper_category.ne("")).sum()),
                "missing_paper_category_rows": int(paper_category.str.strip().eq("").sum()),
                "category_mismatch_rows": int(((category.str.strip() != "") & (paper_category.str.strip() != "") & (category != paper_category)).sum()),
            }
        )
    return pd.DataFrame(rows)


def _build_identity_validation(final_frame: pd.DataFrame, excluded_frame: pd.DataFrame, semantic_frame: pd.DataFrame) -> pd.DataFrame:
    required = ["paper_id", "qualified_paper_id", "paper_category", "paper_category_status", "paper_dir"]
    rows: list[dict[str, Any]] = []
    for name, frame in {
        "all_papers_final_parameters_linked.csv": final_frame,
        "all_papers_excluded_parameters.csv": excluded_frame,
        "all_papers_parameter_semantic_qa.csv": semantic_frame,
    }.items():
        missing_total = 0
        payload: dict[str, Any] = {"table_name": name, "row_count": int(len(frame.index))}
        for column in required:
            if column in frame.columns:
                series = frame[column].fillna("").astype(str).str.strip()
                if column == "paper_category" and "paper_category_status" in frame.columns:
                    status = frame["paper_category_status"].fillna("").astype(str).str.strip()
                    count = int(((status == "official") & series.eq("")).sum())
                else:
                    count = int(series.eq("").sum())
            else:
                count = int(len(frame.index))
            payload[f"missing_{column}_rows"] = count
            missing_total += count
        payload["missing_identity_rows"] = missing_total
        rows.append(payload)
    return pd.DataFrame(rows)


def _build_canonical_before_after(previous_final: pd.DataFrame, candidate_final: pd.DataFrame) -> pd.DataFrame:
    before = previous_final.groupby("canonical_key").size().reset_index(name="before_count") if not previous_final.empty else pd.DataFrame(columns=["canonical_key", "before_count"])
    after = candidate_final.groupby("canonical_key").size().reset_index(name="after_count") if not candidate_final.empty else pd.DataFrame(columns=["canonical_key", "after_count"])
    merged = before.merge(after, on="canonical_key", how="outer").fillna(0)
    merged["delta"] = merged["after_count"] - merged["before_count"]
    return merged.sort_values(["delta", "canonical_key"], ascending=[True, True]).reset_index(drop=True)


def _build_residual_metadata(final_frame: pd.DataFrame) -> pd.DataFrame:
    if final_frame.empty or "canonical_key" not in final_frame.columns:
        return pd.DataFrame(columns=["paper_id", "qualified_paper_id", "canonical_key", "parameter_id", "source_scope", "source_file"])
    frame = final_frame.copy()
    mask = frame["canonical_key"].fillna("").astype(str).str.lower().isin(FORBIDDEN_METADATA_KEYS) | frame["canonical_key"].apply(is_metadata_or_bookkeeping_key)
    cols = [col for col in ["paper_id", "qualified_paper_id", "canonical_key", "parameter_id", "source_scope", "source_file"] if col in frame.columns]
    return frame.loc[mask, cols].reset_index(drop=True)


def _build_excluded_metadata(excluded_frame: pd.DataFrame) -> pd.DataFrame:
    if excluded_frame.empty:
        return pd.DataFrame(columns=["paper_id", "qualified_paper_id", "canonical_key", "exclusion_reason", "parameter_semantic_role"])
    frame = excluded_frame.copy()
    mask = frame["canonical_key"].fillna("").astype(str).str.lower().isin(FORBIDDEN_METADATA_KEYS)
    cols = [
        col
        for col in [
            "paper_id",
            "qualified_paper_id",
            "canonical_key",
            "canonical_name",
            "parameter_family",
            "raw_value",
            "numeric_value",
            "unit",
            "source_file",
            "source_stage",
            "source_scope",
            "parameter_semantic_role",
            "included_in_main_parameter_landscape",
            "exclusion_reason",
        ]
        if col in frame.columns
    ]
    return frame.loc[mask, cols].reset_index(drop=True)


def _build_overfiltering_audit(excluded_frame: pd.DataFrame) -> pd.DataFrame:
    if excluded_frame.empty:
        return pd.DataFrame(columns=["canonical_key", "overfiltering_risk_count"])
    frame = excluded_frame.copy()
    frame["canonical_key"] = frame["canonical_key"].fillna("").astype(str)
    semantic_role = frame["parameter_semantic_role"].fillna("").astype(str) if "parameter_semantic_role" in frame.columns else pd.Series("", index=frame.index)
    mask = frame["canonical_key"].apply(is_true_parameter_key) & semantic_role.ne("characterization_output")
    grouped = (
        frame.loc[mask]
        .groupby("canonical_key")
        .size()
        .reset_index(name="overfiltering_risk_count")
        .sort_values("overfiltering_risk_count", ascending=False)
    )
    return grouped.reset_index(drop=True)


def _build_semantic_role_distribution(semantic_frame: pd.DataFrame) -> pd.DataFrame:
    if semantic_frame.empty:
        return pd.DataFrame(columns=["parameter_semantic_role", "included_in_main_parameter_landscape", "exclusion_reason", "row_count"])
    return (
        semantic_frame.groupby(["parameter_semantic_role", "included_in_main_parameter_landscape", "exclusion_reason"], dropna=False)
        .size()
        .reset_index(name="row_count")
        .sort_values(["parameter_semantic_role", "row_count"], ascending=[True, False])
        .reset_index(drop=True)
    )


def _build_paper_level_delta(previous_final: pd.DataFrame, candidate_final: pd.DataFrame) -> pd.DataFrame:
    before = previous_final.groupby("paper_id").size().reset_index(name="before_count") if not previous_final.empty else pd.DataFrame(columns=["paper_id", "before_count"])
    after = candidate_final.groupby("paper_id").size().reset_index(name="after_count") if not candidate_final.empty else pd.DataFrame(columns=["paper_id", "after_count"])
    merged = before.merge(after, on="paper_id", how="outer").fillna(0)
    merged["delta"] = merged["after_count"] - merged["before_count"]
    return merged.sort_values("delta").reset_index(drop=True)


def _official_categories_only(final_frame: pd.DataFrame) -> bool:
    if final_frame.empty or "paper_category_status" not in final_frame.columns:
        return False
    official = final_frame[final_frame["paper_category_status"].astype(str) == "official"].copy()
    if official.empty:
        return False
    return official["paper_category"].fillna("").astype(str).isin(OFFICIAL_PAPER_CATEGORIES).all()


def _build_report(
    summary_payload: dict[str, Any],
    residual_metadata: pd.DataFrame,
    excluded_metadata: pd.DataFrame,
    overfiltering: pd.DataFrame,
) -> str:
    lines = [
        "# Semantic v1.1 Validation Report",
        "",
        "## Summary",
        f"- official_paper_count: {summary_payload['official_paper_count']}",
        f"- non_primary_paper_count: {summary_payload['non_primary_paper_count']}",
        f"- main_parameter_count: {summary_payload['main_parameter_count']}",
        f"- excluded_parameter_count: {summary_payload['excluded_parameter_count']}",
        f"- residual_metadata_key_count: {summary_payload['residual_metadata_key_count']}",
        f"- category_mismatch_rows: {summary_payload['category_mismatch_rows']}",
        f"- missing_identity_row_count: {summary_payload['missing_identity_row_count']}",
        f"- per_paper_raw_outputs_modified: {summary_payload['per_paper_raw_outputs_modified']}",
        f"- passed: {summary_payload['passed']}",
        "",
        "## Acceptance",
    ]
    for key, value in summary_payload["acceptance"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Residual metadata",
            f"- residual rows in final main parameters: {len(residual_metadata.index)}",
            f"- excluded metadata rows captured: {len(excluded_metadata.index)}",
            "",
            "## Overfiltering risk",
            f"- flagged canonical keys: {len(overfiltering.index)}",
        ]
    )
    return "\n".join(lines) + "\n"
