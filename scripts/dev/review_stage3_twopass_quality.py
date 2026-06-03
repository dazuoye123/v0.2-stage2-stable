"""Legacy wrapper for archived developer tool.

This helper is kept for compatibility while its implementation lives in the archive.

Legacy note: the archived implementation still uses
`evaluate_stage3_twopass_paper` and `aggregate_quality_review`.
"""

from __future__ import annotations

from pathlib import Path

_ARCHIVE_PATH = Path(__file__).resolve().parents[2] / "archive" / "scripts" / "dev_tools_legacy" / "review_stage3_twopass_quality.py"
_SOURCE = _ARCHIVE_PATH.read_text(encoding="utf-8")
exec(compile(_SOURCE, str(_ARCHIVE_PATH), "exec"), globals())
