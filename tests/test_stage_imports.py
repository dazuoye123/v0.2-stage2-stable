from importlib import import_module


def test_new_stage_imports() -> None:
    modules = [
        'alumina_sol_extractor.stage1.pdf_to_markdown',
        'alumina_sol_extractor.stage1.mineru_pdf_to_markdown',
        'alumina_sol_extractor.stage2.pipeline',
        'alumina_sol_extractor.stage2.figure_discovery',
        'alumina_sol_extractor.stage2.caption_extractor',
        'alumina_sol_extractor.stage2.caption_assignment',
        'alumina_sol_extractor.stage2.mineru_layout_parser',
        'alumina_sol_extractor.stage2.figure_filter',
        'alumina_sol_extractor.stage2.clip_prefilter',
        'alumina_sol_extractor.stage2.resnet_classifier',
        'alumina_sol_extractor.stage3.pipeline',
        'alumina_sol_extractor.stage4.extractor',
        'alumina_sol_extractor.stage5',
        'alumina_sol_extractor.batch.categories',
    ]
    for name in modules:
        assert import_module(name)
