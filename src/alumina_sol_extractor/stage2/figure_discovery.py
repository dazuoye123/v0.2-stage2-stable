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
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from alumina_sol_extractor.figures.figure_id import (
    ANY_FIGURE_ID_PATTERN,
    CAPTION_START_PATTERN,
    FIGURE_ID_PATTERN,
    figure_number_from_id as _shared_figure_number_from_id,
    find_figure_id_pair as _shared_find_figure_id_pair,
)
from alumina_sol_extractor.models.figure import FigureInfo


IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^\n]*)\)")
DATA_IMAGE_PATTERN = re.compile(r"^data:image/[^;]+;base64,(?P<data>.+)$", re.DOTALL)
TABLE_START_PATTERN = re.compile(r"^\s*(?:\u8868\s*\d+(?:\.\d+)*|Table\s*\d+(?:\.\d+)*|\[TableID:)", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$", re.MULTILINE)
DETAILS_BLOCK_PATTERN = re.compile(r"<details\b.*?</details>", re.IGNORECASE | re.DOTALL)
REFERENCE_SECTION_PATTERN = re.compile(
    r"^\s*(?:references|bibliography|\u53c2\u8003\u6587\u732e|\u81f4\u8c22|\u5b66\u4f4d\u8bba\u6587\u8bc4\u9605\u53ca\u7b54\u8fa9\u60c5\u51b5\u8868)\b",
    re.IGNORECASE,
)
SENTENCE_END_CHARS = "\u3002\uff1b;\uff1f\uff01!?."
BODY_REFERENCE_PATTERN = re.compile(
    r"(?:"
    r"\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u4e3a|"
    r"\u5c06\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u7531\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u5982\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u7531\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*(?:\u53ef\u77e5|\u53ef\u89c1)|"
    r"\u5982\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u6240\u793a|"
    r"\u6839\u636e\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"\u4ece\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*\u53ef\u4ee5\u770b\u51fa|"
    r"\u56fe\s*\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s*(?:\u8868\u660e|\u663e\u793a)|"
    r"\u6570\u636e\u89c1\u8868\s*\d+(?:\.\d+)*|"
    r"\u89c1\u8868\s*\d+(?:\.\d+)*|"
    r"as shown in\s+(?:Fig\.?|Figure)\s*S?\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"shown in\s+(?:Fig\.?|Figure)\s*S?\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?|"
    r"(?:Fig\.?|Figure)\s*S?\d+(?:[.\-]\d+)*(?:\s*[\uff08(][A-Za-z0-9]+[\uff09)])?\s+(?:shows|indicates)"
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
    figures_all_dir: Path | None = None,
) -> str:
    """Copy local MinerU images into ``figures_all_dir`` or the legacy default output path."""
    markdown_dir = Path(markdown_dir)
    project_root = Path(project_root).resolve()
    figures_dir = Path(figures_all_dir).resolve() if figures_all_dir is not None else (
        project_root / "data" / "outputs" / paper_id / "figures_all"
    )
    figures_dir.mkdir(parents=True, exist_ok=True)

    def replace(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        raw_path = match.group(2).strip().strip('"').strip("'")
        parsed = urlparse(raw_path)
        if parsed.scheme in {"http", "https", "data"}:
            return match.group(0)

        source = _resolve_local_image_path(
            raw_path,
            markdown_dir,
            project_root,
            paper_id,
            figures_all_dir=figures_dir,
        )
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
    mineru_layout: dict[str, dict] | None = None,
    figures_all_dir: Path | None = None,
) -> list[FigureInfo]:
    """Find figures in Markdown and return image-hash de-duplicated records."""
    markdown_path = Path(markdown_path)
    markdown_dir = markdown_path.parent
    project_root = Path(project_root).resolve()
    figures_all_dir = (
        Path(figures_all_dir).resolve()
        if figures_all_dir is not None
        else project_root / "data" / "outputs" / paper_id / "figures_all"
    )
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
        caption_assignments = _build_caption_assignments_for_group(caption_result, len(group))
        fallback_labels = _extract_group_labels(markdown_text, group) if len(group) > 1 else []

        for index_in_group, match in enumerate(group, start=1):
            caption_assignment = caption_assignments[index_in_group - 1]
            caption = caption_assignment.caption
            group_id_raw = caption_assignment.figure_id_raw
            group_figure_id = caption_assignment.figure_id
            subfigure_labels = caption_assignment.subfigure_labels or fallback_labels
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
            layout_record = _match_mineru_layout(
                raw_path=raw_path,
                image_path=image_path,
                mineru_layout=mineru_layout,
            )

            current_caption = caption
            caption_source = caption_assignment.source
            reference_sentences = list(caption_assignment.trailing_reference_sentences)
            if not current_caption:
                pseudo_caption = build_pseudo_caption(figure_id, local_window)
                if pseudo_caption:
                    current_caption = pseudo_caption
                    caption_source = "pseudo_caption"
                else:
                    caption_source = "none"

            section_title = find_section_title_for_position(headings, position)

            subfigure_label = caption_assignment.subfigure_label
            if not subfigure_label and subfigure_labels:
                local_index = caption_assignment.subfigure_index or index_in_group
                subfigure_label = _label_for_index(subfigure_labels, local_index)
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
                    subfigure_index=caption_assignment.subfigure_index,
                    subfigure_label=subfigure_label,
                    alt_text=alt_text,
                    image_path=image_path,
                    image_url=image_url,
                    base64_data=base64_data,
                    image_hash=image_hash,
                    mineru_img_path=layout_record.get("mineru_img_path") if layout_record else None,
                    page_idx=layout_record.get("page_idx") if layout_record else None,
                    page_number=layout_record.get("page_number") if layout_record else None,
                    bbox=layout_record.get("bbox") if layout_record else None,
                    bbox_format=layout_record.get("bbox_format") if layout_record else None,
                    bbox_source=layout_record.get("source") if layout_record else None,
                    position=position,
                    section_title=section_title,
                    context_before=context_before,
                    context_after=context_after,
                    raw_caption=caption_assignment.raw_caption,
                    caption=current_caption,
                    caption_source=caption_source,
                    caption_cleaned=caption_assignment.caption_cleaned,
                    caption_truncation_reason=caption_assignment.truncation_reason,
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
@dataclass
class CaptionAssignment:
    caption: str | None
    source: str
    figure_id_raw: str | None
    figure_id: str | None
    subfigure_labels: list[str] = field(default_factory=list)
    subfigure_index: int | None = None
    subfigure_label: str | None = None
    trailing_reference_sentences: list[str] = field(default_factory=list)
    raw_caption: str | None = None
    caption_cleaned: bool = False
    truncation_reason: str | None = None


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
    in_details_block = False

    for raw_line in lines:
        line = raw_line.strip()
        if in_details_block:
            if re.match(r"^</details\b", line, flags=re.IGNORECASE):
                in_details_block = False
            continue
        if re.match(r"^<details\b", line, flags=re.IGNORECASE):
            in_details_block = True
            continue
        if re.match(r"^</?summary\b", line, flags=re.IGNORECASE):
            continue
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

    boundary = _find_different_figure_boundary(text, figure_id)
    reason = "multiple_figure_ids_in_caption" if boundary is not None else None
    if boundary is None:
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


def _build_caption_assignments_for_group(
    caption_record: CaptionRecord,
    group_size: int,
) -> list[CaptionAssignment]:
    if group_size <= 0:
        return []

    segments = _split_caption_record_into_segments(caption_record)
    if not segments:
        return [CaptionAssignment(caption=None, source="none", figure_id_raw=None, figure_id=None) for _ in range(group_size)]

    if len(segments) == 1:
        segment = segments[0]
        return _expand_segment_assignments(
            segment,
            image_count=group_size,
            preserve_labels=len(segment.subfigure_labels) == group_size,
        )

    assignments: list[CaptionAssignment] = []
    remaining = group_size
    uncertain = False

    for segment in segments:
        if remaining <= 0:
            uncertain = True
            break
        requested = max(1, len(segment.subfigure_labels) or 1)
        assigned_count = min(requested, remaining)
        if assigned_count != requested:
            uncertain = True
        preserve_labels = len(segment.subfigure_labels) == assigned_count
        assignments.extend(
            _expand_segment_assignments(
                segment,
                image_count=assigned_count,
                preserve_labels=preserve_labels,
            )
        )
        remaining -= assigned_count

    if remaining > 0:
        uncertain = True
        fallback = segments[-1]
        assignments.extend(
            _expand_segment_assignments(
                fallback,
                image_count=remaining,
                preserve_labels=False,
            )
        )

    assignments = assignments[:group_size]
    if uncertain:
        for assignment in assignments:
            assignment.caption_cleaned = True
            assignment.truncation_reason = "multiple_figure_ids_caption_assignment_uncertain"
    return assignments


def _split_caption_record_into_segments(caption_record: CaptionRecord) -> list[CaptionAssignment]:
    raw_text = _compact_spaces(caption_record.raw_caption or caption_record.caption or "")
    if not raw_text:
        return []

    raw_segments = _split_multi_figure_caption_segments(raw_text)
    segments: list[CaptionAssignment] = []
    for raw_segment in raw_segments:
        figure_id_raw, figure_id = _find_figure_id_pair(raw_segment)
        caption, trailing_refs, truncation_reason = _split_caption_details(
            raw_segment,
            figure_id=figure_id or figure_id_raw,
        )
        clean_caption = caption or None
        reference_sentences = _clean_caption_reference_sentences(
            trailing_refs,
            current_figure_id=figure_id,
        )
        segments.append(
            CaptionAssignment(
                caption=clean_caption,
                source="standard_caption" if clean_caption else "none",
                figure_id_raw=figure_id_raw,
                figure_id=figure_id,
                subfigure_labels=_extract_subfigure_labels(clean_caption or raw_segment),
                trailing_reference_sentences=reference_sentences,
                raw_caption=raw_segment,
                caption_cleaned=truncation_reason is not None,
                truncation_reason=truncation_reason,
            )
        )
    return segments


def _split_multi_figure_caption_segments(raw_caption_text: str) -> list[str]:
    matches = list(ANY_FIGURE_ID_PATTERN.finditer(raw_caption_text))
    if len(matches) <= 1:
        return [_compact_spaces(raw_caption_text)]

    boundaries = [match.start() for match in matches[1:]]
    segments: list[str] = []
    start = 0
    for boundary in boundaries:
        segment = _compact_spaces(raw_caption_text[start:boundary])
        if segment:
            segments.append(segment)
        start = boundary
    tail = _compact_spaces(raw_caption_text[start:])
    if tail:
        segments.append(tail)
    return segments or [_compact_spaces(raw_caption_text)]


def _expand_segment_assignments(
    segment: CaptionAssignment,
    image_count: int,
    preserve_labels: bool,
) -> list[CaptionAssignment]:
    assignments: list[CaptionAssignment] = []
    for index in range(1, image_count + 1):
        label = segment.subfigure_labels[index - 1] if preserve_labels and index <= len(segment.subfigure_labels) else None
        assignments.append(
            CaptionAssignment(
                caption=segment.caption,
                source=segment.source,
                figure_id_raw=segment.figure_id_raw,
                figure_id=segment.figure_id,
                subfigure_labels=list(segment.subfigure_labels),
                subfigure_index=index if image_count > 1 else None,
                subfigure_label=label,
                trailing_reference_sentences=list(segment.trailing_reference_sentences),
                raw_caption=segment.raw_caption,
                caption_cleaned=segment.caption_cleaned,
                truncation_reason=segment.truncation_reason,
            )
        )
    return assignments


def _clean_caption_reference_sentences(
    sentences: list[str],
    current_figure_id: str | None,
) -> list[str]:
    cleaned: list[str] = []
    for sentence in sentences:
        compact = _compact_spaces(sentence)
        if not compact:
            continue
        sentence_id_raw, sentence_figure_id = _find_figure_id_pair(compact)
        starts_like_caption = bool(CAPTION_START_PATTERN.match(compact))
        if starts_like_caption and sentence_figure_id and sentence_figure_id != current_figure_id:
            continue
        if sentence_id_raw and sentence_figure_id != current_figure_id and not BODY_REFERENCE_PATTERN.search(compact):
            continue
        cleaned.append(compact)
    return _dedupe_texts(cleaned)[:3]


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
    for match in PSEUDO_REFERENCE_PATTERN.finditer(context):
        if match.group("number") != number:
            continue
        next_char = context[match.end()] if match.end() < len(context) else ""
        if next_char and re.match(r"[\d.\-]", next_char):
            continue
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


def _find_different_figure_boundary(text: str, figure_id: str | None) -> int | None:
    first_number = _figure_number_from_id(figure_id) or _figure_number_from_id(text)
    if not first_number:
        return None
    for match in ANY_FIGURE_ID_PATTERN.finditer(text):
        number = next((value for value in match.groupdict().values() if value), None)
        if not number:
            continue
        if match.start() == 0 or number == first_number:
            continue
        return match.start()
    shorthand = re.search(rf"[、,，]\s*(?!{re.escape(first_number)}\b)(\d+(?:[.\-]\d+)+)", text)
    if shorthand:
        return shorthand.start()
    return None


def _include_reference_prefix(text: str, figure_start: int) -> int:
    prefix = text[max(0, figure_start - 4) : figure_start]
    for marker in ["\u6839\u636e", "\u7531", "\u5982", "\u4ece"]:
        if prefix.endswith(marker):
            return figure_start - len(marker)
    return figure_start


def _find_explanatory_phrase_boundary(text: str) -> int | None:
    patterns = [
        r"\s+\u53ef\u7eba\u4e1d\u6eb6\u80f6\u7684\u70ed\u5931\u91cd",
        r"\s+TG\u66f2\u7ebf\u8868\u660e",
        r"\s+TG/DSC\u66f2\u7ebf\u8868\u660e",
        r"\s+\u66f2\u7ebf\u8868\u660e",
        r"\s+\u6d4b\u8bd5\u7ed3\u679c\u8868\u660e",
        r"\s+\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
        r"\s+\u4ece\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
        r"\s+\u6d4b\u8bd5\u53d1\u73b0",
        r"\s+\u968f\u540e",
        r"\s+\u7ecf\u8fc7\u7cbe\u786e\u63a7\u5236",
        r"\s+\u7ed3\u679c\u8868\u660e",
        r"\s+\u5c06\u4e0a\u8ff0",
        r"\s+\u5bf9\u6240\u5236",
        r"\s+\u6b64\u65f6",
        r"\s+\u7ecf\u8fc7",
        r"\s+\u4ece\u52a8\u6469\u64e6\u7cfb\u6570",
        r"\s+[^,，。；;]{0,20}\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
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
        "\u53ef\u7eba\u4e1d\u6eb6\u80f6\u7684\u70ed\u5931\u91cd",
        "TG\u66f2\u7ebf\u8868\u660e",
        "TG/DSC\u66f2\u7ebf\u8868\u660e",
        "\u66f2\u7ebf\u8868\u660e",
        "\u6d4b\u8bd5\u7ed3\u679c\u8868\u660e",
        "\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
        "\u4ece\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
        "\u4ece\u52a8\u6469\u64e6\u7cfb\u6570\u6d4b\u8bd5\u7ed3\u679c\u6765\u770b",
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
    return _shared_figure_number_from_id(figure_id)


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
    source = _resolve_local_image_path(
        raw_path,
        markdown_dir,
        project_root,
        paper_id,
        figures_all_dir=figures_all_dir,
    )
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
    gap = _compact_spaces(DETAILS_BLOCK_PATTERN.sub(" ", text))
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
    raw, figure_id = _shared_find_figure_id_pair(text)
    return _compact_spaces(raw) if raw else None, figure_id


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


def _match_mineru_layout(
    raw_path: str,
    image_path: str | None,
    mineru_layout: dict[str, dict] | None,
) -> dict | None:
    if not mineru_layout:
        return None
    candidates = []
    for value in [raw_path, image_path]:
        if not value:
            continue
        normalized = value.replace("\\", "/").strip().strip('"').strip("'").lstrip("./")
        candidates.append(normalized)
        candidates.append(Path(normalized).name)
        if "/images/" in normalized:
            candidates.append("images/" + normalized.rsplit("/images/", 1)[1])
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if candidate in mineru_layout:
            return mineru_layout[candidate]
    return None


def _extract_base64_data(data_uri: str) -> str:
    match = DATA_IMAGE_PATTERN.match(data_uri)
    return match.group("data") if match else data_uri


def _resolve_local_image_path(
    raw_path: str,
    markdown_dir: Path,
    project_root: Path,
    paper_id: str,
    figures_all_dir: Path | None = None,
) -> Path | None:
    decoded = unquote(raw_path)
    path = Path(decoded)
    parsed = urlparse(decoded)
    explicit_figures_all_dir = figures_all_dir is not None
    figures_all_dir = (
        Path(figures_all_dir).resolve()
        if explicit_figures_all_dir
        else project_root / "data" / "outputs" / paper_id / "figures_all"
    )
    legacy_figures_dir = (
        None
        if explicit_figures_all_dir
        else project_root / "data" / "outputs" / paper_id / "figures"
    )

    def _legacy_match(filename: str) -> Path | None:
        if legacy_figures_dir is None:
            return None
        return _find_by_name(legacy_figures_dir, filename)

    if parsed.scheme and len(parsed.scheme) == 1 and decoded[1:3] in {":/", ":\\"}:
        candidate = Path(decoded)
        return (
            candidate
            if candidate.exists()
            else _find_by_name(figures_all_dir, path.name) or _legacy_match(path.name)
        )
    if path.is_absolute():
        return (
            path
            if path.exists()
            else _find_by_name(figures_all_dir, path.name) or _legacy_match(path.name)
        )
    candidate = markdown_dir / path
    if candidate.exists():
        return candidate
    return (
        _find_by_name(markdown_dir, path.name)
        or _find_by_name(figures_all_dir, path.name)
        or _legacy_match(path.name)
    )


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

