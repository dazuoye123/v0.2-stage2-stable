# DESIGN NOTE

## 1. PDF Sample Observations

The provided papers show that the extraction system must support both well-structured experimental papers and difficult PDFs with poor text extraction.

Observed paper types:
- English precursor chemistry paper: aluminium sec-butoxide chelated with ethyl acetoacetate, mainly NMR evidence and composition/coordination discussion. It is not a fiber preparation paper, but it is useful for precursor/ligand/coordination ontology design.
- Journal paper on dry spinning alpha-Al2O3 ceramic fibers: alumina sol preparation, PVA additive, dry spinning, spinneret parameters, two-step heat treatment, TG-DSC, XRD, FTIR, SEM, fiber diameter, and tensile strength.
- Journal paper on flexible alpha-Al2O3 nanostructured fibers: electrospinning, AlCl3 and aluminium isopropoxide precursor, PVP, pH, viscosity window, applied voltage, collector distance, feed rate, staged calcination, XRD/TG/IR/SEM, fiber diameter, nanosheet thickness, breaking strength, elongation, and thermal shock stability.
- Thesis on polycrystalline alumina continuous fibers: alumina sol plus mullite sol, PEO/spinning additive, zeta potential, solid content, viscosity, spinneret hole count, continuous spinning length/duration, gel fiber water content, multi-stage temperature/humidity/pressure records, two-step ceramic conversion, phase and strength retention after high-temperature exposure.
- Scanned thesis-like PDF on alumina sol precursor: text extraction returned almost no text, so OCR or visual extraction is required. The schema must keep evidence and multimodal extraction objects separate from text extraction results.

Common parameter groups observed:
- Precursor and sol: raw material role, Al/Si/B/Zr/Mg source, polymer additive, pH, solid content, viscosity, particle size, zeta potential, aging, concentration, gelation, drying.
- Forming: dry spinning or electrospinning method, spinneret hole diameter/count, needle/nozzle size, feed pressure, voltage, air pressure, collector distance, feed rate, take-up speed, channel temperature, ambient temperature and humidity.
- Heat treatment: staged drying/calcination/sintering, heating rate, target temperature, holding time, atmosphere, cooling method.
- Structure: main phase and secondary phase, phase transition, fiber diameter, fiber length, crystallite size, pore structure, density, shrinkage, surface/cross-section morphology.
- Performance: tensile/compressive/flexural strength, breaking force, elastic modulus, elongation, thermal conductivity, service temperature, strength retention.
- Evidence: TG-DSC mass loss and peak temperature, XRD phase, FTIR/NMR/XPS/Raman assignments, SEM/TEM morphology, BET pore data, table records.

## 2. What The Original Template Gets Right

The original `prompt2.txt` has several strong ideas:
- It correctly prioritizes experiment series over a flat data array.
- It separates global shared conditions from per-series and per-point data.
- It requires null for missing fields, which is essential for downstream validation.
- It asks for image evidence objects, multimodal extraction records, cross-modal links, and data provenance.
- It explicitly warns against losing qualitative observations.
- It recognizes that figure/table/page evidence is needed for auditability.

These principles should be retained in schema_v2.

## 3. Problems In The Original Template

The original template is too heavy in the wrong places and too loose in places that matter for statistics.

Main issues:
- Field names mix Chinese display names, English suffixes, and unit annotations. This makes database columns and code hard to stabilize.
- Many core statistical fields can also appear in free-form areas, which risks duplicate or unqueryable values.
- The template has many nested narrative fields. They are useful for human reading but expensive for extraction and validation.
- Some parameter names are synonyms rather than canonical keys, for example 粘度/黏度, 工作电压/外加电压, 断裂强度/拉伸强度.
- Figure evidence, multimodal extraction, and provenance are all useful, but they should reference shared IDs instead of repeating long descriptions everywhere.
- Independent variables use `your_variable_key_1`, which invites uncontrolled parameter invention.
- Unit normalization is described in the prompt, but not enforced by a machine-readable ontology.

## 4. What schema_v2 Changes

schema_v2 keeps the required top-level structure but uses English canonical keys:
- `paper_basic_info`
- `global_constants`
- `experiment_series`
- `data_points`
- `evidence_objects`
- `multimodal_extractions`
- `cross_modal_links`
- `data_provenance`

The largest change is that core numeric fields are represented with fixed canonical keys such as `viscosity_Pa_s`, `sintering_temperature_C`, and `tensile_strength_MPa`. Chinese names and aliases are moved to `ontology.yaml`, not repeated as JSON field names.

This makes the output:
- easier to validate with Pydantic
- easier to flatten into relational tables
- easier to query across Chinese and English papers
- safer against accidental model-created parameter names

The schema also supports both wide and long formats:
- Fixed maps in `shared_parameters`, `process_parameters`, and `results` support convenient statistics.
- `additional_parameter_records` supports structured long-format records while still requiring canonical keys.
- `extended_data` remains available only for long-tail non-core facts.

## 5. Why Experiment Series And Data Points Are Designed This Way

Materials papers usually contain several independent experimental dimensions. For example:
- PVP/PVA/PEO amount affects viscosity and spinnability.
- Heat treatment temperature affects phase, fiber diameter, morphology, and strength.
- Electrospinning voltage or feed rate affects fiber diameter.
- Scale-up batch number affects pressure, humidity, water content, and collected mass.
- Commercial fiber comparisons have product-level properties rather than author-run experiments.

If all samples are placed into one flat array, variables from unrelated studies become mixed. This damages statistics because a row may not share the same controlled conditions as the next row.

schema_v2 therefore uses:
- `experiment_series`: the research dimension and controlled context.
- `independent_variables`: what changes within the series.
- `series_constants`: fixed conditions for that series.
- `data_points`: individual sample/condition rows.

This lets the database support both:
- horizontal comparison within one series
- single-sample lookup with complete local context

## 6. Why Use A Canonical Parameter Ontology

The ontology is the control surface of the extraction system. It prevents the model from scattering the same parameter across many names.

Examples:
- 粘度, 黏度, apparent viscosity -> `viscosity_Pa_s`
- 外加电压, 工作电压, electrospinning voltage -> `applied_voltage_kV`
- 断裂强度, tensile strength, breaking strength -> `tensile_strength_MPa`
- 强度保持率, residual strength ratio -> `strength_retention_percent`

Each ontology entry stores:
- canonical key
- Chinese display name
- English aliases
- Chinese aliases
- standard unit
- category
- whether it is a core statistical field

Core statistical fields must never be placed only in `extended_data`. If a required core key is missing from the schema, the ontology should be extended deliberately rather than allowing ad hoc model output.

## 7. Why DSPy Should Be Staged

A single giant prompt has three predictable failure modes:
- It mixes series discovery with value extraction, causing unrelated variables to enter the same group.
- It encourages the model to satisfy the final JSON shape by hallucinating null-like or invented fields.
- It makes errors hard to repair because metadata, evidence, normalization, and merging are entangled.

The staged DSPy design reduces these risks:
- `ExtractPaperBasicInfo` handles metadata only.
- `ExtractGlobalConstants` handles shared conditions.
- `ExtractExperimentSeries` decides grouping before data extraction.
- `ExtractDataPoints` works one series at a time.
- `ExtractEvidenceObjects` builds the figure/table/image index separately.
- `NormalizeCanonicalKeys` maps raw names to ontology keys and normalizes units.
- `MergeAndFillTemplate` is deterministic Python, not free-form generation.

This architecture is more work up front, but it gives better auditability, makes schema evolution manageable, and supports later database construction.

## 8. Simplification Rationale

schema_v2 intentionally removes some deeply nested Chinese narrative fields from the fixed template. Their information is not discarded; it is moved into:
- controlled `qualitative_observations`
- `mechanism_notes`
- `spectroscopic_evidence`
- evidence-linked `additional_parameter_records`
- limited `extended_data`

This keeps common statistics close to fixed canonical fields while preserving rare but important facts.
# 设计说明

## 1. PDF 样本观察

提供的论文表明，提取系统必须支持结构良好的实验论文和文本提取较差的复杂 PDF。

观察到的论文类型：
- 英语前体化学论文：铝二丁氧化物与乙酰乙酰乙酸螯合，主要涉及核磁共振证据及组成/配位讨论。这不是纤维制备论文，但对前体/配体/配位本体设计非常有用。
- 关于干式纺纱α-Al2O3 陶瓷纤维的期刊论文：氧化铝溶胶制备、PVA 添加剂、干纺丝、纺丝机参数、两步热处理、TG-DSC、XRD、FTIR、SEM、纤维直径和拉伸强度。
- 关于柔性α-Al2O3 纳米结构纤维的期刊论文：电旋、AlCl3 和铝异丙氧化物前驱体、PVP、pH 值、粘度窗口、施加电压、集电器距离、进给速率、分级煅烧、XRD/TG/IR/SEM、纤维直径、纳米片厚度、断裂强度、伸长性及热冲击稳定性。
- 关于多晶氧化铝连续纤维的论文：氧化铝溶胶加莫利特溶胶、PEO/纺丝添加剂、Zeta 电位、固体含量、粘度、纺丝孔数、连续纺丝长度/持续时间、凝胶纤维含水量、多级温度/湿度/压力记录、两步陶瓷转化、高温暴露后的相和强度保持。
- 关于氧化铝 sol 前体的扫描类论文 PDF：文本提取几乎不返回文本，因此需要 OCR 或视觉提取。模式必须将证据和多模态提取对象与文本提取结果分开。

常见参数群观察到：
- 前驱体和溶剂：原料角色、Al/Si/B/Zr/Mg 来源、聚合物添加剂、pH 值、固体含量、粘度、粒径、zeta 电位、时效、浓度、凝胶化、干燥。
- 成形：干纺或电旋法，纺丝孔径/数、针头/喷嘴尺寸、进给压力、电压、气压、集电器距离、进给速率、收发速度、通道温度、环境温度和湿度。
- 热处理：分阶段干燥/烧结/烧结，加热速率，目标温度，保持时间，大气层，冷却方法。
- 结构：主相和次相、相变、纤维直径、纤维长度、晶粒大小、孔隙结构、密度、收缩、表面积/截面形态。
- 性能：拉伸/压缩/弯曲强度、断裂力、弹性模量、伸长性、热导率、使用温度、强度保持。
- 证据：TG-DSC 质量损失与峰值温度、XRD 相、FTIR/NMR/XPS/拉曼分配、SEM/TEM 形态、BET 孔隙数据、表格记录。

## 2. 原始模板做对的地方

原版“prompt2.txt”有几个强烈的理念：
- 它正确地优先处理实验序列而非平面数据数组。
- 它将全局共享条件与每系列和每点数据分离。
- 对于缺失字段要求空值，这对下游验证至关重要。
- 它要求图像证据对象、多模态提取记录、跨模态链接和数据来源。
- 它明确警告不要丢失定性观察。
- 它认识到图/表格/页面证据对于可审计性至关重要。

这些原则应在 schema_v2 中保留。

## 3. 原始模板中的问题

原始模板在错误的地方过于沉重，在统计数据重要的地方又过于松散。

主要问题：
- 字段名混合了中文显示名称、英文后缀和单元注释。这使得数据库列和代码难以稳定。
- 许多核心统计字段也可能出现在自由格式区域，这可能导致重叠或无法查询的值。
- 模板包含许多嵌套叙述字段。它们对人类阅读有用，但提取和验证成本较高。
- 有些参数名称是同义词而非规范键，例如粘度/粘度、工作电压/外加电压、断裂强度/拉伸强度。
- 图示证据、多模态提取和来源都有用，但应引用共享的 ID，而非到处重复冗长描述。
- 自变量使用“your_variable_key_1”，这导致了无控制参数的发明。
- 单元归一化在提示中描述，但不由机器可读本体强制执行。

## 4. schema_v2 变化

schema_v2 保留了所需的顶层结构，但使用了英文规范键：
- “paper_basic_info”
- “global_constants”
- “experiment_series”
- “data_points”
- “evidence_objects”
- “multimodal_extractions”
- “cross_modal_links”
- “data_provenance”

最大的变化是核心数字字段用固定的规范键表示，如“viscosity_Pa_s”、“sintering_temperature_C”和“tensile_strength_MPa”。中文名称和别名被移至“ontology.yaml”，不再重复为 JSON 字段名。

这样输出如下：
- 更易用皮丹提克验证
- 更易于扁平化为关系表
- 更易跨中英论文查询
- 更安全防止模型意外创建的参数名称

该模式还支持宽格式和长格式：
- 固定映射在“shared_parameters”、“process_parameters”和“结果”中支持便捷的统计。
- “additional_parameter_records”支持结构化长格式记录，同时仍要求规范键。
- “extended_data”仅适用于长尾非核心事实。

## 5. 为什么实验系列和数据点设计成这样

材料论文通常包含多个独立的实验维度。例如：
- PVP/PVA/PEO 的数量会影响粘度和可旋转性。
- 热处理温度影响相、纤维直径、形态和强度。
- 电旋电压或进给速率会影响纤维直径。
- 放大批次数量影响压力、湿度、含水量和收集质量。
- 商业纤维比较具有产品层面特性，而非作者自主运行的实验。

如果所有样本都放在一个平坦数组中，来自无关研究的变量会混合。这会损害统计学，因为一行可能与下一行共享相同的受控条件。

因此 schema_v2 使用：
- “experiment_series”：研究维度与受控语境。
- “independent_variables”：系列中的变化。
- “series_constants”：该级数的固定条件。
- “data_points”：单个样本/状态行。

这使得数据库能够同时支持：
- 单系列内的水平比较
- 单样本查找，具有完整局部上下文

## 6. 为什么使用规范参数本体

本体是提取系统的控制面。它防止模型将相同参数散布在多个名称上。

示例：
- 粘度、黏度、表观粘度 ->“viscosity_Pa_s”
- 外加电压， 工作电压，电旋电压 -> 'applied_voltage_kV'
- 断裂强度、拉伸强度、断裂强度 ->“tensile_strength_MPa”
- 强度保持率，残余强度比 -> 'strength_retention_percent'

每个本体条目存储：
- 典范密钥
- 中文展示名称
- 英文别名
- 中文别名
- 标准单位
- 类别
- 是否为核心统计场

核心统计字段绝不能仅放在“extended_data”中。如果模式中缺少所需的核心键，应有意扩展本体，而非允许临时输出模型。

## 7. DSPy 为什么应该被分期

单个巨型提示有三种可预测的失败模式：
- 它将级数发现和值提取混合，导致无关变量进入同一组。
- 它通过幻觉类似空字段或虚构字段，鼓励模型满足最终的 JSON 形状。
- 由于元数据、证据、规范化和合并相互纠缠，错误难以修复。

分级 DSPy 设计降低了以下风险：
- “ExtractPaperBasicInfo”仅处理元数据。
- “ExtractGlobalConstants”处理共享条件。
- “ExtractExperimentSeries”在数据提取前决定分组。
- “ExtractDataPoints”一次只处理一组。
- “ExtractEvidenceObjects”单独构建图表/表格/图像索引。
- “规范化规范键”将原始名称映射到本体键并规范化单元。
- “MergeAndFillTemplate”是确定性 Python，不是自由生成。

这种架构前期工作量更大，但提供了更好的可审计性，使模式演进更易管理，并支持后续数据库构建。

## 8. 简化理由

schema_v2 有意从固定模板中移除一些深度嵌套的中文叙事字段。这些信息并未被丢弃;而是移入：
- 受控“qualitative_observations”
- “mechanism_notes”
- “spectroscopic_evidence”
- 证据链接的“additional_parameter_records”
- 有限“extended_data”

这样可以让常见统计量接近固定的典范域，同时保留一些罕见但重要的事实。