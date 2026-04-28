"""Exact figure-reference matching for Markdown papers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from alumina_sol_extractor.models.figure import FigureInfo


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^\n]*)\)")
CAPTION_RE = re.compile(
    r"^\s*(?:\u56fe\s*\d+(?:[.\-]\d+)*|Fig\.?\s*S?\d+(?:[.\-]\d+)*|Figure\s*S?\d+(?:[.\-]\d+)*)\b",
    re.IGNORECASE,
)
SENTENCE_END_RE = re.compile(r"[\u3002\uff1b;\uff1f\uff01!?.]")
FIGURE_ID_FINDER_RE = re.compile(
    r"(?:\u56fe\s*(S?\d+(?:[.\-]\d+)*)|Fig\.?\s*(S?\d+(?:[.\-]\d+)*)|Figure\s*(S?\d+(?:[.\-]\d+)*))",
    re.IGNORECASE,
)
TABLE_OR_PATH_JUNK_RE = re.compile(
    r"TableID|\bCSV:|\bJSON:|[A-Za-z]:[\\/]|(?:/|\\)[\w.\-\\/]+",
    re.IGNORECASE,
)
CUE_WORDS = [
    "\u5982\u56fe",
    "\u7531\u56fe",
    "\u89c1\u56fe",
    "\u6839\u636e\u56fe",
    "\u4ece\u56fe",
    "\u53ef\u77e5",
    "\u53ef\u89c1",
    "\u8868\u660e",
    "\u663e\u793a",
    "as shown",
    "shown in",
    "shows",
    "indicates",
]


@dataclass
class SentenceCandidate:
    sentence: str
    start: int
    end: int


class FigureContextMatcher:
    """Find compact, complete reference sentences for each figure."""

    def __init__(self, markdown_text: str) -> None:
        self.markdown_text = markdown_text
        self.clean_text = self._remove_images_headings_and_captions(markdown_text)
        self.sentences = self._split_sentences(self.clean_text)

    def apply(self, figures: list[FigureInfo]) -> list[FigureInfo]:
        for figure in figures:
            refs = self.find_reference_sentences(figure)
            merged = _dedupe((figure.reference_sentences or []) + refs)
            if merged:
                figure.reference_sentences = merged[:3]
            if figure.caption or figure.reference_sentences:
                figure.description_text = self.build_description_text(figure)
        return figures

    def find_reference_sentences(self, figure: FigureInfo, limit: int = 3) -> list[str]:
        patterns = build_mention_patterns(figure.figure_id)
        if not patterns:
            return []
        caption_tokens = _tokens(figure.caption or "")
        scored: list[tuple[float, str]] = []
        for candidate in self.sentences:
            if not any(pattern.search(candidate.sentence) for pattern in patterns):
                continue
            cleaned_sentence = _clean_reference_sentence(candidate.sentence, figure.figure_id)
            if not cleaned_sentence:
                continue
            score = simple_score(cleaned_sentence, figure.position, candidate.start, caption_tokens)
            if _contains_other_figure_ids(cleaned_sentence, figure.figure_id):
                score -= 2.5
            scored.append((score, cleaned_sentence))
        scored.sort(key=lambda item: item[0], reverse=True)
        return _dedupe([sentence for _, sentence in scored])[:limit]

    def build_description_text(self, figure: FigureInfo, max_chars: int = 1000) -> str | None:
        parts: list[str] = []
        if figure.caption:
            prefix = f"{figure.figure_id}({figure.subfigure_label})" if figure.subfigure_label else figure.figure_id
            parts.append(f"{prefix}: {figure.caption}")
        parts.extend(figure.reference_sentences)
        merged = " ".join(_dedupe([_compact(part) for part in parts if _compact(part)]))
        return merged[:max_chars].rstrip() or None

    def _remove_images_headings_and_captions(self, text: str) -> str:
        text = IMAGE_RE.sub(lambda match: " " * (match.end() - match.start()), text)
        text = re.sub(
            r"^\s{0,3}#{1,6}\s+.*$",
            lambda match: " " * (match.end() - match.start()),
            text,
            flags=re.MULTILINE,
        )
        pieces: list[str] = []
        for line in text.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            newline = line[len(body) :]
            stripped = body.strip()
            if CAPTION_RE.match(stripped) and not _looks_like_reference_line(stripped):
                pieces.append(" " * len(body) + newline)
            else:
                pieces.append(line)
        return "".join(pieces)

    def _split_sentences(self, text: str) -> list[SentenceCandidate]:
        candidates: list[SentenceCandidate] = []
        start = 0
        for match in SENTENCE_END_RE.finditer(text):
            if _is_non_sentence_period(text, match.start()):
                continue
            end = match.end()
            sentence = _compact(text[start:end])
            if len(sentence) >= 8:
                candidates.append(SentenceCandidate(sentence=sentence, start=start, end=end))
            start = end
        tail = _compact(text[start:])
        if len(tail) >= 8:
            candidates.append(SentenceCandidate(sentence=tail, start=start, end=len(text)))
        return candidates


def match_figure_contexts(markdown_text: str, figures: list[FigureInfo]) -> list[FigureInfo]:
    """Convenience function for in-place figure context matching."""
    return FigureContextMatcher(markdown_text).apply(figures)


def build_mention_patterns(figure_id: str) -> list[re.Pattern[str]]:
    """Build exact mention regexes for 图3-17/Fig. S1/Figure 2.3."""
    if not figure_id or figure_id.startswith("Unknown Figure"):
        return []
    number_match = re.search(r"S?\d+(?:[.\-]\d+)*", figure_id, flags=re.IGNORECASE)
    if not number_match:
        return []
    number = re.escape(number_match.group(0))
    exact_end = r"(?![\d.\-])"
    suffix = r"(?:\s*[\uff08(][A-Za-z][\uff09)])?"
    return [
        re.compile(rf"\u56fe\s*{number}{exact_end}{suffix}", re.IGNORECASE),
        re.compile(rf"Fig\.?\s*{number}{exact_end}{suffix}", re.IGNORECASE),
        re.compile(rf"Figure\s*{number}{exact_end}{suffix}", re.IGNORECASE),
    ]


def simple_score(sentence: str, figure_position: int, sentence_position: int, caption_tokens: set[str]) -> float:
    sentence_lower = sentence.lower()
    score = 5.0
    if any(cue in sentence_lower for cue in CUE_WORDS):
        score += 1.5
    score += min(len(caption_tokens & _tokens(sentence)) * 0.25, 1.5)
    distance = abs(sentence_position - figure_position)
    if distance < 2000:
        score += 1.0
    elif distance < 6000:
        score += 0.5
    return score


def _looks_like_reference_line(text: str) -> bool:
    lowered = text.lower()
    if any(cue in lowered for cue in CUE_WORDS):
        return True
    return bool(re.search(r"\u6240\u793a|\u8868\u660e|\u663e\u793a|\u53ef\u77e5|\u53ef\u89c1|\u89c1\u56fe", text))


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|\d+(?:[.\-]\d+)*|[\u4e00-\u9fff]{2,}", text)
    }


def _is_non_sentence_period(text: str, period_index: int) -> bool:
    if text[period_index] != ".":
        return False
    prev_char = text[period_index - 1] if period_index > 0 else ""
    next_char = text[period_index + 1] if period_index + 1 < len(text) else ""
    if prev_char.isdigit() and next_char.isdigit():
        return True
    prefix = text[max(0, period_index - 8) : period_index + 1].lower()
    return prefix.endswith(("fig.", "eq.", "ref.", "al."))


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _dedupe(texts: list[str]) -> list[str]:
    seen = set()
    result = []
    for text in texts:
        compact = _compact(text)
        if compact and compact not in seen:
            seen.add(compact)
            result.append(compact)
    return result


def _clean_reference_sentence(sentence: str, target_figure_id: str) -> str | None:
    compact = _compact(sentence)
    if not compact:
        return None
    compact = re.sub(r"^(?:json|csv)\)\s*", "", compact, flags=re.IGNORECASE)
    compact = _compact(compact)
    compact = re.sub(r"^(?:[A-Za-z]:[\\/]|/|\\)[^\s]+\s*", "", compact)
    compact = _compact(compact)
    if TABLE_OR_PATH_JUNK_RE.search(compact):
        return None
    compact = re.sub(r"\s*\[[^\]]*TableID:[^\]]*\]\s*", " ", compact, flags=re.IGNORECASE)
    compact = re.sub(r"\b(?:json|csv)\)\b", " ", compact, flags=re.IGNORECASE)
    compact = _compact(compact)
    if len(compact) < 8:
        return None
    if not any(pattern.search(compact) for pattern in build_mention_patterns(target_figure_id)):
        return None
    return compact


def _normalized_figure_numbers(text: str) -> set[str]:
    numbers: set[str] = set()
    for match in FIGURE_ID_FINDER_RE.finditer(text):
        number = next((group for group in match.groups() if group), None)
        if number:
            numbers.add(number.lower())
    return numbers


def _contains_other_figure_ids(sentence: str, target_figure_id: str) -> bool:
    target_numbers = _normalized_figure_numbers(target_figure_id)
    if not target_numbers:
        return False
    sentence_numbers = _normalized_figure_numbers(sentence)
    return any(number not in target_numbers for number in sentence_numbers)
