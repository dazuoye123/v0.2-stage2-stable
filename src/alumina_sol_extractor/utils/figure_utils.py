"""Figure extraction helpers for MinerU Markdown.

All MinerU images are copied to ``figures_all``. This module extracts stable
figure IDs, captions, pseudo captions, optional heading metadata, and contexts.
Final classification and vision selection are handled by ``figure_filter``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from alumina_sol_extractor.models.figure import FigureInfo


IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^\n]*)\)")
DATA_IMAGE_PATTERN = re.compile(r"^data:image/[^;]+;base64,(?P<data>.+)$", re.DOTALL)
FIGURE_ID_PATTERN = re.compile(
    r"(?P<zh>\u56fe\s*(?P<zh_num>\d+(?:\.\d+)*))|"
    r"(?P<fig>\bFig\.?\s*(?P<fig_num>S?\d+(?:\.\d+)*))|"
    r"(?P<figure>\bFigure\s*(?P<figure_num>S?\d+(?:\.\d+)*))",
    re.IGNORECASE,
)
CAPTION_START_PATTERN = re.compile(
    r"^\s*(?:\u56fe\s*\d+(?:\.\d+)*|Fig\.?\s*S?\d+(?:\.\d+)*|Figure\s*S?\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)
TABLE_START_PATTERN = re.compile(r"^\s*(?:\u8868\s*\d+(?:\.\d+)*|Table\s*\d+(?:\.\d+)*|\[TableID:)", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", re.MULTILINE)
REFERENCE_SECTION_PATTERN = re.compile(
    r"^\s*(?:references|bibliography|\u53c2\u8003\u6587\u732e|\u81f4\u8c22|\u5b66\u4f4d\u8bba\u6587\u8bc4\u9605\u53ca\u7b54\u8fa9\u60c5\u51b5\u8868)\b",
    re.IGNORECASE,
)
SENTENCE_END_CHARS = "\u3002\uff1b;\uff1f\uff01!?."
BODY_REFERENCE_PATTERN = re.compile(
    r"(?:"
    r"\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u4e3a|"
    r"\u5c06\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u7531\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u5982\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u7531\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*(?:\u53ef\u77e5|\u53ef\u89c1)|"
    r"\u5982\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u6240\u793a|"
    r"\u6839\u636e\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u4ece\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u53ef\u4ee5\u770b\u51fa|"
    r"\u56fe\s*\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*(?:\u8868\u660e|\u663e\u793a)|"
    r"\u6570\u636e\u89c1\u8868\s*\d+(?:\.\d+)*|"
    r"\u89c1\u8868\s*\d+(?:\.\d+)*|"
    r"as shown in\s+(?:Fig\.?|Figure)\s*S?\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"shown in\s+(?:Fig\.?|Figure)\s*S?\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"(?:Fig\.?|Figure)\s*S?\d+(?:\.\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s+(?:shows|indicates)"
    r")",
    re.IGNORECASE,
)
PSEUDO_REFERENCE_PATTERN = re.compile(
    r"(?:\u6838\u78c1\u7ed3\u679c\u89c1\u56fe|"
    r"\u6d4b\u8bd5\u7ed3\u679c\u89c1\u56fe|"
    r"\u7ed3\u679c\u89c1\u56fe|"
    r"\u5982\u56fe|"
    r"\u7531\u56fe|"
    r"\u56fe)\s*(?P<number>\d+(?:\.\d+)*)",
    re.IGNORECASE,
)


def rewrite_mineru_image_paths(
    markdown: str,
    markdown_dir: Path,
    project_root: Path,
    paper_id: str,
) -> str:
    """Copy local MinerU images into ``data/outputs/{paper_id}/figures_all``."""
    markdown_dir = Path(markdown_dir)
    project_root = Path(project_root).resolve()
    figures_dir = project_root / "data" / "outputs" / paper_id / "figures_all"
    figures_dir.mkdir(parents=True, exist_ok=True)

    def replace(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        raw_path = match.group(2).strip().strip('"').strip("'")
        parsed = urlparse(raw_path)
        if parsed.scheme in {"http", "https", "data"}:
            return match.group(0)

        source = _resolve_local_image_path(raw_path, markdown_dir, project_root, paper_id)
        if source is None or not source.exists():
            return match.group(0)

        target = _copy_image_to_figures(source, figures_dir)
        return f"![{alt_text}]({target.resolve().as_posix()})"

    return IMAGE_PATTERN.sub(replace, markdown)


def find_figures_in_markdown_any(
    markdown_text: str,
    markdown_path: Path,
    project_root: Path,
    paper_id: str,
) -> list[FigureInfo]:
    """Find figures in Markdown and return image-hash de-duplicated records."""
    markdown_path = Path(markdown_path)
    markdown_dir = markdown_path.parent
    project_root = Path(project_root).resolve()
    figures_all_dir = project_root / "data" / "outputs" / paper_id / "figures_all"
    figures_all_dir.mkdir(parents=True, exist_ok=True)

    matches = list(IMAGE_PATTERN.finditer(markdown_text))
    groups = _group_consecutive_images(markdown_text, matches)
    headings = _collect_headings(markdown_text)
    seen_hashes: set[str] = set()
    figures: list[FigureInfo] = []

    for group in groups:
        next_image_position = _next_image_position(matches, group[-1])
        caption_result = extract_caption_record(
            markdown_text,
            image_end_position=group[-1].end(),
            next_image_position=next_image_position,
        )
        caption = caption_result.caption
        group_id_raw, group_figure_id = _find_figure_id_pair(caption or "")
        subfigure_labels = _extract_subfigure_labels(caption)
        if not subfigure_labels and len(group) > 1:
            subfigure_labels = _extract_group_labels(markdown_text, group)

        for index_in_group, match in enumerate(group, start=1):
            alt_text = match.group(1)
            raw_path = match.group(2).strip().strip('"').strip("'")
            position = match.start()
            context_before, context_after = _extract_context(markdown_text, position, 800)
            local_window = markdown_text[max(0, position - 800) : min(len(markdown_text), match.end() + 800)]

            image_path, image_url, base64_data = _materialize_image(
                raw_path=raw_path,
                markdown_dir=markdown_dir,
                project_root=project_root,
                paper_id=paper_id,
                figures_all_dir=figures_all_dir,
            )
            image_hash = compute_image_hash(image_path=image_path, base64_data=base64_data)
            if image_hash and image_hash in seen_hashes:
                continue
            if image_hash:
                seen_hashes.add(image_hash)

            alt_id_raw, alt_figure_id = _find_figure_id_pair(alt_text)
            after_id_raw, after_figure_id = _find_figure_id_pair(context_after)
            before_id_raw, before_figure_id = _find_figure_id_pair(context_before)
            figure_id = group_figure_id or alt_figure_id or after_figure_id or before_figure_id
            figure_id_raw = group_id_raw or alt_id_raw or after_id_raw or before_id_raw
            if not figure_id:
                figure_id = f"Unknown Figure {len(figures) + 1}"

            current_caption = caption
            caption_source = caption_result.source
            reference_sentences = list(caption_result.trailing_reference_sentences)
            if not current_caption:
                pseudo_caption = build_pseudo_caption(figure_id, local_window)
                if pseudo_caption:
                    current_caption = pseudo_caption
                    caption_source = "pseudo_caption"
                else:
                    caption_source = "none"

            section_title = find_section_title_for_position(headings, position)

            subfigure_label = _label_for_index(subfigure_labels, index_in_group)
            description_text = build_description_text(
                caption=current_caption,
                reference_sentences=reference_sentences,
                figure_id=figure_id,
                subfigure_label=subfigure_label,
                fallback_context=context_after,
            )

            figures.append(
                FigureInfo(
                    paper_id=paper_id,
                    figure_id=figure_id,
                    figure_id_raw=figure_id_raw,
                    subfigure_index=index_in_group if len(group) > 1 else None,
                    subfigure_label=subfigure_label,
                    alt_text=alt_text,
                    image_path=image_path,
                    image_url=image_url,
                    base64_data=base64_data,
                    image_hash=image_hash,
                    position=position,
                    section_title=section_title,
                    context_before=context_before,
                    context_after=context_after,
                    raw_caption=caption_result.raw_caption,
                    caption=current_caption,
                    caption_source=caption_source,
                    caption_cleaned=caption_result.caption_cleaned,
                    caption_truncation_reason=caption_result.truncation_reason,
                    reference_sentences=reference_sentences,
                    description_text=description_text,
                    keep_for_archive=True,
                    clip_decision="not_run",
                )
            )

    _assign_same_id_caption_subfigure_indices(figures)
    return figures


class CaptionRecord:
    def __init__(
        self,
        caption: str | None,
        source: str,
        trailing_reference_sentences: list[str] | None = None,
        raw_caption: str | None = None,
        caption_cleaned: bool = False,
        truncation_reason: str | None = None,
    ) -> None:
        self.caption = caption
        self.source = source
        self.trailing_reference_sentences = trailing_reference_sentences or []
        self.raw_caption = raw_caption
        self.caption_cleaned = caption_cleaned
        self.truncation_reason = truncation_reason


def extract_caption_near_image(
    markdown_text: str,
    image_end_position: int,
    next_image_position: int | None = None,
) -> str | None:
    """Backward-compatible helper returning only the caption string."""
    return extract_caption_record(markdown_text, image_end_position, next_image_position).caption


def extract_caption_record(
    markdown_text: str,
    image_end_position: int,
    next_image_position: int | None = None,
) -> CaptionRecord:
    """Extract a standard caption and split any swallowed body reference."""
    limit = min(len(markdown_text), image_end_position + 1200)
    if next_image_position is not None:
        limit = min(limit, next_image_position)
    lines = markdown_text[image_end_position:limit].splitlines()
    caption_lines: list[str] = []
    leading_blank_count = 0
    started = False

    for raw_line in lines:
        line = raw_line.strip()
        if IMAGE_PATTERN.search(line) or TABLE_START_PATTERN.match(line):
            break
        if HEADING_PATTERN.match(line) or REFERENCE_SECTION_PATTERN.match(line):
            break
        if not line:
            if started:
                break
            leading_blank_count += 1
            if leading_blank_count > 1:
                return CaptionRecord(None, "none")
            continue
        if not started:
            if not CAPTION_START_PATTERN.match(line):
                return CaptionRecord(None, "none")
            started = True
            caption_lines.append(line)
            continue
        if not _looks_like_caption_continuation(caption_lines[-1], line):
            break
        caption_lines.append(line)
        if len(caption_lines) >= 3:
            break

    if not caption_lines:
        return CaptionRecord(None, "none")
    caption_text = _compact_spaces(" ".join(caption_lines))
    raw_id, figure_id = _find_figure_id_pair(caption_text)
    caption, trailing_refs, reason = _split_caption_details(caption_text, figure_id=figure_id or raw_id)
    return CaptionRecord(
        caption or None,
        "standard_caption" if caption else "none",
        trailing_refs,
        raw_caption=caption_text,
        caption_cleaned=reason is not None,
        truncation_reason=reason,
    )


def split_caption_and_references(text: str) -> tuple[str, list[str]]:
    """Backward-compatible wrapper for caption cleanup."""
    return split_caption_and_following_text(text)


def split_caption_and_following_text(
    raw_caption_text: str,
    figure_id: str | None = None,
) -> tuple[str, list[str]]:
    """Split MinerU raw caption into clean caption and swallowed body text."""
    caption, following, _ = _split_caption_details(raw_caption_text, figure_id)
    return caption, following


def _split_caption_details(
    raw_caption_text: str,
    figure_id: str | None = None,
) -> tuple[str, list[str], str | None]:
    text = _compact_spaces(raw_caption_text)
    if not text:
        return "", [], None
    if figure_id is None:
        _, figure_id = _find_figure_id_pair(text)

    boundary = _find_repeated_figure_boundary(text, figure_id)
    reason = "repeated_figure_id" if boundary is not None else None
    if boundary is None:
        boundary = _find_explanatory_phrase_boundary(text)
        reason = "explanatory_phrase" if boundary is not None else None
    if boundary is None:
        boundary = _find_space_body_start_boundary(text)
        reason = "space_body_start" if boundary is not None else None
    if boundary is None and _caption_needs_length_guard(text):
        boundary = _find_punctuation_body_boundary(text) or _find_explanatory_phrase_boundary(text)
        reason = "length_guard" if boundary is not None else None

    if boundary is None:
        return text, [], None

    caption = text[:boundary].strip()
    trailing = text[boundary:].strip()
    return caption, _following_sentences(trailing), reason


def build_pseudo_caption(figure_id: str, context: str) -> str | None:
    """Build a pseudo caption for figures referenced only in nearby body text."""
    if not figure_id or figure_id.startswith("Unknown Figure"):
        return None
    number_match = re.search(r"\d+(?:\.\d+)*", figure_id)
    if not number_match:
        return None
    number = number_match.group(0)
    if re.search(rf"(?:\u6838\u78c1\u7ed3\u679c\u89c1\u56fe|\u6d4b\u8bd5\u7ed3\u679c\u89c1\u56fe|\u7ed3\u679c\u89c1\u56fe|\u5982\u56fe|\u7531\u56fe|\u56fe)\s*{re.escape(number)}(?![\d.])", context):
        return f"\u56fe{number} \u76f8\u5173\u6d4b\u8bd5\u7ed3\u679c\u56fe"
    if PSEUDO_REFERENCE_PATTERN.search(context):
        return f"\u56fe{number} \u76f8\u5173\u6d4b\u8bd5\u7ed3\u679c\u56fe"
    return None


def _find_repeated_figure_boundary(text: str, figure_id: str | None) -> int | None:
    number = _figure_number_from_id(figure_id) or _figure_number_from_id(text)
    if not number:
        return None
    patterns = [
        rf"\u56fe\s*{re.escape(number)}",
        rf"Fig\.?\s*{re.escape(number)}",
        rf"Figure\s*{re.escape(number)}",
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        if len(matches) < 2:
            continue
        for match in matches[1:]:
            following = text[match.start() : match.start() + 80]
            if re.search(
                r"^(?:\u56fe\s*"
                + re.escape(number)
                + r"\s*(?:\u4e3a|\u662f|\u663e\u793a|\u8868\u660e|\u53ef\u77e5)|"
                + r"\u7531\u56fe\s*"
                + re.escape(number)
                + r"|\u5982\u56fe\s*"
                + re.escape(number)
                + r"|\u6839\u636e\u56fe\s*"
                + re.escape(number)
                + r"|\u4ece\u56fe\s*"
                + re.escape(number)
                + r"|(?:Fig\.?|Figure)\s*"
                + re.escape(number)
                + r"\s+shows|as shown in\s+(?:Fig\.?|Figure)\s*"
                + re.escape(number)
                + r")",
                following,
                flags=re.IGNORECASE,
            ):
                return _include_reference_prefix(text, match.start())
    return None


def _include_reference_prefix(text: str, figure_start: int) -> int:
    prefix = text[max(0, figure_start - 4) : figure_start]
    for marker in ["\u6839\u636e", "\u7531", "\u5982", "\u4ece"]:
        if prefix.endswith(marker):
            return figure_start - len(marker)
    return figure_start


def _find_explanatory_phrase_boundary(text: str) -> int | None:
    patterns = [
        r"\s+\u7531\u56fe",
        r"\s+\u5982\u56fe",
        r"\s+\u6839\u636e\u56fe",
        r"\s+\u4ece\u56fe",
        r"\s+\u56fe\u4e2d\u53ef\u4ee5\u770b\u51fa",
        r"\s+\u53ef\u4ee5\u770b\u51fa",
        r"\s+\u53ef\u77e5",
        r"\s+\u8868\u660e",
        r"\s+\u663e\u793a",
        r"\s+\u8bf4\u660e",
        r"\s+\u7ed3\u679c\u8868\u660e",
        r"\s+\u5982\u4e0a\u56fe\u6240\u793a",
        r"\u6570\u636e\u89c1\u8868\s*\d+(?:\.\d+)*",
        r"\u89c1\u8868\s*\d+(?:\.\d+)*",
        r"\s+\u94dd\u6eb6\u80f6\u4e2d\u542b\u6709",
        r"\s+\u6839\u636e[^,，。；;]{0,30}\u53ef\u77e5",
        r"\s+\u5728\u8fdb\u884c[^,，。；;]{0,30}\u65f6",
        r"\s+\u7ed3\u5408",
        r"\s+\u8fd9\u8bf4\u660e",
        r"\s+as shown",
        r"\s+the results show",
        r"\s+shows that",
        r"\s+indicates that",
    ]
    return _first_boundary(text, patterns)


def _find_space_body_start_boundary(text: str) -> int | None:
    body_starts = [
        "\u94dd\u6eb6\u80f6\u4e2d",
        "\u672c\u6587",
        "\u5b9e\u9a8c",
        "\u7ed3\u679c",
        "\u6839\u636e",
        "\u7531",
        "\u5982",
        "\u4ece",
        "\u5728",
        "\u5f53",
        "\u4e3a\u4e86",
        "\u901a\u8fc7",
        "\u7ed3\u5408",
        "\u53ef\u4ee5",
        "\u56e0\u6b64",
        "\u8fd9\u8bf4\u660e",
        "\u8bf4\u660e",
        "\u8868\u660e",
        "\u663e\u793a",
    ]
    min_index = 12
    for match in re.finditer(r"\s+", text):
        if match.start() < min_index:
            continue
        tail = text[match.end() :]
        if any(tail.startswith(start) for start in body_starts):
            return match.start()
    return None


def _find_punctuation_body_boundary(text: str) -> int | None:
    for match in re.finditer(r"[\u3002\uff1b;.]", text):
        if _is_non_sentence_period(text, match.start()):
            continue
        tail = text[match.end() :].lstrip()
        if re.match(r"^(?:\u7531|\u5982|\u6839\u636e|\u4ece|\u5728|\u5f53|\u7ed3\u679c|the results|as shown)", tail, flags=re.IGNORECASE):
            return match.end()
    return None


def _caption_needs_length_guard(text: str) -> bool:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    return chinese_count > 80 or len(text) > 160


def _following_sentences(text: str) -> list[str]:
    if not text:
        return []
    sentences = extract_complete_sentences(text)
    return sentences or [text]


def _first_boundary(text: str, patterns: list[str]) -> int | None:
    starts = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and match.start() > 0:
            starts.append(match.start())
    return min(starts) if starts else None


def _figure_number_from_id(figure_id: str | None) -> str | None:
    if not figure_id:
        return None
    match = re.search(r"S?\d+(?:\.\d+)*", figure_id, flags=re.IGNORECASE)
    return match.group(0) if match else None


def extract_complete_sentences(text: str) -> list[str]:
    """Split Chinese/English text into complete sentences."""
    cleaned = _strip_markdown_noise(text)
    return [sentence for sentence, _, _ in _iter_complete_sentences(cleaned)]


def build_description_text(
    caption: str | None,
    reference_sentences: list[str],
    figure_id: str | None = None,
    subfigure_label: str | None = None,
    fallback_context: str | None = None,
    max_chars: int = 1000,
) -> str | None:
    """Merge caption and reference sentences into compact prompt text."""
    parts: list[str] = []
    if caption:
        if figure_id and subfigure_label:
            parts.append(f"{figure_id}({subfigure_label}): {caption}")
        else:
            parts.append(caption)
    parts.extend(sentence for sentence in reference_sentences if sentence)
    if not parts and fallback_context:
        parts = extract_complete_sentences(fallback_context)[:2]
    merged = " ".join(_dedupe_texts(parts)).strip()
    return merged[:max_chars].rstrip() or None


def compute_image_hash(
    image_path: str | Path | None = None,
    base64_data: str | None = None,
) -> str | None:
    """Compute a sha256 hash from local image bytes or base64 image data."""
    data: bytes | None = None
    if image_path:
        path = Path(image_path)
        if path.exists():
            data = path.read_bytes()
    elif base64_data:
        try:
            if base64_data.startswith("data:") and "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]
            data = base64.b64decode(base64_data)
        except (binascii.Error, ValueError):
            data = None
    return hashlib.sha256(data).hexdigest() if data is not None else None


def find_reference_sentences(
    markdown_text: str,
    figure_id: str,
    window_start: int,
    window_end: int,
) -> list[str]:
    """Compatibility wrapper now delegated to the context matcher."""
    from alumina_sol_extractor.linking.figure_context_matcher import FigureContextMatcher

    dummy = FigureInfo(paper_id="_", figure_id=figure_id, position=window_start)
    return FigureContextMatcher(markdown_text).find_reference_sentences(dummy)


def find_section_title_for_position(
    headings: list[tuple[int, str]],
    position: int,
) -> str | None:
    """Return nearest preceding Markdown heading for traceability only."""
    selected_title: str | None = None
    for heading_position, title in headings:
        if heading_position > position:
            break
        selected_title = title
    return selected_title


def _materialize_image(
    raw_path: str,
    markdown_dir: Path,
    project_root: Path,
    paper_id: str,
    figures_all_dir: Path,
) -> tuple[str | None, str | None, str | None]:
    parsed = urlparse(raw_path)
    if parsed.scheme in {"http", "https"}:
        return None, raw_path, None
    if parsed.scheme == "data" or raw_path.startswith("data:image/"):
        return None, None, _extract_base64_data(raw_path)
    source = _resolve_local_image_path(raw_path, markdown_dir, project_root, paper_id)
    if source and source.exists():
        return str(_copy_image_to_figures(source, figures_all_dir)), None, None
    return None, None, None


def _collect_headings(markdown_text: str) -> list[tuple[int, str]]:
    headings = []
    for match in HEADING_PATTERN.finditer(markdown_text):
        title = _compact_spaces(match.group("title"))
        headings.append((match.start(), title))
    return headings


def _group_consecutive_images(text: str, matches: list[re.Match[str]]) -> list[list[re.Match[str]]]:
    groups: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    for match in matches:
        if not current:
            current = [match]
            continue
        between = text[current[-1].end() : match.start()]
        if _is_soft_gap_between_group_images(between):
            current.append(match)
        else:
            groups.append(current)
            current = [match]
    if current:
        groups.append(current)
    return groups


def _is_soft_gap_between_group_images(text: str) -> bool:
    gap = _compact_spaces(text)
    if not gap:
        return True
    if len(gap) > 80 or CAPTION_START_PATTERN.search(gap) or HEADING_PATTERN.search(gap):
        return False
    if any(char in gap for char in SENTENCE_END_CHARS):
        return False
    return bool(re.fullmatch(r"[\w\s/\-+&:：,，()（）]+", gap))


def _extract_group_labels(markdown_text: str, group: list[re.Match[str]]) -> list[str]:
    labels: list[str] = []
    for index, match in enumerate(group):
        alt_text = _compact_spaces(match.group(1))
        if alt_text:
            labels.append(alt_text)
            continue
        next_start = group[index + 1].start() if index + 1 < len(group) else min(len(markdown_text), match.end() + 120)
        label = _extract_short_label(markdown_text[match.end() : next_start])
        if label:
            labels.append(label)
    return labels


def _extract_short_label(text: str) -> str | None:
    for line in [_compact_spaces(line) for line in text.splitlines() if _compact_spaces(line)]:
        if CAPTION_START_PATTERN.match(line) or HEADING_PATTERN.match(line):
            return None
        if len(line) <= 30 and not any(char in line for char in SENTENCE_END_CHARS):
            return line
    return None


def _next_image_position(matches: list[re.Match[str]], current_match: re.Match[str]) -> int | None:
    for match in matches:
        if match.start() > current_match.start():
            return match.start()
    return None


def _extract_context(text: str, position: int, window: int) -> tuple[str, str]:
    return text[max(0, position - window) : position], text[position : min(len(text), position + window)]


def _find_figure_id_pair(text: str) -> tuple[str | None, str | None]:
    match = FIGURE_ID_PATTERN.search(text or "")
    if not match:
        return None, None
    raw = _compact_spaces(match.group(0))
    if match.group("zh"):
        return raw, f"\u56fe{match.group('zh_num')}"
    if match.group("fig"):
        return raw, f"Fig.{match.group('fig_num')}"
    return raw, f"Figure {match.group('figure_num')}"


def _extract_subfigure_labels(caption: str | None) -> list[str]:
    if not caption:
        return []
    labels = re.findall(r"[（(]\s*([A-Za-z][A-Za-z0-9_-]{0,20})\s*[）)]", caption)
    result: list[str] = []
    for label in labels:
        if label not in result:
            result.append(label)
    return result


def _label_for_index(labels: list[str], index: int) -> str | None:
    return labels[index - 1] if index <= len(labels) else None


def _assign_same_id_caption_subfigure_indices(figures: list[FigureInfo]) -> None:
    """Index distinct images that share the same figure ID and caption."""
    grouped: dict[tuple[str, str], list[FigureInfo]] = {}
    for figure in figures:
        if not figure.caption or figure.figure_id.startswith("Unknown Figure"):
            continue
        key = (figure.figure_id, _compact_spaces(figure.caption))
        grouped.setdefault(key, []).append(figure)

    for group in grouped.values():
        unique_hashes = {figure.image_hash for figure in group if figure.image_hash}
        if len(group) <= 1 or len(unique_hashes) <= 1:
            continue
        for index, figure in enumerate(sorted(group, key=lambda item: item.position), start=1):
            figure.subfigure_index = index


def _extract_base64_data(data_uri: str) -> str:
    match = DATA_IMAGE_PATTERN.match(data_uri)
    return match.group("data") if match else data_uri


def _resolve_local_image_path(raw_path: str, markdown_dir: Path, project_root: Path, paper_id: str) -> Path | None:
    decoded = unquote(raw_path)
    path = Path(decoded)
    parsed = urlparse(decoded)
    figures_all_dir = project_root / "data" / "outputs" / paper_id / "figures_all"
    legacy_figures_dir = project_root / "data" / "outputs" / paper_id / "figures"
    if parsed.scheme and len(parsed.scheme) == 1 and decoded[1:3] in {":/", ":\\"}:
        candidate = Path(decoded)
        return candidate if candidate.exists() else _find_by_name(figures_all_dir, path.name) or _find_by_name(legacy_figures_dir, path.name)
    if path.is_absolute():
        return path if path.exists() else _find_by_name(figures_all_dir, path.name) or _find_by_name(legacy_figures_dir, path.name)
    candidate = markdown_dir / path
    if candidate.exists():
        return candidate
    return _find_by_name(markdown_dir, path.name) or _find_by_name(figures_all_dir, path.name) or _find_by_name(legacy_figures_dir, path.name)


def _copy_image_to_figures(source: Path, figures_dir: Path) -> Path:
    source = source.resolve()
    figures_dir = figures_dir.resolve()
    if source.parent == figures_dir:
        return source
    source_hash = compute_image_hash(image_path=source)
    if source_hash:
        for existing in figures_dir.glob(f"*{source.suffix}"):
            if compute_image_hash(image_path=existing) == source_hash:
                return existing.resolve()
    target = figures_dir / source.name
    if target.exists():
        target = figures_dir / f"{source.stem}_{source_hash[:8] if source_hash else 'copy'}{source.suffix}"
    shutil.copy2(source, target)
    return target.resolve()


def _find_by_name(root: Path, filename: str) -> Path | None:
    if not filename or not root.exists():
        return None
    exact = list(root.rglob(filename))
    if exact:
        return exact[0]
    wanted = Path(filename)
    if len(wanted.stem) < 16:
        return None
    for candidate in root.rglob(f"*{wanted.suffix}"):
        if wanted.stem.startswith(candidate.stem) or candidate.stem.startswith(wanted.stem) or candidate.stem[:32] == wanted.stem[:32]:
            return candidate
    return None


def _strip_markdown_noise(text: str) -> str:
    text = IMAGE_PATTERN.sub(lambda match: " " * (match.end() - match.start()), text)
    text = re.sub(r"`[^`]*`", lambda match: " " * (match.end() - match.start()), text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", lambda match: " " * (match.end() - match.start()), text)
    return text


def _iter_complete_sentences(text: str) -> list[tuple[str, int, int]]:
    sentences: list[tuple[str, int, int]] = []
    start = 0
    for match in re.finditer(r"[。；;？！!?.]", text):
        if _is_non_sentence_period(text, match.start()):
            continue
        end = match.end()
        sentence = _compact_spaces(text[start:end])
        if len(sentence) >= 8:
            sentences.append((sentence, start, end))
        start = end
    return sentences


def _is_non_sentence_period(text: str, period_index: int) -> bool:
    if text[period_index] != ".":
        return False
    prev_char = text[period_index - 1] if period_index > 0 else ""
    next_char = text[period_index + 1] if period_index + 1 < len(text) else ""
    if prev_char.isdigit() and next_char.isdigit():
        return True
    prefix = text[max(0, period_index - 8) : period_index + 1].lower()
    return prefix.endswith(("fig.", "eq.", "ref.", "al."))


def _looks_like_caption_continuation(previous_line: str, line: str) -> bool:
    if BODY_REFERENCE_PATTERN.search(line) or TABLE_START_PATTERN.match(line):
        return False
    if len(previous_line) >= 100 or len(line) > 160:
        return False
    if re.match(r"^\s*(?:Fig\.?|Figure)\s*", previous_line, re.IGNORECASE) and re.search(r"[\u4e00-\u9fff]", line):
        return False
    return not previous_line.strip().endswith(tuple(SENTENCE_END_CHARS))


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _dedupe_texts(texts: list[str]) -> list[str]:
    seen = set()
    result = []
    for text in texts:
        compact = _compact_spaces(text)
        if compact and compact not in seen:
            seen.add(compact)
            result.append(compact)
    return result


def validate_base64_image(base64_data: str) -> bool:
    """Return True when base64 data looks like an image."""
    try:
        decoded = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError):
        return False
    return decoded.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8")) or len(decoded) > 50


def guess_image_extension_from_base64(base64_data: str) -> str:
    """Guess an image extension from decoded base64 bytes."""
    try:
        decoded = base64.b64decode(base64_data)
    except (binascii.Error, ValueError):
        return ".png"
    mime = None
    if decoded.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif decoded.startswith(b"GIF8"):
        mime = "image/gif"
    return mimetypes.guess_extension(mime or "image/png") or ".png"

