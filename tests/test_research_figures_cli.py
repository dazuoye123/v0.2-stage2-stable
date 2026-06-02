from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_research_figures.py"
SPEC = importlib.util.spec_from_file_location("run_research_figures_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_research_figures(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_research_figures.py",
            "--outputs-dir",
            "data/outputs",
            "--batch-output-dir",
            "data/batch_validation",
            "--manifest",
            "data/batch_manifest/source_manifest.csv",
            "--no-figures",
        ],
    )
    args = MODULE.parse_args()
    assert args.outputs_dir == "data/outputs"
    assert args.batch_output_dir == "data/batch_validation"
    assert args.manifest == "data/batch_manifest/source_manifest.csv"
    assert args.generate_figures is False
