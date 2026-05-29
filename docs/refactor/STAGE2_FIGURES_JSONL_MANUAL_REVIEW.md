# Stage 2 figures.jsonl Manual Review

## Scope

This review is **not** an audit-script refactor and **not** a code change round.

This pass directly inspected:

- `figures.jsonl`
- `figure_stage2_summary.json`
- `figures_all/`
- `figures_for_vision/`
- the actual image files themselves

The goal was to judge whether:

1. `figure_class` looks reasonable
2. `send_to_vision_model` looks reasonable
3. there are obvious false negatives
4. there are obvious false positives
5. there are real `subfigure_label` / caption / description issues

No source code was modified in this round.

## Reviewed data

- Stage 2 batch run inspected:
  - `G:\paper\Al-gel-sol\alumina_sol_extractor\data\batch_validation_reports\stage2_calibration_limit100`
- Batch result:
  - `attempted_count = 100`
  - `success_count = 100`
  - `failed_count = 0`
  - `missing_markdown_count = 0`
  - `skipped_existing_count = 0`
- Reviewed papers:
  - 11 papers sampled from the `limit100` outputs
- Reviewed figures:
  - 17 figure records
- Sampling strategy:
  - suspected false negatives first
  - suspected false positives next
  - class mismatch candidates next
  - HTML `<details>` / `summary` label bugs
  - a small set of representative correct examples

## Summary

- `reviewed_figures_count = 17`
- `correct_count = 5`
- `likely_correct_count = 4`
- `wrong_class_count = 1`
- `false_negative_count = 3`
- `false_positive_count = 3`
- `html_subfigure_label_bug_count = 5`
- `needs_manual_review_count = 1`

Additional consistency conclusion:

- In the reviewed sample, `send_to_vision_model`, `vision_image_path`, and the actual `figures_for_vision/` files were consistent.
- This matches the broader `limit100` audit result:
  - `hard_consistency_error_count = 0`

## High-confidence problems

| category | paper_id | figure_id | current_class | send_to_vision | issue_type | reason | image_path |
|---|---|---|---|---|---|---|---|
| fiber_process | 011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 | 图2 | other | false | false_negative_microscopy | image is clearly a microscopy/SEM-style fiber surface view with scale bar; should be sent to vision | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦\figures_all\1642f67cec49609555a18ae6ec00be892fac732299df233b02ca831c630a09a7.jpg` |
| fiber_process | 011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 | 图2 | other | false | false_negative_microscopy | image is clearly a second microscopy/SEM-style fiber surface view with scale bar; should be sent to vision | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦\figures_all\06f53075dce599049c01c6f48dc5c07e95068916bb8acb47012227ae43a9934f.jpg` |
| fiber_process | 005_α-A12O3连续纤维的制备与表征 | Unknown Figure 28 | other | false | false_negative_scientific_plot | image is a real diffraction-style scientific plot; should be archived as an XRD-like scientific figure and sent to vision | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\005_α-A12O3连续纤维的制备与表征\figures_all\47fdf1b7f575c98d6a26c1c54b222a84e687e74f1289d21ba67f5776aa24590e.jpg` |
| fiber_process | 054_纳米α-Al_2O_3籽晶的合成及其在制备α-Al_2O_3纤维中的应用_肖泓芮 | Unknown Figure 3 | photo_image | true | false_positive_formula_or_text | image is a plain chemical reaction equation and should not be sent to vision | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\054_纳米α-Al_2O_3籽晶的合成及其在制备α-Al_2O_3纤维中的应用_肖泓芮\figures_all\20bf617a65a840f2176fb8914a0b0e4d94d06e417eb89cbd9e19fc82f18b8973.jpg` |
| fiber_process | 243_Preparation_of_yttrium_aluminum_garnet_fibers_by_t | Figure 2 | ftir_spectrum | true | false_positive_formula_or_text | image is a chemical structure / reaction schematic, not an FTIR spectrum | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\243_Preparation_of_yttrium_aluminum_garnet_fibers_by_t\figures_all\7f6b4ed73af2c8b17b0fc6e55624037004a4af75b72fa56ea731fa0fa4149006.jpg` |
| fiber_process | 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | 图3.2 | photo_image | true | false_positive_should_not_send_to_vision | image is a mechanism / reaction schematic, not a photograph; it should likely be schematic_or_flow and not sent under current config | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\010_含硼氧化铝基陶瓷连续纤维的制备及表征\figures_all\6be02a658b12bc70b31c4a84b27f4ac2f8faa44fb18390d95b9e64d08da87d32.jpg` |
| fiber_process | 004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 | 图6 | photo_image | true | wrong_class_microscopy | image itself looks like a microscopy / SEM-style image with magnification marks; `photo_image` is too weak a class here | `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\004_Sol-Gel法制备新型多晶钇-铝石榴石纤维\figures_all\eeee4427290e18bde51c29d03b9430a69d541de68b5977ceab1d982e1898e8bf.jpg` |

## False negatives

These are cases where the image should likely have been included in `figures_for_vision`, but was not.

1. `011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 / 图2 / idx=5`
   - Current state:
     - `figure_class = other`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `false_negative_should_send_to_vision`
   - Reason:
     - The image is clearly a microscopy-style fiber image with a `3 μm` scale bar.

2. `011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 / 图2 / idx=6`
   - Current state:
     - `figure_class = other`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `false_negative_should_send_to_vision`
   - Reason:
     - Same paper, same figure group; clearly another microscopy-style fiber image.

3. `005_α-A12O3连续纤维的制备与表征 / Unknown Figure 28`
   - Current state:
     - `figure_class = other`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `false_negative_should_send_to_vision`
   - Reason:
     - The image is a clear scientific diffraction-style plot and should not have been dropped.

One additional case was suspicious but not high-confidence:

4. `011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 / 图7 / idx=16`
   - Current state:
     - `figure_class = other`
     - `send_to_vision_model = false`
     - `clip_label = an XRD diffraction pattern`
   - Manual judgment:
     - `needs_manual_review`
   - Reason:
     - The extracted image is too degraded / low-quality to confidently decide from the bitmap alone.

## False positives

These are cases where the image was sent into `figures_for_vision`, but visually should not have been.

1. `054_纳米α-Al_2O_3籽晶的合成及其在制备α-Al_2O_3纤维中的应用_肖泓芮 / Unknown Figure 3`
   - Current state:
     - `figure_class = photo_image`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `false_positive_should_not_send_to_vision`
   - Reason:
     - It is a plain chemical reaction equation.

2. `243_Preparation_of_yttrium_aluminum_garnet_fibers_by_t / Figure 2`
   - Current state:
     - `figure_class = ftir_spectrum`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `false_positive_should_not_send_to_vision`
   - Reason:
     - It is a chemical structure / reaction schematic, not a spectrum.

3. `010_含硼氧化铝基陶瓷连续纤维的制备及表征 / 图3.2`
   - Current state:
     - `figure_class = photo_image`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `false_positive_should_not_send_to_vision`
   - Reason:
     - It is a mechanism / reaction schematic. Under current config, this should not be treated as a vision target.

## Wrong classes

These are cases where the image was sent to vision, but the assigned `figure_class` is visually implausible.

1. `004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 / 图6`
   - Current state:
     - `figure_class = photo_image`
   - Manual judgment:
     - `wrong_class`
   - Reason:
     - The image has microscopy / SEM-like appearance and instrument-style markings. `microscopy_image` would be more reasonable than `photo_image`.

## HTML label bugs

Real examples exist where `subfigure_label` or `description_text` still contains `<details>`-derived noise.

Observed high-confidence examples:

1. `054_纳米α-Al_2O_3籽晶的合成及其在制备α-Al_2O_3纤维中的应用_肖泓芮 / Unknown Figure 3`
   - `subfigure_label = "<details>"`

2. `243_Preparation_of_yttrium_aluminum_garnet_fibers_by_t / Figure 2`
   - `subfigure_label = "<details>"`

3. `005_α-A12O3连续纤维的制备与表征 / Unknown Figure 28`
   - `subfigure_label = "<details>"`
   - `description_text` begins with `<details> <summary>line</summary> ...`

4. `002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 / 图2`
   - `subfigure_label = "<details>"`
   - classification itself is still correct, but label noise is real

5. `005_α-A12O3连续纤维的制备与表征 / 图2-6`
   - `subfigure_label = "<details>"`
   - classification is still correct, but the noise is still present

So yes: **`<details> / summary` entering `subfigure_label` is a real bug**, not just an audit artifact.

## Representative correct examples

These examples look good and show that some important Stage 2 rules are already working correctly.

1. `002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 / 图2`
   - Current:
     - `figure_class = microscopy_image`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `likely_correct`
   - Reason:
     - Clear SEM image, correctly sent to vision.

2. `005_α-A12O3连续纤维的制备与表征 / 图2-6`
   - Current:
     - `figure_class = microscopy_image`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `likely_correct`
   - Reason:
     - Multi-panel SEM surfaces / cross-sections are correctly retained.

3. `004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 / 图1`
   - Current:
     - `figure_class = thermal_analysis_plot`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `correct`
   - Reason:
     - Clear TG/DTG plot, correctly classified and retained.

4. `009_含硅氧化物连续纤维的制备及其性质的研究 / 图3-2`
   - Current:
     - `figure_class = formula_or_text`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `correct`
   - Reason:
     - Image is a molecular / formula-style structure and is correctly dropped from vision.

5. `060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 / Fig.4.14`
   - Current:
     - `figure_class = mechanical_property_plot`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `correct`
   - Reason:
     - Clear modulus vs temperature mechanical-property plot.

6. `013_多孔莫来石纤维基隔热陶瓷的制备与性能研究 / 图1-1`
   - Current:
     - `figure_class = schematic_or_flow`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `correct`
   - Reason:
     - Process schematic / workflow diagram; not a VLM target under current config.

7. `014_多晶型氧化铝连续纤维的研制及性能 / 图1-1`
   - Current:
     - `figure_class = schematic_or_flow`
     - `send_to_vision_model = false`
   - Manual judgment:
     - `likely_correct`
   - Reason:
     - It is a phase-transformation diagram / schematic, not a microscopy/spectrum/thermal/mechanical target.

8. `002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 / 图1（XRD）`
   - Current:
     - `figure_class = xrd_pattern`
     - `send_to_vision_model = true`
   - Manual judgment:
     - `correct`
   - Reason:
     - Clear diffraction plot, correctly retained.

## Recommendations

Only minimal fixes are recommended.

1. Clean residual HTML / `<details>` / `summary` contamination in `subfigure_label` and `description_text`.
   - This is a real issue and showed up multiple times in direct review.

2. Tighten formula / reaction-structure exclusion.
   - At least some chemical-equation / structure images are still being sent to vision and misclassified as `photo_image` or `ftir_spectrum`.

3. Improve false-negative recovery for weak-caption microscopy / scientific plots.
   - A small number of real SEM / XRD-like images are still being dropped when caption text is too weak (`图X 相关测试结果图`) even though the image itself and auxiliary model signals are strong.
