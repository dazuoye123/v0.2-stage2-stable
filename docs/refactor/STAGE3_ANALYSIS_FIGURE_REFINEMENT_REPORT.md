# STAGE3 Analysis Figure Refinement Report

## 原图问题

- `process_step_action_distribution` 中 `other` 占比过高，原始 action canonicalization 对 `拉丝成型`、`干法纺丝`、`高温焙烧`、`Characterization` 等未充分识别。
- `process_condition_distribution` 混入 0、空值、范围串、列表串和异常单位，直接统计会拉低可解释性。
- `canonical_key_category_heatmap` 标签过密，Top key 过多且原始 key 文本太长，不适合 PPT。
- `sample_parameter_matrix_sparsity_heatmap` 维度过大，行标签不可读，不适合展示。
- `parameter_cooccurrence_network` 节点标签重叠，未按参数类型区分颜色，边过滤不足。
- `stage3_overview_dashboard` 版式偏拥挤，不够 16:9 PPT 友好。
- 旧 `process_route_sankey` 命名可能引起误解，因此本轮改成基于真实 transition 的 `process_route_transition_diagram`。

## 重新生成的图

- process_step_action_distribution_cleaned
- calcination_temperature_distribution
- holding_time_distribution
- heating_rate_distribution
- canonical_key_category_heatmap_top20_count
- canonical_key_category_heatmap_top20_normalized
- sample_parameter_matrix_sparsity_heatmap_ppt
- parameter_cooccurrence_network_cleaned
- stage3_overview_dashboard_ppt
- process_route_transition_diagram

## 关键修正结果

- `other` 是否下降：是。原始 `other=671`，清洗后 `other=382`。
- 工艺条件异常值是否清洗：是。清洗后保留 `N=853` 条规范化条件记录，已过滤空值/0/不可解析值，并统一到 `℃`、`h`、`℃/min`。

## 图表适用性

### 适合组会

- process_step_action_distribution_cleaned
- canonical_key_category_heatmap_top20_count
- sample_parameter_matrix_sparsity_heatmap_ppt
- stage3_overview_dashboard_ppt
- calcination_temperature_distribution

### 适合论文

- canonical_key_category_heatmap_top20_normalized
- calcination_temperature_distribution
- holding_time_distribution
- process_route_transition_diagram
- stage3_overview_dashboard_ppt

### 适合内部探索

- parameter_cooccurrence_network_cleaned
- parameter_cooccurrence_network_cleaned_edges
- sample_parameter_sparsity_summary

## 输出位置

- refined 输出目录：G:/paper/Al-gel-sol/alumina_sol_extractor/data/analysis_outputs_stage3_refined
- refined figures 目录：G:/paper/Al-gel-sol/alumina_sol_extractor/data/analysis_outputs_stage3_refined/figures
- 首轮 `data/analysis_outputs_stage3` 结果未被覆盖。
