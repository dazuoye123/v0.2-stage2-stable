"""Final send_to_vision_model rule tests."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.vision.figure_filter import FigureFilter


def test_send_to_vision_rules() -> None:
    filt = FigureFilter()

    nmr = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.6",
            caption="\u56fe2.6 \u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe NMR ppm",
            caption_source="standard_caption",
        )
    )
    assert nmr.figure_class == "nmr_spectrum"
    assert nmr.send_to_vision_model

    nmr_without_integral = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.2",
            caption="\u56fe2.2 \u4e0d\u540c\u94dd\u7c89\u8fdb\u6599\u65b9\u5f0f\u5408\u6210\u94dd\u6eb6\u80f6\u7684 ^27AlNMR \u8c31\u56fe",
            caption_source="standard_caption",
        )
    )
    assert nmr_without_integral.figure_class == "nmr_spectrum"
    assert nmr_without_integral.figure_class != "nmr_quantification_plot"

    nmr_with_integral_reference_only = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.2",
            caption="\u56fe2.2 \u4e0d\u540c\u94dd\u7c89\u8fdb\u6599\u65b9\u5f0f\u5408\u6210\u94dd\u6eb6\u80f6\u7684 ^27AlNMR \u8c31\u56fe",
            reference_sentences=["\u5982\u56fe2.2(b)\u6240\u793a\uff0c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u8fbe\u5230\u6700\u5927\u3002"],
            caption_source="standard_caption",
        )
    )
    assert nmr_with_integral_reference_only.figure_class == "nmr_spectrum"

    nmr_unknown_section = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe3.20",
            caption="\u56fe3.20 \u6838\u78c1\u76f8\u5173\u6d4b\u8bd5\u7ed3\u679c\u56fe",
            reference_sentences=["\u6838\u78c1\u7ed3\u679c\u89c1\u56fe3.20\uff0c^27Al NMR ppm \u4fe1\u53f7\u53d8\u5316\u660e\u663e\u3002"],
            caption_source="pseudo_caption",
            clip_decision="negative",
            clip_label="text sentences",
        )
    )
    assert nmr_unknown_section.figure_class == "nmr_spectrum"
    assert nmr_unknown_section.send_to_vision_model

    nmr_combo_a = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.9",
            subfigure_label="a",
            caption="\u56fe2.9\u6700\u4f18\u6761\u4ef6\u5408\u6210\u7684\u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe(a)\u548c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u56fe(b)",
            caption_source="standard_caption",
        )
    )
    assert nmr_combo_a.figure_class == "nmr_spectrum"
    assert nmr_combo_a.send_to_vision_model

    nmr_combo_b = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.9",
            subfigure_label="b",
            caption="\u56fe2.9\u6700\u4f18\u6761\u4ef6\u5408\u6210\u7684\u94dd\u6eb6\u80f6\u6838\u78c1\u8c31\u56fe(a)\u548c\u6838\u78c1\u79ef\u5206\u6bd4\u4f8b\u56fe(b)",
            caption_source="standard_caption",
        )
    )
    assert nmr_combo_b.figure_class == "nmr_quantification_plot"
    assert nmr_combo_b.send_to_vision_model

    tem_with_ir_context = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe3.12",
            caption="\u56fe3.12 \u8461\u805a\u7cd6\u51dd\u80f6\u7684TEM\u56fe",
            reference_sentences=["\u7ea2\u5916 IR \u7ed3\u679c\u5728\u76f8\u90bb\u6bb5\u843d\u4e2d\u51fa\u73b0\u3002"],
            caption_source="standard_caption",
        )
    )
    assert tem_with_ir_context.figure_class == "microscopy_image"
    assert tem_with_ir_context.send_to_vision_model

    ftir_caption_with_tem_reference = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe3.13",
            caption="\u56fe3.13\u5404\u7c7b\u578b\u8461\u805a\u7cd6\u51dd\u80f6\u7ea2\u5916\u8c31\u56fe",
            reference_sentences=["\u8461\u805a\u7cd6\u51dd\u80f6\u7684\u5f62\u8c8c\u89c1TEM\u56fe3.12\u3002"],
            caption_source="standard_caption",
        )
    )
    assert ftir_caption_with_tem_reference.figure_class == "ftir_spectrum"
    assert ftir_caption_with_tem_reference.send_to_vision_model

    schematic_mass_instrument = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe1.1",
            caption="\u56fe1.1 \u98de\u884c\u65f6\u95f4\u8d28\u8c31\u4eea\u539f\u7406\u793a\u610f\u56fe",
            caption_source="standard_caption",
        )
    )
    assert schematic_mass_instrument.figure_class == "schematic_or_flow"
    assert schematic_mass_instrument.figure_class != "mass_spectrum"

    colloid_structure = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe1.5",
            caption="\u56fe1.5 \u94dd\u6eb6\u80f6\u80f6\u4f53\u7ed3\u6784\u56fe",
            caption_source="standard_caption",
        )
    )
    assert colloid_structure.figure_class == "schematic_or_flow"
    assert colloid_structure.maybe_useful

    al13_structure = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.1",
            caption="\u56fe2.1 Al13^7+ Keggin \u56e2\u7c07\u7c7b\u578b\u53ca\u7ed3\u6784",
            caption_source="standard_caption",
            clip_decision="negative",
            clip_label="a small icon or symbol",
        )
    )
    assert al13_structure.figure_class == "schematic_or_flow"
    assert al13_structure.maybe_useful
    assert al13_structure.figure_class != "logo_or_icon"

    mass_spectrum = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe3.9",
            caption="\u56fe3.9 \u98de\u884c\u65f6\u95f4\u8d28\u8c31\u56fe",
            caption_source="standard_caption",
        )
    )
    assert mass_spectrum.figure_class == "mass_spectrum"
    assert mass_spectrum.send_to_vision_model

    material_photo = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.15",
            caption="\u56fe2.15 \u5404\u65cb\u84b8\u72b6\u6001\u5bf9\u7167\u56fe\uff1a(a)\u900f\u660e\uff0c(b)\u5fae\u6697\uff0c(c)\u5fae\u767d",
            caption_source="standard_caption",
        )
    )
    assert material_photo.figure_class == "photo_image"
    assert material_photo.maybe_useful
    assert material_photo.send_to_vision_model

    material_photo_disabled = FigureFilter(include_material_state_photos=False).apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.15",
            caption="\u56fe2.15 \u5404\u65cb\u84b8\u72b6\u6001\u5bf9\u7167\u56fe\uff1a(a)\u900f\u660e\uff0c(b)\u5fae\u6697\uff0c(c)\u5fae\u767d",
            caption_source="standard_caption",
        )
    )
    assert material_photo_disabled.figure_class == "photo_image"
    assert material_photo_disabled.maybe_useful
    assert not material_photo_disabled.send_to_vision_model

    optical_photo_with_xrd_context = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2-4",
            caption="\u56fe2-4\u65b0\u5236\u83ab\u6765\u77f3\u6676\u79cd\u5206\u6563\u6db2(a)\u53ca\u5176\u653e\u7f6e3\u4e2a\u6708\u540e(b)\u7684\u5149\u5b66\u7167\u7247",
            reference_sentences=["\u7531XRD\u53ef\u77e5\uff0c\u6676\u79cd\u7269\u76f8\u672a\u53d1\u751f\u660e\u663e\u53d8\u5316\u3002"],
            caption_source="standard_caption",
        )
    )
    assert optical_photo_with_xrd_context.figure_class == "photo_image"
    assert optical_photo_with_xrd_context.send_to_vision_model

    temperature_curve = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.5",
            caption="\u56fe2.5\u4e0d\u540c\u8d77\u59cb\u53cd\u5e94\u6e29\u5ea6\u7684\u70e7\u74f6\u5185\u6eb6\u6db2\u6e29\u5ea6\u53d8\u5316\u56fe\uff1a(a) 50\u00b0C \uff0c(b) 55\u00b0C",
            reference_sentences=["Al13^7+ \u7ed3\u6784\u8bcd\u5728\u76f8\u90bb\u6bb5\u843d\u51fa\u73b0\uff0c\u4f46\u4e0d\u5e94\u8986\u76d6\u6e29\u5ea6\u53d8\u5316\u56fe\u5206\u7c7b\u3002"],
            caption_source="standard_caption",
        )
    )
    assert temperature_curve.figure_class == "temperature_curve"
    assert temperature_curve.send_to_vision_model

    spinnability = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.16",
            caption="\u56fe2.16 \u94dd\u6eb6\u80f6\u7684\u6210\u4e1d\u6027",
            reference_sentences=["\u7528\u73bb\u7483\u68d2\u8638\u53d6\u6d53\u7f29\u8001\u5316\u540e\u7684\u94dd\u6eb6\u80f6\u8fdb\u884c\u62c9\u4e1d\uff0c\u521d\u6b65\u68c0\u6d4b\u53ef\u7eba\u6027\u3002"],
            caption_source="standard_caption",
        )
    )
    assert spinnability.figure_class == "photo_image"
    assert spinnability.maybe_useful
    assert spinnability.send_to_vision_model

    spinnability_disabled = FigureFilter(include_spinnability_photos_for_vision=False).apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.16",
            caption="\u56fe2.16 \u94dd\u6eb6\u80f6\u7684\u6210\u4e1d\u6027",
            caption_source="standard_caption",
        )
    )
    assert spinnability_disabled.figure_class == "photo_image"
    assert spinnability_disabled.maybe_useful
    assert not spinnability_disabled.send_to_vision_model

    tem_with_spinnability_reference = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe2.17",
            caption="\u56fe2.17\u6d53\u7f29\u540e\u94dd\u6eb6\u80f6TEM\u56fe",
            reference_sentences=["\u94dd\u6eb6\u80f6\u5177\u6709\u4e00\u5b9a\u53ef\u7eba\u6027\uff0c\u4f46\u8be5\u56fe\u662fTEM\u5f62\u8c8c\u56fe\u3002"],
            caption_source="standard_caption",
        )
    )
    assert tem_with_spinnability_reference.figure_class == "microscopy_image"
    assert tem_with_spinnability_reference.send_to_vision_model

    schematic = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe1.4",
            caption="\u56fe1.4 \u51dd\u80f6\u8fc7\u6ee4\u5c42\u6790\u793a\u610f\u56fe",
            caption_source="standard_caption",
        )
    )
    assert schematic.figure_class == "schematic_or_flow"
    assert not schematic.send_to_vision_model

    logo = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="Unknown Figure 1",
            caption=None,
            clip_decision="negative",
            clip_label="a school logo",
        )
    )
    assert logo.figure_class == "logo_or_icon"
    assert not logo.send_to_vision_model

    ocr_suspect = filt.apply_one(
        FigureInfo(
            paper_id="p",
            figure_id="\u56fe3.5",
            caption="\u56fe3.5 \u5185\u786e\u5ea6\u4e0b\u540c\u79cd\u5904\u7406\u540e\u7684\u8be5\u9176\u7684\u6bd4\u503c",
            caption_source="standard_caption",
        )
    )
    assert ocr_suspect.review_reason == "caption_ocr_suspect"


if __name__ == "__main__":
    test_send_to_vision_rules()
    print("send to vision rules test passed")
