# Stage 3 Two-Pass Limit20 Failure and C Review

## Scope
This review focuses on the single failed paper from the `stage3_twopass_after_badb7f8_limit20` live run and the two papers graded `C`. No Stage 2 logic was changed. No additional 20-paper or full batch runs were executed for this review.

## 013 Failure Root Cause
Paper: `013_????????????????????`

### Observed failure
The original limit20 batch report marked this paper as:
- `status = failed`
- `error_type = AttributeError`
- `error_message = 'str' object has no attribute 'get'`

### Root cause analysis
The failure is a deterministic postprocess / schema-adapter bug, not an LLM availability failure and not a Stage 2 problem.

The key code path was in `src/alumina_sol_extractor/stage3/merge.py`:
- `merge_stage_outputs_to_paper_record()` called `_coerce_model()` on every item inside `experiment_series`, `data_points`, and `process_steps` lists.
- `_coerce_model()` assumed each item was either a dict or a Pydantic model.
- If the live two-pass payload mixed in a scalar string item, `_normalize_identifier_fields()` would call `.get(...)` on that string, producing exactly the observed exception: `'str' object has no attribute 'get'`.

This is consistent with the symptoms:
- only one paper failed;
- the failure happened late in postprocessing;
- the paper itself is long, section-aware, and more likely to produce noisy mixed payload fragments.

### Fix applied
A minimal defensive fix was added:
- scalar / non-dict / non-model items in `experiment_series`, `data_points`, and `process_steps` lists are now ignored during merge coercion;
- valid dict/model items are still preserved and validated normally.

### Offline test added
`tests/test_stage3_merge.py::test_merge_ignores_scalar_items_in_series_and_process_lists`

### Single-paper rerun result
After the fix, 013 was rerun alone in two-pass live mode and succeeded:
- `data_point_count = 28`
- `process_steps_count = 9`
- `evidence_object_count = 36`
- `canonical_key_errors_count = 0`
- `rejected_parameter_records_count = 0`
- `schema_valid = true`

Conclusion: 013 was blocked by a single-paper merge robustness bug, and that bug is now fixed.

## C Papers Review
The two `C` papers in the original limit20 quality review were:
1. `060_?????????????????????????`
2. `158_Jing ? - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol?gel method`

### 060: why it was graded C
Main issue from the review CSV:
- `main_problem = process_steps sparse`
- `process_steps_count = 2`

What the output actually looks like:
- `data_point_count = 28`
- `evidence_object_count = 90`
- `canonical_key_errors_count = 0`
- `rejected_parameter_records_count = 0`

The weakness is specifically in process steps:
- both extracted steps are extremely generic;
- `action = other`;
- `evidence_text = null`;
- no explicit temperature / duration / condition fields are populated.

This is not a data-point schema failure. It is a section/procedure scope quality issue on a long thesis:
- `stage3_selected_sections.md` starts in Chapter 3 characterization/results content;
- the selected sections contain a lot of microstructure and characterization discussion;
- the resulting procedure focus is too weak for reliable step extraction.

Assessment:
- not a systemic datapoint normalization bug;
- not a catastrophic two-pass failure;
- still a real quality problem if process steps are expected to be stage-ready.

### 158: why it was graded C
Main issue from the review CSV:
- `main_problem = process_steps_count=0`

What the output actually looks like:
- `data_point_count = 20`
- `evidence_object_count = 7`
- `canonical_key_errors_count = 0`
- `rejected_parameter_records_count = 0`
- `process_steps_count = 0`

The paper has useful evidence and parameters, but process steps were not recovered.

Observations:
- `stage3_procedure_sections.json` contains the expected high-level sections: Introduction / Experimental / Results and discussion / Conclusions;
- however the process-step path still produced zero steps;
- this looks like an English-paper procedure extraction weakness, not a residual key/value schema problem.

Assessment:
- not a Stage 2 issue;
- not a datapoint normalization issue;
- more likely a compact/two-pass process-step extraction weakness for concise English experimental sections.

## Is This Systemic?
### Short answer
No, not in the same way as before.

### Why
Before `badb7f8`, the major two-pass issues were systemic:
- raw_name pseudo-parameters (`key/value/unit/context/evidence_ref`)
- evidence objects frequently zero
- canonical/rejected counts exploding
- list-valued parameters breaking validation

After `badb7f8`, and confirmed in the 20-paper run plus the 013 retry:
- `raw_name=key/value/unit/context/evidence_ref = 0`
- `average_canonical_key_errors_count = 0`
- `average_rejected_parameter_records_count = 0`
- `evidence_zero_with_scientific_figures_count = 0`
- cleaned_body image residue remained `0`

That means the previous systemic datapoint/evidence normalization failures are largely fixed.

The remaining problems are narrower:
- one single-paper merge robustness bug (013), now fixed;
- sparse/zero process-step extraction on a small subset of papers (060, 158).

## Quality Gate Reinterpretation
Original limit20 result was:
- `A = 0`
- `B = 17`
- `C = 2`
- `D = 1`

That `D=1` came entirely from 013's merge bug.

If we exclude that single pipeline failure and use the rerun result for 013, the effective interpretation becomes:
- the datapoint/evidence normalization gate is passed;
- the remaining quality concern is process-step stability on a small subset of papers;
- this is no longer a broad two-pass structural failure.

## Code and Test Changes
### Code changed
- `src/alumina_sol_extractor/stage3/merge.py`

### Test added
- `tests/test_stage3_merge.py::test_merge_ignores_scalar_items_in_series_and_process_lists`

### Verification
- `python -m compileall .\src .\scripts .\tests` passed
- `pytest` passed
- single-paper live rerun for 013 succeeded

## Recommendation
1. `013` no longer blocks batch quality evaluation; it was a repairable postprocess bug.
2. The two remaining `C` papers are not evidence of the old systemic datapoint normalization failure.
3. The next decision point should be based on whether sparse/zero process-step extraction is acceptable for low-cost screening mode.
4. If process steps are critical, fix process-step scope/English experimental extraction before expanding.
5. If process steps can tolerate manual review, the current two-pass output quality is much closer to expandable status than the earlier 3-iteration result suggested.
