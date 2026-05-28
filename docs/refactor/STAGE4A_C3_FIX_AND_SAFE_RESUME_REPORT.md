# Stage4A C3 Fix And Safe Resume Report

- vlm_used_for_c3_fix: false
- new_stage4a_live_run_for_c3_fix: false
- stage5_run: false
- replay_materialized: true
- compileall_passed: true
- pytest_passed: true
- live_only_v2_after_fix: A=23, B=16, C=0, D=0
- full_eligible_continue_attempted: true
- full_eligible_new_completed_papers: 0
- defer_032: true

## C=3 Papers Before Fix

1. fiber_process / 013_????????????????????
   - reason: schema_validation_failed
2. fiber_process / 014_????????????????
   - reason: range_peak_midpoint_error
3. mechanism / 093_Bradley?Hanna - 1993 - Aluminium-27 MAS NMR investigations of sodium aluminates formed from high pH solutions Evidence of
   - reason: minor_failed_records

## What Was Fixed

- schema_validation_failed was repaired offline by replaying existing raw_vlm_outputs with the current universal normalization.
- range peaks are now preserved as source_text with position=null and warning `range_peak_position_not_numeric`; midpoint conversion is not allowed.
- minor_failed_records were retained as warning-level review items instead of hard-C blockers.
- formal `stage4_vision_spectra_universal` outputs were updated in place after backup.
- safe full-eligible resume script was rewritten from scratch and no longer depends on the corrupted `continue_stage4a_runlive_excluding032.py`.

## Formal Output Materialization

- updated_formal_stage4_dir: true
- backup_dir_pattern: `_backup_before_C3_replay_<timestamp>`
- backed_up_files_per_paper:
  - spectra_extractions.jsonl
  - spectra_failed_records.jsonl
  - stage4a_summary.json
  - stage4a_validation_report.md

## Live-Only Review Outcome After Fix

- schema_validation_failed_count: 0
- range_peak_midpoint_error_count: 0
- D_count: 0
- C_count: 0
- remaining_minor_failed_records: 2 papers reviewed as B-level warning, not hard blockers

## Safe Resume Script

- new_script: `scripts/dev/continue_stage4a_full_eligible_live.py`
- broken_script_reused: false
- completion_rule:
  - live_count > 0
  - failed_record_count == 0
  - successful_extractions_count > 0
- dry_run_only_is_not_success: true
- default_defer_032: true
- chunk_size: 10

## Full Eligible Continue Attempt

- continue_started: true
- result: paused_after_stall
- stall_reason: no new stage4 output writes for more than 30 minutes on chunk_001
- stage5_entered: false
- recommended_resume_command:

```powershell
python .\scripts\dev\continue_stage4a_full_eligible_live.py
```
