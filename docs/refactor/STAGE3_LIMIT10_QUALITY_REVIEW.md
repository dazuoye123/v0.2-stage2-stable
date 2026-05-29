# Stage 3 Limit10 Quality Review

## Overall conclusion
本次检查不是 dry-run，而是对 `stage3_limit10` 的 10 篇 **full live Stage 3** 输出做直接质量抽查。整体判断是：**可以作为后续 `two-pass`/`unified` 的质量基线，但还不能作为直接全量生产基线**。

原因很明确：
- 优点：10/10 都成功跑完；`process_steps` 并非空壳，很多论文能抽出真实实验操作；多数论文的 `samples / experiment_series / process_steps / evidence` 至少有一部分结构可用。
- 主要问题：`cleaned_body.md` 在 10 篇里有 7 篇仍残留 Stage 2 图片 markdown 链接；部分论文 `data_points` 的 canonical key 归一化很差；部分论文 `evidence_objects` 为 0 或 figure 对齐很弱；少数论文 `procedure_sections/process_steps` 过碎，且混入结果讨论内容。

结论上，**full Stage 3 值得作为 low-cost mode 的对比基线**，但不建议直接拿 current full 版本全量 343 篇上线，更不建议在不修 `cleaned_body` 的情况下继续扩大 live 成本。

## Reviewed data
检查范围：`data/batch_validation_reports/stage3_limit10/stage3_batch_report.csv` 对应的 10 篇成功论文。

实际读取文件包括：
- `stage3_summary.json`
- `stage3_validation_report.md`
- `paper_extraction.schema_v2.json`
- `process_steps.jsonl`
- `data_points.jsonl`
- `evidence_objects.jsonl`
- `experiment_series.jsonl`
- `paper_basic_info.json`
- `global_constants.json`
- `stage3_procedure_sections.json`
- `stage3_text/cleaned_body.md`
- `stage3_text/markdown_trim_report.json`

## Per-paper summary

| category | paper_id | samples_count | parameters_count | process_steps_count | evidence_count | procedure_sections_count | main_quality_issue | quality_grade |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| fiber_process | 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | 2 | 7 | 10 | 2 | 7 | data_points 几乎全是 `canonical_key=null`，evidence 为空 | C |
| fiber_process | 004_Sol-Gel法制备新型多晶钇-铝石榴石纤维 | 1 | 5 | 13 | 8 | 13 | process_steps 尚可，但 data_points 全部 `canonical_key=null`，evidence 为空 | C |
| fiber_process | 005_α-A12O3连续纤维的制备与表征 | 3 | 10 | 9 | 3 | 50 | section-aware 截断有效，但 data_points 仍大面积 `canonical_key=null`，evidence figure 对齐弱 | C |
| fiber_process | 009_含硅氧化物连续纤维的制备及其性质的研究 | 2 | 7 | 31 | 10 | 42 | canonical key 和 evidence 对齐都不错，但 process_steps 明显过碎 | B |
| fiber_process | 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | 5 | 12 | 23 | 11 | 54 | 结构化程度较高，但存在 duplicate id flag，procedure_sections 偏宽 | B |
| fiber_process | 011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦 | 3 | 7 | 4 | 3 | 12 | process_steps 混入结果讨论与热处理结论，不够像纯方法步骤 | C |
| fiber_process | 013_多孔莫来石纤维基隔热陶瓷的制备与性能研究 | 10 | 14 | 43 | 4 | 74 | process_steps 和 procedure_sections 严重过碎，canonical key 仍有明显空值 | C |
| fiber_process | 014_多晶型氧化铝连续纤维的研制及性能 | 6 | 6 | 17 | 9 | 56 | process_steps 可读，但 parameter canonical 化较弱，cleaned_body 冗长 | B |
| fiber_process | 015_多晶莫来石纤维的制备研究 | 1 | 7 | 6 | 7 | 12 | process_steps 较像真实方法，canonical key 也较好，但 evidence 对图表对齐不稳定 | B |
| fiber_process | 016_多晶莫来石纤维纺丝原液制备与可纺性研究 | 3 | 22 | 4 | 7 | 13 | samples/data_points 最完整，但 cleaned_body 仍残留大量图片 markdown | A |

A/B/C/D 统计：
- A = 1
- B = 4
- C = 5
- D = 0

## Process steps review
整体结论：**process_steps 基本可用，但一致性不够稳定**。

优点：
- `002`、`004`、`015`、`016` 的步骤明显来自制备/实验部分，而不是纯粹瞎编。
- 多数 step 至少包含了 `action / description / temperature / duration / condition` 中的一部分。
- `002` 的“铝溶胶制备 -> 添加助剂与硅溶胶 -> 溶胶浓缩”链路比较像真实实验流程。
- `015` 的“回流 -> 加入酸性硅溶胶和 PVA -> 真空浓缩”也比较贴近论文方法部分。

问题：
- `009` 和 `013` 的 `process_steps_count` 分别达到 31 和 43，明显偏碎，像是把连续实验叙述切成了太多小块。
- `011` 的步骤混入了“不同热处理温度下 XRD 结果/物相变化”的结果讨论，这不应该算纯工艺步骤。
- 很多 step 的 `action` 被泛化成 `other`，可读但不够结构化。
- 不少 step 的 `evidence_text` 为空，导致后续可追溯性不足。

代表例子：
- 好例子：`002` 的 `step-01 ~ step-03`，动作、温度、比例、结果对象都比较自然。
- 好例子：`015` 的 `step-01 ~ step-03`，能看出“原料 -> 条件 -> 浓缩 -> 结果”的实验路径。
- 差例子：`011` 的 `step-02` 和 `step-03`，把不同温度/保温时间下的相变与结果观察写成了工艺步骤，说明 procedure section 边界不够干净。

## Parameters / data_points review
整体结论：**两极分化明显**。

较好的部分：
- `009`、`010`、`011`、`015`、`016` 的 `independent_variable_values` 中已经能出现真实 `canonical_key`，例如 `solid_content_wt_percent`、`pva_content_wt_percent` 等。
- `016` 的 data points 最像“可以直接用于后续比较”的结构化样本：sample、变量、结果、表格 evidence 都有一定对应关系。

明显问题：
- `002`、`004`、`005` 的 parameter/data_point 质量明显不够，`canonical_key` 空值比例达到 **100%**。
- 这些论文里大量 parameter 被塞进 `additional_parameter_records`，但结构是：
  - `raw_name = parameter/value/unit/series_id`
  - `canonical_key = null`
  这更像 LLM 输出的“半结构 JSON”，还没真正落到 ontology/canonical schema 上。
- 很多 `data_points` 没有 `source_text` 字段，只剩 `raw_text` 或 `extended_data.unclassified_results`，对后续校验不够友好。
- 有的 datapoint 把结论性文字塞进 `unclassified_results`，例如 spinnability/appearance 还能接受，但更细颗粒度参数的证据追溯不稳定。

所以如果把 full Stage 3 当质量基线，**parameter 质量不能只看数量，必须看 canonical 落地率**。

## Evidence review
整体结论：**evidence_objects 有一半以上论文是可用的，但稳定性不够，不能当“完全可靠”层**。

较好的部分：
- `009`、`010`、`011` 的 evidence 与 Stage 2 `figure_id` 对齐较好，figure_id 匹配数等于 evidence 数量。
- `016` 也有一定 figure 对齐能力，能把表格和图的事实链挂到 `evidence_refs`。
- 所有抽查论文里没有看到 duplicate `evidence_id` 问题。

问题：
- `002` 和 `004` 的 `evidence_objects` 实际是 0，说明 full 模式也不是每篇都能稳定产出 evidence。
- `005` 虽然有 evidence，但 `matched_figure_refs = 0`，说明 evidence 内容与 Stage 2 figure linkage 很弱。
- 一些论文的 evidence 会带 caption/fact，但 `figure_id` 为空，或者只能靠 caption fallback 判断类型，削弱了可追溯性。
- 某些 evidence 更像“图表结论描述”，而不是严格参数支撑证据。

因此，evidence 这一层**够做基线比较，但不够做最终自动信任层**。

## Cleaned body review
这是这次最明确、最高优先级的问题之一。

结论：**当前 `stage3_limit10` 的 full 输出里，10 篇中有 7 篇 `cleaned_body.md` 仍残留图片 markdown 链接**。

受影响论文包括：
- `009_含硅氧化物连续纤维的制备及其性质的研究`
- `010_含硼氧化铝基陶瓷连续纤维的制备及表征`
- `011_固相反应合成MgAl_2O_4多孔纤维的研究_王昕悦`
- `013_多孔莫来石纤维基隔热陶瓷的制备与性能研究`
- `014_多晶型氧化铝连续纤维的研制及性能`
- `015_多晶莫来石纤维的制备研究`
- `016_多晶莫来石纤维纺丝原液制备与可纺性研究`

这些残留大多是：
- `![](G:/.../figures_all/xxx.jpg)`
- 紧跟 `<details>` 块或图后说明

好消息：
- 目录、参考文献、致谢等 front/back matter 基本已经裁掉。
- 图题文字大体保留了。

坏消息：
- 图片 markdown 链接仍然会直接膨胀 token 成本；
- 还会把 Stage 2 图像上下文噪声重新灌回 Stage 3 prompt；
- 这也是为什么 current full 成本偏高、且 section-aware 长文本文档里容易混入图相关冗余。

## Top problems
1. **cleaned_body 仍残留图片 markdown 链接（7/10）**
   这是最明确、最值得优先修的成本与质量问题，会直接抬高 token 消耗并污染输入文本。

2. **parameter/data_point 的 canonical 落地率不稳定**
   `002/004/005` 三篇里 `canonical_key` 空值比例达到 100%，说明 full 模式虽然“跑出来了”，但不等于真正结构化成功。

3. **process_steps 在长论文里过碎，且个别论文混入结果讨论**
   `009/013` 过碎，`011` 混入相变/XRD 结果描述。这会影响后续 process-step linking 的稳定性。

4. **evidence_objects 并非每篇都稳定可用**
   有的论文 evidence 为 0，有的虽然非 0，但与 Stage 2 figure_id 对齐较弱，说明 evidence 层还不能完全自动信任。

5. **section-aware 截断虽有效，但 procedure_sections 边界仍偏宽**
   `005/009/010/013/014` 的 `procedure_sections_count` 很高，说明程序在“找到相关段落”上偏保守，后续容易把方法和讨论混在一起。

## Recommendation
1. **full Stage 3 是否值得作为后续 two-pass 对比基线：值得。**
   尽管它不完美，但它是目前最完整、真实 live 跑通的质量上限版本，足以作为后续 `two-pass/unified` 的比较基线。

2. **是否应该先修 cleaned_body 图片链接：应该，而且优先级最高。**
   这是最明确的低风险修复点，既能降成本，也能净化 Stage 3 输入。

3. **是否应该继续开发 two-pass：应该。**
   但建议目标不是“完全替代 full”，而是：
   - 先对齐 `process_steps`
   - 再对齐 `samples/series`
   - 最后对齐 `data_points/evidence`

4. **是否建议直接 full 全量：不建议。**
   原因不是 full 跑不通，而是：
   - 成本太高
   - cleaned_body 仍脏
   - canonical/data_point 质量波动还比较大

5. **是否建议先 two-pass limit10 与 full limit10 对比：强烈建议。**
   当前最合理的下一步不是继续扩大 live full，而是：
   - 先修 `cleaned_body` 去图
   - 再跑 `two-pass limit10`
   - 用 current full limit10 当质量基线做逐项对比
