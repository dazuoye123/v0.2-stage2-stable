from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dev" / "rerun_stage4a_from_manifest.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("rerun_stage4a_from_manifest_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_dry_run_only_manifest_row_is_selected_by_default(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img.png,dry_run_only,dry_run_only,rerun_live,True,P1\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["executed_papers"] == 0


def test_run_live_invokes_extractor_only_when_requested(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img.png,failed_retryable,timeout,rerun_live,True,P2\n",
        encoding="utf-8",
    )
    calls: list[dict] = []

    class FakeExtractor:
        def __init__(self, **kwargs):  # noqa: ANN003
            calls.append({"init": kwargs})

        def run(self):
            calls.append({"run": True})
            return {"successful_extractions_count": 1}

    monkeypatch.setattr(module, "Stage4VisionSpectraExtractor", FakeExtractor)
    monkeypatch.setattr(module, "load_project_dotenv", lambda *_args, **_kwargs: None)

    module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=True,
        limit=0,
        status_filter=None,
        summary_json=tmp_path / "summary.json",
    )

    assert any("init" in item for item in calls)
    assert any("run" in item for item in calls)


def test_nonretryable_rows_are_not_selected_by_default(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img.png,failed_nonretryable,missing_image_path,manual_hold,False,\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 0


def test_workers_one_preserves_serial_plan_behavior(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,dry_run_only,dry_run_only,rerun_live,True,P1\n"
        "fiber_process,paper1,fig-2,img2.png,dry_run_only,dry_run_only,rerun_live,True,P1\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        workers=1,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    summary = result["summary"]
    assert summary["workers"] == 1
    assert summary["selected_figure_count"] == 2
    assert summary["selected_paper_count"] == 1
    assert summary["executed_papers"] == 0
    assert summary["per_paper"][0]["figure_ids"] == ["fig-1", "fig-2"]


def test_workers_two_dry_run_does_not_call_vlm(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_retryable,timeout,rerun_live,True,P2\n",
        encoding="utf-8",
    )

    def _should_not_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("dry-run must not invoke live paper execution")

    monkeypatch.setattr(module, "_execute_paper_rerun_task", _should_not_run)

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["workers"] == 2
    assert result["summary"]["executed_papers"] == 0


def test_parallel_mode_groups_by_paper(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "fiber_process,paper1,fig-2,img2.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "mechanism,paper2,fig-3,img3.png,failed_retryable,timeout,rerun_live,True,P2\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str, list[str]]] = []

    def _fake_execute(**kwargs):  # noqa: ANN003
        rows = kwargs["figure_rows"]
        calls.append((kwargs["category"], kwargs["paper_id"], [row["figure_id"] for row in rows]))
        return {"ok": True, "summary": {"successful_extractions_count": len(rows)}, "error_message": None, "elapsed_seconds": 0.01}

    monkeypatch.setattr(module, "_execute_paper_rerun_task", _fake_execute)
    monkeypatch.setattr(module, "load_project_dotenv", lambda *_args, **_kwargs: None)

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=True,
        limit=0,
        status_filter=None,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert len(calls) == 2
    assert ("fiber_process", "paper1", ["fig-1", "fig-2"]) in calls
    assert ("mechanism", "paper2", ["fig-3"]) in calls
    assert result["summary"]["success_papers"] == 2


def test_parallel_mode_records_failure_without_stopping(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "mechanism,paper2,fig-2,img2.png,failed_retryable,timeout,rerun_live,True,P2\n",
        encoding="utf-8",
    )

    def _fake_execute(**kwargs):  # noqa: ANN003
        if kwargs["paper_id"] == "paper1":
            return {
                "ok": False,
                "summary": None,
                "error_message": "boom",
                "error_type": "RuntimeError",
                "traceback": "RuntimeError: boom",
                "elapsed_seconds": 0.01,
            }
        return {"ok": True, "summary": {"successful_extractions_count": 1}, "error_message": None, "elapsed_seconds": 0.01}

    monkeypatch.setattr(module, "_execute_paper_rerun_task", _fake_execute)
    monkeypatch.setattr(module, "load_project_dotenv", lambda *_args, **_kwargs: None)

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=True,
        limit=0,
        status_filter=None,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    summary = result["summary"]
    assert summary["executed_papers"] == 2
    assert summary["success_papers"] == 1
    assert summary["failed_papers"] == 1
    assert any(paper["paper_id"] == "paper1" and paper["error_message"] == "boom" for paper in summary["per_paper"])


def test_limit_applies_before_grouping_in_parallel(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "fiber_process,paper1,fig-2,img2.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "mechanism,paper2,fig-3,img3.png,failed_retryable,timeout,rerun_live,True,P2\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=2,
        status_filter=None,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 2
    assert result["summary"]["selected_paper_count"] == 1


def test_status_filter_applies_in_parallel(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_retryable,timeout,rerun_live,True,P2\n"
        "fiber_process,paper2,fig-2,img2.png,dry_run_only,dry_run_only,rerun_live,True,P1\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter={"failed_retryable"},
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["planned_by_status"] == {"failed_retryable": 1}


def test_force_nonretryable_with_workers_two(tmp_path: Path) -> None:
    module = _load_script_module()
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,status,reason,suggested_action,retryable,priority\n"
        "fiber_process,paper1,fig-1,img1.png,failed_nonretryable,missing_image_path,manual_hold,False,\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        force_nonretryable=True,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["force_nonretryable"] is True


def test_true_nonretryable_rows_are_not_selected_by_default(tmp_path: Path) -> None:
    module = _load_script_module()
    image_path = tmp_path / "img.png"
    Image.new("RGB", (4, 4), color="white").save(image_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,retryable,true_nonretryable,force_retry_candidate,suggested_action\n"
        f"fiber_process,paper1,fig-1,{image_path},{image_path},failed_nonretryable,False,True,False,fix_auth_before_rerun\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 0


def test_force_true_nonretryable_selects_rows(tmp_path: Path) -> None:
    module = _load_script_module()
    image_path = tmp_path / "img.png"
    Image.new("RGB", (4, 4), color="white").save(image_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,retryable,true_nonretryable,force_retry_candidate,suggested_action\n"
        f"fiber_process,paper1,fig-1,{image_path},{image_path},failed_nonretryable,False,True,False,fix_auth_before_rerun\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        force_nonretryable=True,
        force_true_nonretryable=True,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    summary = result["summary"]
    assert summary["selected_figure_count"] == 1
    assert summary["force_true_nonretryable"] is True
    assert summary["skipped_missing_images"] == 0
    assert summary["skipped_unreadable_images"] == 0


def test_force_true_nonretryable_dry_run_does_not_call_vlm(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    image_path = tmp_path / "img.png"
    Image.new("RGB", (4, 4), color="white").save(image_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,retryable,true_nonretryable,force_retry_candidate,suggested_action\n"
        f"fiber_process,paper1,fig-1,{image_path},{image_path},failed_nonretryable,False,True,False,fix_auth_before_rerun\n",
        encoding="utf-8",
    )

    def _should_not_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("dry-run must not invoke live paper execution")

    monkeypatch.setattr(module, "_execute_paper_rerun_task", _should_not_run)

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=0,
        status_filter=None,
        force_nonretryable=True,
        force_true_nonretryable=True,
        workers=8,
        submit_delay_seconds=0.5,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["executed_papers"] == 0


def test_limit_still_applies_with_force_true_nonretryable(tmp_path: Path) -> None:
    module = _load_script_module()
    image_path1 = tmp_path / "img1.png"
    image_path2 = tmp_path / "img2.png"
    Image.new("RGB", (4, 4), color="white").save(image_path1)
    Image.new("RGB", (4, 4), color="white").save(image_path2)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,retryable,true_nonretryable,force_retry_candidate,suggested_action\n"
        f"fiber_process,paper1,fig-1,{image_path1},{image_path1},failed_nonretryable,False,True,False,fix_auth_before_rerun\n"
        f"fiber_process,paper2,fig-2,{image_path2},{image_path2},failed_nonretryable,False,True,False,fix_auth_before_rerun\n",
        encoding="utf-8",
    )

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=False,
        limit=1,
        status_filter=None,
        force_nonretryable=True,
        force_true_nonretryable=True,
        workers=4,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert result["summary"]["selected_figure_count"] == 1
    assert result["summary"]["selected_paper_count"] == 1


def test_workers_two_force_true_nonretryable_still_groups_by_paper(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    image_path1 = tmp_path / "img1.png"
    image_path2 = tmp_path / "img2.png"
    image_path3 = tmp_path / "img3.png"
    Image.new("RGB", (4, 4), color="white").save(image_path1)
    Image.new("RGB", (4, 4), color="white").save(image_path2)
    Image.new("RGB", (4, 4), color="white").save(image_path3)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "category,paper_id,figure_id,image_path,resolved_image_path,status,retryable,true_nonretryable,force_retry_candidate,suggested_action\n"
        f"fiber_process,paper1,fig-1,{image_path1},{image_path1},failed_nonretryable,False,True,False,fix_auth_before_rerun\n"
        f"fiber_process,paper1,fig-2,{image_path2},{image_path2},failed_nonretryable,False,True,False,fix_auth_before_rerun\n"
        f"mechanism,paper2,fig-3,{image_path3},{image_path3},failed_nonretryable,False,True,False,fix_auth_before_rerun\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str, list[str]]] = []

    def _fake_execute(**kwargs):  # noqa: ANN003
        rows = kwargs["figure_rows"]
        calls.append((kwargs["category"], kwargs["paper_id"], [row["figure_id"] for row in rows]))
        return {"ok": True, "summary": {"successful_extractions_count": len(rows)}, "error_message": None, "elapsed_seconds": 0.01}

    monkeypatch.setattr(module, "_execute_paper_rerun_task", _fake_execute)
    monkeypatch.setattr(module, "load_project_dotenv", lambda *_args, **_kwargs: None)

    result = module.execute_rerun_from_manifest(
        manifest_path=manifest,
        outputs_dir=tmp_path / "outputs",
        stage3_subdir="stage3_twopass",
        stage4_subdir="stage4_vision_spectra_universal",
        routing_mode="universal_compact",
        run_live=True,
        limit=0,
        status_filter=None,
        force_nonretryable=True,
        force_true_nonretryable=True,
        workers=2,
        submit_delay_seconds=0.0,
        summary_json=tmp_path / "summary.json",
    )

    assert len(calls) == 2
    assert ("fiber_process", "paper1", ["fig-1", "fig-2"]) in calls
    assert ("mechanism", "paper2", ["fig-3"]) in calls
    assert result["summary"]["selected_figure_count"] == 3
