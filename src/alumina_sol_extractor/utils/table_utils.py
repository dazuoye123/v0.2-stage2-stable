"""Utilities for extracting HTML tables from cleaned MinerU Markdown."""

from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path

import pandas as pd

from alumina_sol_extractor.models.table import TableInfo


HTML_TABLE_PATTERN = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
CAPTION_BEFORE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:表|Table)\s*[\w.\-一二三四五六七八九十百千]+[^\n]{0,120}$",
    re.IGNORECASE,
)


def extract_tables_from_markdown(
    markdown: str,
    project_root: Path,
    paper_id: str,
    preview_rows: int = 8,
    tables_dir: Path | None = None,
) -> tuple[str, list[TableInfo]]:
    """Extract all ``<table>...</table>`` blocks and replace them in Markdown.

    Tables are saved as CSV and JSON under the explicit ``tables_dir`` when
    provided. Otherwise, the legacy default ``data/outputs/{paper_id}/tables``
    is used for backward compatibility. The returned Markdown keeps a compact
    preview in place of the raw HTML table.
    """
    project_root = Path(project_root).resolve()
    tables_dir = (
        Path(tables_dir).resolve()
        if tables_dir is not None
        else project_root / "data" / "outputs" / paper_id / "tables"
    )
    tables_dir.mkdir(parents=True, exist_ok=True)
    index_path = tables_dir / "tables_index.jsonl"

    infos: list[TableInfo] = []
    pieces: list[str] = []
    cursor = 0

    for table_number, match in enumerate(HTML_TABLE_PATTERN.finditer(markdown), start=1):
        table_id = f"table_{table_number:03d}"
        html = match.group(0)
        df = _read_first_html_table(html)
        df = _clean_dataframe(df)

        csv_path = tables_dir / f"{table_id}.csv"
        json_path = tables_dir / f"{table_id}.json"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        json_path.write_text(
            df.to_json(orient="records", force_ascii=False, indent=2),
            encoding="utf-8",
        )

        context_before = _extract_context_before(markdown, match.start())
        context_after = _extract_context_after(markdown, match.end())
        caption = _extract_caption(context_before, context_after)
        info = TableInfo(
            paper_id=paper_id,
            table_id=table_id,
            csv_path=str(csv_path),
            json_path=str(json_path),
            position=match.start(),
            rows=int(df.shape[0]),
            columns=int(df.shape[1]),
            caption=caption,
            context_before=context_before,
            context_after=context_after,
        )
        infos.append(info)

        pieces.append(markdown[cursor : match.start()])
        pieces.append(_build_table_replacement(table_id, df, csv_path, json_path, preview_rows))
        cursor = match.end()

    pieces.append(markdown[cursor:])
    new_markdown = "".join(pieces)

    with index_path.open("w", encoding="utf-8") as file_obj:
        for info in infos:
            file_obj.write(json.dumps(info.to_dict(), ensure_ascii=False) + "\n")

    return new_markdown, infos


def _read_first_html_table(html: str) -> pd.DataFrame:
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise ValueError("No table could be parsed from HTML block.")
    return tables[0]


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pandas output while preserving Chinese headers and units."""
    df = df.copy()
    df.columns = [_clean_cell(col) for col in df.columns]
    df = df.map(_clean_cell)
    return df


def _clean_cell(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_context_before(markdown: str, start: int, max_chars: int = 500) -> str:
    text = markdown[max(0, start - max_chars) : start]
    return _trim_context(text, from_end=True)


def _extract_context_after(markdown: str, end: int, max_chars: int = 500) -> str:
    text = markdown[end : end + max_chars]
    return _trim_context(text, from_end=False)


def _trim_context(text: str, from_end: bool) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    selected = lines[-4:] if from_end else lines[:4]
    return "\n".join(selected)


def _extract_caption(context_before: str, context_after: str) -> str:
    before_lines = [line.strip() for line in context_before.splitlines() if line.strip()]
    for line in reversed(before_lines):
        if CAPTION_BEFORE_PATTERN.search(line):
            return line

    after_lines = [line.strip() for line in context_after.splitlines() if line.strip()]
    for line in after_lines:
        if re.match(r"^(?:表|Table)\s*[\w.\-一二三四五六七八九十百千]+", line, re.IGNORECASE):
            return line
    return ""


def _build_table_replacement(
    table_id: str,
    df: pd.DataFrame,
    csv_path: Path,
    json_path: Path,
    preview_rows: int,
) -> str:
    preview = df.head(preview_rows).to_markdown(index=False)
    csv_link = csv_path.resolve().as_posix()
    json_link = json_path.resolve().as_posix()
    return (
        f"\n\n[TableID: {table_id}]\n\n"
        f"{preview}\n\n"
        f"CSV: [{csv_path.name}]({csv_link})\n\n"
        f"JSON: [{json_path.name}]({json_link})\n\n"
    )
