# Stage4 / Stage4A Structure Audit

## Current official execution path

The current public full-pipeline entrypoint is still:

1. `scripts/run_full_pipeline.py`
2. `run_full_pipeline(...)`
3. `alumina_sol_extractor.pipeline.full_pipeline_runner.run_stage6c_full_resume(...)`
4. `alumina_sol_extractor.pipeline.full_pipeline_runner._execute_full_resume_plan(...)`
5. Stage 4 execution inside `full_pipeline_runner`
6. `alumina_sol_extractor.stage4.extractor.Stage4VisionSpectraExtractor.run()`

The `stage6c` naming remains for backward compatibility, but Stage 4 itself should be treated as a normal official stage rather than a special resume-only branch.

## Core conclusion

The repository already contains the correct Stage 4 technical direction:

- Stage 2-selected figures
- `universal_compact` routing
- figure-level dedup
- `stage3_twopass`
- `stage4_vision_spectra_universal`

However, before this refactor, those behaviors were still concentrated in `scripts/dev/` and had not fully replaced the historical Stage 4A orchestration path in the official pipeline entrypoints.

## Target structure

- `scripts/run_full_pipeline.py`
- `scripts/run_stage4_batch.py`
- `src/alumina_sol_extractor/stage4/extractor.py`
- `src/alumina_sol_extractor/stage4/batch_runner.py`
- `src/alumina_sol_extractor/stage4/stage2_selected_loader.py`
- `src/alumina_sol_extractor/stage4/processed_index.py`
- `docs/RUN_FULL_PIPELINE.md`
- `docs/RUN_STAGE4_BATCH.md`

## Legacy material to downgrade later

The following areas should not remain user-facing primary workflow entrypoints:

- `scripts/dev/run_stage4a_batch.py`
- `scripts/dev/run_stage4a_stage2_selected_batch.py`
- `scripts/dev/continue_stage4a_full_eligible_live.py`
- `scripts/dev/rerun_stage4a_from_manifest.py`
- `scripts/dev/replay_stage4a_*.py`
- `docs/refactor/STAGE4A_*`

These can remain temporarily for compatibility or maintenance, but should eventually be archived out of the main execution surface.
