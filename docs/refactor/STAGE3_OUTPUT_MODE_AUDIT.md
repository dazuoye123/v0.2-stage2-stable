# Stage 3 Output Mode Audit

## Scope

Audit current `data/outputs/<category>/<paper_id>/stage3/stage3_summary.json` modes and compare them against the historical `stage3_limit10` batch report.

## Current stage3/ mode counts

- total scanned summaries: 134
- mode counts: two-pass=134

## stage3_limit10 papers current mode status

| category | paper_id | report_mode | current stage3_summary mode | status |
| --- | --- | --- | --- | --- |
| fiber_process | 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 005_α-A12O3连续纤维的制备与表征 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 009_含硅氧化物连续纤维的制备及其性质的研究 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 013_多孔莫来石纤维基隔热陶瓷的制备与性能研究 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 014_多晶型氧化铝连续纤维的研制及性能 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 015_多晶莫来石纤维的制备研究 | live_pipeline | two-pass | overwritten_by_two_pass |
| fiber_process | 016_多晶莫来石纤维纺丝原液制备与可纺性研究 | live_pipeline | two-pass | overwritten_by_two_pass |

## Conclusion

- `stage3/` currently mixes modes and is therefore not a safe long-term canonical output location without subdir isolation.
- overwritten limit10 full papers by two-pass: 10
- adding `--stage3-subdir` is necessary to preserve `full` and `two-pass` outputs side-by-side.
