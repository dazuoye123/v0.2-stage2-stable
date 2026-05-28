from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.stage4.stage2_selected_loader import load_stage2_selected_figures


def test_loader_prefers_vision_image_path_from_figures_jsonl(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir(parents=True)
    vision_path = paper_dir / "figures_for_vision" / "fig-1.png"
    vision_path.parent.mkdir(parents=True)
    vision_path.write_bytes(b"img")
    (paper_dir / "figures.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-1",
                "image_path": str(paper_dir / "figures_all" / "fig-1.png"),
                "vision_image_path": str(vision_path),
                "caption": "XRD pattern",
                "figure_class": "generic_chart_or_plot",
                "send_to_vision_model": True,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_stage2_selected_figures(paper_dir)

    assert len(records) == 1
    assert records[0]["source_image_path"] == str(vision_path)
    assert records[0]["vision_image_path"] == str(vision_path)


def test_loader_falls_back_to_figures_for_vision_when_figures_jsonl_missing(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    figures_dir = paper_dir / "figures_for_vision"
    figures_dir.mkdir(parents=True)
    image_path = figures_dir / "fig-1.png"
    image_path.write_bytes(b"img")

    records = load_stage2_selected_figures(paper_dir)

    assert len(records) == 1
    assert records[0]["vision_image_path"] == str(image_path)
    assert "figures_jsonl_missing_fallback_to_directory" in records[0]["loader_warnings"]


def test_loader_does_not_use_figures_all_as_formal_input(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    figures_all = paper_dir / "figures_all"
    figures_all.mkdir(parents=True)
    image_path = figures_all / "fig-1.png"
    image_path.write_bytes(b"img")
    (paper_dir / "figures.jsonl").write_text(
        json.dumps(
            {
                "figure_id": "fig-1",
                "image_path": str(image_path),
                "caption": "unused",
                "figure_class": "xrd_pattern",
                "send_to_vision_model": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_stage2_selected_figures(paper_dir)

    assert records == []
