from __future__ import annotations

import json
from pathlib import Path

from alumina_sol_extractor.models.schema_v2 import PaperBasicInfo, PaperExtractionRecord, PaperExtractionRecordList


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_schema_v2_models_allow_sparse_fields() -> None:
    record = PaperExtractionRecord.model_validate(
        {
            "paper_basic_info": PaperBasicInfo().model_dump(),
            "global_constants": {},
            "experiment_series": [],
            "evidence_objects": [],
        }
    )
    assert record.schema_version == "2.0"
    assert record.paper_basic_info is not None
    assert record.paper_basic_info.authors == []


def test_schema_v2_models_validate_seed_record_json() -> None:
    sample_path = PROJECT_ROOT / "resources" / "stage3_seed" / "extraction_lijianjun_full.schema_v2.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    assert isinstance(sample, list)
    validated = [PaperExtractionRecord.model_validate(item) for item in sample]
    assert validated
    assert validated[0].paper_basic_info is not None
    roundtrip = PaperExtractionRecord.model_validate_json(json.dumps(sample[0], ensure_ascii=False))
    assert roundtrip.paper_basic_info is not None


def test_schema_v2_models_validate_seed_record_list_json() -> None:
    sample_path = PROJECT_ROOT / "resources" / "stage3_seed" / "extraction_lijianjun_full.schema_v2.json"
    validated = PaperExtractionRecordList.model_validate_json(sample_path.read_text(encoding="utf-8"))
    assert len(validated.root) >= 1
