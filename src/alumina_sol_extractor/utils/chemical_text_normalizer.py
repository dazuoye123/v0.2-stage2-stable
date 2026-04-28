"""Cleanup helpers for chemistry text produced by MinerU.

MinerU may preserve chemical formulae and units as LaTeX-like fragments. The
rules here are intentionally small and readable, focused on alumina-sol papers.
Markdown image paths are protected before cleanup so file names are not changed.
"""

from __future__ import annotations

import re


GREEK_COMMANDS = {
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\theta": "θ",
    r"\eta": "η",
}

UNICODE_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^\n]*\)")


def normalize_mineru_markdown_chemistry(
    markdown: str,
    unicode_subscript: bool = False,
) -> str:
    """Normalize common MinerU chemistry artifacts in Markdown text."""
    text, protected_images = _protect_markdown_images(markdown)
    text = _normalize_latex_units(text)

    for command, value in GREEK_COMMANDS.items():
        text = text.replace(command, value)

    text = _unwrap_latex_text_commands(text)
    text = re.sub(r"_\s*\{\s*([^{}]+?)\s*\}", r"\1", text)
    text = re.sub(r"_\s*([A-Za-z0-9])", r"\1", text)
    text = text.replace("$", "")
    text = text.replace(r"\-", "-")
    text = re.sub(r"\\\s*", "", text)
    text = text.replace("{", "").replace("}", "")

    text = _normalize_plain_artifacts(text)
    text = _join_common_element_letters(text)
    text = _normalize_alumina_formulae(text)
    text = _normalize_punctuation_spacing(text)

    if unicode_subscript:
        text = _apply_unicode_subscripts(text)
    return _restore_markdown_images(text, protected_images)


def _protect_markdown_images(text: str) -> tuple[str, list[str]]:
    """Protect Markdown image paths from formula cleanup rules."""
    images: list[str] = []

    def replace(match: re.Match[str]) -> str:
        images.append(match.group(0))
        return f"@@IMGPH{len(images) - 1}@@"

    return MARKDOWN_IMAGE_PATTERN.sub(replace, text), images


def _restore_markdown_images(text: str, images: list[str]) -> str:
    for index, image in enumerate(images):
        text = text.replace(f"@@IMGPH{index}@@", image)
    return text


def _unwrap_latex_text_commands(text: str) -> str:
    """Remove wrappers such as \\mathrm{...}, \\text{...}, and \\mathbf{...}."""
    pattern = re.compile(r"\\(?:mathrm|text|mathbf)\s*\{\s*([^{}]*?)\s*\}")
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(r"\1", text)
    return text


def _normalize_latex_units(text: str) -> str:
    """Normalize unit/math command artifacts before backslash cleanup."""
    replacements = [
        (r"\\?\^\s*\{?\s*\\?circ\s*\}?\s*C", "°C"),
        (r"\\?\^\s*\\?circC", "°C"),
        (r"\\?mathbf\s*\{\s*C\s*\}", "°C"),
        (r"\\?mu\s*m\b", "μm"),
        (r"\\?sim\b", "–"),
        (r"\\?cdot\b", "·"),
        (r"\\?rightarrow\b", "→"),
        (r"\\?leftarrow\b", "←"),
    ]
    for pattern, value in replacements:
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)
    return text


def _normalize_plain_artifacts(text: str) -> str:
    """Normalize artifacts that remain after LaTeX backslashes are stripped."""
    replacements = [
        (r"\bsim\b", "–"),
        (r"\bcdot\b", "·"),
        (r"\^\s*circ\s*C", "°C"),
        (r"\^\s*circC", "°C"),
        (r"\bmathbfC\b", "°C"),
        (r"\bmu\s*m\b", "μm"),
        (r"\brightarrow\b", "→"),
        (r"\bleftarrow\b", "←"),
        (r"~\s*(nm|mL)\b", r"\1"),
    ]
    for pattern, value in replacements:
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)
    return text


def _join_common_element_letters(text: str) -> str:
    """Join spaced element symbols often emitted from OCR or formula parsing."""
    replacements = {
        r"\bA\s+l\b": "Al",
        r"\bS\s+i\b": "Si",
        r"\bT\s+i\b": "Ti",
        r"\bZ\s+r\b": "Zr",
        r"\bF\s+e\b": "Fe",
        r"\bM\s+g\b": "Mg",
        r"\bC\s+a\b": "Ca",
        r"\bN\s+a\b": "Na",
        r"\bC\s+l\b": "Cl",
        r"\bO\s+H\b": "OH",
    }
    for pattern, value in replacements.items():
        text = re.sub(pattern, value, text)
    return text


def _normalize_alumina_formulae(text: str) -> str:
    """Fix common Al2O3 OCR variants."""
    text = re.sub(r"\bAl\s*2\s*[0O]\s*3\b", "Al2O3", text)
    text = re.sub(r"\bAl203\b", "Al2O3", text)
    text = re.sub(r"([αβγδθη])\s*-\s*Al2O3", r"\1-Al2O3", text)
    text = re.sub(r"([αβγδθη])\s*-\s*Al203", r"\1-Al2O3", text)
    text = re.sub(r"([αβγδθη])-Al\s*2\s*[0O]\s*3", r"\1-Al2O3", text)
    return text


def _normalize_punctuation_spacing(text: str) -> str:
    """Tighten formula punctuation without changing normal Chinese text."""
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s+-\s+", "-", text)
    text = re.sub(r"([αβγδθη])-?\s+Al2O3", r"\1-Al2O3", text)
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()


def _apply_unicode_subscripts(text: str) -> str:
    """Optionally render digits in common oxide formulae as Unicode subscripts."""

    def repl(match: re.Match[str]) -> str:
        return match.group(0).translate(UNICODE_SUBSCRIPTS)

    return re.sub(r"(?<=[A-Za-z])[0-9]+|(?<=[0-9A-Za-z])O[0-9]+", repl, text)
