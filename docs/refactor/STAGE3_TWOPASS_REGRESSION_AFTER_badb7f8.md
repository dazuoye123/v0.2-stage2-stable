# Stage 3 Two-Pass Regression After badb7f8

## Overall

| paper_id | success | data_point_count | process_steps_count | evidence_object_count | canonical_key_errors_count | rejected_parameter_records_count | pseudo raw_name hits | cleaned_body residue | evidence overlap |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | True | 13 | 6 | 2 | 0 | 0 | 0 | False | 2 |
| 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | True | 22 | 8 | 27 | 0 | 0 | 0 | False | 26 |
| 068_镁铝尖晶石纤维及纤维板的制备与性能研究 | True | 13 | 5 | 15 | 0 | 1 | 0 | False | 15 |

## Before vs After

- 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维: data_points 10 -> 13, process_steps 6 -> 6, evidence 0 -> 2, canonical 43 -> 0, rejected 43 -> 0
- 010_含硼氧化铝基陶瓷连续纤维的制备及表征: data_points 11 -> 22, process_steps 0 -> 8, evidence 5 -> 27, canonical 55 -> 0, rejected 55 -> 0
- 068_镁铝尖晶石纤维及纤维板的制备与性能研究: data_points 8 -> 13, process_steps 5 -> 5, evidence 0 -> 15, canonical 40 -> 0, rejected 40 -> 1

## Notes

### 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维
- pseudo raw_name hits: 0
- evidence overlap examples: ['图1', '图2']
- generic process hits: 0
- paper_id contamination: False

### 010_含硼氧化铝基陶瓷连续纤维的制备及表征
- pseudo raw_name hits: 0
- evidence overlap examples: ['Unknown Figure 1', '图2.10', '图2.11', '图2.12', '图2.13', '图2.14', '图2.15', '图2.16']
- generic process hits: 0
- paper_id contamination: False

### 068_镁铝尖晶石纤维及纤维板的制备与性能研究
- pseudo raw_name hits: 0
- evidence overlap examples: ['Unknown Figure 18', '图2.10', '图2.11', '图2.12', '图2.8', '图2.9', '图3.3', '图3.4']
- generic process hits: 0
- paper_id contamination: False


## Recommendation

- The 3-paper regression is clean enough to justify a new 20-paper round.
