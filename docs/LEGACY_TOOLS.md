# Legacy Tools

These tools are retained only for compatibility, recovery, historical review,
or targeted maintenance. They are not the recommended day-to-day entrypoints.

## Official entrypoints

Use these first:

- `scripts/run_full_pipeline.py`
- `scripts/run_stage4_batch.py`
- `scripts/run_stage5_batch.py`
- `scripts/export_link_aware_dataset.py`
- `scripts/export_batch_link_aware_dataset.py`
- `scripts/run_figure_atlas.py`

## Archived developer tools

- `archive/scripts/stage4_legacy/`
  - historical Stage4A audit / replay / rerun / repair / review helpers
- `archive/scripts/stage5_legacy/`
  - historical Stage5 integrity / developer maintenance helpers
- `archive/scripts/dev_tools_legacy/`
  - one-off audit/review utilities retained for traceability

## Compatibility wrappers still left in place

Some files remain under `scripts/dev/` or `scripts/` only as thin wrappers so:

- old tests keep passing
- old shell history does not break immediately
- historical documentation can be migrated safely

If a wrapper exists both in `scripts/dev/` and `archive/scripts/...`, prefer the
official `scripts/` entrypoint instead of either of them.
