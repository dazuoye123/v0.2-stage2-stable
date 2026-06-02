from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_stage5_batch.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_stage5_batch_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_parse_args_supports_official_stage5_batch_flags(monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_stage5_batch.py",
            "--outputs-dir",
            "tmp",
            "--with-linking",
            "--only-incomplete",
            "--workers",
            "2",
        ],
    )
    args = module.parse_args()
    assert args.outputs_dir == "tmp"
    assert args.with_linking is True
    assert args.only_incomplete is True
    assert args.workers == 2
