"""Small task-specific DSPy modules for staged extraction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .json_utils import safe_json_loads
from .signatures import get_signatures


@dataclass(slots=True)
class ModuleResult:
    payload: object | None
    error: str | None = None
    raw_output: str | None = None


class _BaseDSPyModule:
    signature_name: str
    output_field: str

    def __init__(self) -> None:
        try:
            import dspy  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("dspy-ai is required only when Stage 3 is enabled.") from exc
        signatures = get_signatures()
        self.predictor = dspy.Predict(signatures[self.signature_name])

    def run(self, **kwargs: Any) -> ModuleResult:
        prediction = self.predictor(**kwargs)
        raw_output = getattr(prediction, self.output_field, "")
        payload, error = safe_json_loads(raw_output)
        return ModuleResult(payload=payload, error=error, raw_output=raw_output)


class ExtractPaperBasicInfoModule(_BaseDSPyModule):
    signature_name = "ExtractPaperBasicInfoSignature"
    output_field = "paper_basic_info_json"


class ExtractGlobalConstantsModule(_BaseDSPyModule):
    signature_name = "ExtractGlobalConstantsSignature"
    output_field = "global_constants_json"


class ExtractExperimentSeriesModule(_BaseDSPyModule):
    signature_name = "ExtractExperimentSeriesSignature"
    output_field = "experiment_series_json"


class ExtractProcessStepsModule(_BaseDSPyModule):
    signature_name = "ExtractProcessStepsSignature"
    output_field = "process_steps_json"


class ExtractDataPointsModule(_BaseDSPyModule):
    signature_name = "ExtractDataPointsSignature"
    output_field = "data_points_json"


class ExtractEvidenceObjectsModule(_BaseDSPyModule):
    signature_name = "ExtractEvidenceObjectsSignature"
    output_field = "evidence_objects_json"


class JudgeExtractionModule(_BaseDSPyModule):
    signature_name = "JudgeExtractionSignature"
    output_field = "judge_json"


def to_json_text(data: Any) -> str:
    """Compact JSON dump for prompt inputs."""
    return json.dumps(data, ensure_ascii=False, indent=2)
