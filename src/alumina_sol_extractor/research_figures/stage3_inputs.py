from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import normalize_text, read_json


NUMERIC_FAMILY_RULES = {
    "temperature": ("temperature", "_c", "_k"),
    "time": ("time", "_h", "_min", "_s", "duration", "holding"),
    "pH": ("ph",),
    "concentration": ("concentration", "_mol_l", "_wt_percent", "_percent", "ratio", "content"),
}


def load_stage3_analysis(
    *,
    project_root: Path,
    analysis_dir: Path | None = None,
    publication_dir: Path | None = None,
) -> dict[str, Any]:
    base_dir = analysis_dir or _resolve_existing_dir(
        project_root / "data" / "analysis_outputs_stage3_v2",
        project_root / "data" / "analysis_outputs_stage3",
    )
    fallback_base = project_root / "data" / "analysis_outputs_stage3"
    publication_base = publication_dir or _resolve_existing_dir(
        project_root / "data" / "analysis_outputs_stage3_publication",
    )
    if base_dir is None:
        raise FileNotFoundError("No Stage3 analysis output directory found.")

    payload = {
        "analysis_dir": str(base_dir),
        "publication_dir": str(publication_base) if publication_base else None,
        "stage3_analysis_summary": read_json(
            _first_existing(
                base_dir / "analysis_outputs_stage3_summary.json",
                base_dir / "stage3_analysis_summary.json",
                fallback_base / "analysis_outputs_stage3_summary.json",
                fallback_base / "stage3_analysis_summary.json",
            ),
            default={},
        )
        or {},
        "parameter_distribution": _read_csv(_first_existing(base_dir / "parameter_distribution.csv", fallback_base / "parameter_distribution.csv")),
        "sample_parameter_long": _read_csv(_first_existing(base_dir / "sample_parameter_long.csv", fallback_base / "sample_parameter_long.csv")),
        "paper_stage3_summary": _read_csv(_first_existing(base_dir / "paper_stage3_summary.csv", fallback_base / "paper_stage3_summary.csv")),
        "canonical_key_by_category": _read_csv(
            _first_existing(
                base_dir / "canonical_key_category_summary.csv",
                base_dir / "canonical_key_by_category.csv",
                fallback_base / "canonical_key_category_summary.csv",
                fallback_base / "canonical_key_by_category.csv",
            )
        ),
        "process_condition_distribution": _read_csv(
            _first_existing(
                base_dir / "time_condition_distribution_by_type.csv",
                base_dir / "process_condition_distribution.csv",
                fallback_base / "time_condition_distribution_by_type.csv",
                fallback_base / "process_condition_distribution.csv",
            )
        ),
        "label_mapping": _read_csv(publication_base / "label_mapping.csv") if publication_base and (publication_base / "label_mapping.csv").exists() else pd.DataFrame(),
        "publication_heatmap": _read_csv(publication_base / "fig3_coverage_matrix_plotting_data.csv") if publication_base and (publication_base / "fig3_coverage_matrix_plotting_data.csv").exists() else pd.DataFrame(),
        "paper_metadata": _read_csv(publication_base / "fig3_paper_metadata_plotting_data.csv") if publication_base and (publication_base / "fig3_paper_metadata_plotting_data.csv").exists() else pd.DataFrame(),
        "warnings": [],
    }
    for key in ("parameter_distribution", "sample_parameter_long", "paper_stage3_summary"):
        if payload[key].empty:
            payload["warnings"].append(f"missing_or_empty_{key}")
    return payload


def filter_stage3_analysis(
    stage3_payload: dict[str, Any],
    *,
    selected_pairs: set[tuple[str, str]] | None = None,
    selected_paper_ids: set[str] | None = None,
) -> dict[str, Any]:
    if not selected_pairs and not selected_paper_ids:
        return stage3_payload

    filtered: dict[str, Any] = {}
    for key, value in stage3_payload.items():
        if isinstance(value, pd.DataFrame):
            filtered[key] = _filter_frame(value, selected_pairs=selected_pairs, selected_paper_ids=selected_paper_ids)
        elif key == "stage3_analysis_summary":
            filtered[key] = dict(value or {})
        elif key == "warnings":
            filtered[key] = list(value)
        else:
            filtered[key] = value

    if not filtered["sample_parameter_long"].empty:
        filtered["parameter_distribution"] = _rebuild_parameter_distribution(
            filtered["sample_parameter_long"],
            stage3_payload.get("parameter_distribution", pd.DataFrame()),
        )
    if not filtered["paper_stage3_summary"].empty:
        filtered["stage3_analysis_summary"]["total_papers"] = int(filtered["paper_stage3_summary"]["paper_id"].nunique())
    else:
        filtered["stage3_analysis_summary"]["total_papers"] = 0
    return filtered


def build_stage3_parameter_coverage(stage3_payload: dict[str, Any], *, top_n: int = 20) -> pd.DataFrame:
    frame = stage3_payload["parameter_distribution"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["canonical_key", "paper_count", "coverage_rate", "parameter_family", "short_label"])
    total_papers = _resolve_total_papers(stage3_payload)
    frame["coverage_rate"] = frame["paper_count"].fillna(0).astype(float) / max(total_papers, 1)
    frame["parameter_family"] = frame["canonical_key"].map(classify_parameter_family)
    frame["short_label"] = frame["canonical_key"].map(lambda key: short_label_for_key(key, stage3_payload))
    return frame.sort_values(["coverage_rate", "count"], ascending=[False, False]).head(top_n).reset_index(drop=True)


def build_stage3_sample_parameter_heatmap(
    stage3_payload: dict[str, Any],
    *,
    max_samples: int = 40,
    max_parameters: int = 25,
) -> pd.DataFrame:
    if not stage3_payload["publication_heatmap"].empty:
        frame = stage3_payload["publication_heatmap"].copy()
        frame = frame.head(max_samples)
        label_column = _resolve_matrix_label_column(frame)
        if label_column != "sample_id":
            frame = frame.rename(columns={label_column: "sample_id"})
        desired_columns = ["sample_id"] + [column for column in frame.columns if column != "sample_id"][:max_parameters]
        return frame[desired_columns]
    long_df = stage3_payload["sample_parameter_long"].copy()
    if long_df.empty:
        return pd.DataFrame(columns=["sample_id"])
    parameter_order = (
        long_df.groupby("canonical_key")["sample_id"].nunique().sort_values(ascending=False).head(max_parameters).index.tolist()
    )
    sample_order = (
        long_df.groupby("sample_id")["canonical_key"].nunique().sort_values(ascending=False).head(max_samples).index.tolist()
    )
    subset = long_df[long_df["canonical_key"].isin(parameter_order) & long_df["sample_id"].isin(sample_order)].copy()
    subset["present"] = 1
    matrix = subset.pivot_table(index="sample_id", columns="canonical_key", values="present", aggfunc="max", fill_value=0)
    matrix = matrix.reindex(index=sample_order, columns=parameter_order, fill_value=0)
    matrix.insert(0, "sample_id", matrix.index)
    return matrix.reset_index(drop=True)


def build_stage3_numeric_parameter_distribution(stage3_payload: dict[str, Any], *, max_rows: int = 4000) -> pd.DataFrame:
    long_df = stage3_payload["sample_parameter_long"].copy()
    if long_df.empty or "value" not in long_df.columns:
        return pd.DataFrame(columns=["canonical_key", "parameter_family", "value"])
    long_df["value_numeric"] = pd.to_numeric(long_df["value"], errors="coerce")
    long_df = long_df.dropna(subset=["value_numeric"]).copy()
    long_df["parameter_family"] = long_df["canonical_key"].map(classify_numeric_family)
    long_df = long_df[long_df["parameter_family"] != "other"].copy()
    counts = long_df.groupby("canonical_key")["value_numeric"].count().sort_values(ascending=False)
    keep_keys = counts.head(12).index.tolist()
    long_df = long_df[long_df["canonical_key"].isin(keep_keys)].copy()
    if len(long_df) > max_rows:
        long_df = long_df.groupby("canonical_key", group_keys=False).head(max_rows // max(len(keep_keys), 1))
    long_df["short_label"] = long_df["canonical_key"].map(lambda key: short_label_for_key(key, stage3_payload))
    return long_df[["canonical_key", "short_label", "parameter_family", "value_numeric", "paper_id", "sample_id"]].rename(columns={"value_numeric": "value"})


def build_stage3_paper_lookup(stage3_payload: dict[str, Any]) -> pd.DataFrame:
    frame = stage3_payload["paper_stage3_summary"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["paper_id", "sample_count"])
    return frame[["paper_id", "category", "sample_count", "data_point_count", "process_steps_count", "evidence_object_count"]].copy()


def classify_parameter_family(key: Any) -> str:
    text = normalize_text(key).lower()
    if any(token in text for token in ("temperature", "time", "rate", "duration", "calcination", "sintering", "drying", "aging", "hydrolysis", "stirring")):
        return "process"
    if any(token in text for token in ("concentration", "ratio", "content", "source", "solvent", "additive", "acid", "precursor", "ph", "viscosity")):
        return "synthesis"
    if any(token in text for token in ("surface_area", "pore", "diameter", "particle_size", "porosity", "density", "crystallite")):
        return "structure"
    if any(token in text for token in ("strength", "conductivity", "modulus", "elongation", "loss", "zeta", "size_nm", "size_um", "spinnability")):
        return "property"
    if any(token in text for token in ("nmr", "ftir", "xrd", "raman", "tg", "dsc", "peak", "ppm", "2theta")):
        return "spectra"
    return "other"


def classify_numeric_family(key: Any) -> str:
    text = normalize_text(key).lower()
    for family, tokens in NUMERIC_FAMILY_RULES.items():
        if any(token in text for token in tokens):
            return family
    return "other"


def short_label_for_key(key: Any, stage3_payload: dict[str, Any]) -> str:
    text = normalize_text(key)
    mapping = stage3_payload.get("label_mapping")
    if isinstance(mapping, pd.DataFrame) and not mapping.empty and "canonical_key" in mapping.columns:
        matched = mapping[mapping["canonical_key"] == text]
        if not matched.empty and "short_label" in matched.columns:
            label = normalize_text(matched.iloc[0]["short_label"])
            if label:
                return label
    return text


def _resolve_existing_dir(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _resolve_total_papers(stage3_payload: dict[str, Any]) -> int:
    summary = stage3_payload["stage3_analysis_summary"] or {}
    total_papers = summary.get("total_papers")
    if total_papers:
        return int(total_papers)
    paper_frame = stage3_payload["paper_stage3_summary"]
    return int(len(paper_frame)) if not paper_frame.empty else 0


def _resolve_matrix_label_column(frame: pd.DataFrame) -> str:
    for candidate in ("sample_id", "paper_id", "Unnamed: 0"):
        if candidate in frame.columns:
            return candidate
    return str(frame.columns[0])


def _filter_frame(
    frame: pd.DataFrame,
    *,
    selected_pairs: set[tuple[str, str]] | None,
    selected_paper_ids: set[str] | None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "paper_id" not in frame.columns:
        return frame.copy()
    if "category" in frame.columns and selected_pairs:
        pair_mask = frame.apply(lambda row: (normalize_text(row.get("category")), normalize_text(row.get("paper_id"))) in selected_pairs, axis=1)
        filtered = frame[pair_mask].copy()
    elif selected_paper_ids:
        filtered = frame[frame["paper_id"].astype(str).isin(selected_paper_ids)].copy()
    else:
        filtered = frame.copy()
    return filtered.reset_index(drop=True)


def _rebuild_parameter_distribution(long_df: pd.DataFrame, original: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return pd.DataFrame(columns=list(original.columns) or ["canonical_key", "count", "paper_count"])
    working = long_df.copy()
    numeric = pd.to_numeric(working.get("value"), errors="coerce")
    summary = (
        working.groupby("canonical_key")
        .agg(
            count=("canonical_key", "size"),
            paper_count=("paper_id", "nunique"),
            category_count=("category", "nunique"),
            value_text_count=("value", lambda s: pd.to_numeric(s, errors="coerce").isna().sum()),
        )
        .reset_index()
    )
    summary["value_numeric_count"] = (
        working.assign(_value_numeric=numeric)
        .groupby("canonical_key")["_value_numeric"]
        .apply(lambda series: int(series.notna().sum()))
        .reindex(summary["canonical_key"])
        .to_list()
    )
    if not original.empty and "canonical_key" in original.columns:
        keep_columns = [column for column in original.columns if column not in summary.columns]
        if keep_columns:
            summary = summary.merge(original[["canonical_key"] + keep_columns].drop_duplicates("canonical_key"), on="canonical_key", how="left")
    return summary
