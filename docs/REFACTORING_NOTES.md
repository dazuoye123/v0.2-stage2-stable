# Refactoring Notes

## Current architecture direction

The project is being consolidated around a smaller set of maintained runtime
entrypoints:

- full pipeline
- Stage4 batch
- Stage5 batch
- single-paper link-aware export
- batch link-aware export
- figure atlas

## Naming guidance

Preferred names in new code and docs:

- `stage4`
- `stage5`
- `linking`
- `export`
- `full_pipeline`

Legacy names retained only for compatibility:

- `stage4a`
- `stage55`
- `stage6c`

## Compatibility strategy

- keep wrappers where tests or old shell commands still rely on them
- move historical scripts into `archive/` when safe
- keep official entrypoints under `scripts/`
- keep heavy business logic in `src/alumina_sol_extractor/...`
