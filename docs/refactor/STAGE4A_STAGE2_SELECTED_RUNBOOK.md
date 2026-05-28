# Stage4A Stage2-Selected Runbook

这份 runbook 面向“不熟悉代码、但需要自己运行 Stage4A”的人。  
目标是让你后续不用 Codex，也能自己安全地完成：

1. `audit-only`
2. `live`
3. `review`

并且避免：

- 重复把已成功图片送进 VLM
- 把 dry-run-only 误判为 live success
- 把 `figures_all` 当成正式输入
- 被 `max=10` 截断污染正式统计

---

## 一、当前 Stage4A 新逻辑说明

### 1. Stage2 负责筛图

Stage2 已经帮你完成“哪些图值得给多模态模型看”的前置筛选。

### 2. Stage2 筛出的图在哪里

每篇论文下的筛后图片目录：

`data/outputs/<category>/<paper_id>/figures_for_vision/`

### 3. Stage2 的图信息在哪里

每篇论文的图元数据都在：

`data/outputs/<category>/<paper_id>/figures.jsonl`

这里面通常已经有：

- `image_path`
- `vision_image_path`
- `figure_class`
- `caption`
- `reference_sentences`
- `context_before`
- `context_after`
- 其他 related / OCR / source text 字段

### 4. Stage4A 只读取 Stage2-selected 图

正式 Stage4A 现在只用：

1. `figures.jsonl` 里的 `vision_image_path`
2. 如果 `figures.jsonl` 缺失，再 fallback 到 `figures_for_vision/`

### 5. Stage4A 不再从 `figures_all` 重筛

`figures_all` 不再作为正式 Stage4A 输入。  
Stage4A 不再自己重新全量筛图。

### 6. Stage4A 不再把 `max=10` 当正式逻辑

现在：

- `max_figures_per_paper=0` 或不传，表示**不截断**
- `max=10` 只用于 debug/test
- 正式 full run 不应使用 `max=10`

### 7. Stage2 类型只作为参考

`stage2_figure_class` / `stage2_predicted_figure_type` 只作为 **hint**。  
最终由 VLM 根据图片内容判断 `actual_figure_type`。

### 8. 已成功处理过的图不会再次进入 VLM

只要某个 `figure_id` / `vision_image_path` 已经 live 成功：

- 后续 resume 不会再送进 VLM
- 即使 `force=True` 也不会重打成功图

### 9. `raw_vlm_outputs` 优先 replay

如果某个图已经有：

- `raw_vlm_outputs.jsonl`

但还没 materialize 成正式 extraction：

- 会优先 replay
- 不会重新调用 VLM

---

## 二、运行前检查

### 1. 进入项目目录

```powershell
cd G:\paper\Al-gel-sol\alumina_sol_extractor
```

### 2. 设置环境变量

```powershell
$env:PYTHONPATH="G:\paper\Al-gel-sol\alumina_sol_extractor\src"
$env:PYTHONIOENCODING="utf-8"
```

### 3. 检查 `.env` 是否存在

```powershell
Test-Path .\.env
```

如果返回 `True`，说明 `.env` 文件存在。  
如果返回 `False`，live 前要先确认 API key / base_url 是否通过别的方式注入。

### 4. 检查 Stage3 是否完成

统计 `stage3_twopass/stage3_summary.json` 数量：

```powershell
@'
from pathlib import Path
root = Path(r"G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs")
count = sum(1 for path in root.rglob("stage3_twopass/stage3_summary.json"))
print({"stage3_twopass_summary_count": count})
'@ | python -
```

正常情况下应该接近：

- `343`

### 5. 检查 `figures_for_vision` 是否存在

统计：

- 有 `figures_for_vision` 的论文数
- `figures_for_vision` 总图片数

```powershell
@'
from pathlib import Path
root = Path(r"G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs")
paper_count = 0
image_count = 0
for path in root.rglob("figures_for_vision"):
    if path.is_dir():
        paper_count += 1
        image_count += sum(1 for item in path.iterdir() if item.is_file())
print({
    "papers_with_figures_for_vision": paper_count,
    "figures_for_vision_image_count": image_count,
})
'@ | python -
```

### 6. 检查已完成 Stage4A live 的图数

统计：

- `spectra_extractions.jsonl` 总行数
- `raw_vlm_outputs.jsonl` 总行数
- `failed_records` 总行数

```powershell
@'
import json
from pathlib import Path
root = Path(r"G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs")
extractions = 0
raw_outputs = 0
failed_records = 0
for path in root.rglob("stage4_vision_spectra_universal/spectra_extractions.jsonl"):
    extractions += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
for path in root.rglob("stage4_vision_spectra_universal/raw_vlm_outputs.jsonl"):
    raw_outputs += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
for path in root.rglob("stage4_vision_spectra_universal/spectra_failed_records.jsonl"):
    failed_records += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
print({
    "spectra_extractions_lines": extractions,
    "raw_vlm_outputs_lines": raw_outputs,
    "failed_records_lines": failed_records,
})
'@ | python -
```

---

## 三、先跑 audit-only，不调用 VLM

正式 live 之前，**一定先跑 audit-only**。

### audit-only 完整命令

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --audit-only
```

### 说明

`audit-only`：

- 不会调用 VLM
- 不会消耗额度
- 不会重传图片
- 只会扫描现有 Stage2 / Stage3 / Stage4A 输出，给出真实待跑图统计

### audit-only 跑完后重点看这些文件

- [data/batch_validation_reports/stage4a_stage2_selected_full_audit.csv](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_full_audit.csv)
- [data/batch_validation_reports/stage4a_stage2_selected_full_audit_summary.json](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_full_audit_summary.json)
- [docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md](/G:/paper/Al-gel-sol/alumina_sol_extractor/docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md)

### 重点字段解释

- `total_stage2_selected_figures`
  - Stage2 真正筛出的图总数

- `valid_stage2_selected_figures`
  - 图片路径有效、理论上可以被 Stage4A 正式消费的图数

- `already_live_success_figures`
  - 已经 live 成功过的图数，后续不会再进 VLM

- `raw_vlm_replay_candidates`
  - 已经有 raw VLM 输出，但还没 materialize 的图数，会优先 replay

- `new_live_candidate_figures`
  - 现在如果继续跑，真正还要新进 VLM 的图数

- `missing_image_path_count`
  - 图片路径不存在的图数，这些不会送 VLM

- `duplicate_vlm_prevented_count`
  - 已被保护、不会重复送 VLM 的图数

- `deferred_papers_count`
  - 默认先 defer 的大论文数量，比如 `032`

---

## 四、如何判断能不能开始 live

### 可以开始 live 的条件

1. `audit-only` 成功结束
2. `already_live_success_figures` 没有被混进 `new_live_candidate_figures`
3. `duplicate_vlm_prevented_count` 统计正常
4. `missing_image_path` 只是记录，不会进入 live
5. `raw_vlm_replay_candidates` 会 replay，不会重打 VLM
6. `new_live_candidate_figures` 数量在你当前额度能接受的范围内
7. 没有把 `figures_all` 当正式输入
8. 没有 `max=10` 截断污染 summary

### 出现以下情况时，不要 live

1. `new_live_candidate_figures` 异常接近 `figures_all` 总图数
2. 已成功图仍被列入待 live
3. audit 报告里出现大量 `missing image` / `path is directory`
4. audit 失败
5. 代码测试没有通过

---

## 五、正式 live 怎么跑

### 正式 live 完整命令

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --chunk-size 10 `
  --live
```

### 说明

- `live` 会调用 VLM，会消耗额度
- 默认 `chunk-size=10` 篇论文
- 每个 chunk 会输出单独报告
- `032` 这类大论文默认 defer，后续单独处理
- 已成功图不会重跑
- `raw_vlm_outputs` 已存在的图会优先 replay

---

## 六、如何监控运行是否正常

### 1. 查看 python 进程

```powershell
Get-Process python -ErrorAction SilentlyContinue |
  Sort-Object CPU -Descending |
  Select-Object Id, CPU, WorkingSet, StartTime, ProcessName
```

### 2. 查看最新更新的 `stage4a_summary`

```powershell
@'
from pathlib import Path
from datetime import datetime
root = Path(r"G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs")
latest = None
for path in root.rglob("stage4_vision_spectra_universal/stage4a_summary.json"):
    stat = path.stat()
    if latest is None or stat.st_mtime > latest[0]:
        latest = (stat.st_mtime, path)
if latest is None:
    print({"latest_stage4a_summary": None})
else:
    summary_path = latest[1]
    payload = __import__("json").loads(summary_path.read_text(encoding="utf-8"))
    minutes_since_latest = round((datetime.now().timestamp() - latest[0]) / 60, 2)
    print({
        "latest_stage4a_summary_time": datetime.fromtimestamp(latest[0]).isoformat(timespec="seconds"),
        "minutes_since_latest": minutes_since_latest,
        "paper_id": summary_path.parent.parent.name,
        "live_count": payload.get("live_count"),
        "failed_count": payload.get("failed_record_count"),
    })
'@ | python -
```

### 3. 查看当前 chunk 报告

默认 chunk 报告目录：

`data/batch_validation_reports/stage4a_stage2_selected_live_chunks/`

例如：

- `chunk_001`
- `chunk_002`
- `chunk_003`

### 4. 查看当前已完成多少 live 图

```powershell
@'
from pathlib import Path
root = Path(r"G:\paper\Al-gel-sol\alumina_sol_extractor\data\outputs")
extractions = 0
raw_outputs = 0
failed_records = 0
for path in root.rglob("stage4_vision_spectra_universal/spectra_extractions.jsonl"):
    extractions += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
for path in root.rglob("stage4_vision_spectra_universal/raw_vlm_outputs.jsonl"):
    raw_outputs += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
for path in root.rglob("stage4_vision_spectra_universal/spectra_failed_records.jsonl"):
    failed_records += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
print({
    "spectra_extractions_total_lines": extractions,
    "raw_vlm_outputs_total_lines": raw_outputs,
    "failed_records_total_lines": failed_records,
})
'@ | python -
```

---

## 七、如果卡住怎么办

1. 如果 **30 分钟没有新写入**，先不要立刻重开
2. 先看 python 进程 CPU
3. 先看 `raw_vlm_outputs.jsonl` 是否有新增
4. 先看最新 `stage4a_summary` 的修改时间
5. 如果确认卡住，可以 `Ctrl+C`
6. `Ctrl+C` 后，重新运行**同一个 live 命令**即可  
   因为 figure-level dedup 会跳过已成功图
7. 不要手动删除 `stage4_vision_spectra_universal`
8. 不要手动 `force` 重跑整篇，除非脚本明确保护了 figure-level dedup
9. 不要同时开多个 live 进程跑同一个 `stage4_subdir`

---

## 八、如果报错怎么办

### 1. `FileNotFoundError`

- 检查路径
- 检查 `figures.jsonl`
- 检查 `figures_for_vision`

### 2. `max_figures_per_paper` 的 `NoneType` 错误

- 说明代码还没处理好 `None`
- 现在建议用：
  - `0` 表示不截断
- 如果还有报错，就修代码，不要临时改数据

### 3. `missing_image_path`

- 不需要重跑 VLM
- 这类图应进入 `manual_hold`

### 4. `schema_validation_failed`

- 优先 replay / normalization
- 不要直接重打 VLM

### 5. `range_peak_midpoint_error`

- 必须停下来修
- 范围峰 `position` 必须为 `null`
- 不能取 midpoint

### 6. `VLM timeout`

- 可以重试
- 但如果连续大量 timeout，就先暂停，不要继续烧额度

### 7. API key / base_url 错误

检查：

- `.env`
- `DASHSCOPE_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `VLM_MODEL_NAME`

---

## 九、如何单独跑某几篇论文

### 推荐方式：`--paper-ids-file`

不要直接把长 `paper_id` 拼进命令行。  
尤其 paper_id 里可能有：

- 中文
- 英文逗号
- 特殊符号

### 第一步：创建 txt 文件

例如：

`data/batch_validation_reports/my_stage4_paper_ids.txt`

内容一行一个 `paper_id`：

```text
002_PVA作纺丝助剂制备莫来石-氧化铝长纤维
004_Sol-Gel法制备新型多晶钇-铝石榴石纤维
```

### 第二步：先跑 audit-only

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --paper-ids-file ".\data\batch_validation_reports\my_stage4_paper_ids.txt" `
  --audit-only
```

### 第三步：再跑 live

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --paper-ids-file ".\data\batch_validation_reports\my_stage4_paper_ids.txt" `
  --chunk-size 10 `
  --live
```

---

## 十、如何单独处理 032 这种大论文

这篇大论文：

`fiber_process/032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究`

默认 defer。  
建议单独处理，不要混在普通 batch 里。

### 准备 deferred 列表

建一个文件：

`data/batch_validation_reports/stage4a_deferred_large_papers.txt`

内容：

```text
032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究
```

### 单独 audit

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --paper-ids-file ".\data\batch_validation_reports\stage4a_deferred_large_papers.txt" `
  --audit-only
```

### 单独 live

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --paper-ids-file ".\data\batch_validation_reports\stage4a_deferred_large_papers.txt" `
  --chunk-size 1 `
  --live
```

### 说明

- 大论文建议 `chunk-size=1`
- 不要和普通 batch 混跑
- 已成功图仍会自动跳过

---

## 十一、运行完成后怎么做质量审查

现在可以直接用同一个脚本做 review：

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --review-only
```

输出文件：

- [data/batch_validation_reports/stage4a_stage2_selected_live_quality_review.csv](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_live_quality_review.csv)
- [data/batch_validation_reports/stage4a_stage2_selected_live_quality_review_summary.json](/G:/paper/Al-gel-sol/alumina_sol_extractor/data/batch_validation_reports/stage4a_stage2_selected_live_quality_review_summary.json)
- [docs/refactor/STAGE4A_STAGE2_SELECTED_LIVE_QUALITY_REVIEW.md](/G:/paper/Al-gel-sol/alumina_sol_extractor/docs/refactor/STAGE4A_STAGE2_SELECTED_LIVE_QUALITY_REVIEW.md)

### review 重点看这些字段

- `total_live_figures`
- `successful_extractions`
- `failed_records`
- `schema_validation_failed_count`
- `range_peak_midpoint_error_count`
- `sem_tem_unscaled_diameter_error_count`
- `type_mismatch_count`
- `unknown_or_non_extractable_count`
- `actual_figure_type_distribution`
- `papers_with_failed_records`
- `papers_needing_replay`
- `papers_needing_manual_hold`
- `pass_gate`

---

## 十二、什么时候可以进入 Stage5

**只有 Stage4A 全量或目标批次完成，并且质量审查通过后，才能进入 Stage5。**

进入 Stage5 前，至少满足：

1. `schema_validation_failed_count = 0`，或已全部 replay 修复
2. `range_peak_midpoint_error_count = 0`
3. `SEM/TEM` 无比例尺乱估尺寸 = `0`
4. `failed_records` 可解释
5. `stage4a_summary / spectra_extractions` 稳定
6. 已经生成 Stage4A quality review 报告

否则：

- 不要进入 Stage5

---

## 十三、给我一个最短日常运行流程

### 最短日常版

#### 1. 进入目录

```powershell
cd G:\paper\Al-gel-sol\alumina_sol_extractor
```

#### 2. 设置环境变量

```powershell
$env:PYTHONPATH="G:\paper\Al-gel-sol\alumina_sol_extractor\src"
$env:PYTHONIOENCODING="utf-8"
```

#### 3. 先跑 audit-only

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --audit-only
```

#### 4. 看 summary

重点看：

- `already_live_success_figures`
- `raw_vlm_replay_candidates`
- `new_live_candidate_figures`
- `duplicate_vlm_prevented_count`

#### 5. 再跑 live

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --candidate-source "stage2-selected" `
  --routing-mode "universal_compact" `
  --chunk-size 10 `
  --live
```

#### 6. 监控

```powershell
Get-Process python -ErrorAction SilentlyContinue |
  Sort-Object CPU -Descending |
  Select-Object Id, CPU, WorkingSet, StartTime, ProcessName
```

#### 7. 跑 review

```powershell
python .\scripts\dev\run_stage4a_stage2_selected_batch.py `
  --manifest ".\data\batch_manifest\source_manifest.csv" `
  --outputs-dir ".\data\outputs" `
  --stage3-subdir "stage3_twopass" `
  --stage4-subdir "stage4_vision_spectra_universal" `
  --review-only
```

#### 8. 决定是否 Stage5

只有 review 通过后，再考虑 Stage5。

---

## 十四、补充说明

### 新脚本路径

- [scripts/dev/run_stage4a_stage2_selected_batch.py](/G:/paper/Al-gel-sol/alumina_sol_extractor/scripts/dev/run_stage4a_stage2_selected_batch.py)

### audit-only 报告

- [docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md](/G:/paper/Al-gel-sol/alumina_sol_extractor/docs/refactor/STAGE4A_STAGE2_SELECTED_FULL_AUDIT.md)

### review 报告

- [docs/refactor/STAGE4A_STAGE2_SELECTED_LIVE_QUALITY_REVIEW.md](/G:/paper/Al-gel-sol/alumina_sol_extractor/docs/refactor/STAGE4A_STAGE2_SELECTED_LIVE_QUALITY_REVIEW.md)

### 什么时候能进 Stage5

一句话版本：

> 只有 Stage4A 全量或目标批次完成，并且 review 通过后，才进入 Stage5。
