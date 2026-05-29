# Stage 3 Two-Pass Regression After 1d5c7b5

## Overall

- 3 papers all succeeded in live two-pass rerun.
- The postprocessing fix clearly improved `010` and partially improved `002`.
- `068` still shows residual pseudo-parameter splitting (`raw_name=key/value/unit/context/evidence_ref`) and worse canonical/rejected counts than before.

## Per-paper results

| paper_id | success | data_point_count before -> after | process_steps_count before -> after | evidence_object_count before -> after | canonical_key_errors_count before -> after | rejected_parameter_records_count before -> after | pseudo raw_name remains? |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | yes | 10 -> 0 | 6 -> 5 | 0 -> 2 | 43 -> 0 | 43 -> 0 | no |

### 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维
- success: yes
- data_point_count: 0
- process_steps_count: 5
- evidence_object_count: 2
- pseudo raw_name hits: 0
- cleaned_body image residue: False
- stage2 scientific figure_ids (sample): 
- evidence figure_ids (sample): 
- judgment: pseudo-parameter splitting is gone and evidence/process recovered, but data_point_count dropped to 0, so the data-points path is still not reliable for this paper.

| 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | yes | 11 -> 24 | 0 -> 8 | 5 -> 26 | 55 -> 0 | 55 -> 0 | no |

### 010_含硼氧化铝基陶瓷连续纤维的制备及表征
- success: yes
- data_point_count: 24
- process_steps_count: 8
- evidence_object_count: 26
- pseudo raw_name hits: 0
- cleaned_body image residue: False
- stage2 scientific figure_ids (sample): 
- evidence figure_ids (sample): 鍥?.10
- judgment: strong improvement. process_steps and evidence_objects are both recovered, canonical/rejected counts dropped to 0, and pseudo-parameter splitting is gone.

| 068_镁铝尖晶石纤维及纤维板的制备与性能研究 | yes | 8 -> 18 | 5 -> 7 | 0 -> 15 | 40 -> 108 | 40 -> 108 | yes |

### 068_镁铝尖晶石纤维及纤维板的制备与性能研究
- success: yes
- data_point_count: 18
- process_steps_count: 7
- evidence_object_count: 15
- pseudo raw_name hits: 18
- cleaned_body image residue: False
- stage2 scientific figure_ids (sample): 鍥?.12, 鍥?.5
- evidence figure_ids (sample): 鍥?.12, 鍥?.5
- judgment: evidence and process recovered, but pseudo-parameter splitting still remains through evidence_ref variant, and canonical/rejected counts worsened sharply. This paper is still not trustworthy for structured parameters.

## Recommendation

1. Do not continue the remaining Stage 3 two-pass batch yet.
2. Fix the residual flat bundle variants in two-pass (`evidence_ref` / similar aliases) before spending more.
3. Keep the already completed ~121 papers as intermediate outputs for debugging and comparison, but do not treat them as final Stage 3 data.
4. Do not switch to DeepSeek Flash yet. The dominant problem is postprocessing/schema alignment, not model price-performance.
5. If more live validation is needed, compare two-pass limit10 against full limit10 on overlapping papers before any larger rerun.

## Final recommendation answers

- Should continue fixing? yes
- Should resume spending on remaining papers? no
- Suggest DeepSeek Flash now? no, not until schema/postprocess is stable
- Keep the 121 completed papers? keep as debug/reference outputs, but plan to rerun after fixes before using as final data
