# STAGE3 Analysis Outputs Build Report

## 执行约束

- 是否调用 LLM：没有
- 是否调用 VLM：没有
- 是否重跑 Stage3：没有
- 是否运行 Stage4A：没有
- 是否运行 Stage5：没有
- 是否运行 MinerU：没有

## 构建结果

- 读取了多少篇 stage3_twopass：343
- 成功解析多少篇：343
- 缺失/不可读多少篇：0
- 总 data_points 数：5683
- 总 process_steps 数：2819
- 总 evidence_objects 数：3289
- unique canonical_key 数：102

## Top 20 canonical_key

- nmr_27Al_peak_position_ppm: 315
- pH: 219
- particle_size_nm: 188
- ftir_peak_position_cm_1: 173
- Al_concentration_mol_L: 164
- calcination_temperature_C: 135
- mass_loss_wt_percent: 134
- aging_time_h: 124
- specific_surface_area_m2_g: 115
- heating_rate_C_min: 114
- aging_temperature_C: 109
- holding_time_h: 107
- dsc_peak_temperature_C: 104
- solid_content_wt_percent: 99
- average_fiber_diameter_um: 89
- viscosity_Pa_s: 82
- tensile_strength_MPa: 80
- hydrolysis_temperature_C: 78
- drying_temperature_C: 73
- sintering_temperature_C: 67

## Top 20 process action

- other: 671
- stir: 256
- heat: 224
- dry: 212
- electrospin: 207
- hydrolyze: 186
- add: 183
- dissolve: 161
- age: 130
- prepare: 112
- calcine: 104
- sinter: 60
- add_polymer: 39
- mix: 39
- cool: 37
- filter: 36
- impregnate: 32
- wash: 26
- weigh: 14
- load: 11

## 已生成图表

- stage3_pipeline_funnel
- parameter_distribution_top30_bar
- canonical_key_category_heatmap
- process_step_action_distribution
- process_route_sankey
- process_condition_distribution
- sample_parameter_matrix_sparsity_heatmap
- parameter_cooccurrence_network
- stage3_quality_distribution
- category_contribution_summary
- stage3_overview_dashboard

## 图表数据来源

- stage3_pipeline_funnel: source_manifest.csv + stage3_summary.json
- parameter_distribution_top30_bar: sample_parameter_long.csv / parameter_distribution.csv
- canonical_key_category_heatmap: canonical_key_by_category.csv
- process_step_action_distribution: process_step_action_distribution.csv
- process_route_sankey: process_steps 按 step_order 映射后的高层阶段转移
- process_condition_distribution: process_condition_distribution.csv
- sample_parameter_matrix_sparsity_heatmap: sample_parameter_long.csv 聚合存在矩阵
- parameter_cooccurrence_network: parameter_cooccurrence_edges.csv
- stage3_quality_distribution: paper_stage3_summary.csv
- category_contribution_summary: paper_stage3_summary.csv 按 category 聚合
- stage3_overview_dashboard: 漏斗 + 参数分布 + 动作分布 + category 贡献综合汇总

## 数据不足说明

- 无；全部图均使用实际 Stage3 数据生成。

## 已生成表格

- paper_stage3_summary.csv
- parameter_distribution.csv
- canonical_key_by_category.csv
- process_step_action_distribution.csv
- process_condition_distribution.csv
- sample_parameter_long.csv
- sample_parameter_wide.csv
- parameter_cooccurrence_edges.csv
- stage3_quality_flags.csv
- stage3_analysis_summary.json

## 组会展示推荐

- stage3_pipeline_funnel
- parameter_distribution_top30_bar
- canonical_key_category_heatmap
- process_step_action_distribution
- sample_parameter_matrix_sparsity_heatmap

## 论文方法学图推荐

- stage3_pipeline_funnel
- process_route_sankey
- process_condition_distribution
- canonical_key_category_heatmap
- stage3_overview_dashboard

## Stage4A / Stage5 后续可补强内容

- 融合 Stage4A 光谱/显微视觉结果后的参数-证据跨模态覆盖图。
- 融合 Stage5 link-aware 数据后的 sample-parameter-evidence 三部图。
- 参数与谱图峰位、图像表征类别之间的跨模态共现网络。
- 进入最终数据集前后的漏斗对比图和质量提升对比图。
- 面向论文方法学的“文本抽取到证据链接再到结构化数据集”全流程图。

## Generated Outputs

- 主要生成目录：G:/paper/Al-gel-sol/alumina_sol_extractor/data/analysis_outputs_stage3
- 这些 CSV/JSON/PNG/SVG 为 generated outputs，本次默认保留本地，不要求全部 commit。
