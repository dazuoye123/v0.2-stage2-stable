# Stage 3 Two-Pass After 013 Fix Next50 Quality Review

## Overall conclusion
This next50 validation used the same stable `stage3_twopass/` output directory and a separate report directory. 49 papers succeeded and 1 failed. Datapoint normalization remains stable, evidence coverage remains strong, and the main residual issue is a small number of sparse process-step cases plus one live failure.

## Grade summary
- A=0
- B=44
- C=5
- D=1

## Gate metrics
- raw_name key/value bug count: 0
- list-value validation error count: 0
- process_steps_count=0 papers: 0
- evidence zero with scientific figures: 0
- cleaned_body image residue papers: 1
- average canonical_key_errors_count: 0.00
- average rejected_parameter_records_count: 0.00
- pass_quality_gate: False

## C/D papers
- [D] 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究: run_failed: BadRequestError litellm.BadRequestError: OpenAIException - <400> InternalError.Algo.InvalidParameter: Range of input length should be [1, 229376]
- [C] 072_Abdullah 等 - 2010 - Effects of the polyvinyl alcohol (PVA) on the synthesis of alumina fibers through electrospinning te: process_steps too generic
- [C] 020_拟薄水铝石中水的存在形式及对其溶胶性能的影响: process_steps too generic
- [C] 007_两种钛源对钛酸铝溶胶可纺性影响的对比研究: process_steps too generic
- [C] 012_基于拟薄水铝石氧化铝气凝胶制备工艺研究: process_steps too generic
- [C] 028_整装Fiber@γ-Al_2O_3的涂层制备及其负载Ni基催化剂甲烷干气重整研究_盛雯倩: process_steps too generic

## Recommendation
The next50 gate does not pass. Do not expand further until the remaining failure and sparse process-step cases are addressed.
