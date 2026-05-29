# Stage 3 Two-Pass Next50 Reevaluation After dfa28d5

## Overall conclusion

This reevaluation does not reuse the old next50 quality cache. It rereads the same 50-paper list from the original next50 batch report, but evaluates each paper against the current latest `stage3_twopass/` outputs after the `dfa28d5` fixes and the targeted six-paper live rerun.

## Summary

- tested_papers_count: 50

- A=0, B=7, C=43, D=0

- raw_name_key_value_bug_count: 0

- list_value_validation_error_count: 0

- evidence_zero_with_scientific_figures_count: 0

- process_steps_zero_count: 0

- cleaned_body_image_residue_count: 0

- average_canonical_key_errors_count: 0.00

- average_rejected_parameter_records_count: 0.00

- pass_quality_gate: False

## Key confirmations

- `032_???-?????????????????????` no longer fails and now succeeds under hard input truncation.

- `072_Abdullah ...` no longer shows cleaned_body image residue.

- The six previously problematic papers all succeed in the latest outputs.

- `raw_name=key/value/unit/context/evidence_ref` remains 0 across next50.

- `average_canonical_key_errors_count` and `average_rejected_parameter_records_count` remain 0.

## Remaining C-grade papers

- 009_含硅氧化物连续纤维的制备及其性质的研究: process_steps too generic

- 011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦: process_steps too generic

- 015_多晶莫来石纤维的制备研究: process_steps too generic

- 016_多晶莫来石纤维纺丝原液制备与可纺性研究: process_steps too generic

- 019_干法纺丝制备α-Al_2O_3陶瓷纤维及其力学性能研究_李建军: process_steps too generic

- 029_无机酸铝体系氧化铝连续纤维的制备技术研究: process_steps too generic

- 030_气电纺丝法制备硅铝增强氧化铈纳微纤维: process_steps too generic

- 031_氧化硅_氧化铝前驱体结晶结构演变及其在氧化铝纤维制备中的应用研究: process_steps too generic

- 033_氧化铝_氧化锆前驱体纤维纺丝液的制备技术研究: process_steps too generic

- 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究: process_steps too generic

- 035_氧化铝基陶瓷连续纤维研究进展: process_steps too generic

- 036_氧化铝溶胶浸渍法制备氧化铝纤维的工艺研究: process_steps too generic

- 037_氧化铝纤维制备工艺及表面涂层性能表征研究: process_steps too generic

- 038_氧化铝纤维基层状多孔陶瓷的制备与性能研究: process_steps too generic

- 039_氧化铝纤维晶相抑制剂SiO_2前驱体的选择_宋士玮: process_steps too generic

- 041_氧化铝连续纤维前驱体的制备与表征: process_steps too generic

- 042_氧化铝连续纤维的研制及表征（初步搞到这里了）: process_steps too generic

- 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛: process_steps too generic

- 045_溶胶—凝胶法制备α-Al_2O_3纤维的相变与微观形貌控制_李相东: process_steps too generic

- 046_溶胶—凝胶法制备氧化铝基纤维研究: process_steps too generic

- 048_溶胶—凝胶法制备钛酸铝纤维的研究: process_steps too generic

- 049_溶胶组成对氧化铝纤维微观结构及性质的影响: process_steps too generic

- 050_烧结温度对莫来石纤维组织结构和性能的影响: process_steps too generic

- 051_稀土氧化物对低温固相合成镁铝尖晶石纤维的影响: process_steps too generic

- 054_纳米α-Al_2O_3籽晶的合成及其在制备α-Al_2O_3纤维中的应用_肖泓芮: process_steps too generic

- 055_纳米氧化铝纤维基多孔陶瓷的制备与性能研究: process_steps too generic

- 056_莫来石-氧化铝复合连续纤维制备及研究: process_steps too generic

- 057_莫来石纤维复合网络二级结构的可控化研究: process_steps too generic

- 058_莫来石纳米纤维复合材料的制备及隔热研究: process_steps too generic

- 059_连续氧化铝纤维及其复合材料的研究进展: process_steps too generic

- 062_连续铝硅酸盐纤维增强Al_2O_3-ZrO_2陶瓷基复合材料的制备与表征_张锦昌: process_steps too generic

- 081_Al_sub_2__sub_O_sub_3__sub_-ZrO_sub_2__sub_复合膜的制备与表征: process_steps too generic

- 020_拟薄水铝石中水的存在形式及对其溶胶性能的影响: process_steps too generic

- 021_拟薄水铝石溶胶—凝胶过程的影响因素研究: process_steps too generic

- 024_拟薄水铝石胶溶过程参数及胶团结构: process_steps too generic

- 025_拟薄水铝石胶溶过程研究: process_steps too generic

- 018_干法纺丝中羧酸铝溶胶的流变行为及结构演变模拟: process_steps too generic

- 022_拟薄水铝石溶胶性能的影响因素研究: process_steps too generic

- 043_浅谈氧化铝溶胶制备中溶胶黏度的变化: process_steps too generic

- 065_铝基水溶胶体的制备和特性研究: process_steps too generic

- 006_Γ-Al_2O_3_A-Al_2O_3中空纤维复合膜的制备与性能研究_张许: process_steps too generic

- 012_基于拟薄水铝石氧化铝气凝胶制备工艺研究: process_steps too generic

- 052_纤维增强氧化铝基气凝胶复合材料的制备及性能研究: process_steps too generic

## Recommendation

The reevaluated next50 set still does not pass the current quality gate. Do not expand to 100 yet.
