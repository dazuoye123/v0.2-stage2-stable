# alumina_sol_extractor

用于氧化铝溶胶与氧化铝纤维文献的结构化抽取管线。

## 项目概览

这个仓库的目标是把 PDF 或 Markdown 文献转换成后续分析可直接使用的结构化研究数据。

当前维护中的主流程包括：

- Stage 1 / Stage 2 预处理
- Stage 3 文本结构化抽取
- Stage 4 图像与谱图抽取
- Stage 5 融合、linking 与 link-aware export
- 批量最终导出
- 基于已有结果生成 figure atlas（图谱集）

## 官方入口

正常运行请优先使用以下脚本：

- `python scripts/run_full_pipeline.py`
- `python scripts/run_stage4_batch.py`
- `python scripts/run_stage5_batch.py`
- `python scripts/export_link_aware_dataset.py`
- `python scripts/export_batch_link_aware_dataset.py`
- `python scripts/run_figure_atlas.py`

仓库里仍然保留了一些 legacy 工具和兼容 wrapper，但不再建议新用户把它们当作主入口。

## 快速开始

建议先创建独立环境：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

兼容安装方式：

```bash
pip install -r requirements.txt
```

常见命令示例：

```bash
python scripts/run_stage4_batch.py --outputs-dir .\data\outputs
python scripts/run_stage5_batch.py --outputs-dir .\data\outputs --report-dir .\data\analysis_outputs_stage5_batch --with-linking --skip-existing
python scripts/export_batch_link_aware_dataset.py --outputs-dir .\data\outputs --output-dir .\data\outputs\_batch_final_exports
python scripts/run_figure_atlas.py --outputs-dir .\data\outputs --batch-final-export-dir .\data\outputs\_batch_final_exports --batch-output-dir .\data\batch_validation --audit-only
```

## 输出位置

常见输出目录：

- 单篇论文输出：`data/outputs/{category}/{paper_id}/`
- Stage 5 批量报告：`data/analysis_outputs_stage5_batch/`
- 批量 link-aware export：`data/outputs/_batch_final_exports/`
- figure atlas 运行结果：`data/batch_validation/{timestamp}/figure_atlas/`

## 文档入口

- 中英文文档索引： [docs/README.md](./docs/README.md)
- 英文首页： [README.md](./README.md)

## 历史工具说明

下面这些名称或路径现在只作为兼容概念保留，不再是当前主流程推荐叫法：

- `Stage4A` -> `Stage4`
- `stage55` -> `linking`
- `stage6c` -> `full pipeline`
- `scripts/dev/*`
- `scripts/run_research_figures.py`

详细说明见：[docs/LEGACY_TOOLS.md](./docs/LEGACY_TOOLS.md)

## 不要提交的内容

请不要提交运行产物，例如：

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## 仓库现状

- 当前维护中的运行时代码：`src/alumina_sol_extractor/`
- 历史工具归档：`archive/`
- 回归测试：`tests/`

