"""Final scientific figure classification and vision selection rules.

Caption/reference/description text is the primary evidence. ResNet and CLIP
are kept as auxiliary signals only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import yaml
from PIL import Image

from alumina_sol_extractor.models.figure import FigureInfo


FIGURE_CLASSES = [
    "nmr_spectrum",
    "nmr_quantification_plot",
    "elemental_mapping",
    "mass_spectrum",
    "xrd_pattern",
    "ftir_spectrum",
    "raman_spectrum",
    "thermal_analysis_plot",
    "ferron_curve",
    "calibration_curve",
    "rheology_curve",
    "temperature_curve",
    "particle_size_plot",
    "zeta_potential_plot",
    "microscopy_image",
    "photo_image",
    "mechanical_curve",
    "mechanical_property_plot",
    "process_parameter_plot",
    "generic_chart_or_plot",
    "schematic_or_flow",
    "table_image",
    "logo_or_icon",
    "formula_or_text",
    "pure_text_image",
    "qr_code_or_barcode",
    "cover_decoration",
    "other",
]
SIMPLIFIED_CLASSES = FIGURE_CLASSES

VISION_ALLOWED_CLASSES = {
    "nmr_spectrum",
    "nmr_quantification_plot",
    "elemental_mapping",
    "mass_spectrum",
    "xrd_pattern",
    "ftir_spectrum",
    "raman_spectrum",
    "thermal_analysis_plot",
    "ferron_curve",
    "calibration_curve",
    "rheology_curve",
    "temperature_curve",
    "particle_size_plot",
    "zeta_potential_plot",
    "microscopy_image",
    "photo_image",
    "mechanical_curve",
    "mechanical_property_plot",
    "process_parameter_plot",
    "generic_chart_or_plot",
}

KEYWORDS: dict[str, list[str]] = {
    "nmr_quantification_plot": ["\u79ef\u5206", "\u6838\u78c1\u79ef\u5206", "\u79ef\u5206\u6bd4\u4f8b", "nmr integration", "integral ratio", "integration", "integral"],
    "nmr_spectrum": ["\u6838\u78c1", "nmr", "^27al", "²⁷al", "27al", "ppm", "\u94dd\u6838\u78c1", "nuclear magnetic resonance"],
    "mass_spectrum": ["\u8d28\u8c31", "\u98de\u884c\u65f6\u95f4\u8d28\u8c31", "tof-ms", "tof ms", "mass spectrum", "m/z", "\u8d28\u8377\u6bd4"],
    "xrd_pattern": ["xrd", "diffraction", "\u884d\u5c04", "\u6676\u578b", "\u7269\u76f8"],
    "ftir_spectrum": ["ftir", "ft-ir", " ir ", "ir谱", "ir 谱", "\u7ea2\u5916", "infrared", "cm-1", "cm−1", "\u5438\u6536\u5cf0", "transmittance"],
    "raman_spectrum": ["raman", "\u62c9\u66fc"],
    "thermal_analysis_plot": ["tg", "tga", "dsc", "tg-dsc", "\u70ed\u91cd", "\u5dee\u70ed", "\u5931\u91cd", "mass loss", "weight loss"],
    "ferron_curve": ["ferron", "al-ferron", "\u9010\u65f6\u7edc\u5408", "\u6bd4\u8272"],
    "calibration_curve": ["\u6807\u51c6\u66f2\u7ebf", "calibration curve"],
    "rheology_curve": ["\u6d41\u53d8", "\u9ecf\u5ea6", "\u7c98\u5ea6", "rheology", "shear", "viscosity", "\u526a\u5207"],
    "temperature_curve": ["\u6e29\u5ea6\u53d8\u5316", "temperature profile", "temperature curve"],
    "particle_size_plot": ["\u7c92\u5f84\u5206\u5e03", "particle size distribution", "size distribution", "dls"],
    "zeta_potential_plot": ["zeta", "zeta potential", "\u7535\u4f4d"],
    "microscopy_image": ["sem", "tem", "hrtem", "electron microscopy", "scanning electron microscopy", "transmission electron microscopy", "\u663e\u5fae", "\u5f62\u8c8c", "micrograph", "morphology", "scale bar"],
    "photo_image": ["photograph", "photo", "\u7167\u7247", "\u5b9e\u7269\u56fe", "\u53ef\u7eba\u6027", "\u7ea4\u7ef4\u7167\u7247", "\u72b6\u6001\u5bf9\u7167\u56fe", "\u900f\u660e", "\u5fae\u6697", "\u5fae\u767d", "\u80f6\u51dd", "\u5916\u89c2", "\u65cb\u84b8\u72b6\u6001", "\u6eb6\u80f6\u72b6\u6001"],
    "mechanical_curve": ["load-displacement", "stress-strain", "tensile", "strength", "modulus", "force", "displacement"],
    "process_parameter_plot": [
        "工艺参数",
        "参数影响",
        "环境参数",
        "纺丝环境参数",
        "纺丝参数",
        "工艺条件",
        "条件影响",
        "parameter effect",
        "process parameter",
    ],
    "generic_chart_or_plot": [
        "plot",
        "curve",
        "chart",
        "graph",
        "trend",
        "distribution",
        "comparison",
        "统计图",
        "坐标图",
        "曲线图",
        "参数图",
        "性能图",
    ],
    "schematic_or_flow": ["\u793a\u610f\u56fe", "\u539f\u7406\u56fe", "\u6d41\u7a0b\u56fe", "\u6784\u9020", "\u6b65\u9aa4", "mechanism", "schematic", "diagram", "workflow"],
    "table_image": ["table", "\u8868\u683c"],
    "logo_or_icon": ["logo", "\u6821\u5fbd", "publisher logo", "school logo", "icon"],
    "formula_or_text": ["formula", "equation", "text sentences", "\u516c\u5f0f", "\u7eaf\u6587\u672c"],
    "pure_text_image": ["text image", "pure text", "text only", "paragraph text", "sentence image"],
    "qr_code_or_barcode": ["qr code", "barcode", "bar code"],
    "cover_decoration": ["cover decoration", "cover image", "decorative image"],
}

EXTRA_KEYWORDS: dict[str, list[str]] = {
    "elemental_mapping": ["EDS", "EDS-mapping", "EDS mapping", "elemental mapping", "element mapping", "\u5143\u7d20\u5206\u5e03", "\u9762\u626b\u63cf", "mapping", "\u80fd\u8c31\u9762\u626b"],
    "mechanical_property_plot": ["\u5f3a\u5ea6", "\u6a21\u91cf", "\u62c9\u4f38\u5f3a\u5ea6", "\u65ad\u88c2\u5f3a\u5ea6", "\u5355\u4e1d\u5f3a\u5ea6", "\u79bb\u6563", "strength", "modulus", "tensile", "distribution", "scatter"],
    "schematic_or_flow": ["\u4f5c\u7528\u673a\u7406", "\u5f62\u6210\u8fc7\u7a0b", "\u8f6c\u53d8", "\u76f8\u95f4\u8f6c\u53d8", "\u7ed3\u6784\u793a\u610f", "\u793a\u610f", "\u539f\u7406", "\u8fc7\u7a0b", "\u8bd5\u6837\u886c", "\u5939\u5177", "\u88c5\u7f6e", "\u6d4b\u8bd5\u88c5\u7f6e", "\u6d4b\u8bd5\u5939\u5177", "process", "fixture"],
}
for _class_name, _keywords in EXTRA_KEYWORDS.items():
    KEYWORDS.setdefault(_class_name, [])
    for _keyword in _keywords:
        if _keyword not in KEYWORDS[_class_name]:
            KEYWORDS[_class_name].append(_keyword)


def _load_taxonomy_config() -> None:
    """Merge optional YAML taxonomy keywords into the lightweight rules."""
    config_path = Path(__file__).resolve().parents[3] / "configs" / "figure_taxonomy.yaml"
    if not config_path.exists():
        return
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    for class_name, rule in data.items():
        if not isinstance(rule, dict):
            continue
        keywords = rule.get("positive_keywords") or []
        KEYWORDS.setdefault(class_name, [])
        for keyword in keywords:
            if keyword not in KEYWORDS[class_name]:
                KEYWORDS[class_name].append(str(keyword))


_load_taxonomy_config()

FALSE_CANDIDATE_KEYWORDS = ["\u6838\u78c1", "nmr", "ppm", "\u7ea2\u5916", "ir", "ftir", "ferron", "\u6d41\u53d8", "rheology", "xrd", "sem", "tem", "eds", "mapping", "zeta", "\u7c92\u5f84", "\u5f3a\u5ea6", "\u6a21\u91cf", "\u8d28\u8c31", "tof-ms", "mass spectrum"]

MATERIAL_STATE_PHOTO_KEYWORDS = ["\u72b6\u6001\u5bf9\u7167\u56fe", "\u900f\u660e", "\u5fae\u6697", "\u5fae\u767d", "\u80f6\u51dd", "\u5916\u89c2", "\u65cb\u84b8\u72b6\u6001", "\u6eb6\u80f6\u72b6\u6001"]
SPINNABILITY_PHOTO_KEYWORDS = ["\u6210\u4e1d\u6027", "\u53ef\u7eba\u6027", "\u62c9\u4e1d", "\u7eba\u4e1d\u6027", "spinnability", "fiber drawing", "thread-forming"]
TEMPERATURE_CURVE_KEYWORDS = ["\u6e29\u5ea6\u53d8\u5316\u56fe", "\u6e29\u5ea6\u66f2\u7ebf", "temperature curve", "temperature profile", "temperature variation"]
CAPTION_FTIR_KEYWORDS = ["\u7ea2\u5916", "ir", "ftir", "infrared", "cm-1", "cm\u22121", "\u7ea2\u5916\u8c31\u56fe"]
CAPTION_XRD_KEYWORDS = ["xrd", "\u884d\u5c04", "diffraction"]
CAPTION_MICROSCOPY_KEYWORDS = ["tem", "sem", "hrtem", "\u663e\u5fae", "\u5f62\u8c8c", "\u653e\u5927\u500d\u7387", "magnification", "micrograph", "microscopy", "scale bar"]
CAPTION_THERMAL_KEYWORDS = ["tg", "tga", "dsc", "tg-dsc", "\u70ed\u91cd", "\u5dee\u70ed"]
CAPTION_RHEOLOGY_KEYWORDS = ["\u6d41\u53d8\u66f2\u7ebf", "\u6d41\u53d8\u6027", "\u6d41\u53d8\u6027\u7279\u5f81", "rheology curve", "viscosity curve", "shear curve"]
CAPTION_SCHEMATIC_KEYWORDS = ["\u539f\u7406\u56fe", "\u793a\u610f\u56fe", "\u7ed3\u6784\u56fe", "\u6784\u9020", "\u6b65\u9aa4", "\u6d41\u7a0b\u56fe"]
CAPTION_SPECTRUM_KEYWORDS = ["\u8c31\u56fe", "spectrum", "mass spectrum", "m/z", "\u8d28\u8c31\u56fe"]
CAPTION_SCIENTIFIC_KEYWORDS = [
    "xrd",
    "\u6838\u78c1",
    "nmr",
    "\u7ea2\u5916",
    "ir",
    "ftir",
    "tem",
    "sem",
    "hrtem",
    "\u8d28\u8c31\u56fe",
    "\u8c31\u56fe",
    "\u6e29\u5ea6\u53d8\u5316\u56fe",
    "\u6e29\u5ea6\u66f2\u7ebf",
    "temperature curve",
    "spectrum",
    "ferron",
    "\u6d41\u53d8",
    "\u6210\u4e1d\u6027",
    "\u53ef\u7eba\u6027",
    "\u62c9\u4e1d",
    "spinnability",
    "eds",
    "mapping",
]
STRUCTURE_SCHEMATIC_KEYWORDS = ["\u80f6\u4f53\u7ed3\u6784", "\u80f6\u56e2\u7ed3\u6784", "\u7ed3\u6784\u5f62\u6210\u673a\u7406", "\u53cc\u7535\u5c42\u7ed3\u6784", "al13", "al13^7+", "keggin", "\u56e2\u7c07\u7ed3\u6784", "\u7c7b\u578b\u53ca\u7ed3\u6784"]
NMR_SPECTRUM_KEYWORDS = ["\u6838\u78c1", "nmr", "^27al", "²⁷al", "27al", "ppm", "\u6838\u78c1\u8c31\u56fe"]
NMR_QUANTIFICATION_KEYWORDS = ["\u79ef\u5206", "\u79ef\u5206\u6bd4\u4f8b", "\u6838\u78c1\u79ef\u5206", "integral ratio", "integration", "integral"]
CAPTION_OCR_SUSPECT_PHRASES = [
    "\u5185\u786e\u5ea6\u4e0b\u540c\u79cd\u5904\u7406\u540e\u7684\u8be5\u9176\u7684\u6bd4\u503c",
    "\u8be5\u9176\u7684\u6bd4\u503c",
]
CAPTION_OCR_ANCHOR_KEYWORDS = [
    "\u5185\u786e\u5ea6",
    "\u8be5\u9176",
    "\u540c\u79cd\u5904\u7406",
]

RESNET_SCHEMATIC_CLASSES = {"Flow chart", "Block diagram", "Algorithm", "Tree Diagram", "Sketches"}
RESNET_TABLE_CLASSES = {"Tables"}
RESNET_CHART_CLASSES = {
    "Graph plots",
    "Scatter plot",
    "Bar plots",
    "Heat map",
    "Histogram",
    "Box plot",
    "Area chart",
    "Contour plot",
    "Surface plot",
    "Vector plot",
    "Line graph",
    "Confusion matrix",
}


class FigureFilter:
    """Assign final class and send-to-vision flag."""

    def __init__(
        self,
        include_material_state_photos: bool = True,
        include_schematics_for_vision: bool = False,
        include_spinnability_photos_for_vision: bool = True,
    ) -> None:
        self.include_material_state_photos = include_material_state_photos
        self.include_schematics_for_vision = include_schematics_for_vision
        self.include_spinnability_photos_for_vision = include_spinnability_photos_for_vision

    def apply(self, figures: list[FigureInfo]) -> list[FigureInfo]:
        for figure in figures:
            self.apply_one(figure)
        return figures

    def apply_one(self, figure: FigureInfo) -> FigureInfo:
        text = _classification_text(figure)
        figure.keyword_hits = _keyword_hits(text, _all_keywords())
        figure.figure_class = classify_figure(figure, text)
        self._set_archive_and_vision_fields(figure, text)
        figure.review_reason = review_reason_for_figure(figure, text)
        return figure

    def _set_archive_and_vision_fields(self, figure: FigureInfo, text: str) -> None:
        existing_exclude_reason = figure.exclude_reason
        figure.keep_for_archive = True
        figure.send_to_vision_model = False
        figure.maybe_useful = False
        figure.exclude_reason = None

        if figure.is_fragment:
            figure.send_to_vision_model = False
            figure.keep = False
            figure.exclude_reason = existing_exclude_reason or (
                "replaced_by_bbox_stitched_figure" if figure.fragment_group_id else "fragment_image"
            )
            figure.keep_reason = figure.exclude_reason
            return

        clip_negative = figure.clip_decision == "negative"
        clip_positive = figure.clip_decision == "positive"
        has_science_text = has_scientific_text(figure)
        if figure.figure_class in {
            "logo_or_icon",
            "formula_or_text",
            "pure_text_image",
            "qr_code_or_barcode",
            "cover_decoration",
            "table_image",
        }:
            figure.exclude_reason = figure.figure_class
        elif not figure.caption and figure.figure_id.startswith("Unknown Figure") and not clip_positive:
            figure.exclude_reason = "unknown_without_caption"
        elif figure.figure_class == "schematic_or_flow":
            figure.maybe_useful = True
            if self.include_schematics_for_vision:
                figure.send_to_vision_model = True
                figure.exclude_reason = None
            else:
                figure.exclude_reason = "maybe_useful_schematic"
        elif figure.figure_class == "photo_image" and _keyword_hits(text, MATERIAL_STATE_PHOTO_KEYWORDS):
            figure.maybe_useful = True
            if self.include_material_state_photos:
                figure.send_to_vision_model = True
                figure.exclude_reason = None
            else:
                figure.exclude_reason = "maybe_useful_material_state_photo"
        elif figure.figure_class == "photo_image" and _keyword_hits(text, SPINNABILITY_PHOTO_KEYWORDS):
            figure.maybe_useful = True
            if self.include_spinnability_photos_for_vision:
                figure.send_to_vision_model = True
                figure.exclude_reason = None
            else:
                figure.exclude_reason = "maybe_useful_spinnability_photo"
        elif figure.figure_class in VISION_ALLOWED_CLASSES:
            figure.send_to_vision_model = True
            figure.exclude_reason = None
        elif clip_positive and has_science_text:
            figure.send_to_vision_model = True
            figure.exclude_reason = None
        elif clip_negative and not has_science_text:
            figure.exclude_reason = "clip_negative"
        else:
            figure.exclude_reason = "not_selected_for_vision"

        figure.keep = figure.send_to_vision_model
        figure.keep_reason = f"vision_{figure.figure_class}" if figure.send_to_vision_model else figure.exclude_reason


def classify_figure(figure: FigureInfo, text: str | None = None) -> str:
    """Classify primarily from caption/reference/description text."""
    text = text if text is not None else _classification_text(figure)
    caption_text = (figure.caption or "").lower()
    subfigure_label = (figure.subfigure_label or "").lower()

    if _keyword_hits(text, NMR_SPECTRUM_KEYWORDS):
        caption_has_quantification = bool(_keyword_hits(caption_text, NMR_QUANTIFICATION_KEYWORDS))
        has_no_standard_caption = not figure.caption or figure.caption_source == "pseudo_caption"
        if (
            (caption_has_quantification or has_no_standard_caption and _keyword_hits(text, NMR_QUANTIFICATION_KEYWORDS))
            and subfigure_label != "a"
        ):
            return "nmr_quantification_plot"
        return "nmr_spectrum"
    if _keyword_hits(caption_text, KEYWORDS["elemental_mapping"]):
        return "elemental_mapping"
    if _keyword_hits(caption_text, CAPTION_XRD_KEYWORDS):
        return "xrd_pattern"
    if _keyword_hits(caption_text, CAPTION_FTIR_KEYWORDS):
        return "ftir_spectrum"
    if _keyword_hits(caption_text, KEYWORDS["raman_spectrum"]):
        return "raman_spectrum"
    if _keyword_hits(caption_text, CAPTION_THERMAL_KEYWORDS):
        return "thermal_analysis_plot"
    if _keyword_hits(caption_text, CAPTION_MICROSCOPY_KEYWORDS):
        return "microscopy_image"
    if _keyword_hits(text, KEYWORDS["elemental_mapping"]):
        return "elemental_mapping"
    if _keyword_hits(caption_text, CAPTION_RHEOLOGY_KEYWORDS):
        return "rheology_curve"
    if _keyword_hits(text, TEMPERATURE_CURVE_KEYWORDS):
        return "temperature_curve"
    if _keyword_hits(text, KEYWORDS["process_parameter_plot"]):
        return "process_parameter_plot"
    if _keyword_hits(text, KEYWORDS["mechanical_property_plot"]):
        return "mechanical_property_plot"
    if _keyword_hits(text, KEYWORDS["mechanical_curve"]):
        return "mechanical_curve"
    if _keyword_hits(text, SPINNABILITY_PHOTO_KEYWORDS):
        return "photo_image"
    if _keyword_hits(caption_text, KEYWORDS["schematic_or_flow"]) and not _keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if _keyword_hits(caption_text, CAPTION_SCHEMATIC_KEYWORDS) and not _keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"
    if _keyword_hits(text, STRUCTURE_SCHEMATIC_KEYWORDS) and not _keyword_hits(caption_text, CAPTION_SCIENTIFIC_KEYWORDS):
        return "schematic_or_flow"

    for class_name in [
        "nmr_quantification_plot",
        "nmr_spectrum",
        "elemental_mapping",
        "mass_spectrum",
        "microscopy_image",
        "ferron_curve",
        "calibration_curve",
        "xrd_pattern",
        "ftir_spectrum",
        "raman_spectrum",
        "thermal_analysis_plot",
        "temperature_curve",
        "particle_size_plot",
        "zeta_potential_plot",
        "photo_image",
        "mechanical_curve",
        "mechanical_property_plot",
        "process_parameter_plot",
        "schematic_or_flow",
        "table_image",
        "logo_or_icon",
        "formula_or_text",
    ]:
        if _keyword_hits(text, KEYWORDS[class_name]):
            return class_name

    if figure.clip_decision == "negative":
        if figure.clip_label in {"a publisher logo", "a school logo", "a small icon or symbol"}:
            return "logo_or_icon"
        if figure.clip_label in {"a mathematical formula", "a single equation", "text sentences"}:
            return "formula_or_text"
        if figure.clip_label == "a table with text and numbers":
            return "table_image"
        if figure.clip_label in {"a barcode or qr code"}:
            return "qr_code_or_barcode"
        if figure.clip_label in {"a cover page image", "a decorative image"}:
            return "cover_decoration"

    if figure.resnet_raw_class in RESNET_TABLE_CLASSES:
        return "table_image"
    if figure.resnet_raw_class in RESNET_SCHEMATIC_CLASSES and _keyword_hits(text, KEYWORDS["schematic_or_flow"]):
        return "schematic_or_flow"
    if figure.resnet_raw_class in RESNET_CHART_CLASSES or figure.clip_label in {
        "a scientific graph or plot",
        "a spectrum plot",
        "a thermal analysis curve",
        "a rheology curve",
        "a particle size distribution plot",
        "a zeta potential plot",
    }:
        return "generic_chart_or_plot"
    return "other"


def has_scientific_text(figure: FigureInfo) -> bool:
    text = _classification_text(figure)
    science_classes = [name for name in VISION_ALLOWED_CLASSES if name in KEYWORDS]
    return any(_keyword_hits(text, KEYWORDS[name]) for name in science_classes)


def is_false_candidate(figure: FigureInfo) -> bool:
    if figure.send_to_vision_model:
        return False
    if figure.is_fragment:
        return False
    if figure.exclude_reason == "replaced_by_bbox_stitched_figure":
        return False
    if figure.figure_class == "schematic_or_flow":
        return False
    return bool(_keyword_hits(_classification_text(figure), FALSE_CANDIDATE_KEYWORDS))


def is_review_candidate(figure: FigureInfo) -> bool:
    """Return True when a figure should be manually reviewed."""
    if figure.is_fragment:
        return False
    if figure.exclude_reason == "replaced_by_bbox_stitched_figure":
        return False
    return figure.review_reason is not None or is_caption_ocr_suspect(figure)


def review_reason_for_figure(figure: FigureInfo, text: str | None = None) -> str | None:
    """Return the first lightweight manual-review reason for a figure."""
    text = text if text is not None else _classification_text(figure)
    if is_caption_ocr_suspect(figure):
        return "caption_ocr_suspect"
    if figure.caption_truncation_reason == "multiple_figure_ids_caption_assignment_uncertain":
        return "multiple_figure_ids_caption_assignment_uncertain"
    if figure.caption_truncation_reason == "multiple_figure_ids_in_caption":
        return "multiple_figure_ids_in_caption"
    if figure.caption_cleaned and figure.caption_truncation_reason:
        return "caption_truncated"
    if _keyword_hits(text, KEYWORDS["elemental_mapping"]) and figure.figure_class != "elemental_mapping":
        return "taxonomy_conflict"
    if figure.figure_class == "other":
        return "figure_class_other"
    if _keyword_hits(text, FALSE_CANDIDATE_KEYWORDS) and not figure.send_to_vision_model and not figure.is_fragment:
        return "scientific_figure_not_sent_to_vision"
    return None


def is_caption_ocr_suspect(figure: FigureInfo) -> bool:
    """Conservative OCR anomaly detector for captions.

    This only marks figures for review; it never changes archive or vision
    selection decisions.
    """
    caption = (figure.caption or figure.raw_caption or "").strip()
    if not caption:
        return False
    if any(phrase in caption for phrase in CAPTION_OCR_SUSPECT_PHRASES):
        return True
    anchor_hits = sum(1 for keyword in CAPTION_OCR_ANCHOR_KEYWORDS if keyword in caption)
    if anchor_hits >= 2:
        return True
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", caption)
    if len(chinese_chars) >= 18:
        common_caption_terms = [
            "\u56fe",
            "\u8c31",
            "\u66f2\u7ebf",
            "\u793a\u610f",
            "\u7ed3\u6784",
            "\u5f62\u8c8c",
            "\u6eb6\u80f6",
            "\u51dd\u80f6",
            "\u7ea4\u7ef4",
            "\u6e29\u5ea6",
            "\u6838\u78c1",
            "\u7ea2\u5916",
            "\u8d28\u8c31",
        ]
        if anchor_hits and not any(term in caption for term in common_caption_terms):
            return True
    return False


def _classification_text(figure: FigureInfo) -> str:
    return " ".join(
        [
            figure.caption or "",
            " ".join(figure.reference_sentences),
            figure.description_text or "",
        ]
    ).lower()


def _all_keywords() -> list[str]:
    values: list[str] = []
    for items in KEYWORDS.values():
        values.extend(items)
    return values


def _keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    return sorted({keyword for keyword in keywords if keyword and _keyword_matches(text, keyword)})


def _keyword_matches(text: str, keyword: str) -> bool:
    keyword_lower = keyword.lower()
    if re.fullmatch(r"[a-z0-9+-]{1,5}", keyword_lower):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])", text))
    return keyword_lower in text


def image_size(image_path: str | None) -> tuple[int | None, int | None]:
    if not image_path:
        return None, None
    path = Path(image_path)
    if not path.exists():
        return None, None
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None, None
