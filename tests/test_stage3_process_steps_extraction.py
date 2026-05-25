from __future__ import annotations

from alumina_sol_extractor.dspy_modules.runner import _normalize_process_steps_payload
from alumina_sol_extractor.stage3.merge import merge_stage_outputs_to_paper_record


def test_process_steps_none_normalizes_to_empty_list() -> None:
    record = merge_stage_outputs_to_paper_record(
        paper_basic_info={"paper_id": "paper-1", "title": "demo"},
        process_steps=None,
    )
    assert record.process_steps == []


def test_process_steps_preserve_reagent_amounts_and_conditions() -> None:
    record = merge_stage_outputs_to_paper_record(
        process_steps=[
            {
                "step_order": 1,
                "action": "dissolve",
                "action_zh": "溶解",
                "reagent_name": "AlCl3·6H2O",
                "reagent_amount": 0.005,
                "reagent_unit": "mol",
                "linked_parameter_keys": ["aluminum_source"],
                "evidence_text": "首先将 0.005 mol AlCl3·6H2O 溶于一定量去离子水中。",
            },
            {
                "step_order": 2,
                "action": "electrospin",
                "action_zh": "静电纺丝",
                "condition_key": "applied_voltage_kV",
                "condition_value": 18,
                "condition_unit": "kV",
                "evidence_text": "外加电场 18 kV。",
            },
        ]
    )
    assert len(record.process_steps) == 2
    assert record.process_steps[0].reagent_name == "AlCl3·6H2O"
    assert record.process_steps[0].reagent_amount == 0.005
    assert record.process_steps[1].condition_value == 18
    assert record.process_steps[1].condition_unit == "kV"


def test_process_step_enrichment_extracts_reagents_conditions_and_heat_steps() -> None:
    payload = [
        {
            "step_order": 1,
            "description": "将 0.005 mol AlCl3·6H2O 溶于一定量去离子水中",
            "evidence_text": "首先将 0.005 mol AlCl3·6H2O 溶于一定量去离子水中。",
            "needs_manual_review": True,
        },
        {
            "step_order": 2,
            "description": "加入 0.02 mol 异丙醇铝及无水乙醇",
            "evidence_text": "待完全溶解后加入 0.02 mol 异丙醇铝及无水乙醇，搅拌均匀后再加入。",
        },
        {
            "step_order": 3,
            "description": "加入 0.6 mL 冰醋酸和 1.7 mL 盐酸，搅拌 8 h 至溶胶透明",
            "evidence_text": "再加入 0.6 mL 冰醋酸和 1.7 mL 盐酸，搅拌 8 h 至溶胶透明。",
        },
        {
            "step_order": 4,
            "description": "加入一定量的 PVP，形成透明澄清的可纺性溶胶",
            "evidence_text": "然后加入一定量的 PVP，形成透明澄清的可纺性溶胶。",
            "needs_manual_review": True,
        },
        {
            "step_order": 5,
            "description": "将可纺性溶胶注入到 10.0 mL 塑料注射器中，利用静电纺丝机进行静电纺丝，外加电场 18 kV，喷丝头与接收板的距离为 20 cm，进料速率为 2.8 mL/h。",
            "evidence_text": "将可纺性溶胶注入到 10.0 mL 塑料注射器中，利用静电纺丝机进行静电纺丝，外加电场 18 kV，喷丝头与接收板的距离为 20 cm，进料速率为 2.8 mL/h。",
        },
        {
            "step_order": 6,
            "description": "静电纺丝时采用齿形接收器收集氧化铝干凝胶纤维",
            "evidence_text": "静电纺丝时采用齿形接收器收集氧化铝干凝胶纤维。",
        },
        {
            "step_order": 7,
            "description": "以 1 ℃/min 的速率升温至 600 ℃，保持 2 h",
            "evidence_text": "将得到的凝胶纤维以 1 ℃/min 的速率升温至 600 ℃，保持 2 h。",
        },
        {
            "step_order": 8,
            "description": "以 5 ℃/min 的速率升温到 800 ℃，保温 2 h，凝胶纤维转化为 γ-Al2O3 纤维",
            "evidence_text": "再以 5 ℃/min 的速率升温到 800 ℃，保温 2 h，凝胶纤维转化为 γ-Al2O3 纤维。",
        },
        {
            "step_order": 9,
            "description": "于 1200 ℃ 煅烧 2 h",
            "evidence_text": "再于 1200 ℃ 煅烧 2 h。",
        },
        {
            "step_order": 10,
            "description": "自然降至室温，得到 α-Al2O3 纳米结构纤维",
            "evidence_text": "自然降至室温，得到 α-Al2O3 纳米结构纤维。",
        },
    ]

    steps = _normalize_process_steps_payload(payload)

    assert any(step["reagent_name"] == "AlCl3·6H2O" and step["reagent_amount"] == 0.005 and step["reagent_unit"] == "mol" for step in steps)
    assert any(step["reagent_name"] == "异丙醇铝" and step["reagent_amount"] == 0.02 and step["reagent_unit"] == "mol" for step in steps)
    assert any(step["reagent_name"] == "冰醋酸" and step["reagent_amount"] == 0.6 and step["reagent_unit"] == "mL" for step in steps)
    assert any(step["reagent_name"] == "盐酸" and step["reagent_amount"] == 1.7 and step["reagent_unit"] == "mL" for step in steps)
    assert any(step["action"] == "stir" and step["duration_value"] == 8.0 and step["duration_unit"] == "h" for step in steps)
    assert any(step["action"] == "inject" and step["equipment"] == "10.0 mL 塑料注射器" for step in steps)
    assert any(step["condition_key"] == "applied_voltage_kV" and step["condition_value"] == 18.0 for step in steps)
    assert any(step["condition_key"] == "collector_distance_cm" and step["condition_value"] == 20.0 for step in steps)
    assert any(step["condition_key"] == "feed_rate_ml_h" and step["condition_value"] == 2.8 for step in steps)
    assert any(step["action"] == "collect" and step["equipment"] == "齿形接收器" for step in steps)
    assert any(step["temperature_value"] == 600.0 and step["duration_value"] == 2.0 for step in steps)
    assert any(step["temperature_value"] == 800.0 and step["product_or_outcome"] == "γ-Al2O3 纤维" for step in steps)
    assert any(step["action"] == "calcine" and step["temperature_value"] == 1200.0 for step in steps)
    assert any(step["action"] == "obtain_product" and step["product_or_outcome"] == "α-Al2O3 纳米结构纤维" for step in steps)


def test_process_step_normalization_repairs_weak_llm_steps_from_description() -> None:
    payload = [
        {
            "step_order": 1,
            "action": "other",
            "description": "PVA was dissolved in water at 80 °C and stirred for 2 h.",
            "evidence_text": "",
        },
        {
            "step_order": 2,
            "action": "other",
            "description": "The sol was electrospun at 15 kV and 0.5 mL/h.",
        },
    ]

    steps = _normalize_process_steps_payload(payload)

    assert any(step["action"] == "dissolve" and step.get("temperature_value") == 80.0 for step in steps)
    assert any(step["action"] == "stir" and step.get("duration_value") == 2.0 for step in steps)
    assert any(step["action"] == "electrospin" and step.get("condition_key") == "applied_voltage_kV" and step.get("condition_value") == 15.0 for step in steps)
    assert all(step.get("evidence_text") for step in steps)
