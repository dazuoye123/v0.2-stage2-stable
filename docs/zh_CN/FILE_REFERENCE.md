# 文件参考

## `scripts/`

### `scripts/run_full_pipeline.py`

- 用途：官方顶层 CLI
- 读取：CLI 参数与项目路径
- 输出：通过 orchestrator 调用生成批量报告和下游结果
- 主调用函数：`alumina_sol_extractor.pipeline.orchestrator.run_full_pipeline_orchestrated`
- 备注：保留了 Stage 4 的 legacy alias

### `scripts/run_stage4_batch.py`

- 用途：官方 Stage 4 batch CLI
- 读取：`data/outputs/{category}/{paper_id}`，以及可选 manifest / figure id
- 输出：Stage 4 per-paper 结果和 batch 报告
- 主调用函数：`alumina_sol_extractor.stage4.batch_runner.run_stage4_batch`

### `scripts/run_stage5_batch.py`

- 用途：官方 Stage 5 batch CLI
- 读取：Stage 3 和 Stage 4 的 per-paper 输出
- 输出：`final_dataset/`、可选 linking / link-aware export、batch 汇总报告
- 主调用函数：`alumina_sol_extractor.stage5.batch_runner.run_stage5_batch`

### `scripts/export_link_aware_dataset.py`

- 用途：基于已有 `final_dataset/` 重新导出单篇 link-aware 表格
- 主调用函数：`alumina_sol_extractor.dataset_fusion.link_aware_export.generate_link_aware_exports`

### `scripts/export_batch_link_aware_dataset.py`

- 用途：聚合多篇论文的 link-aware exports
- 主调用函数：`alumina_sol_extractor.dataset_fusion.batch_link_aware_export.export_batch_link_aware_dataset`

### `scripts/run_figure_atlas.py`

- 用途：官方 figure atlas CLI
- 主调用函数：`alumina_sol_extractor.figure_atlas.run_figure_atlas`

### `scripts/run_research_figures.py`

- 仅 legacy 使用
- 新路径请改用 `scripts/run_figure_atlas.py`

## `src/alumina_sol_extractor/pipeline/`

### `orchestrator.py`

- 现在的正式编排层
- 负责 Stage 1 恢复、全流程 resume、Stage 5-only 路径和 link-aware export 总结

### `full_pipeline_runner.py`

- 保留旧 full resume 主体实现和兼容逻辑
- 里面仍然能看到 `stage6c`、`stage4a`、`stage55` 等历史命名

### `resume_status.py`

- 负责识别每篇论文当前已经完成了哪些阶段、哪些阶段仍待跑

### `stage1_pdf_to_markdown.py`

- Stage 1 的 PDF 转 Markdown 包装层

### `stage2_figure_pipeline.py`

- Stage 2 的 figure/table 预处理编排辅助

## `src/alumina_sol_extractor/stage4/`

### `extractor.py`

- Stage 4 真正的核心执行逻辑
- 读取 Stage 2 已筛图和 Stage 3 上下文
- 输出：
  - `spectra_extractions.jsonl`
  - `raw_vlm_outputs.jsonl`
  - `spectra_failed_records.jsonl`
  - `stage4a_summary.json`（文件名仍沿用 legacy）

### `batch_runner.py`

- 官方 Stage 4 batch 编排器
- 输出：
  - `stage4_batch_rows.jsonl`
  - `stage4_batch_summary.json`
  - `stage4_batch_report.md`

### `processed_index.py`

- 负责 figure-level dedup、dry-run 识别、replay 分类、retry 分类

### `routing.py`

- Stage 4 路由与 figure type 处理

### `prompt_templates.py`

- Stage 4 prompt 模板

### `schemas.py`

- Stage 4 输出 schema

### `normalization.py`

- Stage 4 原始 payload 的规整层

### `validators.py`

- Stage 4 输出校验辅助

### `stage2_selected_loader.py`

- 从 `figures.jsonl` 或 `figures_for_vision/` 读取 Stage 2 已筛图

### `stage4_context.py`

- 组装 Stage 4 所需文本上下文

### `stage4_failures.py`

- 失败记录与 fallback / previous success 复用逻辑

### `io.py`

- Stage 4 的 JSON / JSONL 读写工具

### `quality_review.py`

- Stage 4 结果 review 辅助

### `reparse.py`

- 已有 Stage 4 raw outputs 的重新解析工具
- 属于 helper / maintenance 路径，不是主用户入口

### `vlm_client.py`

- Stage 4 模型调用包装层
- 只有 Stage 4 live 模式下才会参与

## `src/alumina_sol_extractor/stage5/`

### `batch_runner.py`

- 官方 Stage 5 batch runner
- 支持 dry-run、`--skip-existing`、`--only-incomplete` 以及可选 linking/export

### `dataset_fusion/`

- Stage 5 融合与导出逻辑
- 关键文件：
  - `fusion.py`
  - `loaders.py`
  - `exporters.py`
  - `link_aware_export.py`
  - `batch_link_aware_export.py`
  - `validators.py`
  - `report.py`

### `linking/`

- 确定性 linking 逻辑
- 关键文件：
  - `candidate_builder.py`
  - `models.py`
  - `validators.py`
  - `exporters.py`
  - `report.py`

## `src/alumina_sol_extractor/figure_atlas/`

### `runner.py`

- figure atlas 主运行器
- 只读取已有结果
- 不会重跑 Stage 3 / 4 / 5

### `audit.py`

- 生成 result inventory、availability matrix、feasibility matrix

### `loaders.py`

- 读取 batch export 和分阶段输入表

### `normalization.py`

- atlas 表和绘图前的共用归一化工具

### `table_builder.py`

- 对外稳定 API：`build_normalized_tables(payload)`
- 内部逻辑已经拆到 `figure_atlas/tables/`

### `tables/*`

- 内部表构建器，分别负责 parameters、process steps、spectra、peaks、links、sample matrix 和 category summary

### `main_figures.py`、`stage3_figures.py`、`stage4_figures.py`、`stage5_figures.py`、`cross_stage_figures.py`、`qa_figures.py`、`auto_figures.py`

- 负责不同层级的图生成

### `plot_utils.py`、`plot_style.py`

- 绘图公用工具

### `source_data.py`

- 为每张 atlas 图写入 source CSV 和 source JSON

## `archive/`

- 保存历史工具实现
- 不再推荐作为正式运行入口
- 当前很多 `scripts/dev/*` wrapper 会从这里执行真实实现

## `tests/`

- Stage 4 tests
- Stage 5 tests
- batch export tests
- figure atlas tests
- full pipeline tests
- legacy compatibility tests

