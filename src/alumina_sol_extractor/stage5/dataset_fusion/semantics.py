from __future__ import annotations

from pathlib import Path
from typing import Any

OFFICIAL_PAPER_CATEGORIES = ("mechanism", "fiber_process", "applications", "rheology")
OFFICIAL_PAPER_CATEGORY_SET = set(OFFICIAL_PAPER_CATEGORIES)

METADATA_OR_BOOKKEEPING_KEYS = {
    "axis_label",
    "caption",
    "comment",
    "condition",
    "context",
    "description_only",
    "evidence",
    "evidence_ref",
    "evidence_reference",
    "experiment_series",
    "parent_series_id",
    "figure_id",
    "index",
    "key",
    "label",
    "legend",
    "material_system",
    "metadata",
    "notes",
    "parameter",
    "raw_value",
    "record_id",
    "row_id",
    "sample_id",
    "sample_label",
    "series",
    "series_id",
    "series_name",
    "series_ref",
    "source_id",
    "source_text",
    "table_id",
    "unit",
    "value",
    "variables",
    "x_label",
    "y_label",
}

METADATA_SCOPE_HINTS = (
    "bookkeeping",
    "extended_data.parent_series_id",
    "extended_data.series_id",
    "extended_data.unclassified_results",
)

TRUE_PARAMETER_KEYS = {
    "acid_type",
    "acid_to_aluminum_ratio",
    "aging_temperature_c",
    "aging_time_h",
    "air_gap_cm",
    "al_concentration_mol_l",
    "al_concentration_mol_per_l",
    "al13_fraction_percent",
    "aluminum_source",
    "applied_voltage_kv",
    "average_fiber_diameter_um",
    "base_to_aluminum_ratio",
    "bet_surface_area_m2_g",
    "base_type",
    "calcination_temperature_c",
    "calcination_time_h",
    "chelating_agent",
    "coating_sintering_temperature_c",
    "collector_distance_cm",
    "concentration_temperature_c",
    "concentration_time_h",
    "density_g_cm3",
    "density_kg_m3",
    "dopant",
    "drying_temperature_c",
    "drying_time_h",
    "elongation_at_break_percent",
    "feed_rate_ml_h",
    "fiber_diameter_um",
    "flow_rate_ml_h",
    "gel_time_h",
    "heating_rate_c_min",
    "holding_temperature_c",
    "holding_time_h",
    "hydrolysis_temperature_c",
    "hydrolysis_time_h",
    "mechanical_strength_mpa",
    "modulus_gpa",
    "particle_size_nm",
    "peptization_temperature_c",
    "peptization_time_h",
    "ph",
    "pore_volume_cm3_g",
    "porosity_percent",
    "precursor",
    "relative_humidity_percent",
    "sintering_temperature_c",
    "sintering_time_h",
    "solid_content_percent",
    "solid_content_wt_percent",
    "solvent",
    "specific_surface_area_m2_g",
    "spinneret_hole_diameter_mm",
    "spinning_rate_m_min",
    "spinnability",
    "stabilizer",
    "stirring_speed_rpm",
    "take_up_speed_m_min",
    "target_temperature_c",
    "tensile_strength_mpa",
    "thermal_conductivity_w_m_k",
    "withdrawal_speed_m_min",
    "viscosity_mpa_s",
    "viscosity_pa_s",
    "zeta_potential_mv",
}

TRUE_PARAMETER_KEY_SUBSTRINGS = (
    "acid",
    "additive",
    "agent",
    "aging",
    "aluminum",
    "base",
    "calcination",
    "chelating",
    "collector_distance",
    "concentration",
    "content",
    "diameter",
    "dopant",
    "drying",
    "feed_rate",
    "fiber",
    "fraction",
    "gel_time",
    "heating_rate",
    "holding",
    "hydrolysis",
    "humidity",
    "particle_size",
    "peptization",
    "ph",
    "porosity",
    "potential",
    "precursor",
    "rheology",
    "sintering",
    "solid_content",
    "solvent",
    "spinneret",
    "spinnability",
    "stabilizer",
    "stirring_speed",
    "strength",
    "take_up_speed",
    "temperature",
    "time",
    "viscosity",
)

CHARACTERIZATION_OUTPUT_KEYS = {
    "xrd_peak_position_2theta_deg",
    "ftir_peak_position_cm_1",
    "nmr_27al_peak_position_ppm",
    "nmr_27Al_peak_position_ppm",
    "raman_peak_position_cm_1",
    "dsc_peak_temperature_c",
    "tg_mass_loss_percent",
}

CHARACTERIZATION_CATEGORY_HINTS = {
    "spectra",
    "spectroscopy",
    "spectral_feature",
    "figure_observation",
    "performance",
}


def normalize_official_paper_category(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text if text in OFFICIAL_PAPER_CATEGORY_SET else ""


def resolve_paper_identity_from_dir(paper_dir: Path) -> dict[str, str]:
    paper_dir = Path(paper_dir)
    parent_category = normalize_official_paper_category(paper_dir.parent.name)
    if parent_category:
        status = "official"
        category = parent_category
    else:
        status = "missing_or_non_primary"
        category = ""
    return {
        "paper_id": paper_dir.name,
        "paper_category": category,
        "paper_category_status": status,
        "paper_dir": str(paper_dir.resolve()),
    }


def resolve_paper_identity_from_final_dataset_dir(final_dataset_dir: Path) -> dict[str, str]:
    final_dataset_dir = Path(final_dataset_dir)
    return resolve_paper_identity_from_dir(final_dataset_dir.parent)


def build_qualified_paper_id(paper_identity: dict[str, Any] | None, paper_id: Any) -> str:
    paper_text = str(paper_id or "").strip()
    if not paper_text:
        return ""
    category = normalize_official_paper_category((paper_identity or {}).get("paper_category"))
    return f"{category}/{paper_text}" if category else paper_text


def is_metadata_or_bookkeeping_key(value: Any) -> bool:
    key = str(value or "").strip().lower()
    if not key:
        return False
    if key in METADATA_OR_BOOKKEEPING_KEYS:
        return True
    if key.endswith("_id") or key.endswith("_ids"):
        return True
    return any(token in key for token in ("figure_id", "table_id", "series_id", "parent_series"))


def is_true_parameter_key(value: Any) -> bool:
    key = str(value or "").strip().lower()
    if not key:
        return False
    if key in TRUE_PARAMETER_KEYS:
        return True
    return any(token in key for token in TRUE_PARAMETER_KEY_SUBSTRINGS)


def classify_parameter_semantic_role(
    *,
    canonical_key: Any,
    source_scope: Any,
    local_category: Any = None,
    source_category: Any = None,
    normalization_note: Any = None,
) -> tuple[str, bool, str]:
    key = str(canonical_key or "").strip()
    key_lower = key.lower()
    scope = str(source_scope or "").strip().lower()
    local = str(local_category or "").strip().lower()
    source = str(source_category or "").strip().lower()
    note = str(normalization_note or "").strip().lower()
    whitelist_hit = is_true_parameter_key(key_lower)

    if not key and ("value_only" in note or scope.endswith(".value")):
        return "metadata_or_bookkeeping", False, "value_only_row"
    if is_metadata_or_bookkeeping_key(key_lower):
        return "metadata_or_bookkeeping", False, "metadata_like_key"

    if scope.startswith("stage4.spectra.peaks"):
        return "characterization_output", False, "characterization_peak_from_stage4"
    if key_lower in {item.lower() for item in CHARACTERIZATION_OUTPUT_KEYS}:
        return "characterization_output", False, "characterization_output_key"
    if any(token in key_lower for token in ("xrd_peak", "ftir_peak", "raman_peak", "nmr_", "peak_position", "peak_intensity", "chemical_shift", "dsc_", "tg_", "thermal_event")):
        return "characterization_output", False, "characterization_output_key"
    if any(token in local for token in CHARACTERIZATION_CATEGORY_HINTS) or any(token in source for token in CHARACTERIZATION_CATEGORY_HINTS):
        return "characterization_output", False, "characterization_output_category"
    if "stage5_derived_from_stage4_spectra_peak" in note:
        return "characterization_output", False, "characterization_derived_peak_row"
    if not whitelist_hit and any(token in scope for token in METADATA_SCOPE_HINTS):
        return "metadata_or_bookkeeping", False, "bookkeeping_scope"
    if scope.endswith(".value") and not whitelist_hit:
        return "metadata_or_bookkeeping", False, "value_only_row"

    if not key:
        return "unknown", False, "missing_canonical_key"
    return "synthesis_process_property", True, ""
