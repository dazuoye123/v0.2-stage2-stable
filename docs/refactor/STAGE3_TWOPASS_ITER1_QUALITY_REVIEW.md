# Stage 3 Two-Pass Iter1 Quality Review

## Overall conclusion

当前 20 篇 two-pass live 抽查未达到质量门槛。A+B=5，C=14，D=1。主要问题仍集中在 data_points schema、evidence 对齐，以及少量综述/研究进展类论文的 process_steps。

## Per-paper summary

| category | paper_id | samples_count | parameters_count | process_steps_count | evidence_count | procedure_sections_count | main_quality_issue | quality_grade |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| fiber_process | 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | 0 | 0 | 5 | 2 | 7 | mixed_quality_issues | C |
| fiber_process | 004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 | 5 | 22 | 10 | 8 | 13 | mixed_quality_issues | B |
| fiber_process | 005_α-A12O3连续纤维的制备与表征 | 4 | 14 | 4 | 19 | 50 | raw_name_key_value_bug | C |
| fiber_process | 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | 2 | 24 | 8 | 26 | 54 | mixed_quality_issues | C |
| fiber_process | 013_多孔莫来石纤维基隔热陶瓷的制备与性能研究 | 4 | 7 | 8 | 36 | 73 | mixed_quality_issues | B |
| fiber_process | 014_多晶型氧化铝连续纤维的研制及性能 | 4 | 22 | 5 | 49 | 56 | raw_name_key_value_bug | C |
| fiber_process | 035_氧化铝基陶瓷连续纤维研究进展 | 0 | 0 | 5 | 17 | 41 | stage3_failed | D |
| fiber_process | 059_连续氧化铝纤维及其复合材料的研究进展 | 0 | 0 | 29 | 5 | 18 | mixed_quality_issues | C |
| fiber_process | 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 | 0 | 0 | 5 | 87 | 106 | mixed_quality_issues | C |
| fiber_process | 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究 | 0 | 0 | 12 | 80 | 82 | mixed_quality_issues | C |
| fiber_process | 064_铁复合铝硅系溶胶制备及其性能基础研究 | 4 | 15 | 5 | 27 | 67 | mixed_quality_issues | C |
| fiber_process | 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响 | 4 | 24 | 5 | 5 | 11 | mixed_quality_issues | B |
| fiber_process | 068_镁铝尖晶石纤维及纤维板的制备与性能研究 | 3 | 18 | 7 | 15 | 90 | mixed_quality_issues | B |
| fiber_process | 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m | 1 | 5 | 4 | 8 | 3 | raw_name_key_value_bug | C |
| fiber_process | 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method | 0 | 0 | 7 | 9 | 4 | mixed_quality_issues | C |
| fiber_process | 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol | 2 | 16 | 5 | 11 | 10 | process_steps_weak_or_zero | C |
| fiber_process | 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber | 2 | 10 | 6 | 9 | 11 | process_steps_weak_or_zero | C |
| mechanism | 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞 | 4 | 21 | 4 | 7 | 13 | mixed_quality_issues | B |
| mechanism | 008_前驱体铝溶胶中的水解和聚合反应的机理研究 | 3 | 15 | 6 | 9 | 79 | mixed_quality_issues | C |
| mechanism | 023_拟薄水铝石胶溶机理的探究 | 3 | 34 | 3 | 7 | 15 | raw_name_key_value_bug | C |

## Top problems

- mixed_quality_issues: 13
- raw_name_key_value_bug: 4
- process_steps_weak_or_zero: 2
- stage3_failed: 1

## Recommendation

1. 第 1 轮未达标，不应继续跑剩余论文。
2. 第 2 轮优先修：残留 flat parameter bundle 变体（尤其 evidence_ref）、data_point_count=0 的回退、以及 review/综述类论文的 procedure/process gating。
3. 暂不建议切 DeepSeek Flash；当前主问题仍是 two-pass 结构化后处理。
