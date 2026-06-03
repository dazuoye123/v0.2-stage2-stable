from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_manuscript_figures.py"
SPEC = importlib.util.spec_from_file_location("run_manuscript_figures_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_manuscript_figures(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_manuscript_figures.py",
            "--diagnosis-dir",
            "data/batch_validation/20260602_212510/manuscript_figure_diagnosis",
            "--output-dir",
            "data/batch_validation/20260602_212510/manuscript_figures_nature_v1",
            "--figures",
            "Fig1",
            "Fig2",
            "Fig4",
            "--dry-run",
            "--continue-on-error",
        ],
    )
    args = MODULE.parse_args()
    assert args.diagnosis_dir.endswith("manuscript_figure_diagnosis")
    assert args.output_dir.endswith("manuscript_figures_nature_v1")
    assert args.figures == ["Fig1", "Fig2", "Fig4"]
    assert args.dry_run is True
    assert args.continue_on_error is True
