"""Data models used by alumina_sol_extractor."""

from alumina_sol_extractor.models.figure import FigureInfo
from alumina_sol_extractor.models.schema_v2 import PaperExtractionRecord, PaperExtractionRecordList
from alumina_sol_extractor.models.table import TableInfo

__all__ = ["FigureInfo", "TableInfo", "PaperExtractionRecord", "PaperExtractionRecordList"]
