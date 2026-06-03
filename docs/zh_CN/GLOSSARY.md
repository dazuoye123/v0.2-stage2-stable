# 术语表

| 中文名 | 英文名 | 简短解释 | 对应文件或输出位置 |
|---|---|---|---|
| Stage 3 | Stage3 | 文本结构化抽取阶段 | `stage3_*`，Stage 3 输出 |
| Stage 4 | Stage4 | 图像与谱图抽取阶段 | `stage4/`，`stage4_vision_spectra_universal/` |
| Stage 5 | Stage5 | 融合阶段 | `stage5/`，`final_dataset/` |
| 批量运行器 | batch runner | 批量处理多篇论文的脚本或模块 | `run_stage4_batch.py`，`run_stage5_batch.py` |
| 全流程 | full pipeline | 顶层编排工作流 | `scripts/run_full_pipeline.py` |
| 图谱集 | figure atlas | 基于已有结果生成的审计/绘图包 | `scripts/run_figure_atlas.py`，`figure_atlas/` |
| 链接感知导出 | link-aware export | 带链接上下文的单篇导出表 | `final_dataset/link_aware_exports/` |
| 确定性链接 | deterministic linking | 基于规则的 evidence / spectra / process step / parameter 连接 | `stage5/linking/` |
| 证据链接 | evidence link | evidence object 到 parameter 的链接 | `evidence_parameter_links.csv` |
| 谱图链接 | spectra link | spectra 到 parameter 的链接 | `spectra_parameter_links.csv` |
| 工艺步骤链接 | process-step link | process step 到 parameter 的链接 | `process_step_parameter_links.csv` |
| 样品矩阵 | sample matrix | sample-by-parameter 导出矩阵 | `sample_parameter_matrix.csv` |
| 最终数据集 | final dataset | 单篇论文 Stage 5 输出包 | `final_dataset/` |
| 批量最终导出 | batch final export | 跨论文聚合导出包 | `data/outputs/_batch_final_exports/` |
| 兼容 wrapper | legacy wrapper | 转发到新实现或 archive 实现的兼容脚本 | `scripts/dev/*`，`scripts/run_research_figures.py` |
| 归档 | archive | 历史实现存放区 | `archive/` |
| 干跑 | dry-run | 只规划或不触发 live 调用的模式 | Stage 4 batch、Stage 5 batch、full pipeline |
| 跳过已有结果 | skip-existing | 跳过已完成输出 | Stage 5 batch |
| 仅处理不完整 | only-incomplete | 只处理缺少 Stage 5/linking/export 关键文件的论文 | Stage 5 batch |
| 强制补跑 | force rerun | 覆盖已有结果重新执行 | Stage 4 / Stage 5 受控补跑 |
| 部分成功 | partial success | 有可用输出，但仍带 warning 或覆盖不足 | `stage5_summary.json`、batch 报告 |
| QA 图 | QA figure | 用于质量检查的 atlas 图 | `figures/qa/` |
| source data | source data | 构成 atlas 图的源 CSV / JSON | `tables/{figure_id}_source.csv`，`figure_data/{figure_id}.json` |
| 归一化表 | normalized table | atlas 使用的标准化表层 | `tables/normalized_*.csv` |
| 清单 | manifest | 记录生成物和计数的结构化摘要 | `figure_atlas_manifest.json` |
| 图索引 | figure_index | atlas 中所有图的一览表 | `figure_index.csv` |

