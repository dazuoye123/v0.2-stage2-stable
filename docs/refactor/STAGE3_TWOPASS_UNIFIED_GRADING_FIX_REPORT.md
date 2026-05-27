# Stage 3 Two-pass Unified Grading Fix Report

## Findings

- Scoring drift was confirmed: the previous combined 70+100 review treated sparse `source_text` support as an A-level veto, even when datapoint/evidence/process outputs were otherwise stable.
- A single evaluator now owns Stage 3 two-pass quality grading: `src/alumina_sol_extractor/stage3/quality_grading.py`.
- Future quality reviews should use `scripts/dev/review_stage3_twopass_quality.py` so the same rubric is applied everywhere.

- rubric_version = stage3_twopass_quality_v1

## Next100 Unified Result

- A = 51
- B = 31
- C = 18
- D = 0
- manual_hold = 10

## 70+100 Unified Result

- A = 65
- B = 76
- C = 29
- D = 0
- manual_hold = 21

## Grade Transition Highlights

- next100 old -> unified: {'C->C': 11, 'A->A': 51, 'B->B': 22, 'A->B': 9, 'B->C': 7}
- 70+100 old -> unified: {'B->B': 74, 'B->A': 65, 'C->C': 29, 'C->B': 2}

## Conclusion

- The `A=60` vs `A=0` contradiction is resolved: both reports now use the same evaluator and produce non-zero A counts.
- The running `remaining_all` batch is not affected because this fix is read-only and only changes review logic.
- After `remaining_all` completes, the full-corpus review should use this same evaluator and rubric version.