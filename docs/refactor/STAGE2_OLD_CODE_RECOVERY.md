# Stage 2 Old Code Recovery

## Goal

Find the historical Stage 2 code that most likely produced the satisfied output generated on `2026-05-05 17:35:43`, then reproduce the Li Jianjun paper with that old code in an isolated worktree without touching the current branch.

This audit did not modify current source code, did not check out an old commit in the current working tree, and did not run any full pipeline.

## Gold output

- Gold output source:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军\figures.jsonl`
- Protected backup:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor\data\gold_outputs\stage2\li_jianjun_stage2_satisfied_20260505_flat_output`
- Gold output generation time:
  - `2026-05-05 17:35:43`
- Gold statistics:
  - `total = 19`
  - `caption_source: standard_caption = 11, pseudo_caption = 8`
  - `figure_class: microscopy_image = 12, xrd_pattern = 3, photo_image = 2, mechanical_property_plot = 2`
  - `send_to_vision_model = 19`

## Git history availability

The repository history does **not** contain any Stage 2 commit on `2026-05-05`.

Closest commits around the gold output timestamp:

| commit | date | message | note |
|---|---|---|---|
| `9914534` | 2026-05-05 17:03:12 +0800 | `fix: backfill stage3 core parameter evidence` | Stage 3 only |
| `14bc576` | 2026-05-05 18:21:41 +0800 | `fix: improve stage3 full-text evidence backfill` | Stage 3 only |
| `b34c126` | 2026-05-05 18:35:27 +0800 | `fix: harden stage3 merge postprocess` | Stage 3 only |

Most relevant Stage 2 commits are earlier:

| commit | date | message | reason selected |
|---|---|---|---|
| `c74b2dc` | 2026-04-29 11:51:59 +0800 | `修复照片分类优先级与caption正文截断` | Tagged stable Stage 2 checkpoint (`v0.2-stage2-stable`) |
| `25b7d7a` | 2026-04-29 17:26:02 +0800 | `refactor: split taxonomy and figure text modules` | Later than `c74b2dc`, still Stage 2-focused |

Additional evidence:

- `git diff --name-only 25b7d7a..9914534 -- <Stage2 key files>` shows **no changes** in:
  - `src/alumina_sol_extractor/utils/figure_utils.py`
  - `src/alumina_sol_extractor/vision/figure_filter.py`
  - `src/alumina_sol_extractor/vision/taxonomy_classifier.py`
  - `src/alumina_sol_extractor/vision/taxonomy_config.py`
  - `src/alumina_sol_extractor/pdf/mineru_layout_parser.py`
  - `src/alumina_sol_extractor/linking/figure_context_matcher.py`
- Between `25b7d7a` and `9914534`, only `main.py` and `storage/save_figures.py` changed in the Stage 2 area, and those changes do not alter the classification rules reproduced below.

Conclusion:

- The gold output was most likely produced by Stage 2 code in the interval:
  - **`25b7d7a` through at least `9914534`**
- Git cannot prove the exact `2026-05-05 17:35:43` commit, but it can prove that the Stage 2 implementation used for the gold output was already present by `25b7d7a` and remained stable through `2026-05-05`.

## Worktree

An isolated worktree was created for reproduction:

- `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2`

Current branch worktree remained untouched.

## Minimal reproduction inputs

The old-code worktree used the original flat-path inputs that still exist in the current repository:

- Markdown:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor\data\markdown\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军.md`
- MinerU raw:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor\data\mineru_raw\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军`

These were copied into the worktree under the same flat paths.

This is important because the current category-aware markdown for the same paper is structurally different:

| input | length | image count | `<details>` count | `<summary>` count |
|---|---:|---:|---:|---:|
| old flat markdown | 11766 | 19 | 0 | 0 |
| current category-aware markdown | 18427 | 19 | 19 | 19 |

So the old-code reproduction used the historically faithful Stage 2 input, not the newer category-aware rebuilt markdown.

## Candidate commits

| commit | date | message | reason selected | run status | result summary |
|---|---|---|---|---|---|
| `c74b2dc` | 2026-04-29 11:51:59 +0800 | `修复照片分类优先级与caption正文截断` | Stable Stage 2 tag and directly relevant caption/classification fix | ran successfully | exact gold match |
| `25b7d7a` | 2026-04-29 17:26:02 +0800 | `refactor: split taxonomy and figure text modules` | Later candidate, closest known Stage 2 code interval before 2026-05-05 | ran successfully | exact gold match |

## Reproduction attempts

### Candidate `c74b2dc`

- Worktree state:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2 @ c74b2dc`
- Run method:
  - No batch runner existed yet.
  - Reproduced Stage 2 by running the same logic as `main.py` **after** the MinerU conversion step, using the existing flat markdown and flat MinerU raw cache.
- Output path:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2\data\outputs\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军`
- Result:
  - `total = 19`
  - `caption_source: standard_caption = 11, pseudo_caption = 8`
  - `figure_class: microscopy_image = 12, xrd_pattern = 3, photo_image = 2, mechanical_property_plot = 2`
  - `send_to_vision_model = 19`
- Match status:
  - **exactly matches the gold output statistics**

### Candidate `25b7d7a`

- Worktree state:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2 @ 25b7d7a`
- Run method:
  - Same isolated single-paper Stage 2 replay as above.
- Output path:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2\data\outputs\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军`
- Result:
  - `total = 19`
  - `caption_source: standard_caption = 11, pseudo_caption = 8`
  - `figure_class: microscopy_image = 12, xrd_pattern = 3, photo_image = 2, mechanical_property_plot = 2`
  - `send_to_vision_model = 19`
- Match status:
  - **exactly matches the gold output statistics**
  - A field-level comparison of:
    - `figure_id`
    - `subfigure_index`
    - `subfigure_label`
    - `caption_source`
    - `figure_class`
    - `send_to_vision_model`
    - `exclude_reason`
    - `caption`
    also matched the gold output exactly.

## Best match

### FOUND_MATCH = true

Because `25b7d7a` is later than `c74b2dc`, and because Stage 2 key files remained unchanged through the `2026-05-05` interval, the best historical recovery target is:

- **commit:** `25b7d7a83ccbce7c81e675341bc6d25c4e791476`
- **message:** `refactor: split taxonomy and figure text modules`

Why this is the best match:

1. It reproduces the gold output exactly.
2. It is later than `c74b2dc`, so it is closer to the actual `2026-05-05` generation time.
3. Git history shows no subsequent Stage 2 rule changes before the gold output timestamp.

### Reproduction command style

No historical Stage 2 batch runner existed at that commit, so reproduction was done by replaying the Stage 2 section of `main.py` after MinerU conversion, using the existing flat markdown and flat MinerU raw cache for the Li Jianjun paper only.

### Output path

- `G:\paper\Al-gel-sol\alumina_sol_extractor_old_stage2\data\outputs\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军\figures.jsonl`

### Reproduction statistics

- `total = 19`
- `caption_source: standard_caption = 11, pseudo_caption = 8`
- `figure_class: microscopy_image = 12, xrd_pattern = 3, photo_image = 2, mechanical_property_plot = 2`
- `send_to_vision_model = 19`

### Consistency with gold output

- **Exact match on summary counts**
- **Exact match on the key per-figure fields listed above**

## Code behavior notes

### 1. Old satisfied behavior is recoverable from Git

The gold behavior is **not** purely from an uncommitted local state. It is reproducible from committed history.

### 2. The old satisfied behavior depends on old flat markdown inputs

The exact match was achieved using the preserved flat markdown and flat MinerU raw cache.

The current category-aware markdown for the same paper is materially different:

- longer text
- per-image `<details>...</details>` blocks
- extra summary-like content around images

So the current output drift is not explained by code changes alone.

### 3. Stage 2 classification rules in the recovered old code

Recovered old code shows:

- `figure_class` is ultimately set in:
  - `src/alumina_sol_extractor/vision/figure_filter.py::classify_figure`
- `FigureFilter.apply_one(...)` computes:
  - classification text
  - keyword hits
  - final `figure_class`
  - archive / send-to-vision flags
- CLIP and ResNet are auxiliary:
  - CLIP mostly helps negative/fallback cases
  - ResNet mostly helps chart/table/schematic fallback cases
  - neither is the main source of the gold scientific classes when caption/reference text is strong

### 4. Why the current branch can differ even if send-to-vision recovers to 19

The strongest evidence points to **input text drift**, not just taxonomy drift:

- old markdown has no `<details>` noise
- new category-aware markdown contains 19 `<details>` blocks
- those blocks change:
  - local context windows
  - pseudo-caption opportunities
  - `reference_sentences`
  - `description_text`
  - sometimes downstream scientific class cues

### 5. What this means for future fixes

If the goal is to restore old Stage 2 figure classes exactly, the most faithful source of truth is now known:

- old code interval: `25b7d7a .. 9914534`
- old flat markdown/raw input structure

That means future fixes should diff **current taxonomy / text assembly** against this recovered baseline, not guess from counts alone.

## Recommendation

### If you want exact old Stage 2 behavior back

Use `25b7d7a` as the extraction baseline for Stage 2 rules.

Do **not** roll back the whole repository.

Instead, selectively compare and port back only the Stage 2 behavior that diverged:

1. taxonomy priority
2. text assembly for classification
3. pseudo-caption and context interaction
4. handling of `<details>` blocks in rebuilt markdown

### If you want current code to match old satisfied output

The safest next step is:

1. treat the backed-up gold `figures.jsonl` as the gold sample
2. use `25b7d7a` as the historical code baseline
3. compare:
   - current category-aware markdown
   - old flat markdown
   - current Stage 2 classification text assembly
   - old Stage 2 classification text assembly
4. make **minimal** fixes in current taxonomy / text preprocessing rather than reverting unrelated work

## Final conclusion

- A reproducible old-code match **was found**
- The best matching historical code is:
  - `25b7d7a83ccbce7c81e675341bc6d25c4e791476`
- The gold output is therefore recoverable from committed history
- The remaining discrepancy in the current branch is most likely due to:
  - changed Stage 2 inputs (especially rebuilt category-aware markdown with `<details>` blocks)
  - not the loss of the old satisfied Stage 2 code itself
