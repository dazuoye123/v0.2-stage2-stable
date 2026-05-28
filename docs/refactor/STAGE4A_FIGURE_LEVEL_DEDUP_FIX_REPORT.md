# Stage4A Figure-Level Dedup Fix Report

- generated_at: 2026-05-28T11:13:43
- vlm_called: no
- audit_only_run: yes

## What Was Fixed

- Added a figure-level processed index that reads existing `spectra_extractions.jsonl`, `raw_vlm_outputs.jsonl`, `spectra_failed_records.jsonl`, and `stage4a_summary.json`.
- Live-success figures are now identified by figure ID and image path and are never re-sent to VLM on resume.
- Dry-run-only papers are no longer treated as successful; `live_count=0` keeps them eligible for future live processing.
- Figures with replayable raw VLM outputs are routed to replay candidates instead of live rerun candidates.
- `force=True` now reopens dry-run-only / partial papers without bypassing figure-level live-success protection.
- The extractor now merges new partial results into existing stage4 files instead of overwriting prior successful figures.

## Audit-Only Results

- total_papers_scanned: 343
- total_candidate_figures: 4981
- live_success_figures: 156
- dry_run_only_figures: 1634
- raw_vlm_only_figures: 1
- failed_figures: 2
- remaining_figures_to_send_vlm (excluding deferred 032): 4345
- duplicate_vlm_prevented_count: 157
- papers_with_partial_live_outputs: 31
- papers_with_dry_run_only_outputs: 231
- papers_with_replay_candidates: 1
- papers_with_transient_rerun_candidates: 0
- papers_with_missing_image_path: 125
- deferred_remaining_figures (032 only): 109

## Resume Safety

- If live resume continues now, already-successful figures will stay out of `remaining_figures_to_send_vlm`.
- `raw_vlm_outputs.jsonl` is preferred for replay whenever a replayable response exists.
- 032 remains deferred and is excluded from current live-send counts.

## Next Safe Step

- The correct next step is to resume Stage4A live with the new figure-level dedup in place.
- That resume should use the fixed `scripts/dev/continue_stage4a_full_eligible_live.py` and not the old per-paper-only behavior.
