# Stage4A Figure-Level Dedup Audit

## Findings

- Duplicate-send risk existed before this fix.
- The risk was not in Stage5 or paper-level review; it was in Stage4A resume paths that only looked at `stage4a_summary.json` and paper-level skip flags.
- `run_stage4a_batch.py` originally treated `skip_existing` at the paper level. If a paper had any existing summary and the caller used `force=True` / `skip_existing=False`, partially completed papers could re-enter extraction without a figure-level guard.
- `continue_stage4a_full_eligible_live.py` originally classified papers by summary state only. It did not distinguish `live_success`, `raw_vlm_only`, `schema_failed`, `transient_failed`, and `dry_run_only` at the figure level.
- `Stage4VisionSpectraExtractor.run()` also overwrote stage4 output files from the current pass only. That meant a partial rerun could both resend already-successful figures and overwrite previous success/failure ledgers.

## Risk Conditions

- Highest duplicate VLM risk: `force=True` + `skip_existing=False` on a paper with mixed state (some figures already live-successful, some still dry-run-only or failed).
- Dry-run-only directories were a second risk: `stage4a_summary.json` existed, but `live_count=0`, so the paper was not actually complete. Those figures still need live processing and must not be confused with prior success.
- Figures with `raw_vlm_outputs.jsonl` but no successful extraction should be replayed offline first, not resent to VLM.

## Files Updated

- `src/alumina_sol_extractor/stage4/processed_index.py`
- `src/alumina_sol_extractor/stage4/extractor.py`
- `src/alumina_sol_extractor/stage4/validators.py`
- `scripts/dev/run_stage4a_batch.py`
- `scripts/dev/continue_stage4a_full_eligible_live.py`
- `tests/test_stage4_figure_level_dedup.py`
- `tests/test_stage4_batch_runner.py`
- `tests/test_stage4_universal_routing.py`
- `tests/test_stage4a_reuse_previous_success.py`

## Current Counts From Audit-Only Scan

- total_papers_scanned: 343
- total_candidate_figures: 4981
- current live-success figures already protected from rerun: 156
- replayable raw-VLM-only figures: 1
- duplicate VLM calls now prevented by figure-level dedup: 157
- figures that would still go to VLM if resumed now (excluding deferred 032): 4345
- deferred figures in 032 only: 109

## Conclusion

- Duplicate-send risk was real before the fix.
- After the fix, successful figure IDs/image paths are protected even when a caller uses `force=True` to reopen a partially completed paper.
- Raw VLM outputs are now classified as replay candidates rather than automatic rerun candidates.
