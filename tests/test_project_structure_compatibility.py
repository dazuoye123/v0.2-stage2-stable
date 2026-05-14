from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_stage4_extractor_import_path_remains_compatible() -> None:
    from alumina_sol_extractor.vision_spectra.extractor import Stage4VisionSpectraExtractor

    assert Stage4VisionSpectraExtractor.__name__ == "Stage4VisionSpectraExtractor"


def test_vlm_client_import_paths_remain_compatible() -> None:
    from alumina_sol_extractor.vision_spectra.vlm_client import VLMRequest, VLMRequestError, VisionLanguageModelClient

    assert VLMRequest.__name__ == "VLMRequest"
    assert VLMRequestError.__name__ == "VLMRequestError"
    assert VisionLanguageModelClient.__name__ == "VisionLanguageModelClient"


def test_link_aware_export_public_imports_remain_compatible() -> None:
    from alumina_sol_extractor.dataset_fusion.link_aware_export import (
        generate_link_aware_exports,
        load_link_aware_inputs,
    )

    assert callable(generate_link_aware_exports)
    assert callable(load_link_aware_inputs)


def test_run_full_pipeline_help_still_works() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_full_pipeline.py"), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Run the controlled full pipeline" in result.stdout


def test_scripts_root_no_longer_contains_test_prefixed_helpers() -> None:
    scripts_dir = REPO_ROOT / "scripts"
    root_test_scripts = sorted(path.name for path in scripts_dir.glob("test_*.py"))
    assert root_test_scripts == []
