"""Stage 3 deterministic merge, normalization, and validation helpers."""

from .merge import merge_stage_outputs_to_paper_record
from .normalization import (
    collect_parameter_records,
    normalize_parameter_records,
    reject_noncanonical_records,
    validate_canonical_keys,
)
from .report import build_stage3_validation_report
from .validators import (
    build_quality_flags,
    validate_evidence_refs,
    validate_id_uniqueness,
    validate_no_core_keys_in_extended_data,
    validate_units_against_ontology,
)

__all__ = [
    "build_quality_flags",
    "build_stage3_validation_report",
    "collect_parameter_records",
    "merge_stage_outputs_to_paper_record",
    "normalize_parameter_records",
    "reject_noncanonical_records",
    "validate_canonical_keys",
    "validate_evidence_refs",
    "validate_id_uniqueness",
    "validate_no_core_keys_in_extended_data",
    "validate_units_against_ontology",
]
