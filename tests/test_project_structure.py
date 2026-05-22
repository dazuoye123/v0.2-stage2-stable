from pathlib import Path

from alumina_sol_extractor.batch.paths import (
    get_category_figures_all_dir,
    get_category_markdown_path,
    get_category_mineru_raw_dir,
    get_category_output_dir,
    get_category_supplementary_dir,
    get_category_tables_dir,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_stage_directories_exist() -> None:
    src = PROJECT_ROOT / 'src' / 'alumina_sol_extractor'
    for name in ['stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'batch', 'common']:
        assert (src / name).is_dir()


def test_batch_path_helpers_are_category_aware() -> None:
    assert get_category_markdown_path('data/markdown', 'fiber_process', 'paper1') == Path('data/markdown/fiber_process/paper1.md')
    assert get_category_mineru_raw_dir('data/mineru_raw', 'fiber_process', 'paper1') == Path('data/mineru_raw/fiber_process/paper1')
    assert get_category_output_dir('data/outputs', 'fiber_process', 'paper1') == Path('data/outputs/fiber_process/paper1')
    assert get_category_supplementary_dir('data/supplementary', 'fiber_process', 'paper1') == Path('data/supplementary/fiber_process/paper1')
    assert get_category_figures_all_dir('data/outputs', 'fiber_process', 'paper1') == Path('data/outputs/fiber_process/paper1/figures_all')
    assert get_category_tables_dir('data/outputs', 'fiber_process', 'paper1') == Path('data/outputs/fiber_process/paper1/tables')


def test_no_formal_mineru_layout_caption_logic_left_in_source() -> None:
    src = PROJECT_ROOT / 'src' / 'alumina_sol_extractor'
    matches = []
    for path in src.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'mineru_layout_caption' in text:
            matches.append(path)
    assert matches == []
