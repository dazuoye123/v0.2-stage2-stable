# Troubleshooting

## Environment or dependency issues

### `ModuleNotFoundError` or missing package

- Activate the intended environment.
- Run:

```powershell
pip install -e .
```

Fallback:

```powershell
pip install -r requirements.txt
```

## Windows Unicode / GBK issues

Symptoms:

- console output crashes on Chinese paths
- `OSError: [Errno 22] Invalid argument`
- Unicode rendering problems

Recommendation:

```powershell
$env:PYTHONIOENCODING='utf-8'
```

## VPN / network / timeout

Relevant mostly when a stage would call a model or remote service.

- Stage 5 batch and figure atlas do not need VLM calls.
- Stage 4 live mode does need model access.

## Missing model credentials

If Stage 4 live mode is enabled and credentials are missing:

- check `.env`
- check `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `OPENAI_BASE_URL`, `VLM_MODEL_NAME`

## Stage 3 missing outputs

If Stage 5 reports `failed_missing_stage3`:

- verify `stage3_twopass/` or another supported Stage 3 directory exists
- check for `stage3_summary.json`
- confirm the paper is under `data/outputs/{category}/{paper_id}/`

## Stage 4 missing images

If Stage 4 has `missing_image_path`:

- inspect `figures.jsonl`
- inspect `figures_for_vision/`
- confirm `vision_image_path` or `image_path` resolves correctly

## Stage 4 has few spectra results

Possible causes:

- many figures were not selected by Stage 2
- many figures were non-extractable
- missing or unreadable image files
- live extraction was never run, only dry-run

Check:

- `stage4a_summary.json`
- `spectra_extractions.jsonl`
- `spectra_failed_records.jsonl`

## Stage 5 `failed_missing_stage3`

- Upstream Stage 3 data is missing.
- Do not force Stage 5 until Stage 3 exists.

## Stage 5 `failed_missing_stage4`

Stage 5 batch does not always fail hard when Stage 4 is missing.

- It may still produce `partial_success`
- text-based fusion can still proceed

## `failed_linking_exception`

Check:

- `final_dataset/linking/linking_summary.json`
- `final_dataset/linking/linking_report.md`
- current deterministic linking candidate values

Recent validation issues around scalar-vs-dict values should already be fixed in current code.

## `zero_evidence_links`

Interpretation:

- evidence objects exist
- but no evidence-to-parameter links were materialized

Usually this is a coverage issue, not necessarily a crash.

## `zero_spectra_links`

Interpretation:

- spectra exist
- but no spectra-to-parameter links were created

Review:

- `spectra_parameter_links.csv`
- per-paper `linking/links.jsonl`

## `zero_process_step_links`

Interpretation:

- process steps exist
- but no process-step-to-parameter links were created

This is a common deterministic linking coverage issue.

## `dry_run_only_spectra`

Meaning:

- dry-run spectra existed
- no valid live/fallback spectra were available for Stage 5 use

Stage 5 can still produce text fusion, but the paper may be `partial_success`.

## `figure_atlas` Unknown / Other too high

Meaning:

- normalization could not classify enough rows into a more specific family
- this often reflects input quality or taxonomy coverage

Check:

- `tables/normalized_stage4_spectra.csv`
- `tables/normalized_stage5_links.csv`
- QA figures under `figures/qa/`

## `figure_atlas` empty-data note figure

This is expected in some cases.

The atlas can intentionally generate a placeholder artifact with:

- empty source CSV
- JSON metadata
- a warning or `empty_data_note`

This is safer than silently skipping the figure.

## `git status` shows many data outputs

Do not commit:

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## Safe rerun strategy

- Prefer `--dry-run` first
- Prefer `--skip-existing` for already completed outputs
- Prefer `--only-incomplete` when available
- Use `--force` only for tightly scoped recovery

## How to inspect report CSVs

For Stage 5 batch:

- `stage5_batch_paper_summary.csv`
- `stage5_batch_failure_manifest.csv`
- `stage5_batch_quality_summary.csv`
- `stage5_batch_overall_summary.json`

For figure atlas:

- `audit/result_inventory.md`
- `audit/data_availability_matrix.csv`
- `audit/figure_feasibility_matrix.csv`
- `figure_index.csv`

