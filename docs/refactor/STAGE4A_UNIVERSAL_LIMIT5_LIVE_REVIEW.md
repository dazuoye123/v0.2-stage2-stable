# Stage4A Universal Limit5 Live Review

- ???? VLM: ?
- ???? Stage4A live: ???? 5 ?
- ?????: 5
- ?????: 0
- total_candidate_figures: 100
- total_successful_extractions: 26
- total_failed_records: 14
- actual_figure_type ??: {"unknown": 1, "sem_image": 13, "tg_curve": 1, "tem_image": 4, "tg_dsc_curve": 3, "nmr_spectrum": 2, "microscopy": 1, "xrd_pattern": 1}
- type_mismatch_count: 4
- needs_manual_review_count: 1
- schema_validation_failed_count: 14
- vlm_timeout_count: 0
- previous_success_fallback_count: 0
- suspected_hallucination_count: 0
- SEM/TEM ???????: 0
- range_peak_midpoint_error_count: 0
- unknown/generic rescued by caption: 1

## ??

- universal_compact live ??????actual_figure_type ?? schema ???????
- stage2/stage3 ????????? metadata ?? XRD ?????? chemical equation ?????? UnknownFigureExtraction?
- ??????????????? live ????? schema ??????? 14 ???????? `band_assignments`?`phase_assignments`?`diameter_range`?thermal peak list ??????
- ?????????? limit20????? prompt/schema ????? limit10?

## ??

- 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维: live=2, failed_records=0, type_mismatch=1, rescued_unknown=0, main_issue=none
- 004_Sol-Gel法制备新型多晶钇-铝石榴石纤维: live=4, failed_records=4, type_mismatch=2, rescued_unknown=1, main_issue=schema_validation_failed
- 005_α-A12O3连续纤维的制备与表征: live=5, failed_records=5, type_mismatch=1, rescued_unknown=0, main_issue=schema_validation_failed
- 009_含硅氧化物连续纤维的制备及其性质的研究: live=8, failed_records=2, type_mismatch=0, rescued_unknown=0, main_issue=schema_validation_failed
- 010_含硼氧化铝基陶瓷连续纤维的制备及表征: live=7, failed_records=3, type_mismatch=0, rescued_unknown=0, main_issue=schema_validation_failed
