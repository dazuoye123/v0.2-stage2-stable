# Project Cleanup Audit

Date: 2026-05-19
Scope: structure audit only. No runtime code, test logic, or pipeline behavior was changed in this pass.

## Audit Basis

This audit classifies files by current runtime usage, import references, script entry-point reachability, and documentation visibility.

Important guardrails for this pass:
- No Stage 3 / Stage 4A / Stage 5 logic changes.
- No file moves or deletions.
- No pipeline reruns.
- No LLM or VLM calls.

## Executive Summary

The repository already contains a usable core pipeline, but the project shape now mixes three layers in one tree:
- stable runtime code for Stage 1 / Stage 2 / Stage 3 / Stage 4A / Stage 5 / Stage 5.5
- operational resume / batch orchestration code that is runtime-critical but named like validation utilities
- a growing maintenance shell of smoke tests, diagnosis scripts, manifests, and historical notes

The single biggest structural issue is not dead code. It is naming drift:
- `src/alumina_sol_extractor/batch_validation/full_resume.py` is not just a validation helper; it is part of the real orchestrator used by `scripts/run_full_pipeline.py`.
- `src/alumina_sol_extractor/batch_validation/resume.py` is also runtime-relevant for candidate discovery and safe resume behavior.
- `main.py` and `README.md` still present a lightweight Stage 1/2/optional Stage 3 view of the project, while the actual maintained workflow is now `scripts/run_full_pipeline.py` plus the Stage 5 / link-aware export stack.

## A. CORE_RUNTIME

These files or directories are required for the current main pipeline behavior and should be treated as protected runtime code.

### Entry Points
- `scripts/run_full_pipeline.py`
  Current controlled end-to-end orchestrator from Stage 1 through Stage 5.5 / link-aware export.
- `scripts/run_stage5_dataset_fusion.py`
  Direct Stage 5 entry.
- `scripts/run_stage5_linking.py`
  Direct Stage 5.5 linking entry.
- `scripts/export_link_aware_dataset.py`
  Direct per-paper link-aware export entry.
- `scripts/export_batch_link_aware_dataset.py`
  Batch export entry used by current workflow and docs.

### Config / Settings / Packaging
- `pyproject.toml`
- `settings.yaml`
- `configs/*.yaml`
- `src/alumina_sol_extractor/config/settings_loader.py`

### Stage 1: PDF -> Markdown
- `src/alumina_sol_extractor/pdf/mineru_pdf_to_markdown.py`
- `src/alumina_sol_extractor/pdf/mineru_layout_parser.py`
- `src/alumina_sol_extractor/pipeline/stage1_pdf_to_markdown.py`
- `src/alumina_sol_extractor/utils/chemical_text_normalizer.py`

### Stage 2: Figure / Table Preparation
- `src/alumina_sol_extractor/pipeline/stage2_figure_pipeline.py`
- `src/alumina_sol_extractor/figures/*`
- `src/alumina_sol_extractor/storage/save_figures.py`
- `src/alumina_sol_extractor/stage2_summary.py`
- `src/alumina_sol_extractor/models/figure.py`
- `src/alumina_sol_extractor/models/table.py`

### Stage 3: Structured Text Extraction
- `src/alumina_sol_extractor/pipeline/stage3_dspy_pipeline.py`
- `src/alumina_sol_extractor/dspy_modules/*`
- `src/alumina_sol_extractor/stage3/merge.py`
- `src/alumina_sol_extractor/stage3/normalization.py`
- `src/alumina_sol_extractor/stage3/procedure_sections.py`
- `src/alumina_sol_extractor/stage3/report.py`
- `src/alumina_sol_extractor/stage3/sections.py`
- `src/alumina_sol_extractor/stage3/validators.py`
- `src/alumina_sol_extractor/markdown_processing/body_trim.py`
- `src/alumina_sol_extractor/markdown_processing/pipeline.py`
- `src/alumina_sol_extractor/models/schema_v2.py`

### Stage 4A: Vision / Spectra Extraction
- `src/alumina_sol_extractor/vision/*`
- `src/alumina_sol_extractor/vision_spectra/*`
- `src/alumina_sol_extractor/models/schema_v2.py`
- `src/alumina_sol_extractor/ontology/*`

Note:
- There is no single clean `pipeline/stage4a_*.py` orchestrator yet. The Stage 4A runtime stack exists, but part of its orchestration currently lives in `batch_validation/full_resume.py`.

### Stage 5: Fusion + Stage 5.5 Linking + Link-Aware Export
- `src/alumina_sol_extractor/dataset_fusion/fusion.py`
- `src/alumina_sol_extractor/dataset_fusion/exporters.py`
- `src/alumina_sol_extractor/dataset_fusion/loaders.py`
- `src/alumina_sol_extractor/dataset_fusion/models.py`
- `src/alumina_sol_extractor/dataset_fusion/validators.py`
- `src/alumina_sol_extractor/dataset_fusion/report.py`
- `src/alumina_sol_extractor/dataset_fusion/link_aware_export.py`
- `src/alumina_sol_extractor/dataset_fusion/link_aware_fields.py`
- `src/alumina_sol_extractor/dataset_fusion/link_aware_io.py`
- `src/alumina_sol_extractor/dataset_fusion/batch_link_aware_export.py`
- `src/alumina_sol_extractor/dataset_fusion/spectra_units.py`
- `src/alumina_sol_extractor/linking/*`

### Shared Runtime Assets
- `src/alumina_sol_extractor/ontology/*`
- `src/alumina_sol_extractor/utils/*`
- `src/alumina_sol_extractor/models/*`

## B. CORE_BUT_MISPLACED

These are runtime-relevant and should not be deleted, but their package location or naming makes the project look more experimental than it really is.

### 1. `src/alumina_sol_extractor/batch_validation/full_resume.py`
Why it is core:
- Imported directly by `scripts/run_full_pipeline.py`.
- Owns real orchestration decisions for Stage 3 / Stage 4A / Stage 5 / Stage 5.5 resume behavior.
- Not just a report or validator.

Why it is misplaced:
- The directory name `batch_validation` suggests optional QA tooling, not a main pipeline runner.
- The exported function name `run_stage6c_full_resume` encodes historical naming rather than project structure.

Suggested future destination:
- `src/alumina_sol_extractor/pipeline/full_pipeline_runner.py`

### 2. `src/alumina_sol_extractor/batch_validation/resume.py`
Why it is core:
- Imported by `scripts/run_full_pipeline.py` for `discover_resume_candidates`.
- Implements real resume planning and stage status logic.

Why it is misplaced:
- Same naming problem as above: it is runtime orchestration, not just validation.

Suggested future destination:
- `src/alumina_sol_extractor/pipeline/resume_runner.py`

### 3. `src/alumina_sol_extractor/dataset_fusion/batch_link_aware_export.py`
Why it is close to core:
- Used directly by `scripts/run_full_pipeline.py` and `scripts/export_batch_link_aware_dataset.py`.
- It is part of the current operational export story.

Why it is slightly misplaced:
- It lives under `dataset_fusion`, but functionally it is a batch export / reporting layer above per-paper fusion.

Suggested future destination:
- `src/alumina_sol_extractor/pipeline/batch_exports.py`
  or
- `src/alumina_sol_extractor/linking/batch_export.py`

## C. DEV_TOOLS

These are useful and should stay available, but they are not part of the minimum production runtime.

### Dev / Manifest / Manual Review Scripts
- `scripts/dev/build_source_manifest.py`
- `scripts/dev/build_supplementary_manifest.py`
- `scripts/dev/download_supplementary_candidates.py`
- `scripts/dev/review_stage4_vision_spectra.py`

### Smoke / Maintenance Scripts
- `scripts/run_stage3_dspy_smoke_test.py`
- `scripts/run_stage4_vision_spectra_smoke_test.py`
- `scripts/reparse_stage4_vlm_outputs.py`

Rationale:
- Useful for debugging, review, maintenance, and partial validation.
- Not required for the normal steady-state pipeline when the main flow is driven by `scripts/run_full_pipeline.py` or the Stage 5 standalone entries.

### Design / Operational Docs
- `docs/RUN_FULL_PIPELINE.md`
- `docs/stage3/DESIGN_NOTE.md`
- `docs/stage3/DSPY_PIPELINE_DESIGN.md`
- `docs/stage3/ontology_cleanup_report.md`

These are valuable engineering memory, but they are not runtime dependencies.

## D. TEST_ONLY

All files under `tests/` are test-only. They should not be treated as application clutter to delete blindly.

Recommended minimum keep set for regression protection:

### Must-Keep Runtime Regression Tests
- `tests/test_stage5_link_aware_export_with_evidence.py`
  Keep for FTIR / Raman / XRD / NMR unit normalization regressions in link-aware export.
- `tests/test_stage5_missing_parameter_evidence_matching.py`
  Keep for pH false-link prevention and text-reference evidence behavior.
- `tests/test_stage5_linking_process_steps.py`
  Keep for numeric substring mislink prevention and process-step semantic linking rules.
- `tests/test_sample_matrix_spectra_links.py`
  Keep for sample matrix dynamic fields, long-table provenance, and missing-value diagnosis behavior.
- `tests/test_stage55_process_step_parameter_links.py`
  Keep for Stage 5.5 process-step link retention.
- `tests/test_stage3_process_steps_extraction.py`
  Keep for process-step extraction presence.
- `tests/test_stage3_process_steps_fallback.py`
  Keep for fallback behavior when procedure sections exist but the LLM path returns no steps.
- `tests/test_stage4a_conservative_normalization.py`
  Keep for the rule that range peaks stay conservative and do not collapse to midpoint.
- `tests/test_markdown_body_trim.py`
  Keep for body-trim behavior and legacy import compatibility.

### Broader Test Surface Worth Keeping
- Stage 1 / Stage 2 parser and routing tests.
- Stage 3 sectioning / evidence / normalization tests.
- Stage 4A prompt-contract and validation tests.
- Stage 5 fusion / linking / export tests.
- Resume and full-pipeline script tests.

Recommendation:
- Do not delete `tests/` as a cleanup tactic.
- If startup time becomes an issue later, split tests into `smoke`, `core_regression`, and `extended` groups rather than removing them.

## E. LEGACY_COMPAT

These files exist primarily to preserve old imports, old commands, or historical usage patterns.

### 1. `src/alumina_sol_extractor/stage3/document_trim.py`
Why it stays:
- Old import path still used by runtime code and tests.
- Now acts as a forwarding shim to `markdown_processing.body_trim`.

### 2. `main.py`
Why it stays for now:
- Still works as a lightweight `settings.yaml`-driven entry point.
- README still points to it.

Why it is not the main future entry:
- It only represents the early lightweight flow: Stage 1, Stage 2, and optional Stage 3.
- It does not represent the actual maintained end-to-end workflow that now includes Stage 4A, Stage 5, Stage 5.5, and link-aware export.

### 3. `scripts/run_stage6b_batch_resume.py`
### 4. `scripts/run_stage6c_full_resume.py`
Why they are compat wrappers:
- Thin CLI layers over `batch_validation.resume` and `batch_validation.full_resume`.
- Useful for direct invocation, but the naming is historical and the main user-facing entry is now `scripts/run_full_pipeline.py`.

### 5. `requirements.txt`
Why it is legacy-compat rather than obsolete:
- README still recommends `pip install -r requirements.txt`.
- `pyproject.toml` is the better canonical packaging source now, but `requirements.txt` still serves a compatibility install path.

## F. OBSOLETE_CANDIDATE

These are conservative archive/delete candidates for a later pass. They are not being removed now.

### 1. `refactor_audit.md`
Evidence:
- No runtime imports.
- No script entry points call it.
- No tests depend on it.
- Not part of the current docs entry path.

Recommendation:
- Move to an archive docs area later, or remove after preserving its conclusions elsewhere.

### 2. `docs/stage3/prompt2_reference.txt`
Evidence:
- No import references found.
- No script references found.
- No tests reference it.
- Not surfaced by README or `docs/RUN_FULL_PIPELINE.md` as a required user-facing artifact.

Recommendation:
- Candidate for archive if the team no longer uses it as prompt archaeology.

## Files That Look Noisy But Should Not Be Misclassified As Obsolete

- `tests/test_mechanical_property_plot.py`
- `tests/test_process_parameter_plot.py`

Reason:
- They still protect active figure-taxonomy behavior in `configs/figure_taxonomy.yaml` and `src/alumina_sol_extractor/vision/taxonomy_classifier.py`.

## README.md Audit

`README.md` is outdated.

Current mismatch:
- It still presents the repo mainly as a MinerU Stage 1 PDF -> markdown project.
- It recommends `python main.py` as the primary flow.
- It does not explain the current Stage 3, Stage 4A, Stage 5, Stage 5.5, or link-aware export architecture.
- Its testing section points to an old script-style test command instead of the real `pytest` suite.

Recommended future README shape:
- quick start for current full pipeline
- architecture overview for Stage 1 / 2 / 3 / 4A / 5 / 5.5
- safe rerun and export commands
- data layout and non-committed output policy
- optional dependency groups

## `settings.yaml` Audit

`settings.yaml` still reflects the earlier lightweight entry model.

Observations:
- Good for Stage 1-centric local runs.
- Not yet a complete representation of the present multi-stage operational workflow.
- This is acceptable short-term because `scripts/run_full_pipeline.py` now carries most run-time control flags, but it adds conceptual duplication.

Recommendation:
- Keep `settings.yaml` for now.
- Later decide whether it remains a lightweight local config, or whether stage orchestration settings should be centralized more explicitly.

## `pyproject.toml` Audit

`pyproject.toml` is currently heavier than the true core runtime needs.

Current always-on dependencies include:
- `torch`
- `torchvision`
- `transformers`
- `huggingface_hub`
- `dspy-ai`

Assessment:
- That is probably too heavy for a minimal Stage 1 + Stage 2 + Stage 5 environment.
- Vision-classification and VLM-adjacent utilities justify some of these packages, but not as unconditional core dependencies.

Recommended future split:

### `core`
- `PyYAML`
- `requests`
- `pydantic`
- `pandas`
- `lxml`
- `tabulate`
- `pillow`
- `python-dotenv`

### `vision`
- `torch`
- `torchvision`
- `transformers`
- `huggingface_hub`

### `dspy`
- `dspy-ai`

### `dev`
- `pytest`
- coverage / lint / formatting tools if adopted later

Practical recommendation:
- Keep the current dependency set until packaging cleanup is scheduled.
- In the next packaging pass, split optional dependencies into extras exactly along `core`, `vision`, `dspy`, and `dev`.

## Suggested Near-Term Cleanup Sequence

This is a future plan only. No files were moved in this pass.

1. Update `README.md` to describe the current real pipeline.
2. Rename or relocate `batch_validation/full_resume.py` into a real pipeline namespace.
3. Rename or relocate `batch_validation/resume.py` into the same namespace.
4. Keep `stage3/document_trim.py` as a compat shim until old imports are gone.
5. Move historical notes like `refactor_audit.md` and `docs/stage3/prompt2_reference.txt` into an archive bucket if still worth keeping.
6. Split optional dependencies in `pyproject.toml`.
7. Only after the above, consider whether any thin wrapper scripts should be retired.

## Bottom-Line Recommendations

- Do not delete tests as a first cleanup step.
- Do migrate `full_resume.py` later; it is core orchestration wearing the wrong name.
- Do treat README and packaging metadata as the highest-value documentation cleanup items.
- Do not assume all verbose-looking files are dead; several of the noisiest pieces are still on the live runtime path.
