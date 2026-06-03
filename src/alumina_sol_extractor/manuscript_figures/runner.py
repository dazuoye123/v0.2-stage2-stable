from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd

from .captions import build_caption, write_caption
from .data_logic import prepare_v2_payload
from .io import copy_file, ensure_dir, write_frame, write_json, write_markdown
from .loaders import figure_plan_lookup, load_diagnosis_payload
from .main_figures import build_fig1, build_fig2, build_fig4
from .nature_adapter import detect_nature_skills
from .qc import verify_outputs, write_qc_png
from .source_data import export_figure_data, export_source_data
from .style import configure_style


FIGURE_BUILDERS = {
    "Fig1": build_fig1,
    "Fig2": build_fig2,
    "Fig4": build_fig4,
}

FIGURE_DIR_NAMES = {
    "Fig1": "Fig1_dataset_coverage",
    "Fig2": "Fig2_synthesis_parameter_landscape",
    "Fig4": "Fig4_characterization_evidence_atlas",
}

FIGURE_TITLES = {
    "Fig1": "Dataset coverage and extraction reliability",
    "Fig2": "Synthesis parameter landscape of alumina sols",
    "Fig4": "Characterization evidence atlas",
}


def run_manuscript_figures(
    *,
    diagnosis_dir: Path,
    output_dir: Path,
    nature_skills_dir: Path | None = None,
    support_tables_dir: Path | None = None,
    legacy_v1_source_dir: Path | None = None,
    figures: list[str] | None = None,
    version_label: str = "v2",
    figure_dir_overrides: dict[str, str] | None = None,
    dry_run: bool = False,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    selected = figures or ["Fig1", "Fig2", "Fig4"]
    payload = load_diagnosis_payload(Path(diagnosis_dir))
    v2_payload = prepare_v2_payload(
        Path(diagnosis_dir),
        support_tables_dir=support_tables_dir,
        legacy_v1_source_dir=legacy_v1_source_dir,
    )
    adapter = detect_nature_skills(nature_skills_dir)
    plan_lookup = figure_plan_lookup(payload["figure_plan_json"])
    figure_dir_names = {**FIGURE_DIR_NAMES, **(figure_dir_overrides or {})}

    root = Path(output_dir)
    if dry_run:
        return {
            "dry_run": True,
            "diagnosis_dir": str(diagnosis_dir),
            "output_dir": str(output_dir),
            "nature_skills": adapter,
            "figures": selected,
            "input_source_tables": [_source_table_path(payload["source_root"], figure_id) for figure_id in selected],
            "support_tables_dir": str(v2_payload["contexts"]["Fig1"].get("atlas_root", Path(diagnosis_dir).parent / "figure_atlas" / "tables")),
            "version_label": version_label,
        }

    main_root = ensure_dir(root / "main_figures")
    source_root = ensure_dir(root / "source_data")
    figure_data_root = ensure_dir(root / "figure_data")
    captions_root = ensure_dir(root / "captions")
    contact_root = ensure_dir(root / "contact_sheets")
    qc_root = ensure_dir(root / "qc")
    audit_records: list[dict[str, Any]] = []

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for figure_id in selected:
        try:
            records.append(
                _generate_one(
                    figure_id=figure_id,
                    frame=v2_payload["figures"][figure_id],
                    plan=plan_lookup.get(figure_id, {}),
                    context=v2_payload["contexts"][figure_id],
                    figure_dir_names=figure_dir_names,
                    main_root=main_root,
                    source_root=source_root,
                    figure_data_root=figure_data_root,
                    captions_root=captions_root,
                    qc_root=qc_root,
                )
            )
        except Exception as exc:
            if continue_on_error:
                warnings.append(f"{figure_id}: {exc}")
                continue
            raise

    for audit_name, audit_frame in v2_payload["audits"].items():
        audit_path = write_frame(qc_root / audit_name, audit_frame)
        audit_records.append({"audit_name": audit_name, "path": str(audit_path), "row_count": int(len(audit_frame))})

    contact_sheet = _build_contact_sheet(records, contact_root / "main_figures_contact_sheet.png")
    qc_summary = _build_qc_summary(records, audit_records)
    qc_summary_path = write_frame(qc_root / "qc_summary.csv", qc_summary)
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "input_diagnosis_dir": str(diagnosis_dir),
        "input_source_tables": [_source_table_path(payload["source_root"], figure_id) for figure_id in selected],
        "support_tables_dir": str(support_tables_dir) if support_tables_dir else "",
        "legacy_v1_source_dir": str(legacy_v1_source_dir) if legacy_v1_source_dir else "",
        "output_dir": str(root),
        "version_label": version_label,
        "nature_skills_used": adapter["nature_skills_used"],
        "nature_skills_path": adapter["nature_skills_path"],
        "nature_skills_mode": adapter["adapter_mode"],
        "fallback_used": adapter["fallback_used"],
        "fallback_reason": adapter["fallback_reason"],
        "figure_count": len(records),
        "figures": records,
        "qc_audits": audit_records,
        "warnings": warnings,
        "data_safety": {
            "stage3_rerun": False,
            "stage4_rerun": False,
            "stage5_rerun": False,
            "llm_or_vlm_called": False,
            "wrote_data_outputs": False,
        },
    }
    write_json(root / "manuscript_figures_manifest.json", manifest)
    write_frame(root / "manuscript_figures_index.csv", pd.DataFrame(records))
    write_markdown(root / "manuscript_figures_readme.md", _build_readme(records, adapter, warnings, contact_sheet, version_label=version_label))
    return {
        "output_dir": str(root),
        "manifest": str(root / "manuscript_figures_manifest.json"),
        "index": str(root / "manuscript_figures_index.csv"),
        "contact_sheet": str(contact_sheet),
        "qc_summary": str(qc_summary_path),
        "figure_count": len(records),
        "nature_skills": adapter,
    }


def _generate_one(
    *,
    figure_id: str,
    frame: pd.DataFrame,
    plan: dict[str, Any],
    context: dict[str, Any],
    figure_dir_names: dict[str, str],
    main_root: Path,
    source_root: Path,
    figure_data_root: Path,
    captions_root: Path,
    qc_root: Path,
) -> dict[str, Any]:
    directory_name = figure_dir_names[figure_id]
    figure_dir = ensure_dir(main_root / directory_name)
    prefix = directory_name
    source_data_name = f"{prefix}_source_data.csv"
    figure_data_name = f"{prefix}_figure_data.json"
    caption_name = f"{prefix}_caption.md"
    qc_name = f"{prefix}_qc.png"
    source_csv_path = export_source_data(frame, figure_dir / source_data_name)
    copy_file(source_csv_path, source_root / source_data_name)

    builder = FIGURE_BUILDERS[figure_id]
    fig_paths, meta = builder(frame, figure_dir / prefix, context=context)
    figure_data = {
        "figure_id": figure_id,
        "title": FIGURE_TITLES[figure_id],
        "scientific_question": plan.get("scientific_question", ""),
        "expected_claim": context.get("expected_claim", plan.get("expected_claim", "")),
        "source_tables": sorted(set(frame["source_table"].dropna().astype(str))) if "source_table" in frame.columns else [],
        "panels": meta["panels"],
        "filters_applied": meta["filters_applied"],
        "unknown_other_handling": meta["unknown_other_handling"],
        "unit_handling": meta["unit_handling"],
        "category_handling": meta["category_handling"],
        "limitations": meta["limitations"],
        "row_counts": meta["row_counts"],
        "excluded_row_counts": meta["excluded_row_counts"],
        "generated_at": datetime.now().isoformat(),
    }
    figure_data.update(meta.get("extra_metadata", {}))
    figure_data_path = export_figure_data(figure_data, figure_dir / figure_data_name)
    copy_file(figure_data_path, figure_data_root / figure_data_name)

    caption_text = build_caption(
        figure_id=figure_id,
        title=FIGURE_TITLES[figure_id],
        scientific_question=plan.get("scientific_question", ""),
        expected_claim=context.get("expected_claim", plan.get("expected_claim", "")),
        panel_descriptions=meta.get("panel_descriptions", [text.strip() for text in str(plan.get("panels", "")).split(";") if text.strip()]),
        source_tables=figure_data["source_tables"],
        filtering_and_normalization=meta["filters_applied"] + [meta["unknown_other_handling"], meta["unit_handling"], meta["category_handling"]],
        limitations=meta["limitations"],
    )
    caption_path = write_caption(figure_dir / caption_name, caption_text)
    copy_file(caption_path, captions_root / caption_name)

    bundle = {
        "output_svg": fig_paths["svg"],
        "output_pdf": fig_paths["pdf"],
        "output_png": fig_paths["png"],
        "source_data_csv": str(source_csv_path),
        "figure_data_json": str(figure_data_path),
        "caption_md": str(caption_path),
    }
    qc_checks = verify_outputs(bundle)
    qc_path = write_qc_png(figure_dir / qc_name, figure_id=figure_id, checks=qc_checks, notes=meta["limitations"])
    copy_file(qc_path, qc_root / qc_name)

    return {
        "figure_id": figure_id,
        "title": FIGURE_TITLES[figure_id],
        "output_svg": fig_paths["svg"],
        "output_pdf": fig_paths["pdf"],
        "output_png": fig_paths["png"],
        "source_data_csv": str(source_csv_path),
        "figure_data_json": str(figure_data_path),
        "caption_md": str(caption_path),
        "panels": meta["panels"],
        "filters_applied": meta["filters_applied"],
        "limitations": meta["limitations"],
        "qc_png": str(qc_path),
    }


def _build_contact_sheet(records: list[dict[str, Any]], output_path: Path) -> Path:
    configure_style()
    cols = 2
    rows = max(1, (len(records) + cols - 1) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 3.6))
    axes_list = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax, record in zip(axes_list, records):
        ax.axis("off")
        ax.imshow(mpimg.imread(record["output_png"]))
        ax.set_title(f"{record['figure_id']}\n{record['title']}", fontsize=7)
    for ax in axes_list[len(records) :]:
        ax.axis("off")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _build_readme(records: list[dict[str, Any]], adapter: dict[str, Any], warnings: list[str], contact_sheet: Path, *, version_label: str) -> str:
    lines = [
        f"# Manuscript Figures Nature {version_label}",
        "",
        "## Nature-skills status",
        f"- nature_skills_used: {adapter['nature_skills_used']}",
        f"- nature_skills_path: {adapter['nature_skills_path'] or 'N/A'}",
        f"- fallback_used: {adapter['fallback_used']}",
        "",
        "## Figures",
    ]
    for record in records:
        lines.append(f"- {record['figure_id']}: {record['title']}")
    lines.extend(
        [
            "",
            "## Contact sheet",
            f"- {contact_sheet}",
            "",
            "## Warnings",
        ]
    )
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _source_table_path(source_root: Path, figure_id: str) -> str:
    return str(source_root / f"{FIGURE_DIR_NAMES[figure_id]}_source.csv")


def _build_qc_summary(records: list[dict[str, Any]], audit_records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "entry_type": "figure",
                "name": record["figure_id"],
                "path": record["output_png"],
                "row_count": "",
                "status": "generated",
            }
        )
    for audit in audit_records:
        rows.append(
            {
                "entry_type": "audit_table",
                "name": audit["audit_name"],
                "path": audit["path"],
                "row_count": audit["row_count"],
                "status": "generated",
            }
        )
    return pd.DataFrame(rows)
