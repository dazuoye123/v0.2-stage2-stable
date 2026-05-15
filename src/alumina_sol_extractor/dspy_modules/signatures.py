"""Lazy DSPy signature definitions for Stage 3 extraction."""

from __future__ import annotations


def get_signatures():
    """Create DSPy Signature classes lazily so Stage 1/2 do not require dspy."""
    try:
        import dspy  # type: ignore
    except ImportError as exc:  # pragma: no cover - only triggered in enabled stage3
        raise RuntimeError("DSPy signatures requested but dspy-ai is not installed.") from exc

    class ExtractPaperBasicInfoSignature(dspy.Signature):
        """Extract document metadata from the paper head. Output JSON only."""

        paper_text_head = dspy.InputField()
        source_file = dspy.InputField()
        paper_basic_info_json = dspy.OutputField(
            desc="Return JSON only. Use null for missing facts. Do not invent fields."
        )

    class ExtractGlobalConstantsSignature(dspy.Signature):
        """Extract shared/global constants. Output JSON only."""

        paper_text = dspy.InputField()
        ontology_keys = dspy.InputField()
        paper_basic_info_json = dspy.InputField()
        global_constants_json = dspy.OutputField(
            desc="Return JSON only. Use ontology keys only when supported."
        )

    class ExtractExperimentSeriesSignature(dspy.Signature):
        """Discover experiment series definitions. Output JSON only."""

        paper_text = dspy.InputField()
        figure_summaries = dspy.InputField()
        table_summaries = dspy.InputField()
        ontology_keys = dspy.InputField()
        paper_basic_info_json = dspy.InputField()
        global_constants_json = dspy.InputField()
        experiment_series_json = dspy.OutputField(
            desc="Return JSON only. One list of experiment series."
        )

    class ExtractProcessStepsSignature(dspy.Signature):
        """Extract ordered experimental procedure steps. Output JSON only."""

        procedure_text = dspy.InputField()
        paper_basic_info_json = dspy.InputField()
        process_steps_json = dspy.OutputField(
            desc=(
                "Return JSON only as a JSON list. The input is a methods or procedure section, not the whole paper. "
                "Each item must describe one ordered experimental operation with step_order and evidence_text. "
                "Extract only experimental actions such as weighing, adding, stirring, heating, holding, cooling, filtering, drying, calcining, spinning, or collecting. "
                "Do not output background discussion, spectrum interpretation, or references as steps. "
                "If a quantity is vague like '一定量' or '适量', keep that original text and set needs_manual_review=true. "
                "Split heating, holding, cooling, and reagent-addition operations into separate steps when temperatures, rates, or holding times differ. "
                "Preserve reagent_name, reagent_formula, reagent_amount, reagent_unit, reagent_role, equipment, condition_key, condition_value, condition_unit, duration_value, duration_unit, temperature_value, temperature_unit, heating_rate_value, heating_rate_unit, and product_or_outcome whenever supported by the text. "
                "If no procedure steps are found, return []. Never return null."
            )
        )

    class ExtractDataPointsSignature(dspy.Signature):
        """Extract one series worth of data points. Output JSON only."""

        one_series_json = dspy.InputField()
        relevant_text = dspy.InputField()
        table_summaries = dspy.InputField()
        figure_summaries = dspy.InputField()
        ontology_keys = dspy.InputField()
        data_points_json = dspy.OutputField(
            desc=(
                "Return JSON only as a JSON list. Each item must be an object with keys: "
                "sample_id, sample_label, independent_variable_values, process_parameters, "
                "results, evidence_refs, additional_parameter_records, extended_data. "
                "If there is only one datapoint, still return a one-item JSON list. "
                "If the paper gives multiple values for viscosity, sintering_temperature, "
                "heating_rate, feed_pressure, humidity, channel temperature, batch number, "
                "or other independent variables, split them into multiple datapoint objects. "
                "Use null for missing values and do not invent facts."
            )
        )

    class ExtractEvidenceObjectsSignature(dspy.Signature):
        """Build structured evidence objects. Output JSON only."""

        figures_jsonl_summary = dspy.InputField()
        tables_summary = dspy.InputField()
        captions_and_references = dspy.InputField()
        evidence_objects_json = dspy.OutputField(
            desc="Return JSON only. Each key fact should keep evidence linkage."
        )

    class JudgeExtractionSignature(dspy.Signature):
        """Judge extraction quality against the paper text. Output JSON only."""

        paper_text = dspy.InputField()
        extraction_json = dspy.InputField()
        ontology_keys = dspy.InputField()
        schema_hint = dspy.InputField()
        judge_json = dspy.OutputField(
            desc="Return JSON only with quality issues, missing evidence, and confidence."
        )

    return {
        "ExtractPaperBasicInfoSignature": ExtractPaperBasicInfoSignature,
        "ExtractGlobalConstantsSignature": ExtractGlobalConstantsSignature,
        "ExtractExperimentSeriesSignature": ExtractExperimentSeriesSignature,
        "ExtractProcessStepsSignature": ExtractProcessStepsSignature,
        "ExtractDataPointsSignature": ExtractDataPointsSignature,
        "ExtractEvidenceObjectsSignature": ExtractEvidenceObjectsSignature,
        "JudgeExtractionSignature": JudgeExtractionSignature,
    }
