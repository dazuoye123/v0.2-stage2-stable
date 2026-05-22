"""Configuration-backed taxonomy constants for stage 2 figure handling."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import yaml


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
    "nmr_quantification_plot": ["积分", "核磁积分", "积分比例", "nmr integration", "integral ratio", "integration", "integral"],
    "nmr_spectrum": ["核磁", "nmr", "^27al", "27al", "ppm", "铝核磁", "nuclear magnetic resonance"],
    "elemental_mapping": ["EDS", "EDS-mapping", "EDS mapping", "elemental mapping", "element mapping", "元素分布", "面扫描", "mapping", "能谱面扫"],
    "mass_spectrum": ["质谱", "飞行时间质谱", "tof-ms", "tof ms", "mass spectrum", "m/z", "质荷比"],
    "xrd_pattern": ["xrd", "diffraction", "衍射", "晶型", "物相", "物相分析", "衍射谱", "衍射图", "x-ray diffraction"],
    "ftir_spectrum": ["ftir", "ft-ir", " ir ", "红外", "infrared", "cm-1", "cm−1", "吸收峰", "transmittance"],
    "raman_spectrum": ["raman", "拉曼"],
    "thermal_analysis_plot": ["tg", "tga", "dsc", "dta", "tg-dsc", "热重", "差热", "失重", "mass loss", "weight loss", "thermal analysis"],
    "ferron_curve": ["ferron", "al-ferron", "逐时络合", "比色"],
    "calibration_curve": ["标准曲线", "calibration curve"],
    "rheology_curve": ["流变", "黏度", "粘度", "rheology", "shear", "viscosity", "剪切"],
    "temperature_curve": ["温度变化", "temperature profile", "temperature curve", "temperature variation"],
    "particle_size_plot": ["粒径分布", "particle size distribution", "size distribution", "dls"],
    "zeta_potential_plot": ["zeta", "zeta potential", "电位"],
    "microscopy_image": ["sem", "tem", "hrtem", "electron microscopy", "scanning electron microscopy", "transmission electron microscopy", "显微", "形貌", "微观结构", "微结构", "截面", "断面", "断裂面", "晶粒", "纤维内部", "表面结构", "孔洞", "孔隙", "致密", "烧结颈", "micrograph", "morphology", "microstructure", "cross section", "cross-section", "fracture surface", "grain", "grain boundary", "porosity", "pore", "dense", "densification", "scale bar"],
    "photo_image": ["photograph", "photo", "照片", "实物图", "可纺性", "纤维照片", "状态对照图", "透明", "微暗", "微白", "胶凝", "外观", "旋蒸状态", "溶胶状态", "光学照片", "optical image"],
    "mechanical_curve": ["load-displacement", "stress-strain", "tensile", "strength", "modulus", "force", "displacement"],
    "mechanical_property_plot": ["强度", "模量", "拉伸强度", "断裂强度", "单丝强度", "离散", "力学性能", "应力-应变", "应力应变", "伸长率", "strength", "modulus", "tensile", "mechanical property", "mechanical properties", "tensile strength", "fracture strength", "stress-strain", "stress strain", "elongation", "distribution", "scatter"],
    "process_parameter_plot": ["工艺参数", "参数影响", "环境参数", "纺丝环境参数", "纺丝参数", "工艺条件", "条件影响", "parameter effect", "process parameter"],
    "generic_chart_or_plot": ["plot", "curve", "chart", "graph", "trend", "distribution", "comparison", "统计图", "坐标图", "曲线图", "参数图", "性能图"],
    "schematic_or_flow": ["示意图", "原理图", "流程图", "构造", "步骤", "mechanism", "schematic", "diagram", "workflow", "作用机理", "形成过程", "转变", "相间转变", "结构示意", "示意", "原理", "过程", "试样衬", "夹具", "装置", "测试装置", "测试夹具", "process", "fixture"],
    "table_image": ["table", "表格"],
    "logo_or_icon": ["logo", "校徽", "publisher logo", "school logo", "icon"],
    "formula_or_text": ["formula", "equation", "text sentences", "公式", "纯文本", "化学式", "分子式", "结构式", "结构简式", "反应式", "方程式", "分子结构", "化学结构", "chemical formula", "molecular formula", "structural formula", "chemical structure", "reaction equation"],
    "pure_text_image": ["text image", "pure text", "text only", "paragraph text", "sentence image"],
    "qr_code_or_barcode": ["qr code", "barcode", "bar code"],
    "cover_decoration": ["cover decoration", "cover image", "decorative image"],
}


def _load_taxonomy_config() -> None:
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
            keyword_text = str(keyword)
            if keyword_text not in KEYWORDS[class_name]:
                KEYWORDS[class_name].append(keyword_text)


_load_taxonomy_config()

FALSE_CANDIDATE_KEYWORDS = ["核磁", "nmr", "ppm", "红外", "ir", "ftir", "ferron", "流变", "rheology", "xrd", "sem", "tem", "eds", "mapping", "zeta", "粒径", "强度", "模量", "质谱", "tof-ms", "mass spectrum"]
MATERIAL_STATE_PHOTO_KEYWORDS = ["状态对照图", "透明", "微暗", "微白", "胶凝", "外观", "旋蒸状态", "溶胶状态"]
SPINNABILITY_PHOTO_KEYWORDS = ["成丝性", "可纺性", "拉丝", "纺丝性", "spinnability", "fiber drawing", "thread-forming"]
TEMPERATURE_CURVE_KEYWORDS = ["温度变化图", "温度曲线", "temperature curve", "temperature profile", "temperature variation"]
CAPTION_FTIR_KEYWORDS = ["红外", "ir", "ftir", "infrared", "cm-1", "cm−1", "红外谱图"]
CAPTION_XRD_KEYWORDS = ["xrd", "衍射", "diffraction"]
CAPTION_MICROSCOPY_KEYWORDS = ["tem", "sem", "hrtem", "显微", "形貌", "微观结构", "微结构", "截面", "断面", "断裂面", "晶粒", "纤维内部", "表面结构", "孔洞", "孔隙", "致密", "烧结颈", "放大倍率", "magnification", "micrograph", "microscopy", "microstructure", "cross section", "cross-section", "fracture surface", "grain", "scale bar"]
CAPTION_THERMAL_KEYWORDS = ["tg", "tga", "dsc", "dta", "tg-dsc", "热重", "差热", "失重"]
CAPTION_RHEOLOGY_KEYWORDS = ["流变曲线", "流变性", "流变性特征", "rheology curve", "viscosity curve", "shear curve"]
CAPTION_SCHEMATIC_KEYWORDS = ["原理图", "示意图", "结构图", "构造", "步骤", "流程图"]
CAPTION_PHOTO_KEYWORDS = ["光学照片", "照片", "photo", "photograph", "optical image", "实物图", "外观"]
CAPTION_MECHANICAL_KEYWORDS = ["力学性能", "拉伸强度", "断裂强度", "应力-应变", "应力应变", "伸长率", "mechanical property", "mechanical properties", "tensile strength", "fracture strength", "stress-strain", "stress strain", "elongation"]
CAPTION_SCIENTIFIC_KEYWORDS = ["xrd", "核磁", "nmr", "红外", "ir", "ftir", "tem", "sem", "hrtem", "质谱图", "谱图", "温度变化图", "温度曲线", "temperature curve", "spectrum", "ferron", "流变", "成丝性", "可纺性", "拉丝", "spinnability", "eds", "mapping"]
STRUCTURE_SCHEMATIC_KEYWORDS = ["胶体结构", "胶团结构", "结构形成机理", "双电层结构", "al13", "al13^7+", "keggin", "团簇结构", "类型及结构"]
NMR_SPECTRUM_KEYWORDS = ["核磁", "nmr", "^27al", "27al", "ppm", "核磁谱图"]
NMR_QUANTIFICATION_KEYWORDS = ["积分", "积分比例", "核磁积分", "integral ratio", "integration", "integral"]
FORMULA_TEXT_KEYWORDS = ["化学式", "分子式", "结构式", "结构简式", "反应式", "方程式", "分子结构", "化学结构", "chemical formula", "molecular formula", "structural formula", "chemical structure", "reaction equation", "formula", "equation"]
MICROSCOPY_MATERIAL_CONTEXT_KEYWORDS = ["纤维", "陶瓷", "氧化铝", "凝胶", "溶胶", "粉体", "煅烧", "烧结", "热处理", "fiber", "fibre", "ceramic", "grain", "particle", "powder"]
CAPTION_OCR_SUSPECT_PHRASES = ["内确度下同种处理后的该酶的比值", "该酶的比值"]
CAPTION_OCR_ANCHOR_KEYWORDS = ["内确度", "该酶", "同种处理"]

for _keyword in [
    "有机结构式",
    "配位结构式",
    "molecular structure",
    "skeletal formula",
    "constitutional formula",
]:
    if _keyword not in KEYWORDS["formula_or_text"]:
        KEYWORDS["formula_or_text"].append(_keyword)
    if _keyword not in FORMULA_TEXT_KEYWORDS:
        FORMULA_TEXT_KEYWORDS.append(_keyword)


RESNET_SCHEMATIC_CLASSES = {"Flow chart", "Block diagram", "Algorithm", "Tree Diagram", "Sketches"}
RESNET_TABLE_CLASSES = {"Tables"}
RESNET_CHART_CLASSES = {"Graph plots", "Scatter plot", "Bar plots", "Heat map", "Histogram", "Box plot", "Area chart", "Contour plot", "Surface plot", "Vector plot", "Line graph", "Confusion matrix"}


def keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    return sorted({keyword for keyword in keywords if keyword and keyword_matches(text, keyword)})


def keyword_matches(text: str, keyword: str) -> bool:
    keyword_lower = keyword.lower()
    if re.fullmatch(r"[a-z0-9+-]{1,5}", keyword_lower):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])", text))
    return keyword_lower in text


def all_keywords() -> list[str]:
    values: list[str] = []
    for items in KEYWORDS.values():
        values.extend(items)
    return values
