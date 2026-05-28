# Stage4A Stage2-Selected Universal Refactor Report

## 结果

1. 本轮**没有调用 VLM**。  
2. 本轮**没有运行 Stage5**。  
3. 本轮**没有重跑 Stage2 / Stage3**。  
4. 现在已经明确收敛到：**Stage2 负责选图，Stage4A 不再做复杂二次筛图**。  
5. Stage4A 正式 candidate 已改成：
   - `figures.jsonl`
   - `vision_image_path`
   - `figures_for_vision/` fallback
6. `figures_all` **不再是正式 Stage4A 输入**。  
7. `stage2_figure_class` / `stage2_predicted_figure_type` 现在只作为 **hint**。  
8. `universal_compact` prompt 保留，并且由 VLM 负责纠正 `actual_figure_type`。  
9. figure-level dedup 保留并加强：已成功图不会再送 VLM。  
10. `raw_vlm_outputs` 会优先 replay。  
11. dry-run-only 不再被当成 live success。  
12. `max=10` 截断污染正式 summary 的问题已经隔离：  
    - `max_figures_per_paper=0` / `None` 表示不截断  
    - `max=10` 只保留为 debug 选项  
    - summary 中会明确记录 `max_figures_per_paper_applied`

## 新增/修改的核心文件

- [src/alumina_sol_extractor/stage4/stage2_selected_loader.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/stage2_selected_loader.py)
- [src/alumina_sol_extractor/stage4/extractor.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/extractor.py)
- [src/alumina_sol_extractor/stage4/processed_index.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/processed_index.py)
- [src/alumina_sol_extractor/stage4/prompt_templates.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/prompt_templates.py)
- [src/alumina_sol_extractor/stage4/routing.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/routing.py)
- [src/alumina_sol_extractor/stage4/schemas.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/schemas.py)
- [src/alumina_sol_extractor/stage4/stage4_context.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/stage4_context.py)
- [src/alumina_sol_extractor/stage4/validators.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/src/alumina_sol_extractor/stage4/validators.py)
- [scripts/dev/run_stage4a_stage2_selected_batch.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/scripts/dev/run_stage4a_stage2_selected_batch.py)
- [scripts/dev/continue_stage4a_full_eligible_live.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/scripts/dev/continue_stage4a_full_eligible_live.py)

## 新 audit-only 结果

来自：

- [data/batch_validation_reports/stage4a_stage2_selected_full_audit.csv](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_full_audit.csv)
- [data/batch_validation_reports/stage4a_stage2_selected_full_audit_summary.json](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_full_audit_summary.json)
- [docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md](/G:/paper/Al-gel-sol/alumina_sol_extractor/docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md)

当前真实统计：

- `total_stage3_done_papers = 343`
- `papers_with_figures_jsonl = 343`
- `papers_with_figures_for_vision = 343`
- `papers_without_stage2_selected_figures = 1`
- `total_stage2_selected_figures = 6114`
- `valid_stage2_selected_figures = 6114`
- `missing_image_path_count = 0`
- `directory_path_error_count = 0`
- `already_live_success_figures = 279`
- `raw_vlm_replay_candidates = 1`
- `schema_replay_candidates = 0`
- `transient_rerun_candidates = 0`
- `new_live_candidate_figures = 5570`
- `duplicate_vlm_prevented_count = 280`
- `dry_run_only_records_ignored_as_success = 1634`
- `deferred_papers_count = 1`
- `deferred_figures_count = 264`

## 解释

- `6114` 是 **Stage2 真正筛出来的图总数**
- `279` 是 **已经 live 成功的图数**
- `280` 是 **这轮已经明确保护、不再重打的图数**
  - 其中 `279` 张已成功
  - `1` 张 raw output 会优先 replay
- `5570` 是 **如果现在继续 live，还需要真正进入 VLM 的图数**
- `1634` 是 **dry-run-only 旧记录，已经明确忽略为“非 live 成功”**
- `032` 默认 defer，所以有 `264` 张图先不混入普通批次

## 兼容旧输出

兼容目录：

- `data/outputs/<category>/<paper_id>/stage4_vision_spectra_universal/`

兼容原则：

- 不删除旧成功结果
- 不重复发送旧成功图
- `raw_vlm_outputs` 优先 replay
- 如果后续需要 materialize/rewrite summary，先备份旧文件，不备份图片

## 测试与校验

- `python -m compileall .\src .\scripts .\tests`：通过
- 局部测试：通过
- 全量 `pytest`：`485 passed`

## 后续建议

后续正式运行应统一使用：

- [scripts/dev/run_stage4a_stage2_selected_batch.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/scripts/dev/run_stage4a_stage2_selected_batch.py)

而不是继续围绕旧的：

- `run_stage4a_batch.py`
- `continue_stage4a_full_eligible_live.py`

去做复杂论文级判断。
