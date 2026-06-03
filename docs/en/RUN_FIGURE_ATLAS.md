# Run Figure Atlas

## Purpose

Use `scripts/run_figure_atlas.py` to generate a figure atlas from existing Stage 3 / Stage 4 / Stage 5 outputs.

## Important rule

Figure atlas is downstream-only.

It reads existing results and does **not** rerun:

- Stage 3
- Stage 4
- Stage 5

## Supported arguments

- `--outputs-dir`
- `--batch-final-export-dir`
- `--stage3-analysis-dir`
- `--stage3-publication-dir`
- `--batch-output-dir`
- `--audit-only`
- `--generate-figures`
- `--skip-auto-figures`
- `--max-auto-figures`
- `--continue-on-error`

## Audit only

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --audit-only
```

## Generate figures

```powershell
python .\scripts\run_figure_atlas.py `
  --outputs-dir ".\data\outputs" `
  --batch-final-export-dir ".\data\outputs\_batch_final_exports" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures `
  --max-auto-figures 50
```

## Output structure

```text
data/batch_validation/{timestamp}/figure_atlas/
  audit/
  tables/
  figure_data/
  figures/
  figure_atlas_manifest.json
  figure_index.csv
  figure_atlas_readme.md
```

### `audit/`

- `result_inventory.json`
- `result_inventory.md`
- `data_availability_matrix.csv`
- `figure_feasibility_matrix.csv`
- `input_table_schema_report.json`
- `input_table_schema_report.md`

### `tables/`

- normalized tables
- per-figure source CSV files such as `{figure_id}_source.csv`

### `figure_data/`

- per-figure source JSON files such as `{figure_id}.json`

### `figures/`

- `main/`
- `stage3/`
- `stage4/`
- `stage5/`
- `cross_stage/`
- `qa/`
- `auto/`

## Manifest and index

- `figure_atlas_manifest.json`: global summary, counts, figure metadata, and provenance flags
- `figure_index.csv`: one-row-per-figure index for the generated atlas

## Empty-data figures

Some atlas figures may be emitted with an empty-data note rather than silently skipped. This is intentional and helps QA.

## Unknown / Other

If atlas QA shows many `Unknown` or `Other` rows, inspect:

- `normalized_stage4_spectra.csv`
- `normalized_stage5_links.csv`
- QA figures under `figures/qa/`

