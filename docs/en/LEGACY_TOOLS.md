# Legacy Tools

## What is `archive/`?

`archive/` stores historical helper implementations that are no longer recommended as the primary runtime path.

## What are `scripts/dev/` wrappers?

Many `scripts/dev/*` files are now thin wrappers that execute archived implementations from `archive/`.

They remain to avoid breaking:

- old local notes
- old commands
- historical repair workflows

## What is `research_figures` now?

`research_figures` is legacy compatibility only.

Preferred replacement:

- `scripts/run_figure_atlas.py`

## Historical naming

These older names still exist in compatibility layers:

- `stage4a`
- `stage55`
- `stage6c`

New documentation uses:

- `stage4`
- `linking`
- `full_pipeline`

## Why new users should avoid legacy names

Legacy commands and names:

- are harder to reason about
- may refer to older report formats
- may preserve one-off repair paths that are not part of the normal workflow

## Migration map

| Legacy | Current |
|---|---|
| `scripts/dev/run_stage5_batch.py` | `scripts/run_stage5_batch.py` |
| `scripts/run_research_figures.py` | `scripts/run_figure_atlas.py` |
| `stage4a` | `stage4` |
| `stage55` | `linking` |
| `stage6c` | `full_pipeline` |

