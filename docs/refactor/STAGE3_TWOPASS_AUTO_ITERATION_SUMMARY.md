# Stage 3 Two-Pass Auto Iteration Summary

## Rounds Completed
- Iteration 1: code fix + compileall + pytest + live 20 + quality review
- Iteration 2: code fix + compileall + pytest + live 20 + quality review
- Iteration 3: code fix + compileall + pytest + live 20 + quality review

## Per-round Outcome
| Iteration | Code Changed | Live LLM Tested Papers | Success | Failed | A | B | C | D | Gate Passed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Yes | 20 | 19 | 1 | 0 | 5 | 14 | 1 | No |
| 2 | Yes | 20 | 19 | 1 | 0 | 5 | 14 | 1 | No |
| 3 | Yes | 20 | 19 | 1 | 0 | 5 | 14 | 1 | No |

## Quality Gate Verdict
Target gate:
- A + B >= 12
- D = 0
- C <= 8
- raw_name pseudo-parameter bug basically gone
- evidence zero with scientific figures reduced
- process_steps_count = 0 <= 2
- no cleaned_body image residue

Actual final state after Iteration 3:
- A + B = 5
- D = 1
- C = 14
- residual raw_name-style flat bundle issues still present in a few papers
- evidence zero with scientific figures improved to 0 in sampled successful papers
- process_steps_count = 0 improved to 0 in sampled successful papers
- cleaned_body image residue remained 0

Conclusion: gate not met.

## Biggest Remaining Problems
1. Residual data_points / parameter structuring issues remain in a subset of papers (notably `003`, `098`, `158`), likely from additional flat-bundle variants not fully normalized.
2. One hard failure remains (`002_PVA作纺丝助剂制备莫来石-氧化铝长纤维`) caused by list-valued parameter payloads failing Pydantic scalar validation.
3. Mixed quality issues remain in many papers even when schema-valid: process steps are present but not yet strong enough, and data/evidence quality is still only borderline usable.

## Recommendation
1. Do not continue running remaining papers yet.
2. Do not expand to 50 papers yet.
3. Keep two-pass as a low-cost experimental mode, not as the default production batch mode.
4. Do not switch to DeepSeek Flash yet; the dominant problems are postprocessing / schema handling, not model cost alone.
5. Do not fully revert to full mode, but keep full mode as the higher-quality reference baseline.
6. Keep the already completed ~121 two-pass outputs as diagnostic artifacts, but plan to rerun them after fixing the remaining schema / list-valued parameter / residual flat-bundle issues.

## Commits
- Iteration 1: `5b9f5ea`
- Iteration 2: `fb94473`
- Iteration 3: `3dfbad5`

## Report Paths
- `docs/refactor/STAGE3_TWOPASS_ITER1_QUALITY_REVIEW.md`
- `docs/refactor/STAGE3_TWOPASS_ITER2_QUALITY_REVIEW.md`
- `docs/refactor/STAGE3_TWOPASS_ITER3_QUALITY_REVIEW.md`
