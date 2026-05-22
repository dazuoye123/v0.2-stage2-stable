"""Regression tests for stage 2 figure classification priority rules."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo  # noqa: E402
from alumina_sol_extractor.vision.figure_filter import FigureFilter  # noqa: E402


def _apply(figure: FigureInfo) -> FigureInfo:
    return FigureFilter().apply_one(figure)


def test_sem_photo_prefers_microscopy_over_photo() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="图5",
            caption="图5 SEM 照片及纤维表面形貌",
            caption_source="standard_caption",
        )
    )
    assert figure.figure_class == "microscopy_image"
    assert figure.figure_class != "photo_image"
    assert figure.send_to_vision_model is True


def test_microstructure_cross_section_and_grain_prefers_microscopy() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="Fig.7",
            caption="Fig.7 纤维截面的微观结构、晶粒与致密化形貌",
            reference_sentences=["烧结后陶瓷纤维内部孔隙减少，表面结构更致密。"],
            caption_source="standard_caption",
        )
    )
    assert figure.figure_class == "microscopy_image"


def test_xrd_keywords_prefer_xrd_pattern() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="图3",
            caption="图3 XRD 衍射谱图与物相分析结果",
            caption_source="standard_caption",
            resnet_raw_class="Graph plots",
            clip_decision="positive",
            clip_label="a scientific graph or plot",
        )
    )
    assert figure.figure_class == "xrd_pattern"
    assert figure.figure_class != "generic_chart_or_plot"


def test_ftir_keywords_prefer_ftir_spectrum() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="Fig.4",
            caption="Fig.4 FTIR spectra of alumina fibers",
            reference_sentences=["主要吸收峰位于 3440 cm-1 与 1640 cm-1。"],
            caption_source="standard_caption",
        )
    )
    assert figure.figure_class == "ftir_spectrum"


def test_thermal_keywords_prefer_thermal_analysis_plot() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="图2",
            caption="图2 TG/TGA/DSC 热重-差热曲线",
            caption_source="standard_caption",
            resnet_raw_class="Graph plots",
        )
    )
    assert figure.figure_class == "thermal_analysis_plot"
    assert figure.figure_class != "generic_chart_or_plot"


def test_mechanical_keywords_prefer_mechanical_property_plot() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="Fig.9",
            caption="Fig.9 力学性能：拉伸强度与应力-应变曲线",
            reference_sentences=["同时比较断裂强度与伸长率。"],
            caption_source="standard_caption",
            resnet_raw_class="Graph plots",
        )
    )
    assert figure.figure_class == "mechanical_property_plot"
    assert figure.figure_class != "generic_chart_or_plot"


def test_formula_or_chemical_structure_hard_drops_from_vision() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="图1",
            caption="图1 乙基纤维素分子式与 Chemical structure",
            caption_source="standard_caption",
            clip_decision="positive",
            clip_label="a scientific graph or plot",
        )
    )
    assert figure.figure_class == "formula_or_text"
    assert figure.send_to_vision_model is False


def test_mechanism_schematic_not_misclassified_as_formula() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="图6",
            caption="图6 氧化铝纤维形成机理示意图",
            caption_source="standard_caption",
            clip_decision="negative",
            clip_label="a mathematical formula",
        )
    )
    assert figure.figure_class == "schematic_or_flow"
    assert figure.figure_class != "formula_or_text"


def test_clip_negative_does_not_override_strong_microscopy_text() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="Fig.8",
            caption="Fig.8 TEM micrograph of ceramic fiber cross section",
            caption_source="standard_caption",
            clip_decision="negative",
            clip_label="a decorative image",
        )
    )
    assert figure.figure_class == "microscopy_image"
    assert figure.send_to_vision_model is True


def test_resnet_graph_does_not_override_strong_xrd_text() -> None:
    figure = _apply(
        FigureInfo(
            paper_id="p",
            figure_id="Fig.10",
            caption="Fig.10 X-ray diffraction pattern of alumina fiber",
            caption_source="standard_caption",
            resnet_raw_class="Graph plots",
        )
    )
    assert figure.figure_class == "xrd_pattern"
    assert figure.send_to_vision_model is True
