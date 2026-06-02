# RUN_RESEARCH_FIGURES

## 功能定位

`research_figures` 是一个独立的 **Stage3 + Stage4 科研绘图模块**。

它只负责：

- 读取已有 Stage3 analysis 输出
- 读取已有 Stage4 输出
- 做 Stage4 batch-level 统计汇总
- 构建 Stage3 + Stage4 联合绘图数据
- 输出 SVG + PNG 科研图
- 输出对应 CSV / JSON 作为绘图数据来源

它不会：

- 重跑 Stage3
- 重跑 Stage4
- 调用 LLM
- 调用 VLM
- 接入 `run_full_pipeline.py`
- 生成每篇文献的 summary 报告

## CLI

```powershell
python .\scripts\run_research_figures.py `
  --outputs-dir ".\data\outputs" `
  --batch-output-dir ".\data\batch_validation" `
  --generate-figures
```

也支持用 manifest 限定批次范围：

```powershell
python .\scripts\run_research_figures.py `
  --outputs-dir ".\data\outputs" `
  --batch-output-dir ".\data\batch_validation" `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --generate-figures
```

## 输入来源

Stage3 优先复用：

- `data/analysis_outputs_stage3_v2/`
- 回退到 `data/analysis_outputs_stage3/`
- 可选读取 `data/analysis_outputs_stage3_publication/`

Stage4 读取：

- `data/outputs/{category}/{paper_id}/stage4_vision_spectra_universal/`
- 回退到 `data/outputs/{category}/{paper_id}/stage4_vision_spectra/`

如果存在 `final_dataset/` 与 `final_dataset/linking/`，会用于构建 Stage3 / Stage4 linkage overview。

## 输出目录

输出到：

`data/batch_validation/{timestamp}/research_figures/`

其中包含：

- `figures/*.svg`
- `figures/*.png`
- `tables/*.csv`
- `figure_data/*.json`
- `stage3_stage4_figure_data.csv`
- `batch_research_figures.md`

## 主要图

- `stage3_parameter_coverage`
- `stage3_sample_parameter_heatmap`
- `stage3_numeric_parameter_distribution`
- `stage4_extraction_overview`
- `stage4_figure_type_distribution`
- `stage4_spectra_type_distribution`
- `stage4_peak_summary`
- `stage3_stage4_link_overview`
- `stage3_stage4_research_overview`

## 绘图规范

- Python + matplotlib
- Agg backend
- 不使用 seaborn
- SVG 主输出
- PNG 300 dpi 预览
- 白底
- 标签清晰
- 图例简洁
- 支持 empty-data fallback
- 某类数据缺失时不崩溃
