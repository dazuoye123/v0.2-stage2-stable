"""Shared figure-ID regexes and helpers.

This module centralizes figure-ID parsing so we do not maintain slightly
different regexes in figure extraction, context matching, and fragment logic.
"""

from __future__ import annotations

import re


FIGURE_ID_PATTERN = re.compile(
    r"(?P<zh>\u56fe\s*(?P<zh_num>\d+(?:[.\-]\d+)*))|"
    r"(?P<fig>\bFig\.?\s*(?P<fig_num>S?\d+(?:[.\-]\d+)*))|"
    r"(?P<figure>\bFigure\s*(?P<figure_num>S?\d+(?:[.\-]\d+)*))",
    re.IGNORECASE,
)

ANY_FIGURE_ID_PATTERN = re.compile(
    r"(?:\u56fe\s*(?P<zh>\d+(?:[.\-]\d+)*)|Fig\.?\s*(?P<fig>S?\d+(?:[.\-]\d+)*)|Figure\s*(?P<figure>S?\d+(?:[.\-]\d+)*))",
    re.IGNORECASE,
)

CAPTION_START_PATTERN = re.compile(
    r"^\s*(?:\u56fe\s*\d+(?:[.\-]\d+)*|Fig\.?\s*S?\d+(?:[.\-]\d+)*|Figure\s*S?\d+(?:[.\-]\d+)*)\b",
    re.IGNORECASE,
)


def find_figure_id_pair(text: str) -> tuple[str | None, str | None]:
    """Return raw ID text and normalized figure ID with prefix preserved."""
    match = FIGURE_ID_PATTERN.search(text or "")
    if not match:
        return None, None
    raw = match.group(0).strip()
    if match.group("zh_num"):
        return raw, f"\u56fe{match.group('zh_num')}"
    if match.group("fig_num"):
        return raw, f"Fig.{match.group('fig_num')}"
    if match.group("figure_num"):
        return raw, f"Figure {match.group('figure_num')}"
    return raw, raw


def figure_number_from_id(text: str | None) -> str | None:
    """Extract only the numeric part of a figure ID."""
    if not text:
        return None
    match = re.search(r"S?\d+(?:[.\-]\d+)*", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def build_mention_patterns(figure_id: str) -> list[re.Pattern[str]]:
    """Build exact figure mention regexes for downstream context matching."""
    number = figure_number_from_id(figure_id)
    if not number:
        return []
    escaped = re.escape(number)
    exact_end = r"(?![\d.\-])"
    suffix = r"(?:\s*[\uff08(][A-Za-z][\uff09)])?"
    return [
        re.compile(rf"\u56fe\s*{escaped}{exact_end}{suffix}", re.IGNORECASE),
        re.compile(rf"Fig\.?\s*{escaped}{exact_end}{suffix}", re.IGNORECASE),
        re.compile(rf"Figure\s*{escaped}{exact_end}{suffix}", re.IGNORECASE),
    ]
