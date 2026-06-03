# Legacy Tools

## `archive/` 是什么

`archive/` 用来存放不再推荐作为主运行路径的历史实现。

## `scripts/dev/` wrapper 是什么

现在很多 `scripts/dev/*` 都是薄 wrapper，真正实现已经放进 `archive/`。

这样做是为了：

- 保留旧命令
- 不打断旧笔记和历史操作
- 让官方入口更清楚

## `research_figures` 现在是什么

`research_figures` 现在只保留 legacy compatibility。

推荐替代路径：

- `scripts/run_figure_atlas.py`

## 历史命名

兼容层里仍能看到这些旧名：

- `stage4a`
- `stage55`
- `stage6c`

当前新文档统一使用：

- `stage4`
- `linking`
- `full_pipeline`

## 为什么不建议新用户继续用旧命令

旧命令和旧命名：

- 更难理解
- 常常对应旧报告格式
- 可能保留某些一次性 repair / replay 路径，不适合作为常规工作流

## 迁移映射表

| Legacy | Current |
|---|---|
| `scripts/dev/run_stage5_batch.py` | `scripts/run_stage5_batch.py` |
| `scripts/run_research_figures.py` | `scripts/run_figure_atlas.py` |
| `stage4a` | `stage4` |
| `stage55` | `linking` |
| `stage6c` | `full_pipeline` |

