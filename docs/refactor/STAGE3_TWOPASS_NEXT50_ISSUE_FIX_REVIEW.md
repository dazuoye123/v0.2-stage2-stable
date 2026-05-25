# Stage 3 Two-Pass Next50 Issue Fix Review

## Scope
This review covers the narrow offline fixes and targeted six-paper live two-pass rerun for the next50 failure/C-grade cases:
- 032_???-?????????????????????
- 072_Abdullah ? - 2010 - Effects of the polyvinyl alcohol (PVA) on the synthesis of alumina fibers through electrospinning te
- 020_??????????????????????
- 007_????????????????????
- 012_???????????????????
- 028_??Fiber@?-Al_2O_3?????????Ni????????????_???

No Stage 2 logic was changed. No Stage 4A / Stage 5 was run.

## Fixes applied
1. **Long-input protection for two-pass**
   - Added compact prompt payload builders for pass1/pass2.
   - Figures, tables, captions/references, procedure sections, ontology keys, and stage3 core payload are now compacted and bounded by explicit char budgets.
   - `stage3_summary.json` now records:
     - `pass1_input_chars`
     - `pass2_input_chars`
     - `input_truncated`
     - `truncation_reason`

2. **cleaned_body image residue cleanup**
   - Removed residual bare image-path tails such as `.../figures_all/xxx.jpg)` that survived after markdown image cleanup.
   - Preserved figure captions like `Fig. 4: ...`.

3. **Process-step fallback strengthening**
   - Added better rule-based fallback for Chinese and English experimental sentences.
   - Added action inference for `add / dissolve / stir / electrospin / calcine / heat / wash / filter / cool / prepare`.
   - Added basic extraction for temperature / duration / heating rate / simple condition value.
   - Added generic-process-step replacement rule: if compact/two-pass returns all-generic steps, prefer rule-based fallback when it is more informative.

## Test status
- `python -m compileall .\src .\scripts .\tests` passed.
- `pytest` passed (`409 passed`).

## Six-paper live rerun result
- success_count = 6
- failed_count = 0

## Per-paper outcome summary
- **032**
  - before: failed with `BadRequestError / InvalidParameter: Range of input length should be [1, 229376]`
  - after: success
  - `pass1_input_chars = 56697`
  - `pass2_input_chars = 58717`
  - `input_truncated = true`
  - `data_point_count = 28`
  - `process_steps_count = 10`
  - `evidence_object_count = 73`
  - `canonical_key_errors_count = 0`
  - `rejected_parameter_records_count = 0`
  - conclusion: long-input failure resolved

- **072**
  - before: `process_steps too generic` and `cleaned_body` image residue present
  - after: success
  - `cleaned_body` image residue cleared
  - `process_steps_count = 9`
  - `evidence_object_count = 4`
  - `action=other` ratio reduced to ~0.11
  - conclusion: materially improved

- **020**
  - before: `process_steps too generic`
  - after: success
  - `process_steps_count = 6`
  - `evidence_object_count = 4`
  - `action=other` ratio ~0.50
  - conclusion: improved, but still only moderately strong

- **007**
  - before: `process_steps too generic`
  - after: success
  - `process_steps_count = 4`
  - `evidence_object_count = 8`
  - `action=other` ratio = 0
  - conclusion: clearly improved

- **012**
  - before: `process_steps too generic`
  - after: success
  - `process_steps_count = 5`
  - `evidence_object_count = 11`
  - `action=other` ratio ~0.60
  - conclusion: partially improved; still somewhat generic

- **028**
  - before: `process_steps too generic`
  - after: success
  - `process_steps_count = 2`
  - `evidence_object_count = 31`
  - `action=other` ratio = 0
  - conclusion: improved structurally, but still sparse

## Structural checks
Across all 6 rerun papers:
- `raw_name=key/value/unit/context/evidence_ref` residuals: 0
- `list_value_validation_error_count`: 0
- `canonical_key_errors_count`: 0 or effectively 0
- `rejected_parameter_records_count`: 0 or effectively 0
- `evidence_objects_count > 0`: yes for all 6
- `cleaned_body` image residue: 0

## Recommendation
1. The `032` hard failure is fixed.
2. The cleaned-body image residue issue is fixed for the observed failing pattern.
3. The remaining quality risk is now mainly **process-step richness**, not schema/evidence/datapoint normalization.
4. It is reasonable to **re-evaluate the next50 quality gate** using the updated outputs before deciding on any larger expansion.
5. It is still premature to jump directly to 100 papers until the next50 gate is recomputed with the fixed outputs.
