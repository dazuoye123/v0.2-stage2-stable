from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .io import write_frame, write_json


def export_source_data(frame: pd.DataFrame, output_path: Path) -> Path:
    return write_frame(output_path, frame)


def export_figure_data(payload: dict[str, Any], output_path: Path) -> Path:
    return write_json(output_path, payload)
