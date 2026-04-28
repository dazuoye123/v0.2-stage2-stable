"""Table metadata model."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TableInfo:
    """Metadata for one table extracted from MinerU Markdown."""

    paper_id: str
    table_id: str
    csv_path: str
    json_path: str
    position: int
    rows: int
    columns: int
    caption: str = ""
    context_before: str = ""
    context_after: str = ""

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)
