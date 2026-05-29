# Stage4/Stage5 Autorun Progress Report

- Generated at: 2026-05-28T00:14:35
- Stage4A remaining chunk execution was paused conservatively after a long no-write window; Stage3 remaining_all was not touched.

## Current Stage4A Status
- manifest_total_count: 343
- completed_stage3_twopass_count: 343
- missing_stage3_twopass_count: 0
- eligible_stage4a_count: 270
- completed_stage4a_universal_count: 39
- remaining_stage4a_eligible_count: 231
- no_candidate_figures_count: 73
- total_successful_extractions: 156
- total_failed_records: 2
- schema_validation_failed_count: 0
- previous_success_fallback_count: 0
- type_mismatch_count: 6
- rescued_unknown_generic_count: 14
- needs_manual_review_count: 1
- suspected_hallucination_count: 0
- sem_tem_unscaled_diameter_error_count: 0
- range_peak_midpoint_error_count: 0
- xrd_reference_tick_as_peak_error_count: 0
- chunk1_completed_count: 4

## Last Successful Paper
- {"category": "fiber_process", "paper_id": "029_无机酸铝体系氧化铝连续纤维的制备技术研究", "time": "2026-05-28T00:00:06"}

## Pause Reason
- chunk_001_no_new_writes_for_12m_possible_timeout_or_long_stall

## Resume Assets
- Remaining selected CSV: `G:\paper\Al-gel-sol\alumina_sol_extractor\data\batch_validation_reports\stage4a_universal_remaining_after_pause_selected_papers.csv`
- Remaining paper IDs: `G:\paper\Al-gel-sol\alumina_sol_extractor\data\batch_validation_reports\stage4a_universal_remaining_after_pause_paper_ids.txt`
- Waiting Stage3 list: `G:\paper\Al-gel-sol\alumina_sol_extractor\data\batch_validation_reports\stage4a_waiting_for_stage3_missing_papers.csv`

## Resume Command
```powershell
python -c "from pathlib import Path; import sys; root=Path(r'G:\\paper\\Al-gel-sol\\alumina_sol_extractor'); sys.path.insert(0, str(root / 'src')); from scripts.dev.run_stage4a_batch import run_stage4a_batch; paper_ids=[line.strip() for line in (root / 'data' / 'batch_validation_reports' / 'stage4a_universal_remaining_after_pause_paper_ids.txt').read_text(encoding='utf-8').splitlines() if line.strip()][:10]; run_stage4a_batch(manifest=root / 'data' / 'batch_manifest' / 'source_manifest.csv', outputs_dir=root / 'data' / 'outputs', report_dir=root / 'data' / 'batch_validation_reports' / 'stage4a_universal_resume_limit10', paper_ids=paper_ids, stage3_subdir='stage3_twopass', stage4_subdir='stage4_vision_spectra_universal', routing_mode='universal_compact', dry_run=False, force=False, continue_on_error=True, estimate_only=False, max_figures_per_paper=10, skip_existing=True)"
```