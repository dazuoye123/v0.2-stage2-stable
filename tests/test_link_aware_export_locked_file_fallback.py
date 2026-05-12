from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.dataset_fusion.link_aware_export import _safe_write


def test_safe_write_emits_fallback_file_on_permission_error(tmp_path: Path) -> None:
    canonical_path = tmp_path / "process_steps_table.csv"
    generated_path = tmp_path / "process_steps_table.generated.csv"
    warnings: list[str] = []
    locked_files: list[str] = []
    fallback_outputs: list[str] = []

    def writer(path: Path) -> None:
        if path == canonical_path:
            raise PermissionError("locked")
        path.write_text("header\nvalue\n", encoding="utf-8")

    _safe_write(
        canonical_path,
        writer,
        warnings,
        locked_files=locked_files,
        fallback_outputs=fallback_outputs,
    )

    assert canonical_path.exists() is False
    assert generated_path.exists() is True
    assert "could_not_overwrite_locked_file:process_steps_table.csv" in warnings
    assert "wrote_fallback_output:process_steps_table.generated.csv" in warnings
    assert locked_files == ["process_steps_table.csv"]
    assert fallback_outputs == ["process_steps_table.generated.csv"]
