# Stage 2 Old vs New Output Comparison

## Compared files
- old: `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军\figures.jsonl`
- new: `G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs\fiber_process\019_干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军\figures.jsonl`

## Summary counts
| metric | old | new | comment |
|---|---:|---:|---|
| total figure records | 19 | 19 | same record count |
| caption_source=standard_caption | 11 | 18 | standard caption usage |
| caption_source=pseudo_caption | 8 | 1 | pseudo caption usage |
| caption_source=none | 0 | 0 | no caption |
| send_to_vision_model=true | 19 | 19 | vision selected |
| send_to_vision_model=false | 0 | 0 | not sent to vision |
| matched records | 6 | 6 | paired for direct comparison |
| unmatched old records | 13 | 0 | old-only records |
| unmatched new records | 0 | 13 | new-only records |

## Figure class changes
| class | old_count | new_count | delta |
|---|---:|---:|---:|
| generic_chart_or_plot | 0 | 1 | 1 |
| mechanical_property_plot | 2 | 0 | -2 |
| microscopy_image | 12 | 10 | -2 |
| photo_image | 2 | 6 | 4 |
| thermal_analysis_plot | 0 | 1 | 1 |
| xrd_pattern | 3 | 1 | -2 |

## Vision selection changes
| case | count | examples |
|---|---:|---|
| old true -> new false | 0 |  |
| old microscopy_image -> new non-microscopy | 0 |  |
| old xrd/photo/mechanical -> new other | 0 |  |
| standard_caption -> pseudo/none | 0 |  |
| new html-like subfigure_label | 5 | old#13 Fig.7 microscopy_image -> new#13 microscopy_image<br>old#14 Fig.7 microscopy_image -> new#14 microscopy_image<br>old#15 Fig.7 microscopy_image -> new#15 microscopy_image<br>old#16 Fig.7 microscopy_image -> new#16 microscopy_image<br>old#17 Fig.7 microscopy_image -> new#17 microscopy_image |
| new formula/pure_text capture | 0 |  |

## Per-figure comparison
| old_idx | new_idx | figure_id | old_class | new_class | old_vision | new_vision | old_caption_source | new_caption_source | note |
|---:|---:|---|---|---|---|---|---|---|---|
| 4 | 5 | 图3 -> 图3 | xrd_pattern | generic_chart_or_plot | True | True | pseudo_caption | pseudo_caption | changed; figure_id+subfigure_index+caption30 |
| 13 | 13 | Fig.7 -> Fig.7 | microscopy_image | microscopy_image | True | True | standard_caption | standard_caption | possible_regression; figure_id+subfigure_index+caption30; html_label |
| 14 | 14 | Fig.7 -> Fig.7 | microscopy_image | microscopy_image | True | True | standard_caption | standard_caption | possible_regression; figure_id+subfigure_index+caption30; html_label |
| 15 | 15 | Fig.7 -> Fig.7 | microscopy_image | microscopy_image | True | True | standard_caption | standard_caption | possible_regression; figure_id+subfigure_index+caption30; html_label |
| 16 | 16 | Fig.7 -> Fig.7 | microscopy_image | microscopy_image | True | True | standard_caption | standard_caption | possible_regression; figure_id+subfigure_index+caption30; html_label |
| 17 | 17 | Fig.7 -> Fig.7 | microscopy_image | microscopy_image | True | True | standard_caption | standard_caption | possible_regression; figure_id+subfigure_index+caption30; html_label |

## Possible regressions
1. old#13 -> new#13: `figure_id+subfigure_index+caption30; html_label`; caption `standard_caption` -> `standard_caption`, class `microscopy_image` -> `microscopy_image`
2. old#14 -> new#14: `figure_id+subfigure_index+caption30; html_label`; caption `standard_caption` -> `standard_caption`, class `microscopy_image` -> `microscopy_image`
3. old#15 -> new#15: `figure_id+subfigure_index+caption30; html_label`; caption `standard_caption` -> `standard_caption`, class `microscopy_image` -> `microscopy_image`
4. old#16 -> new#16: `figure_id+subfigure_index+caption30; html_label`; caption `standard_caption` -> `standard_caption`, class `microscopy_image` -> `microscopy_image`
5. old#17 -> new#17: `figure_id+subfigure_index+caption30; html_label`; caption `standard_caption` -> `standard_caption`, class `microscopy_image` -> `microscopy_image`

## Clearly recovered or improved
- none flagged by the current rules

## Need manual image review
- unmatched old old#1: figure_id=`图1`, class=`photo_image`, caption_source=`standard_caption`
- unmatched old old#2: figure_id=`图1`, class=`photo_image`, caption_source=`standard_caption`
- unmatched old old#3: figure_id=`图2`, class=`xrd_pattern`, caption_source=`pseudo_caption`
- unmatched old old#5: figure_id=`图4`, class=`xrd_pattern`, caption_source=`pseudo_caption`
- unmatched old old#6: figure_id=`Fig.5`, class=`microscopy_image`, caption_source=`standard_caption`
- unmatched old old#7: figure_id=`Fig.5`, class=`microscopy_image`, caption_source=`standard_caption`
- unmatched old old#8: figure_id=`Fig.5`, class=`microscopy_image`, caption_source=`standard_caption`
- unmatched old old#9: figure_id=`图6`, class=`microscopy_image`, caption_source=`pseudo_caption`
- unmatched old old#10: figure_id=`图6`, class=`microscopy_image`, caption_source=`pseudo_caption`
- unmatched old old#11: figure_id=`图6`, class=`microscopy_image`, caption_source=`pseudo_caption`
- unmatched new new#1: figure_id=`图1`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#2: figure_id=`图1`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#3: figure_id=`图2`, class=`thermal_analysis_plot`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#4: figure_id=`图3`, class=`xrd_pattern`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#6: figure_id=`图5`, class=`microscopy_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#7: figure_id=`图5`, class=`microscopy_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#8: figure_id=`图6`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#9: figure_id=`图6`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#10: figure_id=`图6`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`
- unmatched new new#11: figure_id=`图6`, class=`photo_image`, caption_source=`standard_caption`, note=`unmatched_new`

## Recommendations
- ????????????????????????? unmatched/changed ???????
