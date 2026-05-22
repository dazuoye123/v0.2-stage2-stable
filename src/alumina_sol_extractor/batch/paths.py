"""Category-aware batch path helpers."""

from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.batch.categories import normalize_batch_category


def _base_dir(root: str | Path, category: str, paper_id: str) -> Path:
    return Path(root) / normalize_batch_category(category) / paper_id


def get_category_markdown_path(markdown_dir: str | Path, category: str, paper_id: str) -> Path:
    return _base_dir(markdown_dir, category, paper_id).with_suffix('.md')


def get_category_mineru_raw_dir(mineru_raw_dir: str | Path, category: str, paper_id: str) -> Path:
    return _base_dir(mineru_raw_dir, category, paper_id)


def get_category_output_dir(outputs_dir: str | Path, category: str, paper_id: str) -> Path:
    return _base_dir(outputs_dir, category, paper_id)


def get_category_supplementary_dir(supplementary_dir: str | Path, category: str, paper_id: str) -> Path:
    return _base_dir(supplementary_dir, category, paper_id)


def get_category_figures_all_dir(outputs_dir: str | Path, category: str, paper_id: str) -> Path:
    return get_category_output_dir(outputs_dir, category, paper_id) / 'figures_all'


def get_category_tables_dir(outputs_dir: str | Path, category: str, paper_id: str) -> Path:
    return get_category_output_dir(outputs_dir, category, paper_id) / 'tables'


__all__ = [
    'get_category_markdown_path',
    'get_category_mineru_raw_dir',
    'get_category_output_dir',
    'get_category_supplementary_dir',
    'get_category_figures_all_dir',
    'get_category_tables_dir',
]
