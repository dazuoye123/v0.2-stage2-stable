# Stage 3 Completed Output Quality Review

## Overall conclusion

当前已完成的 Stage 3 two-pass 输出**不能直接作为继续烧钱扩展的稳定版本**。抽查结果以 **B/C 档为主**：少量论文已经接近可用，但 data_points 规范化、evidence_objects 缺失、以及个别论文 process_steps 过弱或为 0 的问题仍然明显。

## Reviewed data

- completed_papers_count: 120
- sampled_papers_count: 20
- categories covered: fiber_process, mechanism
- report path used: data/outputs/**/stage3/stage3_summary.json (two-pass completed outputs)

## Per-paper summary

| category | paper_id | samples_count | parameters_count | process_steps_count | evidence_count | procedure_sections_count | main_quality_issue | quality_grade |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| fiber_process | 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 | 2 | 10 | 6 | 0 | 7 | NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  | C |
| mechanism | 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞 | 3 | 23 | 5 | 7 | 13 | Al sol hydrolysis | weak_action | 将Al(OPr^i)3溶于异丙醇(PrOH)成糊状，加入80℃热水(水/铝摩尔比120)进行水解。 | C |
| fiber_process | 010_含硼氧化铝基陶瓷连续纤维的制备及表征 | 2 | 11 | 0 | 5 | 54 | no_process_steps | C |
| fiber_process | 059_连续氧化铝纤维及其复合材料的研究进展 | 0 | 0 | 0 | 10 | 18 | no_process_steps | C |
| fiber_process | 069_静电纺氧化铝！！会议！！纤维膜的制备与构效关系 | 3 | 10 | 0 | 3 | 1 | no_process_steps | C |
| fiber_process | 035_氧化铝基陶瓷连续纤维研究进展 | 0 | 0 | 5 | 17 | 41 | no_data_points | B |
| fiber_process | 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method | 2 | 0 | 7 | 0 | 4 | no_data_points | C |
| fiber_process | 212_Milanović 等 - 2013 - Preparation of low cost alumina nanofibers via electrospinning of aluminium chloride hydroxidepoly | 0 | 0 | 4 | 13 | 8 | no_data_points | C |
| fiber_process | 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究 | 4 | 45 | 5 | 0 | 91 | other | weak_action | 将铝粉、甲酸、乙酸、硝酸和水按设定摩尔比混合，在85°C水浴下反应23小时，形成羧酸铝溶胶。 | C |
| fiber_process | 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol | 2 | 9 | 5 | 0 | 10 | other | weak_action |  | C |
| fiber_process | 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber | 2 | 18 | 6 | 0 | 11 | Sol Preparation | weak_action |  | C |
| mechanism | 008_前驱体铝溶胶中的水解和聚合反应的机理研究 | 3 | 12 | 4 | 0 | 79 | NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  | C |
| fiber_process | 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛 | 2 | 20 | 6 | 0 | 40 | dissolve | weak_action | 将AlCl3·6H2O溶于去离子水，加入铝粉，100℃回流搅拌至完全溶解，过滤得澄清氧化铝溶胶。加入9% ZrOCl2·8H2O、1%硅溶胶及3% PVP，常温 | C |
| fiber_process | 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究 | 4 | 14 | 6 | 0 | 103 | 配制混合溶剂 | weak_action |  | C |
| fiber_process | 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 | 3 | 20 | 2 | 10 | 106 | other | weak_action | Sol-gel method for Al2O3/Al2O3 composite preparation | C |
| fiber_process | 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究 | 4 | 33 | 5 | 0 | 82 | stir | weak_action | 将金属盐类与溶剂混合搅拌溶解，控制水浴温度加热搅拌，发生水解与聚合反应制成溶胶。 | C |
| fiber_process | 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m | 2 | 5 | 4 | 0 | 3 | NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  | C |
| fiber_process | 015_多晶莫来石纤维的制备研究 | 1 | 4 | 6 | 8 | 12 | NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  | C |
| fiber_process | 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响 | 2 | 15 | 12 | 4 | 11 | stir | weak_action | 配制助纺剂溶液：称取13.65 g环氧树脂加入50 mL烧杯，量取6.8 mL DBE溶剂，室温密封搅拌12 h待用。 | C |
| fiber_process | 096_Cai 等 - 2006 - Azeotropic distillation-assisted preparation of macro-mesostructured γ-Al2O3 nanofibres of crumpled | 1 | 15 | 7 | 5 | 5 | NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  | C |

## Process steps review

### fiber_process / 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 (B)
- correct examples: stir | 将铝粉和六水合氯化铝按物质的量比3.4:1加入烧瓶，加入蒸馏水(H2O:Al=15:1)，80 ℃磁力搅拌冷凝回流制得铝溶胶。 ; add | 向铝溶胶中加入封端剂(1%)、PVA(变量)和硅溶胶(SiO2物质的量分数10%)。
- error examples: other | weak_action | 用细玻璃棒浸入溶胶中慢慢提起，拉制出凝胶纤维。

### mechanism / 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞 (C)
- error examples: Al sol hydrolysis | weak_action | 将Al(OPr^i)3溶于异丙醇(PrOH)成糊状，加入80℃热水(水/铝摩尔比120)进行水解。 ; Al sol peptization | weak_action | 加入HAC作为解胶剂(酸/铝摩尔比1.0)，在88℃下解胶0.5~1小时，获得透明铝溶胶。 ; Si sol hydrolysis | weak_action | 将TEOS、水(水/TEOS摩尔比200)和HAC(酸/TEOS摩尔比2.0)混合，在70℃下水解60分钟，获得透明硅溶胶。

### fiber_process / 010_含硼氧化铝基陶瓷连续纤维的制备及表征 (C)
- process_steps missing

### fiber_process / 059_连续氧化铝纤维及其复合材料的研究进展 (C)
- process_steps missing

### fiber_process / 069_静电纺氧化铝！！会议！！纤维膜的制备与构效关系 (C)
- process_steps missing

### fiber_process / 035_氧化铝基陶瓷连续纤维研究进展 (B)
- correct examples: add | 将无机铝盐或有机铝盐溶解在水或醇中，加入催化剂，在控制温度下进行水解与聚合反应，生成透明的氧化铝溶胶。核心是调控反应条件促使铝单体水解聚合生成足量的Al13^7 ; other | 将基础铝溶胶与改性溶胶（如Si、Zr、Mg源）及纺丝助剂混合。通过浓缩和老化过程，使Al13团簇间的活性Al-OH位点相互结合形成羟基桥联的链状无机高分子结构，

### fiber_process / 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method (B)
- correct examples: other | Distilled water heated to 80 °C, followed by adding ASB with continuous mixing t ; other | After stirring for 5 min, nitric acid added step-wise with stirring until precip

### fiber_process / 212_Milanović 等 - 2013 - Preparation of low cost alumina nanofibers via electrospinning of aluminium chloride hydroxidepoly (B)
- correct examples: other | Prepared 10 mass% aqueous PVA solution and added aluminum chloride hydroxide to  ; other | Stirred the mixture on a laboratory mixer for 1 h at 30 °C. Allowed to stand for

### fiber_process / 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究 (C)
- error examples: other | weak_action | 将铝粉、甲酸、乙酸、硝酸和水按设定摩尔比混合，在85°C水浴下反应23小时，形成羧酸铝溶胶。 ; stir | weak_action | 采用后加方式加入TEOS，常温搅拌12小时，制备氧化铝-莫来石前驱体溶胶。 ; other | weak_action | 脱除溶胶中多余水分，提高黏度至可纺状态(出现拉丝现象)。

### fiber_process / 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol (C)
- error examples: other | weak_action |  ; other | weak_action |  ; other | weak_action | 

### fiber_process / 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber (C)
- error examples: Sol Preparation | weak_action |  ; Additive Incorporation | weak_action |  ; Concentration | weak_action | 

### mechanism / 008_前驱体铝溶胶中的水解和聚合反应的机理研究 (B)
- correct examples: stir | 九水合硝酸铝溶于去离子水，转移至三口烧瓶水浴加热。缓慢滴加稀释氨水并搅拌至目标pH，保温反应生成悬浊液。 ; stir | 沉淀重新分散于去离子水，加热搅拌下滴加胶溶剂至目标pH使沉淀溶解澄清。继续恒温老化并定期无损取样。
- error examples: other | weak_action | 悬浊液立即离心分离固体沉淀，多次洗涤至上清液中性，去除表面铵根和硝酸根离子。

### fiber_process / 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛 (C)
- error examples: dissolve | weak_action | 将AlCl3·6H2O溶于去离子水，加入铝粉，100℃回流搅拌至完全溶解，过滤得澄清氧化铝溶胶。加入9% ZrOCl2·8H2O、1%硅溶胶及3% PVP，常温 ; dissolve | weak_action | 将AlCl3·6H2O溶于去离子水，加入铝粉，100℃回流搅拌至完全溶解，过滤得澄清氧化铝溶胶。加入9% ZrOCl2·8H2O、1%硅溶胶及3% PVP，常温 ; other | weak_action | 将前驱体溶胶装入计量泵，经喷丝板挤出进入纺丝通道，与空气热交换蒸发水分固化成凝胶纤维。鼓风干燥箱烘干后，置于管式炉中经900℃高温热处理得到Zr掺杂Al2O3纤

### fiber_process / 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究 (C)
- error examples: 配制混合溶剂 | weak_action |  ; 溶解铝源与水解反应 | weak_action |  ; 缩聚与溶胶老化 | weak | 

### fiber_process / 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 (C)
- error examples: other | weak_action | Sol-gel method for Al2O3/Al2O3 composite preparation ; other | weak_action | Thermal evolution of Al2O3 gel to ceramic

### fiber_process / 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究 (C)
- error examples: stir | weak_action | 将金属盐类与溶剂混合搅拌溶解，控制水浴温度加热搅拌，发生水解与聚合反应制成溶胶。 ; other | weak_action | 对合成溶胶进行浓缩处理，调节至合适黏度，获得可纺凝胶。 ; other | weak_action | 可纺凝胶经喷丝板孔压出进入纺丝甬道，与热空气进行热质交换，溶剂挥发并在卷绕张力下凝固拉长，形成前驱体纤维。

### fiber_process / 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m (B)
- correct examples: other | Fibers sintered at various temperatures to induce phase transformation, grain gr
- error examples: other | weak_action | Boehmite sol prepared. α-Al2O3 seed particles introduced via extended ball milli ; other | weak_action | Alumina fibers prepared by sol-gel processing from the seeded sol. ; other | weak_action | Thermal analysis (TGA, DTA), XRD, SEM, and tensile strength testing performed to

### fiber_process / 015_多晶莫来石纤维的制备研究 (B)
- correct examples: other | 制备聚合氯化铝(PAC)溶胶 ; add | 加入酸性硅溶胶和聚乙烯醇(PVA)助纺剂
- error examples: other | weak | 真空浓缩脱除自由水 ; other | weak | 甩丝成纤 ; other | weak | 干燥前驱体纤维

### fiber_process / 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响 (C)
- error examples: stir | weak_action | 配制助纺剂溶液：称取13.65 g环氧树脂加入50 mL烧杯，量取6.8 mL DBE溶剂，室温密封搅拌12 h待用。 ; other | weak_action | 在带干燥剂的通风橱内，量取21.9 mL无水乙醇于锥形瓶中。 ; add | weak_action | 用吸量管称取8.2 mL四氯化钛缓慢加入乙醇中。

### fiber_process / 096_Cai 等 - 2006 - Azeotropic distillation-assisted preparation of macro-mesostructured γ-Al2O3 nanofibres of crumpled (B)
- correct examples: other | 12 mass% H2O2 pumped into NaAlO2 solution under controlled temperature and stirr ; other | Precipitate aged, separated, and washed repeatedly with distilled water until fi

## Parameters / data_points review

### fiber_process / 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### mechanism / 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 010_含硼氧化铝基陶瓷连续纤维的制备及表征 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 059_连续氧化铝纤维及其复合材料的研究进展 (C)
- data_points missing

### fiber_process / 069_静电纺氧化铝！！会议！！纤维膜的制备与构效关系 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 035_氧化铝基陶瓷连续纤维研究进展 (C)
- data_points missing

### fiber_process / 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method (C)
- data_points missing

### fiber_process / 212_Milanović 等 - 2013 - Preparation of low cost alumina nanofibers via electrospinning of aluminium chloride hydroxidepoly (C)
- data_points missing

### fiber_process / 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### mechanism / 008_前驱体铝溶胶中的水解和聚合反应的机理研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 015_多晶莫来石纤维的制备研究 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响 (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

### fiber_process / 096_Cai 等 - 2006 - Azeotropic distillation-assisted preparation of macro-mesostructured γ-Al2O3 nanofibres of crumpled (C)
- error examples: NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found |  ; NO_KEY | bad_canonical_or_raw_name,missing_value,source_text_not_found | 

## Evidence review

### fiber_process / 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维 (C)
- scientific figure_ids in Stage 2: ['图1', '图1', '图2', '图2']
- no evidence_objects produced

### mechanism / 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞 (B)
- scientific figure_ids in Stage 2: ['图3', '图2', '图2', '图3']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 010_含硼氧化铝基陶瓷连续纤维的制备及表征 (B)
- scientific figure_ids in Stage 2: ['Unknown Figure 1', '图2.4', '图2.4', '图2.9', '图2.9', '图2.10', '图2.11', '图2.11']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 059_连续氧化铝纤维及其复合材料的研究进展 (B)
- scientific figure_ids in Stage 2: ['图2', '图12']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 069_静电纺氧化铝！！会议！！纤维膜的制备与构效关系 (A)
- scientific figure_ids in Stage 2: []
- linked evidence examples: NO_FIG | 纤维的比表面积为 242.6m^2/g ，孔径为 8.2nm，孔体积为 0.534cm^3/g ，纤维对刚果红的最大吸附 ; NO_FIG | 此纤维膜对刚果红的最大吸附量为 115mg / g

### fiber_process / 035_氧化铝基陶瓷连续纤维研究进展 (B)
- scientific figure_ids in Stage 2: ['图2', '图2', '图2', '图3', 'Unknown Figure 7', '图3', '图3', '图4']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method (C)
- scientific figure_ids in Stage 2: ['Fig.1', 'Fig.2', 'Fig.2', 'Fig.4', 'Fig.5', 'Fig.6', 'Fig.6', 'Fig.6']
- no evidence_objects produced

### fiber_process / 212_Milanović 等 - 2013 - Preparation of low cost alumina nanofibers via electrospinning of aluminium chloride hydroxidepoly (B)
- scientific figure_ids in Stage 2: ['Fig.1', 'Fig.2', 'Fig.3', 'Fig.3', 'Fig.3', 'Fig.3']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究 (C)
- scientific figure_ids in Stage 2: ['图1-1', '图1-1', 'Fig.1-1', '图1-6', '图1-6', '图1-6', '图1-6', '图1-6']
- no evidence_objects produced

### fiber_process / 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol (C)
- scientific figure_ids in Stage 2: ['Figure 2', 'Unknown Figure 5', 'Figure 1', 'Figure 2', 'Figure 3', 'Figure 5', 'Figure 6', 'Figure 7']
- no evidence_objects produced

### fiber_process / 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber (C)
- scientific figure_ids in Stage 2: ['Fig.2', 'Fig.3', 'Fig.4', 'Fig.5', 'Fig.6', 'Fig.6', 'Fig.7', 'Fig.7']
- no evidence_objects produced

### mechanism / 008_前驱体铝溶胶中的水解和聚合反应的机理研究 (C)
- scientific figure_ids in Stage 2: ['图1-16', '图2-2', 'Fig.2-5', '图4-2', '图4-2', '图4-3', '图4-3', '图4-3']
- no evidence_objects produced

### fiber_process / 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛 (C)
- scientific figure_ids in Stage 2: ['Unknown Figure 1', '图0-1', '图0-1', '图0-2', '图0-2', '图0-3', '图0-3', '图0-3']
- no evidence_objects produced

### fiber_process / 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究 (C)
- scientific figure_ids in Stage 2: ['图1.2', '图1.3', '图2.3', '图3.2', '图3.3', '图4.2', '图4.2', '图4.4']
- no evidence_objects produced

### fiber_process / 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究 (B)
- scientific figure_ids in Stage 2: ['图1.4', 'Fig.1.4', '图1.7', '图1.9', '图1.9', '图1.11', 'Fig.1.11', '图1.12']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究 (C)
- scientific figure_ids in Stage 2: ['图1-8', '图1-8', '图1-9', '图1-10', '图1-10', '图1-10', '图1-10', '图1-11']
- no evidence_objects produced

### fiber_process / 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m (C)
- scientific figure_ids in Stage 2: ['Unknown Figure 5', 'Figure 3', 'Figure 4', 'Figure 5', 'Figure 6', 'Figure 6', 'Figure 7']
- no evidence_objects produced

### fiber_process / 015_多晶莫来石纤维的制备研究 (B)
- scientific figure_ids in Stage 2: ['图2', '图3', '图3', '图3', '图4', '图4']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

### fiber_process / 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响 (B)
- scientific figure_ids in Stage 2: ['图1', '图1', '图1', '图1', '图2', '图3', '图4']
- linked evidence examples: 图3 | 图 3 镁源种类对钛酸铝稳定化效果的影响 ; 图4 | 图 4 不同镁源制备样品的红外图谱
- evidence problems: 图1 | evidence_text_not_found | 图1 相关测试结果图 ; NO_FIG | evidence_text_not_found | 

### fiber_process / 096_Cai 等 - 2006 - Azeotropic distillation-assisted preparation of macro-mesostructured γ-Al2O3 nanofibres of crumpled (B)
- scientific figure_ids in Stage 2: ['Fig.1', 'Fig.2', 'Fig.3', 'Fig.3']
- evidence problems: NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found |  ; NO_FIG | evidence_text_not_found | 

## Cleaned body review

- fiber_process / 002_PVA作纺丝助剂制备莫来石-氧化铝长纤维: A (cleaned_body_ok)
- mechanism / 001_Al_2O_3－SiO_2系透明溶胶的制备及溶胶特性_徐明霞: A (cleaned_body_ok)
- fiber_process / 010_含硼氧化铝基陶瓷连续纤维的制备及表征: A (cleaned_body_ok)
- fiber_process / 059_连续氧化铝纤维及其复合材料的研究进展: A (cleaned_body_ok)
- fiber_process / 069_静电纺氧化铝！！会议！！纤维膜的制备与构效关系: A (cleaned_body_ok)
- fiber_process / 035_氧化铝基陶瓷连续纤维研究进展: A (cleaned_body_ok)
- fiber_process / 158_Jing 等 - 2007 - Synthesis of sub-micro-sized solid alpha alumina fibers with smooth surfaces by sol–gel method: B (possible_back_matter_residue)
- fiber_process / 212_Milanović 等 - 2013 - Preparation of low cost alumina nanofibers via electrospinning of aluminium chloride hydroxidepoly: B (possible_back_matter_residue)
- fiber_process / 032_氧化铝-莫来石前驱体纤维的溶胶设计及预烧结机理研究: A (cleaned_body_ok)
- fiber_process / 194_Liu 等 - 2020 - Preparation of continuous alumina fiber with nano grains by the addition of iron sol: A (cleaned_body_ok)
- fiber_process / 213_Mirjalili 等 - 2020 - The effect of adding different amount of   spinning additives   on preparation of nano alumina fiber: A (cleaned_body_ok)
- mechanism / 008_前驱体铝溶胶中的水解和聚合反应的机理研究: A (cleaned_body_ok)
- fiber_process / 044_溶胶—凝胶法制备ZrO_2掺杂和CuO@In_2O_3负载的氧化铝复合材料及其应用性能_阮铖涛: A (cleaned_body_ok)
- fiber_process / 034_氧化铝基纤维_氧化铝复合材料的制备及其性能研究: A (cleaned_body_ok)
- fiber_process / 060_连续氧化铝纤维增强氧化铝基复合材料的制备与性能研究: A (cleaned_body_ok)
- fiber_process / 061_连续氧化铝纤维高温烧结的相变行为及致密化机理研究: A (cleaned_body_ok)
- fiber_process / 098_Chandradass 等 - 2008 - Synthesis and characterization of sol–gel alumina fiber by seeding α-alumina through extended ball m: B (possible_back_matter_residue)
- fiber_process / 015_多晶莫来石纤维的制备研究: A (cleaned_body_ok)
- fiber_process / 067_镁源种类非水解溶胶-凝胶法制备镁稳定钛酸铝纤维的影响: A (cleaned_body_ok)
- fiber_process / 096_Cai 等 - 2006 - Azeotropic distillation-assisted preparation of macro-mesostructured γ-Al2O3 nanofibres of crumpled: B (possible_back_matter_residue)

## Top problems

- process_steps_weak_or_generic: 20
- data_points_canonical_schema_broken: 20
- evidence_objects_missing_or_unlinked: 19
- section_selection_or_procedure_scope_weak: 12
- cleaned_body_quality_issue: 4

## Recommendation

1. full Stage 3 可以作为后续 two-pass 的质量基线，但 two-pass 目前还不够稳，不能直接替代 full。
2. cleaned_body 图片链接在这批样本里基本已清干净，不再是当前最大问题。
3. 应继续开发 two-pass，但优先修 data_points canonical/schema 和 evidence_objects 生成。
4. 不建议现在继续花钱跑剩余论文。
5. 建议先做 two-pass limit10 与 full limit10 的定点对比，再决定是否恢复批量。

## Full vs two-pass baseline note

- overlapping papers with full limit10: 3
- 在重叠样本上，full 通常 evidence 更完整、结构更稳；two-pass 的主要收益是调用成本下降，但质量退化集中在 data_points 和 evidence_objects。
