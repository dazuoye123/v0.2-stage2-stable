# 架构说明

## 官方入口

当前维护中的正式入口全部位于 `scripts/`：

- `run_full_pipeline.py`
- `run_stage4_batch.py`
- `run_stage5_batch.py`
- `export_link_aware_dataset.py`
- `export_batch_link_aware_dataset.py`
- `run_figure_atlas.py`

## 运行层次

### CLI 层

- `scripts/` 下的薄包装脚本
- 负责解析参数、解析相对路径、调用 `src/` 模块

### 编排层

- `src/alumina_sol_extractor/pipeline/orchestrator.py`
- `src/alumina_sol_extractor/pipeline/full_pipeline_runner.py`
- `src/alumina_sol_extractor/pipeline/resume_status.py`

### 阶段层

- `stage1/`
- `stage2/`
- `stage3/`
- `stage4/`
- `stage5/`

### 分析 / 绘图层

- `figure_atlas/`

## pipeline orchestration

`orchestrator.py` 现在是首选的正式编排层。

它负责：

- 缺失 Markdown 时的 Stage 1 恢复
- 全流程 resume 执行
- Stage 5-only 复用路径
- link-aware export 汇总写入

`full_pipeline_runner.py` 仍然保留了较多旧兼容逻辑和旧命名。

## Stage 3 模块职责

Stage 3 负责：

- 文本裁剪
- section 选择
- process steps 抽取
- parameters / evidence 抽取
- 校验与质量评级

## Stage 4 模块职责

Stage 4 负责：

- 读取 Stage 2 已筛图
- per-figure routing
- live 模式下的 VLM 调用
- normalization 和 validation
- processed-index dedup
- fallback / replay 兼容逻辑

## Stage 5 模块职责

Stage 5 负责：

- dataset fusion
- deterministic linking
- per-paper link-aware export
- batch-level aggregation

## Linking 与 export 模块

代码里同时保留了：

- `src/alumina_sol_extractor/linking/`
- `src/alumina_sol_extractor/stage5/linking/`

以及：

- `src/alumina_sol_extractor/dataset_fusion/`
- `src/alumina_sol_extractor/stage5/dataset_fusion/`

当前官方 batch 入口主要走 Stage 5 命名空间；兼容导入仍然保留。

## figure_atlas 模块

`figure_atlas/` 是只读下游分析层。

它依赖：

- audit 与 discovery
- normalized tables
- 分层 figure generators
- per-figure source CSV / JSON

## 兼容命名空间

以下兼容命名空间仍然存在：

- `vision_spectra`
- `dataset_fusion`
- `linking`
- `research_figures`
- `batch_validation`

如果已经有明确的官方入口，不应把这些兼容层当作用户第一选择。

## legacy wrappers

`scripts/dev/` 下很多脚本现在都是 wrapper，会转发到 `archive/` 中的历史实现。

目的：

- 保留旧命令
- 不打断旧笔记和历史排障流程
- 让正式入口更干净

## 归档策略

`archive/` 用来存放不再推荐作为主运行路径的历史实现。

它仍然有价值的场景包括：

- 回看旧审计 / 修复脚本
- 理解历史 replay / rerun 方案
- 追踪旧命令到新入口的迁移关系

## 测试策略

仓库当前依赖广覆盖回归测试，包括：

- Stage 3 tests
- Stage 4 tests
- Stage 5 tests
- linking tests
- batch export tests
- figure atlas tests
- full pipeline tests
- compatibility tests

## 数据安全策略

源码仓库不应提交运行产物，例如：

- `data/outputs/`
- `data/batch_validation/`
- `data/analysis_outputs*/`
- `presentation_outputs/`
- `tmp_*/`

## 后续可扩展点

- 提升 deterministic linking coverage
- 继续增强 figure_atlas 的 source normalization
- 进一步收缩 legacy wrapper 的数量

