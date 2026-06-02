# Run Stage 4 Batch

## Purpose

Use this command when you want to run the official Stage 4 batch flow directly.

Stage 4 now uses the following official defaults:

- `stage3_subdir = stage3_twopass`
- `stage4_subdir = stage4_vision_spectra_universal`
- `routing_mode = universal_compact`
- `candidate_source = stage2-selected`

The Stage 4 core execution logic lives in:

- `src/alumina_sol_extractor/stage4/extractor.py`

The official batch entrypoints are:

- `src/alumina_sol_extractor/stage4/batch_runner.py`
- `scripts/run_stage4_batch.py`

## Dry Run

Dry run plans the per-paper Stage 4 execution without calling the VLM.

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs" `
  --manifest ".\data\batch_manifest\source_manifest.csv"
```

## Live Run

```powershell
python .\scripts\run_stage4_batch.py `
  --outputs-dir ".\data\outputs" `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --live `
  --continue-on-error
```

## Common Options

- `--paper-ids "paper_a,paper_b"`: run only the selected papers
- `--category mechanism`: restrict to one category
- `--limit 10`: restrict paper count
- `--force-stage4`: rerun Stage 4 for the selected papers
- `--stage4-figure-ids "fig-1,fig-2"`: rerun only selected figures
- `--stage3-subdir stage3_twopass`
- `--stage4-subdir stage4_vision_spectra_universal`
- `--stage4-routing-mode universal_compact`
- `--candidate-source stage2-selected`
- `--max-figures-per-paper 0`: do not truncate selected figures

## Notes

- This runner does not invoke Stage 1, Stage 2, Stage 3, or Stage 5.
- Stage 4 consumes Stage 2-selected figures instead of rebuilding candidates from `figures_all`.
- `Stage4VisionSpectraExtractor.run()` remains the single Stage 4 execution core.
- Historical `scripts/dev/` audit, replay, repair, and rerun helpers are not the recommended user entrypoints anymore.
