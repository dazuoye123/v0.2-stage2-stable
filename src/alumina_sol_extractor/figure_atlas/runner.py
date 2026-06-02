from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .audit import run_audit
from .auto_figures import generate_auto_figures
from .cross_stage_figures import generate_cross_stage_figures
from .io import ensure_dir, write_frame, write_json, write_markdown
from .loaders import load_all_inputs
from .main_figures import generate_main_figures
from .qa_figures import generate_qa_figures
from .stage3_figures import generate_stage3_figures
from .stage4_figures import generate_stage4_figures
from .stage5_figures import generate_stage5_figures
from .table_builder import build_normalized_tables


def run_figure_atlas(
    *,
    project_root: Path,
    outputs_dir: Path,
    batch_final_export_dir: Path,
    batch_output_dir: Path,
    stage3_analysis_dir: Path | None = None,
    stage3_publication_dir: Path | None = None,
    audit_only: bool = False,
    generate_figures: bool = True,
    skip_auto_figures: bool = False,
    max_auto_figures: int = 50,
    delete_old_research_figures_code: bool = False,
    dry_run_delete_old_code: bool = False,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    timestamp_dir = ensure_dir(batch_output_dir / datetime.now().strftime("%Y%m%d_%H%M%S") / "figure_atlas")
    audit_dir = ensure_dir(timestamp_dir / "audit")
    tables_dir = ensure_dir(timestamp_dir / "tables")
    figure_data_dir = ensure_dir(timestamp_dir / "figure_data")
    figures_root = ensure_dir(timestamp_dir / "figures")

    audit_result = run_audit(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_final_export_dir,
        audit_dir=audit_dir,
        stage3_analysis_dir=stage3_analysis_dir,
        stage3_publication_dir=stage3_publication_dir,
    )
    if audit_only or not audit_result["core_inputs_ready"]:
        manifest = _write_manifest(
            output_dir=timestamp_dir,
            artifacts=[],
            warnings=["audit_only"] if audit_only else ["core_inputs_missing"],
            input_dirs={
                "outputs_dir": str(outputs_dir),
                "batch_final_export_dir": str(batch_final_export_dir),
            },
        )
        return {
            "output_dir": str(timestamp_dir),
            "audit_dir": str(audit_dir),
            "core_inputs_ready": audit_result["core_inputs_ready"],
            "manifest": str(manifest),
        }
    if not generate_figures:
        manifest = _write_manifest(
            output_dir=timestamp_dir,
            artifacts=[],
            warnings=["generate_figures_disabled"],
            input_dirs={
                "outputs_dir": str(outputs_dir),
                "batch_final_export_dir": str(batch_final_export_dir),
                "stage3_analysis_dir": str(stage3_analysis_dir) if stage3_analysis_dir else "",
                "stage3_publication_dir": str(stage3_publication_dir) if stage3_publication_dir else "",
            },
        )
        return {
            "output_dir": str(timestamp_dir),
            "audit_dir": str(audit_dir),
            "core_inputs_ready": audit_result["core_inputs_ready"],
            "manifest": str(manifest),
        }

    inputs = load_all_inputs(
        project_root=project_root,
        outputs_dir=outputs_dir,
        batch_final_export_dir=batch_final_export_dir,
        stage3_analysis_dir=stage3_analysis_dir,
        stage3_publication_dir=stage3_publication_dir,
    )
    tables = build_normalized_tables(inputs)
    for name, frame in tables.items():
        write_frame(tables_dir / f"{name}.csv", frame)

    artifacts: list[dict[str, Any]] = []
    generators = [
        lambda: generate_main_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables),
        lambda: generate_stage3_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables),
        lambda: generate_stage4_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables),
        lambda: generate_stage5_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables),
        lambda: generate_cross_stage_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables),
        lambda: generate_qa_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables, availability=audit_result["availability"]),
    ]
    for generator in generators:
        artifacts.extend(_run_generator(generator, continue_on_error=continue_on_error))
    if not skip_auto_figures:
        artifacts.extend(
            _run_generator(
                lambda: generate_auto_figures(figures_root=figures_root, tables_root=tables_dir, json_root=figure_data_dir, tables=tables, max_auto_figures=max_auto_figures),
                continue_on_error=continue_on_error,
            )
        )

    manifest_path = _write_manifest(
        output_dir=timestamp_dir,
        artifacts=artifacts,
        warnings=[],
        input_dirs={
            "outputs_dir": str(outputs_dir),
            "batch_final_export_dir": str(batch_final_export_dir),
            "stage3_analysis_dir": str(stage3_analysis_dir) if stage3_analysis_dir else "",
            "stage3_publication_dir": str(stage3_publication_dir) if stage3_publication_dir else "",
        },
    )
    write_frame(timestamp_dir / "figure_index.csv", pd.DataFrame(artifacts))
    write_markdown(timestamp_dir / "figure_atlas_readme.md", _readme_text(artifacts, timestamp_dir))

    legacy_cleanup = _handle_legacy_cleanup(project_root, delete_old_research_figures_code=delete_old_research_figures_code, dry_run_delete_old_code=dry_run_delete_old_code)
    return {
        "output_dir": str(timestamp_dir),
        "audit_dir": str(audit_dir),
        "tables_dir": str(tables_dir),
        "figure_data_dir": str(figure_data_dir),
        "figures_root": str(figures_root),
        "manifest": str(manifest_path),
        "figure_count": len(artifacts),
        "legacy_cleanup": legacy_cleanup,
    }


def _run_generator(generator: Any, *, continue_on_error: bool) -> list[dict[str, Any]]:
    try:
        return list(generator())
    except Exception:
        if continue_on_error:
            return []
        raise


def _write_manifest(*, output_dir: Path, artifacts: list[dict[str, Any]], warnings: list[str], input_dirs: dict[str, str]) -> Path:
    counts = {
        "main_figures": sum(1 for item in artifacts if item.get("tier") == "main"),
        "stage3_figures": sum(1 for item in artifacts if item.get("tier") == "stage3"),
        "stage4_figures": sum(1 for item in artifacts if item.get("tier") == "stage4"),
        "stage5_figures": sum(1 for item in artifacts if item.get("tier") == "stage5"),
        "cross_stage_figures": sum(1 for item in artifacts if item.get("tier") == "cross_stage"),
        "qa_figures": sum(1 for item in artifacts if item.get("tier") == "qa"),
        "auto_figures": sum(1 for item in artifacts if item.get("tier") == "auto"),
        "total_figures": len(artifacts),
    }
    payload = {
        "generated_at": datetime.now().isoformat(),
        "input_dirs": input_dirs,
        "output_dir": str(output_dir),
        "counts": counts,
        "figures": artifacts,
        "global_warnings": warnings,
        "data_provenance": {
            "stage3_rerun": False,
            "stage4_rerun": False,
            "stage5_rerun": False,
            "llm_or_vlm_called": False,
        },
    }
    path = output_dir / "figure_atlas_manifest.json"
    write_json(path, payload)
    return path


def _readme_text(artifacts: list[dict[str, Any]], output_dir: Path) -> str:
    grouped: dict[str, list[str]] = {}
    for item in artifacts:
        grouped.setdefault(item["tier"], []).append(item["figure_id"])
    lines = [
        "# Figure Atlas",
        "",
        "## Data sources",
        "- Stage3 analysis outputs",
        "- Stage4 per-paper spectra outputs",
        "- Stage5 batch final exports",
        "",
        "## Figure counts",
    ]
    for tier, names in grouped.items():
        lines.append(f"- {tier}: {len(names)}")
    lines.extend(["", "## Figure groups"])
    for tier, names in grouped.items():
        lines.append(f"- {tier}: {', '.join(names[:20])}")
    lines.extend(
        [
            "",
            "## Recommended main figures",
            "- main_fig1_dataset_overview",
            "- main_fig2_parameter_landscape",
            "- main_fig7_stage4_characterization_coverage",
            "- main_fig10_research_atlas_summary",
            "",
            "## Known limitations",
            "- Auto figures are exploratory.",
            "- Unknown spectra/parameter categories depend on raw extraction quality.",
            "- Some plots are QA-oriented rather than publication-polished.",
        ]
    )
    return "\n".join(lines) + "\n"


def _handle_legacy_cleanup(project_root: Path, *, delete_old_research_figures_code: bool, dry_run_delete_old_code: bool) -> dict[str, Any]:
    targets = [
        project_root / "src" / "alumina_sol_extractor" / "research_figures",
        project_root / "scripts" / "run_research_figures.py",
    ]
    if not delete_old_research_figures_code:
        return {"performed": False, "targets": [str(path) for path in targets]}
    archive_dir = ensure_dir(project_root / "archive" / "research_figures_legacy")
    if dry_run_delete_old_code:
        return {"performed": False, "dry_run": True, "targets": [str(path) for path in targets], "archive_dir": str(archive_dir)}
    moved: list[str] = []
    for target in targets:
        if not target.exists():
            continue
        destination = archive_dir / target.name
        if destination.exists():
            continue
        target.rename(destination)
        moved.append(str(destination))
    return {"performed": True, "archive_dir": str(archive_dir), "moved": moved}
