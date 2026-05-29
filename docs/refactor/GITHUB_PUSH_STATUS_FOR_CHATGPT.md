# GitHub Push Status For ChatGPT

- repository URL: `https://github.com/dazuoye123/v0.2-stage2-stable.git`
- repository full name: `dazuoye123/v0.2-stage2-stable`
- branch name: `feature/full-pipeline-link-aware-fixes`
- latest commit hash: `417d81a45e94369ec3dad1349bc8bf2132819e64`
- push success: `false`
- push failure reason: `schannel: failed to receive handshake, SSL/TLS connection failed`

## Stage 4A Related Files

Tracked Stage 4A / stage4 / spectra / vision / vlm files count: `74`

Tracked files:

- `configs/examples/stage4_expected_peaks_niu_yanqiang_example.json`
- `scripts/dev/review_stage4_vision_spectra.py`
- `scripts/reparse_stage4_vlm_outputs.py`
- `scripts/run_stage4_vision_spectra_smoke_test.py`
- `src/alumina_sol_extractor/dataset_fusion/spectra_units.py`
- `src/alumina_sol_extractor/stage2/vision_selector.py`
- `src/alumina_sol_extractor/stage4/__init__.py`
- `src/alumina_sol_extractor/stage4/extractor.py`
- `src/alumina_sol_extractor/stage4/io.py`
- `src/alumina_sol_extractor/stage4/normalization.py`
- `src/alumina_sol_extractor/stage4/prompt_templates.py`
- `src/alumina_sol_extractor/stage4/quality_review.py`
- `src/alumina_sol_extractor/stage4/reparse.py`
- `src/alumina_sol_extractor/stage4/routing.py`
- `src/alumina_sol_extractor/stage4/schemas.py`
- `src/alumina_sol_extractor/stage4/stage4_context.py`
- `src/alumina_sol_extractor/stage4/stage4_failures.py`
- `src/alumina_sol_extractor/stage4/validators.py`
- `src/alumina_sol_extractor/stage4/vlm_client.py`
- `src/alumina_sol_extractor/stage5/dataset_fusion/spectra_units.py`
- `src/alumina_sol_extractor/vision/__init__.py`
- `src/alumina_sol_extractor/vision/bbox_fragment_stitcher.py`
- `src/alumina_sol_extractor/vision/clip_prefilter.py`
- `src/alumina_sol_extractor/vision/figure_filter.py`
- `src/alumina_sol_extractor/vision/figure_fragment_merger.py`
- `src/alumina_sol_extractor/vision/resnet_classifier.py`
- `src/alumina_sol_extractor/vision/review_rules.py`
- `src/alumina_sol_extractor/vision/taxonomy_classifier.py`
- `src/alumina_sol_extractor/vision/taxonomy_config.py`
- `src/alumina_sol_extractor/vision/vision_selector.py`
- `src/alumina_sol_extractor/vision_spectra/__init__.py`
- `src/alumina_sol_extractor/vision_spectra/extractor.py`
- `src/alumina_sol_extractor/vision_spectra/io.py`
- `src/alumina_sol_extractor/vision_spectra/normalization.py`
- `src/alumina_sol_extractor/vision_spectra/prompt_templates.py`
- `src/alumina_sol_extractor/vision_spectra/quality_review.py`
- `src/alumina_sol_extractor/vision_spectra/reparse.py`
- `src/alumina_sol_extractor/vision_spectra/routing.py`
- `src/alumina_sol_extractor/vision_spectra/schemas.py`
- `src/alumina_sol_extractor/vision_spectra/stage4_context.py`
- `src/alumina_sol_extractor/vision_spectra/stage4_failures.py`
- `src/alumina_sol_extractor/vision_spectra/validators.py`
- `src/alumina_sol_extractor/vision_spectra/vlm_client.py`
- `tests/test_sample_matrix_spectra_links.py`
- `tests/test_send_to_vision_rules.py`
- `tests/test_stage3_list_valued_spectral_parameters.py`
- `tests/test_stage4_candidate_selection.py`
- `tests/test_stage4_context_assembly.py`
- `tests/test_stage4_dry_run.py`
- `tests/test_stage4_failed_record_handling.py`
- `tests/test_stage4_figure_id_selection.py`
- `tests/test_stage4_json_parser.py`
- `tests/test_stage4_live_response_parsing.py`
- `tests/test_stage4_prompt_includes_text_context.py`
- `tests/test_stage4_prompt_routing.py`
- `tests/test_stage4_quality_review.py`
- `tests/test_stage4_schemas.py`
- `tests/test_stage4a_conservative_normalization.py`
- `tests/test_stage4a_ferron_rich_output.py`
- `tests/test_stage4a_live_multiphase_prompt_contract.py`
- `tests/test_stage4a_microscopy_rich_output.py`
- `tests/test_stage4a_nmr_rich_output.py`
- `tests/test_stage4a_prompt_contract.py`
- `tests/test_stage4a_reparse_raw_outputs.py`
- `tests/test_stage4a_reuse_previous_success.py`
- `tests/test_stage4a_thermal_rich_output.py`
- `tests/test_stage4a_transient_failure_summary.py`
- `tests/test_stage4a_vibrational_rich_output.py`
- `tests/test_stage4a_vlm_output_normalization.py`
- `tests/test_stage4a_vlm_retry.py`
- `tests/test_stage4a_vlm_timeout_config.py`
- `tests/test_stage4a_xrd_rich_peaks_prompt.py`
- `tests/test_stage5_linking_spectra_peaks.py`
- `tests/test_stage5_spectra_link_sanity.py`

## Tracking Status

- Stage 4A related files already tracked by git: `true`
- Stage 4A related files still untracked: `false`

## Safety Confirmation

- confirmed not committed: `data/outputs`
- confirmed not committed: `data/markdown`
- confirmed not committed: `data/mineru_raw`
- confirmed not committed: `*.png`
- confirmed not committed: `*.jpg`
- confirmed not committed: `*.jpeg`
- confirmed not committed: `*.webp`
- confirmed not committed: `*.pdf`
- confirmed not committed: `.env`

## What ChatGPT Should Review

- repo: `dazuoye123/v0.2-stage2-stable`
- branch: `feature/full-pipeline-link-aware-fixes`
- commit: `417d81a45e94369ec3dad1349bc8bf2132819e64`

Note: the local branch contains the latest source commit, but the attempted push failed due to an HTTPS/TLS handshake problem on this machine, so GitHub may still lag behind the local commit until push succeeds.
