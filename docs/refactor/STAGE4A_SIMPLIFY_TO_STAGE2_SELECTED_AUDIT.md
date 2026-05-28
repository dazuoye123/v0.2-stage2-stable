# Stage4A Simplify To Stage2-Selected Audit

## 结论

- 当前旧版 Stage4A **确实存在二次筛选**。
- 旧逻辑的 candidate 并不是“Stage2 已筛图 = Stage4A 待看图”，而是把 `figures.jsonl`、`vision_inputs.jsonl`、`evidence_objects.jsonl` 混合后重新构建。
- 旧逻辑里 `total_candidates` / `skipped_count` / `send_to_vision_model_count` 的口径混在一起，**不适合作为正式 full run 的待处理图统计**。
- 旧 runner 默认 `max_figures_per_paper=10`，会把“调试截断”混进正式 summary，**会污染 skipped 统计**。
- 在 `force=True` / `skip_existing=False` 的续跑场景下，旧 runner 存在**论文级通过但图级重复送 VLM**的风险。

## 旧逻辑问题

### 1. 图源不清

旧 extractor 会同时读取：

- `figures.jsonl`
- `vision_inputs.jsonl`
- `stage3_twopass/evidence_objects.jsonl`
- `stage3_twopass/paper_extraction.schema_v2.json`

然后重新拼 candidate。  
这意味着 Stage4A 不只是“看 Stage2 已筛出的图”，而是在 Stage4A 内部又做了一轮“谁算 candidate”的再判断。

### 2. Stage2 类型参与了前置筛选

旧 universal 路由虽然已经弱化了 `stage2_figure_class` 的硬路由，但在候选构建阶段，仍然会借助：

- `initial_figure_type`
- `stage2_figure_class`
- `stage3_figure_type`
- `caption/context`

决定 `send_to_vlm`。  
这会把 Stage4A 变成“再筛图”，而不是“对 Stage2 已选图统一看图 + 统一结构化”。

### 3. `max=10` 会污染正式 summary

旧 extractor 在 candidate 构建后仍会执行：

- `prioritize_sendable_candidates(...)`
- `blocked_ids = prioritized[self.max_figures:]`
- `skip_reason = max_figures_limit`

所以：

- `total_candidates` 不是正式待处理图数
- `skipped_count` 混入了“仅因 debug 截断被跳过”的图
- `032` 这种大论文会出现 `total_candidates` 很大、`processed_count=10`、`skipped_count` 很多的 summary，看起来像“正式跑过”，其实只是 dry-run 占位

### 4. 旧 `skip_existing` 主要是论文级

旧 runner 会先看：

- `stage4a_summary.json`

再决定是否整篇跳过。  
虽然最近已经补上了 figure-level dedup，但旧 runner 的核心入口并没有把：

- `successful_extractions`
- `raw_vlm_outputs`
- `failed_records`

系统地当成“图级 processed index”来驱动正式 audit。

## 现在需要的改动

需要改的文件：

- [src/alumina_sol_extractor/stage4/extractor.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/extractor.py)
- [src/alumina_sol_extractor/stage4/stage2_selected_loader.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/stage2_selected_loader.py)
- [src/alumina_sol_extractor/stage4/processed_index.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/processed_index.py)
- [src/alumina_sol_extractor/stage4/prompt_templates.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/prompt_templates.py)
- [src/alumina_sol_extractor/stage4/validators.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/validators.py)
- [scripts/dev/run_stage4a_stage2_selected_batch.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/scripts/dev/run_stage4a_stage2_selected_batch.py)

## 重构后原则

正式 Stage4A 现在应当变成：

1. 只读 `figures.jsonl` 里的 `vision_image_path`
2. 如果 `figures.jsonl` 缺失，才 fallback `figures_for_vision/`
3. Stage2 类型只做 hint
4. VLM 负责判断 `actual_figure_type`
5. `successful figure_id / vision_image_path` 永不重送
6. `raw_vlm_outputs` 优先 replay
7. `schema_validation_failed` 优先 replay/normalization
8. `missing_image_path / directory_path` 直接 manual hold，不进 VLM

## 这轮 audit 结论

- 当前 **确实存在** Stage4A 二次筛选
- 当前 **确实存在** `max=10` 截断污染 summary 的问题
- 当前 **确实存在** `total_candidates / skipped_count` 统计口径混乱
- 当前 **确实存在** 在某些参数组合下重复送 VLM 的风险
- 当前对 `vision_image_path` 的使用是**部分正确、但不够收敛**
- 因此已经改为：**Stage2 负责选图，Stage4A 负责看图和结构化**
