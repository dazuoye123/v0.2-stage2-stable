"""Small JSONL helpers reused by figure writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Any


def write_jsonl(records: Iterable[Mapping[str, Any]], output_path: Path) -> Path:
    """Write iterable mapping records to a UTF-8 JSONL file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_obj:
        for record in records:
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path
