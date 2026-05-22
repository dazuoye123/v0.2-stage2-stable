from importlib import import_module


def test_old_imports_still_work() -> None:
    modules = [
        'alumina_sol_extractor.pipeline.stage2_figure_pipeline',
        'alumina_sol_extractor.utils.figure_utils',
        'alumina_sol_extractor.pdf.mineru_layout_parser',
        'alumina_sol_extractor.vision.clip_prefilter',
        'alumina_sol_extractor.vision.resnet_classifier',
        'alumina_sol_extractor.figures.caption_extractor',
        'alumina_sol_extractor.figures.caption_assignment',
        'alumina_sol_extractor.dataset_fusion',
        'alumina_sol_extractor.linking',
    ]
    for name in modules:
        assert import_module(name)


def test_wrapper_exports_point_to_stage_modules() -> None:
    from alumina_sol_extractor.pipeline.stage2_figure_pipeline import run_stage2_figure_pipeline as old_run_stage2_figure_pipeline
    from alumina_sol_extractor.stage2.pipeline import run_stage2_figure_pipeline as new_run_stage2_figure_pipeline
    from alumina_sol_extractor.utils.figure_utils import find_figures_in_markdown_any as old_find_figures
    from alumina_sol_extractor.stage2.figure_discovery import find_figures_in_markdown_any as new_find_figures
    from alumina_sol_extractor.pdf.mineru_layout_parser import load_mineru_image_layout as old_load_layout
    from alumina_sol_extractor.stage2.mineru_layout_parser import load_mineru_image_layout as new_load_layout

    assert old_run_stage2_figure_pipeline is new_run_stage2_figure_pipeline
    assert old_find_figures is new_find_figures
    assert old_load_layout is new_load_layout
