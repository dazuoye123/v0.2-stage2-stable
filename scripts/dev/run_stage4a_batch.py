"""Legacy wrapper for archived developer tool.

This helper is kept for compatibility while its implementation lives in the archive.
"""

from __future__ import annotations

from pathlib import Path

_ARCHIVE_PATH = Path(__file__).resolve().parents[2] / r"archive\\scripts\\stage4_legacy" / "run_stage4a_batch.py"
_SOURCE = _ARCHIVE_PATH.read_text(encoding="utf-8")
exec(compile(_SOURCE, str(_ARCHIVE_PATH), "exec"), globals())
