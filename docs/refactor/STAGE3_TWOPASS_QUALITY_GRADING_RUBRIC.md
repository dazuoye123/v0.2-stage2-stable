# Stage 3 Two-pass Quality Grading Rubric

`rubric_version = "stage3_twopass_quality_v1"`

This rubric is the single grading contract for Stage 3 two-pass output quality. All future Stage 3 two-pass quality reviews must call the shared evaluator in:

- `src/alumina_sol_extractor/stage3/quality_grading.py`

## A

- `data_points`, `process_steps`, and `evidence` are all substantively usable.
- No `raw_name=key/value/unit/context/evidence_ref` pseudo-parameters.
- `canonical_key_errors_count` and `rejected_parameter_records_count` are effectively zero.
- `evidence_objects` are present and align with Stage 2 figures where scientific figures exist.
- `cleaned_body` has no image residue.
- `process_steps` correspond to actual experimental procedure.
- Extremely small warnings are allowed if they do not materially reduce trust.

## B

- `data_points` and `evidence` remain stable and usable.
- No hard schema/canonical/evidence failure.
- `process_steps` may be sparse or somewhat generic.
- `source_text` / `evidence_text` may be partially missing, but the output is still globally credible.
- Suitable for Stage 5 or human review.

## C

- A core module is clearly not usable without repair.
- Examples:
  - `process_steps` are seriously generic or cannot be mapped back to experiment.
  - `data_points` lack reliable support and cannot be defended by `context` / `evidence_refs`.
  - `evidence` is missing or weakly linked.
- This bucket should trigger a targeted action such as offline repair, process-steps-only LLM, manual hold, or full-mode fallback.

## D

- Pipeline failure, unreadable `stage3_summary`, schema crash, or globally unusable output.

## manual_hold

- Use for review/progress papers, no-experiment papers, severe source-loss cases, or OCR/markdown failure cases.
- Do not silently wash these into `B`.
- Exclude them from the mainline usable set.

## Important Rule

`data_point_source_missing_ratio` is **not** a standalone hard veto for `A`.

It can only act as a warning unless it co-occurs with genuinely weak support, such as:

- no `source_text`
- no `context`
- no `evidence_refs`
- and the parameter appears model-inferred rather than text-grounded

This rule exists specifically to prevent the prior grading drift where strong next100 `A` papers were incorrectly collapsed into `B`.
