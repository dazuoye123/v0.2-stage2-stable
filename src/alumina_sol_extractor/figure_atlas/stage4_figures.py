from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .plot_utils import bar_figure, box_figure, heatmap_figure, hist_figure
from .source_data import artifact_paths, write_figure_bundle


def generate_stage4_figures(*, figures_root: Path, tables_root: Path, json_root: Path, tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    frames = {
        "stage4_fig1_extraction_overview": _extraction_overview(tables),
        "stage4_fig2_per_paper_success_rate": tables["stage4_paper_summary"][["paper_id", "coverage_rate"]].copy(),
        "stage4_fig3_candidate_count_distribution": tables["stage4_paper_summary"][["candidate_count"]].copy(),
        "stage4_fig4_success_failure_distribution": _success_failure(tables),
        "stage4_fig5_full_figure_class_distribution": _figure_class_distribution(tables),
        "stage4_fig6_characterization_family_distribution": _spectra_type_distribution(tables),
        "stage4_fig7_spectra_type_by_category": tables["spectra_type_by_category"].copy(),
        "stage4_fig8_ftir_peak_distribution": _peaks_by_type(tables, "FTIR"),
        "stage4_fig9_xrd_peak_distribution": _peaks_by_type(tables, "XRD"),
        "stage4_fig10_nmr_shift_distribution": _peaks_by_type(tables, "NMR"),
        "stage4_fig11_raman_peak_distribution": _peaks_by_type(tables, "Raman"),
        "stage4_fig12_thermal_event_distribution": _peaks_by_type(tables, "TG/DSC"),
        "stage4_fig13_microscopy_distribution": _spectra_subset_counts(tables, "SEM/TEM microscopy"),
        "stage4_fig14_ferron_distribution": _spectra_subset_counts(tables, "Ferron"),
        "stage4_fig15_unknown_other_breakdown": _unknown_other_breakdown(tables),
        "stage4_fig16_failure_reason_distribution": _failed_reason_distribution(tables),
        "stage4_fig17_validation_error_summary": tables["stage4_paper_summary"][["paper_id", "validation_error_count"]].copy(),
        "stage4_fig18_peak_value_availability": _peak_value_availability(tables),
        "stage4_fig19_spectra_extraction_density_by_paper": _spectra_density_by_paper(tables),
        "stage4_fig20_characterization_coverage_by_category": tables["spectra_type_by_category"].copy(),
    }
    artifacts: list[dict[str, Any]] = []
    for figure_id, frame in frames.items():
        title = figure_id.replace("_", " ")
        paths = artifact_paths(figures_root=figures_root, tables_root=tables_root, json_root=json_root, tier="stage4", figure_id=figure_id)
        if figure_id in {"stage4_fig7_spectra_type_by_category", "stage4_fig20_characterization_coverage_by_category"}:
            svg, png = heatmap_figure(paths["figure_stem"], frame, index_col="category", column_col="normalized_spectra_type", value_col="count", title=title, top_n_rows=10, top_n_cols=15)
        elif figure_id in {"stage4_fig8_ftir_peak_distribution", "stage4_fig9_xrd_peak_distribution", "stage4_fig10_nmr_shift_distribution", "stage4_fig11_raman_peak_distribution", "stage4_fig12_thermal_event_distribution", "stage4_fig3_candidate_count_distribution", "stage4_fig19_spectra_extraction_density_by_paper"}:
            value_col = "peak_value" if "peak_value" in frame.columns else frame.columns[0] if not frame.empty else "value"
            svg, png = hist_figure(paths["figure_stem"], frame, value_col=value_col, title=title)
        elif figure_id in {"stage4_fig2_per_paper_success_rate", "stage4_fig17_validation_error_summary"}:
            value_col = frame.columns[1] if frame.shape[1] > 1 else "count"
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=frame.columns[0], value_col=value_col, title=title, top_n=30, compress_other=False)
        else:
            label_col = frame.columns[0] if not frame.empty else "label"
            value_col = frame.columns[1] if frame.shape[1] > 1 else "count"
            svg, png = bar_figure(paths["figure_stem"], frame, label_col=label_col, value_col=value_col, title=title, top_n=15, compress_other=True)
        artifact = write_figure_bundle(
            figure_id=figure_id,
            title=title,
            tier="stage4",
            recommendation="supplementary",
            feasibility="ready" if not frame.empty else "partial",
            source_df=frame,
            input_tables=[],
            source_csv_path=paths["source_csv"],
            source_json_path=paths["source_json"],
            svg_path=svg,
            png_path=png,
            empty_data_note=None if not frame.empty else "No Stage4 data available.",
        )
        artifacts.append(artifact.__dict__)
    return artifacts


def _extraction_overview(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage4_paper_summary"]
    if frame.empty:
        return pd.DataFrame(columns=["metric", "count"])
    return pd.DataFrame([
        {"metric": "candidates", "count": int(frame["candidate_count"].sum())},
        {"metric": "success", "count": int(frame["success_count"].sum())},
        {"metric": "failed", "count": int(frame["failed_count"].sum())},
        {"metric": "validated", "count": int(frame["validated_count"].sum())},
        {"metric": "validation_errors", "count": int(frame["validation_error_count"].sum())},
    ])


def _success_failure(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage4_paper_summary"]
    if frame.empty:
        return pd.DataFrame(columns=["metric", "count"])
    return pd.DataFrame([
        {"metric": "success", "count": int(frame["success_count"].sum())},
        {"metric": "failed", "count": int(frame["failed_count"].sum())},
    ])


def _figure_class_distribution(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_stage4_spectra"]
    if frame.empty:
        return pd.DataFrame(columns=["figure_class", "count"])
    return frame.groupby("figure_class").size().reset_index(name="count").sort_values("count", ascending=False)


def _spectra_type_distribution(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return tables["normalized_stage4_spectra"].groupby("normalized_spectra_type").size().reset_index(name="count").sort_values("count", ascending=False)


def _peaks_by_type(tables: dict[str, pd.DataFrame], spectra_type: str) -> pd.DataFrame:
    frame = tables["normalized_stage4_peaks"]
    return frame[frame["normalized_spectra_type"] == spectra_type][["peak_value", "peak_unit", "peak_source_field"]].dropna(subset=["peak_value"]).copy()


def _spectra_subset_counts(tables: dict[str, pd.DataFrame], spectra_type: str) -> pd.DataFrame:
    frame = tables["normalized_stage4_spectra"]
    subset = frame[frame["normalized_spectra_type"] == spectra_type]
    return subset.groupby("category").size().reset_index(name="count")


def _unknown_other_breakdown(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_stage4_spectra"]
    subset = frame[frame["normalized_spectra_type"].isin(["Unknown", "Other"])]
    return subset.groupby("normalized_spectra_type").size().reset_index(name="count")


def _failed_reason_distribution(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["stage4_failed"]
    if frame.empty:
        return pd.DataFrame(columns=["error_type", "count"])
    series = frame.get("error_type", pd.Series(dtype=str)).fillna("unknown")
    return series.value_counts().reset_index().rename(columns={"index": "error_type", "count": "count", 0: "count"})


def _peak_value_availability(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_stage4_peaks"]
    if frame.empty:
        return pd.DataFrame(columns=["normalized_spectra_type", "count"])
    grouped = frame.groupby("normalized_spectra_type").agg(count=("peak_value", lambda s: int(s.notna().sum()))).reset_index()
    return grouped


def _spectra_density_by_paper(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = tables["normalized_stage4_spectra"]
    if frame.empty:
        return pd.DataFrame(columns=["count"])
    return frame.groupby("paper_id").size().reset_index(name="count")
