from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _split_evidence_objects_payload


def _figure_metadata_map() -> dict[str, dict[str, str]]:
    return {
        "图2.12": {
            "caption": "图2.12 Al-Ferron 曲线",
            "figure_class": "ferron_curve",
        },
        "图2.18": {
            "caption": "图2.18 FTIR 光谱",
            "figure_class": "ftir_spectrum",
        },
        "图2.19": {
            "caption": "图2.19 XRD 谱图",
            "figure_class": "xrd_pattern",
        },
    }


def test_dict_of_dicts_evidence_is_flattened_and_ids_are_generated() -> None:
    payload = {
        "Al13_Synthesis_Optimization": {
            "ferron_curve": {
                "fact": "Ferron 曲线显示 Al13 比例更高。",
                "evidence_source": "图2.12",
                "caption": "图2.12 Al-Ferron 曲线",
                "reference_text": "如图2.12 所示，Ferron 曲线发生变化。",
            },
            "ftir_and_xrd": {
                "fact": "FTIR 与 XRD 共同支持凝胶结构。",
                "evidence_source": "图2.18, 图2.19",
                "caption": "图2.18 FTIR 光谱; 图2.19 XRD 谱图",
                "reference_text": "图2.18 和图2.19 给出了 FTIR 与 XRD 证据。",
            },
        }
    }

    evidence_objects = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map=_figure_metadata_map(),
        tables_summary=[],
    )

    assert len(evidence_objects) == 3
    assert {item["figure_id"] for item in evidence_objects} == {"图2.12", "图2.18", "图2.19"}
    assert any(item["evidence_id"] == "图2.12" for item in evidence_objects)
    assert any(item["figure_type"] == "ferron_curve" for item in evidence_objects)
    assert any(item["figure_type"] == "ftir_spectrum" for item in evidence_objects)
    assert any(item["figure_type"] == "xrd_pattern" for item in evidence_objects)


def test_multiple_facts_for_same_figure_get_unique_suffixes() -> None:
    payload = {
        "group": {
            "fact_a": {
                "fact": "第一条 NMR 事实。",
                "evidence_source": "图2.12",
                "caption": "图2.12 27Al NMR 光谱",
            },
            "fact_b": {
                "fact": "第二条 NMR 事实。",
                "evidence_source": "图2.12",
                "caption": "图2.12 27Al NMR 光谱",
            },
        }
    }

    evidence_objects = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map={"图2.12": {"caption": "图2.12 27Al NMR 光谱", "figure_class": "nmr_spectrum"}},
        tables_summary=[],
    )

    assert [item["evidence_id"] for item in evidence_objects] == ["图2.12__ev01", "图2.12__ev02"]
    assert all(item["figure_id"] == "图2.12" for item in evidence_objects)


def test_nested_table_evidence_can_be_materialized() -> None:
    payload = {
        "Quantitative": {
            "rows": [
                {
                    "fact": "表中给出最优旋蒸条件。",
                    "evidence_source": "table_001",
                    "caption": "表 2.1 旋蒸条件",
                }
            ]
        }
    }

    evidence_objects = _split_evidence_objects_payload(
        payload=payload,
        figure_metadata_map={},
        tables_summary=[{"table_id": "table_001", "rows": [{"condition": "38 C"}]}],
    )

    assert len(evidence_objects) == 1
    assert evidence_objects[0]["table_id"] == "table_001"
    assert evidence_objects[0]["evidence_id"] == "table_001"


def test_stage2_figure_class_is_inherited_for_figure_type() -> None:
    evidence_objects = _split_evidence_objects_payload(
        payload=[
            {
                "id": "图2.18",
                "type": "figure",
                "caption": "图2.18 旋蒸后铝溶胶的IR谱图",
                "fact": "红外证据",
            }
        ],
        figure_metadata_map={"图2.18": {"figure_id": "图2.18", "figure_class": "ftir_spectrum"}},
        tables_summary=[],
    )

    assert len(evidence_objects) == 1
    assert evidence_objects[0]["figure_id"] == "图2.18"
    assert evidence_objects[0]["figure_type"] == "ftir_spectrum"
    assert "inherited_figure_type_from_stage2" in str(evidence_objects[0].get("normalization_note") or "")
    assert "peak_positions" not in evidence_objects[0]
    assert "assignments" not in evidence_objects[0]


def test_caption_fallback_sets_spectral_figure_type_without_stage2_metadata() -> None:
    evidence_objects = _split_evidence_objects_payload(
        payload=[
            {"id": "图2.18", "type": "figure", "caption": "图2.18 IR谱图"},
            {"id": "图2.11", "type": "figure", "caption": "图2.11 27Al NMR谱图"},
            {"id": "图2.12", "type": "figure", "caption": "图2.12 Al-Ferron标准曲线"},
            {"id": "图2.19", "type": "figure", "caption": "图2.19 XRD谱图"},
            {"id": "图2.20", "type": "figure", "caption": "图2.20 Raman谱图"},
        ],
        figure_metadata_map={},
        tables_summary=[],
    )

    assert [item["figure_type"] for item in evidence_objects] == [
        "ftir_spectrum",
        "nmr_spectrum",
        "ferron_curve",
        "xrd_pattern",
        "raman_spectrum",
    ]
    assert all(
        "fallback_figure_type_from_caption" in str(item.get("normalization_note") or "")
        for item in evidence_objects
    )


def test_missing_stage2_figure_metadata_does_not_crash() -> None:
    evidence_objects = _split_evidence_objects_payload(
        payload=[{"id": "图9.9", "type": "figure", "caption": "图9.9 未知图谱"}],
        figure_metadata_map={},
        tables_summary=[],
    )

    assert len(evidence_objects) == 1
    assert evidence_objects[0]["figure_id"] == "图9.9"
