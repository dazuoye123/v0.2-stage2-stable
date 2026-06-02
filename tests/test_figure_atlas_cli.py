from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_figure_atlas.py"
SPEC = importlib.util.spec_from_file_location("run_figure_atlas_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_figure_atlas(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_figure_atlas.py",
            "--outputs-dir",
            "data/outputs",
            "--batch-final-export-dir",
            "data/outputs/_batch_final_exports",
            "--batch-output-dir",
            "data/batch_validation",
            "--audit-only",
            "--skip-auto-figures",
        ],
    )
    args = MODULE.parse_args()
    assert args.outputs_dir == "data/outputs"
    assert args.batch_final_export_dir == "data/outputs/_batch_final_exports"
    assert args.audit_only is True
    assert args.skip_auto_figures is True
    assert not hasattr(args, "delete_old_research_figures_code")
    assert not hasattr(args, "dry_run_delete_old_code")
