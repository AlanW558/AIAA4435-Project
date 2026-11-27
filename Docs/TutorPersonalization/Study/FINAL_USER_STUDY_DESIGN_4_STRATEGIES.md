# Final User Study：四属性四策略比较与 Selective 自然情境评估

> **2026-11-28 最新问卷修订：** 当前属性问卷为 `attribute-summary-feedback-v3`，每属性八题后填写 20 项 A0–A4 七点评分及一项可多选的策略偏好；E/A/N/S 可选 1–4 项，No preference 必须单独选择。只移除偏好题的 Unable to judge / Unable to compare，不移除 A0–A4 的独立无法判断选项。Unity 偏好版本为 `strategy-preference-v2`；旧属性问卷 v1/v2 和旧偏好 v1 保留原形状、原量尺和版本。

> **2026-11-27 实现修订：** Unity 新建运行与辅助工具统一为每属性八题后填写 20 项评价及一次属性偏好；任务卡采用三字段，移除固定试听，属性通过 Confirm changes 统一提交。详见[本次实现契约](GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)。下文较早日期的逐任务流程与试听设计为历史记录，不作为当前实现要求。

版本：v1.9；研究范围/原问卷冻结日期：2026-11-16；工程状态核对：2026-11-27；属性评价单位及 A0 七点量尺修订：2026-11-27。

**2026-11-27 当前任务材料修订：** 当前资源为 `task-navigation-v4` / `attribute-materials-v3`。新辅助批次使用 `StudyData/text-check-v3/`：32 题、情境内 1／2 连续编号、Task goal / Keep unchanged / Request example 三字段、全部策略播放 API 正常生成的回复，固定起始／参考试听已移除。旧数值和任务表保留为研究设计历史；当前完整题卡以资源题库和新版任务文件为准。内部 task_code 未变，旧批次记录保留。

**2026-11-27 当前辅助试听问卷修订：** 用户决定将每道任务的 20 项改为每个属性的 20 项，再加 1 次属性内策略偏好；四属性合计 80 个核心答案＋4 个偏好＝84 项，32 道任务不变。具体题干范围、保存版本与分析单位见[属性级问卷修订](ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)。Unity 新建运行与辅助页面现均使用属性级评价；旧逐任务反馈仅作历史记录，不平均或重标为新评价。

**当前量尺：** 四属性每策略 5 题、每属性一次，均使用 1–7 评分（`attribute-summary-feedback-v3`）。A0 需求满足程度端点为 1 Not at all、7 Completely，原英文题干不变；Unable to judge 独立保存。自然模拟 26 题（`natural-selective-feedback-v2`）、32 题导航、偏好安排与 Selective 自然会话不因本次量尺调整而改变。见[本次问卷契约](ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)、[流程接入](../STUDY_FLOW_INTEGRATION.md)与[数据契约](STUDY_DATA_PERSISTENCE_CONTRACT.md)。研究入口仍为 engineering，正式采集与新版头显整体验收未完成；工程可运行不代表混合问卷已获心理测量验证。

以下保留此前冻结的研究设计与 Unity 接线说明。当前辅助试听页面的填写单位与保存版本，以顶部 2026-11-28 多选偏好及属性级问卷修订为准；其余范围仍参考下文及数据契约。早期阶段记录见同目录历史草案。

## 0. 最新范围决定（研究范围 2026-11-11；问卷更新 2026-11-16）

依据用户与组员讨论，保留五个研究方向，改为 **Speech rate / Reply length / Tone / Voice / 模拟自然情境**。调整原因是原任务与评分负担过大，独立外观任务与第一次 User Study 重复，且回合式单项调整不适合承载所有过程体验评价。

- 四属性方向各保留四种情境，每情境由三题减为两题，即每方向八题、四方向共 **32 题**。第 5 节已完成并获用户接受的两题筛选；Voice 定性描述仍需与当前真实音色重新绑定。
- 第五方向由独立外观实验扩展为模拟自然情境：研究者提供大方向，参与者自行决定细节；采用一段连续的开放交流：开始与 tutor 交谈并探索适合自己的交流方式，外观与交流属性在全过程都可随时调整；不分“先属性、后外观”的固定阶段，不规定具体数值、外观目标或固定口述。外观能力保留，纳入综合过程；旧十二道外观题只保留为可参考素材，不自动照搬到新模块。
- 自然情境只运行 **Selective（S）**，每位参与者进行一段连续自由交流，结束后填写一次专用问卷。它不进行策略横向比较，也不套用四属性的“每情境两题”。当前范围为 **32 道受控任务＋1 段自然情境**，不能把两类活动当作 33 道等价任务。
- 2026-11-16 原方案为完成情况分类题加四道 1–7 评分题；2026-11-27 后续修订将 A0 改为需求满足程度 1–7 分。当前五项为需求满足程度、感知难易度（SEQ 改编）、修改控制感（SASSI 改编）、澄清决策合适程度、总体满意度。A0 使用完全未满足—完全满足端点，A1 使用难—易端点，A2–A4 使用同意度。“打断感”等过程维度用于模拟自然情境结束后的评估，两类任务不强制使用相同问卷。
- 四属性继续 E/A/N/S 同题并行和首次统一展示；每属性结束一次偏好，共四次。四属性全部结束后、自然情境之前，收集一次四属性比较的总体偏好。自然情境不再设置策略偏好，不将单策略体验解释为四策略比较。
- 此次更新研究文档与已确认题目选择，不修改运行代码或问卷校验。四属性、外观、对话历史、澄清/修复、分支隔离及恢复能力继续实现。后续正式任务库、调度与问卷接线依据更新后的设计，不固定为五方向相同题量或六项评分。

新增功能决定：**对话文本日志默认开启**，保存参与者提交的 STT 文本与 tutor 输出，以任务、策略和版本关联问卷，支持一致性核对与后续分析。研究者在实验前告知参与者，VR 不新增标注或开关；不保存原始音频。澄清和后续修复也纳入记录，问卷备注与 tutor 对话分开。实现及当前 STT 边界见[对话日志说明](../DIALOGUE_LOGGING.md)。

本版是问卷内容的最新依据；最新字段与保存规范见[数据保存契约](STUDY_DATA_PERSISTENCE_CONTRACT.md)，[旧字段对照表](STUDY_PROTOCOL_AND_QUESTIONNAIRE_CONTRACT.md)仅作历史参考；文档更新不表示新问卷已接线。自然情境时长/结束规则、正式音色素材、任务顺序及分析计划等仍待完善；本版不是已经验收可施测的协议。旧外观任务仅供历史参考；访谈保持可选，五选二规则不变。

## 1. 实验目的与总体设计

研究分为两部分：四属性受控任务比较同一初始请求下四种策略的目标达成、过程体验与偏好；随后用单一 Selective 连续交流评估其完整使用体验、问题与改进方向。主结果来自参与者问卷，不进行研究者客观音频测量或自动音频达标判定。自然情境不支持 Selective 优于其他策略的因果结论；第一次外观研究作为独立既有证据讨论，不与本轮直接合并成同一受控样本。

四属性部分由研究者提供任务目标；参与者自由使用英文语音提出请求，不要求照读固定句。一次 STT 后，同一请求文本与相同公开起始状态进入四个独立策略分支。四策略在后台并行处理。首次展示前，参与者先回答实际触发的澄清；所有分支准备完毕后统一开放结果，避免提前完成的结果影响其他分支的澄清回答。开放后可自由切换、试听、查看和修复；每题结束保存结果后进入下一题；该属性八题全部完成后，回顾结果并填写一次属性问卷。

实验保留五个方向模块，前四个为属性比较，最后一个为 Selective 自然情境。四属性内部的呈现顺序尚未冻结，不沿用原 E/A/S 六序列方案；并行要求仅适用于属性比较。流程为：熟悉操作 → 四属性任务及各属性偏好 → 四属性总体偏好 → 休息/重置 → Selective 自然情境 → 自然情境问卷 → 可选访谈。允许旧研究参与者加入并记录既往参与情况；正式任务、界面说明及问卷使用英文。

## 2. 四种策略及公平比较范围

| 代码 | 名称 | 对受支持的独立定制请求的行为 | 边界 |
| --- | --- | --- | --- |
| E | Execute-first | 直接执行共同默认有效候选，用户随后可以检查和修复。 | 不强行执行非法或不受支持的修改。 |
| A | Always-ask | 在执行前询问；明确请求可以确认，含糊请求用共同澄清问题。 | 回答澄清完成原请求，不再次要求对同一回答确认。 |
| N | Native-gate | 由同一基础 LLM 自主选择 ASK、ACT 或 UNRESOLVED，不向它提供 S 的决策规则。 | 是共同框架内的原生模型决策模块，不是拥有额外工具或记忆的完全自由 agent。 |
| S | Selective | 按选择性规则判断何时询问、何时执行，包括历史引用、偏好覆盖、不同实质解释及受支持的小幅可逆调整。 | 已有四属性规则实现；正式材料与整套流程仍待验收，不预设 S 优于其他策略。 |

第四种恢复的是旧外观研究的 N（Native-gate），已核对项目协议及 Backend/core.py。旧研究“仅首次请求过策略”的范围不直接继承：本轮每条新的自然语言定制/修复请求均使用该分支策略；普通知识问答、回答已有澄清、试听和明确控件操作不重复触发策略。

四分支共用模型与能力、公共上下文、候选生成/排序、默认修改、问题及选项呈现、手动控件和恢复能力。对同一初始请求，生成一次公共候选再复制给四种决策模块，公共候选生成不接收策略标签。N 额外做策略决策不意味着给它额外目标信息；四分支都不能读取研究者私有目标。

### 2.1 一致输入与独立后续交互

- 一次自然口述只做一次 STT；四分支读取同一份实际识别文本，不分别识别出四种输入。
- 同时复制本题基线和公开历史；四分支各自维护修改、澄清、修复和最新结果。
- **首次结果统一展示**：澄清阶段仅显示共同起点、待回答问题/选项及中性状态。已完成分支的新属性、回答、外观、修改历史及声音均暂存，不提前显示或播放。所有实际触发的澄清处理完毕，且对应结果准备完成后，才一次性开放四分支。失败须重试或明确结束为未完成，不自动放行，也不伪装成功。
- 首次开放的四份结果快照固定保存。之后的追加修复独立记录，评价与所针对的结果版本关联；不将修复后结果误记为首次展示结果。
- 用户回答某分支的问题只进入该分支，不自动传入其他分支，也不由研究者私有目标代答。
- 切换分支恢复其已有状态，不能每次切换都清空已完成修改；新题开始才恢复新的共同起点。
- 语音一次播放一个选中分支，由用户自由决定先后和重听；外观自由切换比较，视角、光照、距离保持一致。
- 开始比较时展示中性策略名称/说明，不称全程盲测，不用“最佳”“智能”等暗示标签。策略标识不随卡片位置改变。
- 同时处理不代表没有呈现位置、先看先听或记忆影响。界面位置与实际查看路径可记录；本稿不重新强制分配策略体验顺序。
- 多个策略得到相同结果时照常呈现和评价，不重生成到产生差异。

## 3. 五个方向与当前题量

| 材料轮次 | 方向 | 情境数 | 每情境任务数 | 本轮任务数 | 方向末偏好 |
| --- | --- | --- | --- | --- | --- |
| Round 1 | Speech rate | 4 | 2 | 8 | 1 次 |
| Round 2 | Reply length | 4 | 2 | 8 | 1 次 |
| Round 3 | Tone | 4 | 2 | 8 | 1 次 |
| Round 4 | Voice | 4 | 2 | 8 | 1 次 |
| Round 5 | Selective 自然情境（含属性调整与外观改造） | 不划分固定情境 | 不适用 | 1 段连续交流 | 无策略偏好；结束一次专用问卷 |

四属性合计 **32 题**；每题比较四策略，对应 128 个“任务×策略”结果。主观评价按每属性八题汇总，保存 16 份“属性×策略”五题问卷；自然情境另有 1 份会话问卷，共 17 份评价记录。128 个策略结果不是 128 个独立参与者，也不是 128 份当前主观问卷。四属性内部顺序待定，自然情境在四属性比较和总体偏好之后。

四属性每属性八题后反馈一次，自然情境结束一次反馈。保留 **4 次属性末偏好＋1 次四属性总体偏好，共 5 次**，无每题偏好或自然情境偏好。完整路径的核心作答量为四属性 80 项＋自然情境 26 项＋偏好 5 项，共 **111 项**；不含可选原因、文字备注及访谈，实际点击次数受修改/多选影响，不等同于该数字。

### 3.1 四类情境

| 情境 | 共通设计角度 | 按属性的适配 |
| --- | --- | --- |
| C1 明确目标的修改 | 用户有明确目标，比较直接执行与确认的体验。 | 具体速率、回答结构、风格/声音选项或外观修改。 |
| C2 程度或定性偏好描述 | 不必报出精确值/选项名称，观察如何把描述转为可接受调整。 | rate/scale 是幅度；length 是内容增减；tone/voice 是风格/音色偏好，不假设连续强度。 |
| C3 可能存在不同解释 | 同一整体意图可能通过不同属性或结果实现。 | 如“更平静”可能涉及速度、措辞或声音；具体任务有参与者私有目标。 |
| C4 历史/偏好及局部恢复 | 使用公开历史、已有软偏好，或恢复部分设置同时保持新变化。 | 包含唯一引用、多个历史目标、明确覆盖旧偏好和选择性恢复。 |

这些类别用于任务设计，不是强制口述类型，也不是保证互斥的独立因子。C2 在不同方向的含义不完全同构。C3 任务如果被参与者主动表达得很明确，就如实保留，不要求重说得含糊或删掉试次。

## 4. 共同设置与参与者材料

### 4.1 任务卡和保持要求

后面的英文任务内容是**给参与者看的私有目标卡**，不是固定输入脚本。可统一提示：

> Use your own words to ask the tutor for the change. You may mention any details you consider useful. Keep all settings not targeted by this task unchanged.

用户可以主动把目标说给 tutor，但后台不能自动将任务卡、目标值、研究类型或任务 ID 填入模型上下文。公共状态、能力和公开历史在四分支一致可用。

除每题列出的目标字段外，其余字段保持不变。对话任务保持全部外观；外观任务保持全部对话设置。各题独立重置，不自动沿用上一题的更改。表格未注明的字段使用下述基线。

### 4.2 基线与档位

| 项目 | 当前设计 |
| --- | --- |
| Rate | 1.00× 表示模型在当前声音下的默认速度；默认倍数与当前倍数分别计算。 |
| Length | Brief：关键答案/建议；Balanced：关键点＋简短理由；Detailed：关键点＋较充分解释＋相关例子或必要步骤。无固定字数/句数限制。 |
| Tone | Professional：专业、克制、直接；Friendly：温暖、友好；Encouraging：支持尝试、鼓励进步。不是连续强度顺序。 |
| Voice | 已有五个声音 A–E，运行默认 D。旧任务表中的 A/B/C 定性描述仍需用当前真实声音核对并重新绑定，不将旧描述直接当现有声音事实。 |
| 受控任务基线 | 未另注明时 rate=1.00、length=Balanced、tone=Professional、voice=Voice A；任务专用值优先。任务基线与应用默认 Voice D 不混用。自然情境另行定义共同起点。 |
| 外观基线 | Liang、蓝色西装、眼镜、整体比例 1.00；本稿十二道外观题保持角色身份。 |

Voice 任务中的定性描述仍是待核对素材。现有语速范围 0.70–1.30、步进 0.01，支持 1.08×，不静默取整。旧外观材料不代表自然情境必须完成的目标；所有能力仍需在最终实验入口联调验收。

### 4.3 输出呈现

- Speech rate / Voice：可使用同一句 `The next section explains the main idea and gives one example.` 试听，四策略本题文字一致。
- Reply length / Tone：需要实际生成回答，不能只用固定短句；同题四分支使用同一内容提示。任务末位 1、2、3 可分别对应以下提示：
  - `How can I make a useful study plan for next week?`
  - `How can I check whether I understand a new concept?`
  - `What should I do after getting a practice question wrong?`
- Appearance：实际外观呈现，角度/光照/距离一致；目标大小图卡用同相机制作。
- 历史任务提供相同的公开历史，标明是本题的示例历史，不伪称参与者刚刚真实操作。私人目标样例不自动传给 agent。
- 不保存问卷录音，只保留需要的 STT 文本；参与者实际听输出后评分，研究者不分析音频时长或波形。
- 不自动增加旧协议的固定三回合保持检查；若后来加入实际后续交流，另确定流程。本稿问卷中的不保持原因仅在确实有后续交流时显示。

## 5. 各方向的具体情境与任务

每个任务都从表中起点开始，四策略共享该起点与自然请求。目标提示用于参与者/研究者理解目标，不是后台自动判分。2026-11-10 已从四属性原有 48 道候选中，每情境保留两题，形成下列 32 题已选清单；无需为 E/A/N/S 分别准备变体。第五方向按第 11 节采用一段 Selective 连续交流，5.5 的旧外观表仅作历史参考。

### 5.0 本轮删题记录与使用边界（2026-11-10）

本次从当前四属性清单移除的题号为：R1-3、R2-3、R3-3、R4-2；L1-2、L2-3、L3-3、L4-1；T1-2、T2-1、T3-3、T4-2；V1-3、V2-3、V3-3、V4-1。保留原 ID，避免旧记录错配；每个情境的两道保留题不重新编号。

筛选优先保留不同参照基准、增减方向、跨属性竞争解释，以及历史恢复/偏好覆盖/局部恢复等机制，而非仅删去每组第三题。这是基于项目覆盖需要的设计判断，不声称已由实测证明题目最优。旧 60 题草稿保留为历史资料，不作为当前执行清单。

- 正式计分题应加载表中规定的公共起点；自由选择初始偏好宜放在熟悉阶段。不能在 R1-1/R1-2 开始前任意改变 1.20 的基准。现有共享准备界面后续需区分熟悉阶段与受控任务准备。
- 任务卡仍允许参与者自然表达。C2/C3 是设计情境，不保证每次实际口述都不精确或有歧义；表达清楚的试次不能强迫重说或删去。
- Voice 的旧声线特征是历史占位。2026-11-11 预演材料已绑定当前音色 B/C/A，V2/V3 的目标卡改为试听并自行描述，不再把 Voice C 预设为低沉男声；正式施测前仍需试听复核可辨性和 C2/C3 的区别。应用默认 Voice D 与本研究普通起点 Voice A 是不同概念。
- 2026-11-11 已确认四属性保留四项评分（含总体满意度），移除打断感和独立顺利程度题；2026-11-16 更新题干及来源，以第 6 节为准。新版已接入，问卷版本与旧数据边界见第 6.5 节。

### 5.1 Speech rate：语速

本方向 4 类情境 × 2 题 = 8 题；每题比较四策略。本方向结束后填写一次方向偏好。

#### C1 明确目标的修改

保留模型默认基准与当前值相对变化的对照；恢复默认不再单独占用一题。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| R1-1 | rate=1.20 | Change the speaking speed to 90% of the model’s default speed. | 0.90× 默认 |
| R1-2 | rate=1.20 | Reduce the current speaking speed by 10%. | 1.20 × 0.90 = 1.08× 默认 |

#### C2 程度不精确的小幅调整

目标范围是给参与者的判断依据；可以自然表达，也允许报数值。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| R2-1 | rate=1.00 | Make the tutor speak a little more slowly. Your target is between 0.90 and 0.95 of the default speed. | 0.90–0.95× |
| R2-2 | rate=0.85 | Make the tutor speak a little faster, aiming for 0.90 to 0.95 of the default speed. | 0.90–0.95× |

#### C3 可能存在不同解释

以速度实现整体意图，与改语气、声音或缩短回复形成可能的竞争解释。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| R3-1 | rate=1.00 | You want the delivery to feel calmer by slowing the pace to 0.85–0.90, without changing the tone or voice. | rate=0.85–0.90；竞争解释可能是 Friendly/Voice B |
| R3-2 | rate=1.15; length=Detailed | You want the detailed explanation to be easier to follow by slowing the pace to 0.95–1.00. Keep all its detail. | rate=0.95–1.00；竞争解释可能是减少解释 |

#### C4 历史与偏好

保留唯一旧值恢复与明确覆盖旧软偏好；多历史目标在其他属性任务中保留。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| R4-1 | 公开语速历史 0.90 → 当前 1.10；仅一个先前值 | Restore the previous speaking pace, leaving the other settings as they are now. | 0.90×；唯一引用 |
| R4-3 | rate=1.10；公开软偏好 “I usually prefer a pace of 1.10.” | For this task, use 0.90 of the default speed, even though your earlier preference was 1.10. | 0.90×；明确覆盖旧软偏好 |

### 5.2 Reply length：回答内容构成

本方向 4 类情境 × 2 题 = 8 题；每题比较四策略。本方向结束后填写一次方向偏好。

#### C1 明确目标的修改

直接指定回答应包含哪些组成，不按固定句数或字数。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| L1-1 | length=Balanced | Give only the key answer or recommendation, without explaining the reason or adding an example. | Brief：关键点 |
| L1-3 | length=Balanced | Give the key answer, explain why it makes sense, and add one relevant concrete example. | Detailed：关键点＋解释＋相关例子 |

#### C2 内容增减

增加或减少理由/例子，保持核心信息。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| L2-1 | length=Detailed | Make the answer a little less detailed: keep the key point and a short reason, but remove the example. | Balanced；删去例子保留理由 |
| L2-2 | length=Brief | Add a little explanation to the key answer so you know why it is useful, without adding an example. | Balanced；补理由 |

#### C3 可能存在不同解释

区分减少内容、增加理解支持与改语速/鼓励风格等解释。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| L3-1 | length=Detailed | You feel overloaded and want a less overwhelming answer: keep only its key point, rather than changing the speaking speed. | Brief；竞争解释可能是减慢语速 |
| L3-2 | length=Brief | You need more support to understand the material: add an explanation and an example, rather than only receiving more encouraging wording. | Detailed；竞争解释可能是 Encouraging；实际 tone 保持当前 |

#### C4 历史与局部恢复

恢复过去的回答结构，并在需要时保留最新语气。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| L4-2 | 公开结构历史 Balanced → Detailed → 当前 Brief；配各自回答例子 | Restore the middle answer format, which included an explanation and a concrete example. | Detailed；多历史目标 |
| L4-3 | 公开旧状态 length=Balanced,tone=Professional；当前 length=Detailed,tone=Friendly | Restore the earlier key-point-plus-reason format, while keeping the friendly tone you now have. | Balanced；保留 Friendly，非整套恢复 |

### 5.3 Tone：语气风格

本方向 4 类情境 × 2 题 = 8 题；每题比较四策略。本方向结束后填写一次方向偏好。

#### C1 明确风格选择

在三个离散风格间明确切换。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| T1-1 | tone=Professional | Use a Friendly tone for the tutor’s responses. | Friendly |
| T1-3 | tone=Encouraging | Use a Professional tone for the tutor’s responses. | Professional |

#### C2 定性风格偏好

用日常语言描述风格，不编造连续强度刻度。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| T2-2 | tone=Friendly | Make the wording more neutral and matter-of-fact, while keeping the same amount of information. | Professional；定性风格偏好 |
| T2-3 | tone=Friendly | After a practice mistake, you want wording that supports another attempt and reinforces that progress is possible. | Encouraging；定性风格偏好 |

#### C3 可能存在不同解释

整体氛围目标可能由措辞、语速或声音实现；本题指定私有目标。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| T3-1 | tone=Professional; rate=1.10 | Make the interaction feel less intimidating by using friendly wording. Keep the current pace and voice. | Friendly；竞争解释可能是语速/声线 |
| T3-2 | tone=Professional; length=Brief | You want to feel more motivated to continue: use supportive encouragement, without giving a longer explanation. | Encouraging；竞争解释可能是增加说明 |

#### C4 历史与偏好

恢复历史风格或明确覆盖旧软偏好。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| T4-1 | 公开语气历史 Friendly → 当前 Professional；配实际表达例子 | Restore the friendly style used in the previous response. | Friendly；唯一历史 |
| T4-3 | tone=Professional; voice=Voice B；公开软偏好 “I usually prefer professional wording.” | For this task, use an Encouraging tone instead of your earlier preference for professional wording. Keep Voice B. | Encouraging；明确覆盖软偏好，保留 Voice B |

### 5.4 Voice：声音选择

本方向 4 类情境 × 2 题 = 8 题；每题比较四策略。本方向结束后填写一次方向偏好。

#### C1 明确声音选择

参与者熟悉当前实际 A–E 声音后按目标切换。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| V1-1 | voice=Voice A | Switch to Voice B, which you heard during familiarisation. | Voice B |
| V1-2 | voice=Voice B | Switch to Voice C, which you heard during familiarisation. | Voice C |

#### C2 定性音色偏好

目标样例私有可听，以当前 A–E 声音绑定为准；参与者自行描述听到的声线特征，不预设“低沉／温柔”等尚未核验标签，不连续调音高。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| V2-1 | voice=Voice A | Listen to target sample B. Choose that vocal character and describe what you would like in your own words. Keep the speaking rate and wording style. | Voice B；以当前实际样例为准 |
| V2-2 | voice=Voice A | Listen to target sample C. Choose that vocal character and describe what you would like in your own words. Keep the other settings. | Voice C；以当前实际样例为准 |

#### C3 可能存在不同解释

区分换声音与改速度/措辞风格。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| V3-1 | voice=Voice A; rate=1.10 | You want a different feel to the delivery by changing to target voice B. Keep the current pace and wording style. Listen to the target before making your request. | Voice B；保持 rate/tone |
| V3-2 | voice=Voice B | You want a different feel to the delivery by changing to target voice A. Keep the current pace and wording style. Listen to the target before making your request. | Voice A；保持 rate/tone |

#### C4 历史与局部恢复

重用先前声音，同时保持要求保留的当前设置。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| V4-2 | 公开声音历史 Voice B → Voice C → 当前 Voice A；可重听 | Restore the voice from the middle history entry. | Voice C；多历史目标 |
| V4-3 | 公开旧状态 voice=B,rate=0.90,tone=Professional；当前 voice=A,rate=1.15,tone=Friendly | Restore the earlier Voice B, but keep the current faster pace and friendly tone. | Voice B；保留 rate=1.15、Friendly |

### 5.5 旧 Appearance 外观任务（历史参考，不施测）

以下十二题保留作既有设计资料，不进入本轮任务清单、问卷计数或偏好采集。当前外观能力在第 11 节的自由自然情境中使用，不要求参与者完成这些目标。

#### C1 明确目标的定向修改

覆盖颜色、配饰和服装，包含保持要求。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| A1-1 | 外观基线 | Change the jacket colour to green. Keep the glasses, outfit type and size unchanged. | green；其余外观不变 |
| A1-2 | 外观基线 | Replace the glasses with a hat. Keep the colour, outfit and size unchanged. | hat；去除 glasses，其余不变 |
| A1-3 | outfit=suit; colour=purple; accessory=glasses; scale=0.95 | Change to sportswear while keeping the purple colour, glasses and current size. | sport；purple/glasses/0.95 保留 |

#### C2 程度不精确的小幅调整

只使用已有整体比例能力，不假设独立身高/材质明度控件。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| A2-1 | scale=1.00 | Make the tutor slightly larger. Either target size shown, 1.05 or 1.10, is acceptable; keep the rest unchanged. | scale∈{1.05,1.10} |
| A2-2 | scale=1.10 | Make the tutor slightly smaller. Either target size shown, 1.00 or 1.05, is acceptable; keep the rest unchanged. | scale∈{1.00,1.05} |
| A2-3 | scale=0.85 | The tutor looks too small. Increase it modestly toward target size 0.90 or 0.95, without returning all the way to 1.00. | scale∈{0.90,0.95} |

#### C3 风格或整体印象调整

多个外观属性可能达成整体印象，私有目标限定所需结果。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| A3-1 | 外观基线 | You want a more casual look through sportswear. Keep the glasses, colour and size unchanged. | sport；竞争解释可能是去配饰 |
| A3-2 | colour=orange; accessory=hat | You want a more understated look through a grey outfit colour. Keep the hat, outfit type and size. | gray；竞争解释可能是去帽子 |
| A3-3 | 外观基线 | You want the tutor to stand out more through a yellow outfit colour, without making it larger or changing the accessories. | yellow；竞争解释可能是放大比例 |

#### C4 历史引用与选择性恢复

区分唯一历史、多历史目标与只恢复部分字段。

| ID | 公共起点／上下文 | 英文任务目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- |
| A4-1 | 公开颜色历史 green → 当前 blue；其余外观相同 | Restore the jacket colour used immediately before the current blue. Keep everything else as it is now. | green；唯一历史 |
| A4-2 | 公开颜色历史 orange → gray → 当前 blue；配图 | Restore the jacket colour from the first history entry. Keep the other appearance settings unchanged. | orange；多历史目标 |
| A4-3 | 公开旧状态 sport/blue/glasses/1.00；当前 suit/purple/hat/1.05 | Restore the earlier sportswear, while keeping the current purple colour, hat and size. | sport；保留 purple/hat/1.05 |

## 6. 四属性统一属性级问卷（2026-11-27：每策略 5 题版）

适用于 Speech rate、Reply length、Tone、Voice。评价单位为参与者在该属性全部八道任务中体验的一种策略；每属性四份反馈。四属性统一五题 1–7 评分，不增加属性专用评分，每题另有独立的无法判断选项。可重看、重听后作答，不要求照读请求。本版是项目混合问卷：SEQ/SASSI 改编项与项目专用项分别报告，不称完整 SEQ/SASSI 量表。

英文引导：

> Please rate your experience with this approach across all tasks for this attribute. Consider its responses, any clarification, and the outcomes. Do not rate the questionnaire or the process of switching between approaches.

该引导帮助区分策略体验与实验操作负担，但不能消除并行比较、共享初始请求及先看先听的影响。SEQ 的评价单位已从独立任务改为该策略在整组属性任务中的调整体验，不直接使用原工具常模或百分位。

### 6.1 需求满足程度 A0

**English:** `Overall, to what extent did this approach’s outcomes meet your requirements across the tasks for this attribute?`

帮助说明：`Consider both the requested change and the settings that were supposed to stay unchanged.`

评分：1–7，端点为 **1 Not at all（完全未满足）**、**7 Completely（完全满足）**。另有独立的 **Unable to judge**，表示无法判断，不记为 4，也不当作失败。

来源：项目自编结果题，不来自标准量表。设计理由：同时考虑要求的修改和保持要求，以七点程度评分表达整组任务的主观目标符合程度；原英文题干不变。A0 关注结果是否满足具体要求，A4 关注整体使用体验的满意度，分别分析，不合成总分。结束、提交或播放均不自动表示成功，本题也不称客观成功率。旧 v1 的分类答案保留原版本，不转换为分数或与 v2 合并分析。

### 6.2 四项评分 A1–A4

| ID | 角度 | 英文施测候选题干 | 来源与改编范围 | 设计理由 | 评分 |
| --- | --- | --- | --- | --- | --- |
| A1 | 感知难易度 | Overall, how difficult or easy was it to make adjustments to this attribute using this approach? | [SEQ] 改编：限定本次调整及当前策略；并行评价的使用情境也不同于独立完成任务 | 评价调整过程的难易度，与结果满足要求的程度分开 | 1 Very difficult—7 Very easy；高分更容易 |
| A2 | 修改控制感 | Across the tasks for this attribute, I felt in control of the changes made to the tutor with this approach. | [SASSI] Table 4 控制感内容改编：一般交互改为 tutor 修改，采用本项目七点量尺 | 直接执行或澄清都可能影响控制感；不预设某策略更好 | 七点同意度；高分控制感更强 |
| A3 | 澄清决策合适程度 | This approach’s decisions about whether to ask for clarification suited my needs across the tasks for this attribute. | 项目专用题，不声称来自标准量表 | 同时评价询问与不询问的选择，避免把询问数量等同质量 | 七点同意度；高分更合适 |
| A4 | 总体满意度 | Overall, I am satisfied with my experience of adjusting this attribute using this approach. | 项目自编单题满意度；不称 SUS 或 SASSI 分数 | 保留用户确认的整体体验判断；与目标达标、控制感分开 | 七点同意度；高分更满意 |

A1 显示数字 1–7 和难—易端点，不套用同意度标签。A2–A4 的锚点为 1 Strongly disagree、2 Disagree、3 Somewhat disagree、4 Neither agree nor disagree、5 Somewhat agree、6 Agree、7 Strongly agree。

A0–A4 各有独立 Unable to judge，作为缺失/不可判断类别报告，不记为 4 或失败。无预填答案。五项分别分析，不相加形成“策略质量总分”，不把不同构念合成一套量表计算整体内部一致性来证明效度。

本部分不加入完整 SUS、NASA-TLX 或更多 SASSI 条目：属性级评价已有 80 个核心作答项；共享初始 STT 的识别问题也难以分别归因给四策略。打断感只进入自然模拟。

### 6.3 可选原因与口述备注

正式 Unity 问卷中，A0 为 1–6 分或 Unable to judge 时可选填下列原因。这里仅控制原因选项是否显示，不据此定义客观任务成功阈值。辅助试听页面保留可选自由文字备注，不增加这些原因必答项。

| 字段 | English option |
| --- | --- |
| target_mismatch | The requested change did not meet the requirements. |
| unwanted_change | Something that should have stayed unchanged was changed. |
| not_maintained | The change was not maintained during later interaction. |
| hard_to_verify | I could not tell whether the change had taken effect or met the requirements. |
| interaction_problem | A speech, playback, or interaction problem affected my attempt or judgement. |
| other | Another reason. |

not_maintained 只在确实发生后续交流时提供。所有评价（包括 A0 为 7 分）均可添加 Additional comments。VR 中备注采用口述 STT，参与者确认后保存文字；不保存问卷录音，不送入 Tutor 上下文，不根据文字自动改评分。辅助页面使用可选文字输入。原因与备注均不作为继续条件。

### 6.4 提交及题量

每属性八题完成后，四策略各五题评分均有有效答案，才可最终提交该属性问卷，再填写偏好并进入下一属性。Unable to judge 为有效作答。回顾不清空答案；问卷绑定八题的冻结结果版本。暂停不依赖问卷完整，也不自动算作成功。

四属性共 4 属性 × 4 策略 × 5 题＝80 个评分答案；另有四次属性末偏好，辅助试听页面合计 84 个必答项目。自然情境、正式流程的总体偏好和可选内容另计。每个属性八题结束后只问一次偏好，不在此基础上再重复“方向末偏好”。

### 6.5 与现有实现的关系

当前问卷契约为 `attribute-summary-feedback-v3`：A0 使用需求满足程度七点量尺，A1 使用 perceived_ease 难易度量尺，A2–A4 使用各自同意度题干。新版 Unity manifest 显式设置 `attribute_questionnaire_version` 为 v3，并将 `preference_questionnaire_version` 固定为 `strategy-preference-v2`；缺少该字段的旧属性级 manifest 仍按 v1 处理。当前自然问卷保持 `natural-selective-feedback-v2`。原始量尺、无法判断、显式跳答与未作答状态按数据契约区分。

旧属性级 `attribute-summary-feedback-v1` 的分类 A0、逐任务 `attribute-feedback-v3`、旧 `attribute-feedback-v2` 的 effort_ease 及更早 `task-feedback-q1-q7-v1` 仍只属于各自版本，不回填、不重标为新问卷或真实研究数据。v3 草稿与旧版本隔离，类别不转换为分数。旧属性级 v2 的 A0 仍为 1–7 数值、偏好仍按单选标量读取；不会因当前版本升级误变成类别题，也不会把已有标量自动改成多选数组。正式施测前仍需预测试和头显验收。

## 7. 四次属性末偏好与一次比较总体偏好

### 7.1 每属性一次，共四次

| 方向 | English question |
| --- | --- |
| Speech rate | For speech-rate adjustments, which approaches would you prefer to use? |
| Reply length | For reply-length adjustments, which approaches would you prefer to use? |
| Tone | For tone adjustments, which approaches would you prefer to use? |
| Voice | For voice adjustments, which approaches would you prefer to use? |

### 7.2 四属性比较结束后一次

**English:** `Considering the speech-rate, reply-length, tone, and voice tasks, which approaches would you prefer to use overall?`

在四个属性及其偏好完成后、进入自然情境前填写。只评价四属性比较经历，避免后续额外 Selective 暴露改变比较基础。自然情境只体验 S，不询问该模块的策略偏好，结束后也不重复总体偏好。

### 7.3 五次偏好的统一规则

- E — Execute-first；A — Always-ask；N — Native-gate；S — Selective；可多选 1–4 个偏好策略。英文指导：`Select all approaches you prefer (one to four), or choose No preference on its own.` 保存唯一策略集合，不自动排序、不把多选换算成多个人。
- 新偏好题仅另设 `No preference`，与策略集合互斥。选择它会清除策略勾选；选择任一策略会清除它。去掉偏好题的 Unable to judge / Unable to compare；旧提交中的这些状态按旧版本保留，不能解释成偏好 S 或均分给四策略。
- 无默认答案；至少勾选一项策略，或独立选择 No preference，才完成该偏好题。全部取消回到未作答。A0–A4 的 Unable to judge 仍为有效独立作答；它们不受偏好选项删减影响。可选 STT 理由不作为继续条件。
- 属性偏好与总体偏好独立收集，不从评分计算，也不强制一致。
- 暂停/退出不以作答为前提；只有正常继续路径要求当前偏好已提交并获得保存确认。

## 8. 问卷数据含义与当前待落实内容

任务与条件以方向、情境、任务 ID、策略代码关联。四属性保存新版 A0–A4 五项评分的 1–7 整数或独立无法判断状态及问卷版本、原因集合、可选确认文本、四次属性偏好和一次四属性总体偏好。旧版完成情况类别保留原版本，不与新数值混算。简要记录实际体验范围及结果版本，防止评分错配；不要求参与者输入编号。

自然情境另以独立会话 ID、S 条件和会话评价版本关联，保存 goal_fit、七项交互诊断评分、完整 SUS 十题、完整 UEQ-S 八题及可选确认文本；不伪造受控任务情境标签或另外三个策略的反馈。与四属性同名的评分维度仍保留不同问卷版本和评价单位，不直接混算。

参与者、整场研究、模块、任务／对话及问卷使用分层编号；四属性 `attribute-summary-feedback-v3`、自然 `natural-selective-feedback-v2` 与旧记录分离。草稿、最终提交、同步和完整性按[数据保存契约](STUDY_DATA_PERSISTENCE_CONTRACT.md)及本次版本修订分别记录。

不把未答当作中间分，不把无法判断当失败，不将各角度混成总分。新问卷的评价单位是参与者 × 属性 × 策略；八道任务构成同一属性评价的证据，不能由属性总评还原某一道任务或情境的主观评分。四策略为参与者内比较，后续分析需保留这些关联。主要对比、统计处理和缺失分母尚未在本稿定案，不按结果挑选有利题目。英文自由表达使设计情境不保证成为实际歧义，不能用题库标签替代实际口述特征。

当前已实现四策略隔离与每轮统一揭示、真实语音接口、文本日志、独立问卷面板、新版 5/26 题反馈、五次偏好、32 题预演及 Selective 自然会话，并接通身份、可靠保存、导出和中断恢复。仍需完成正式分配/时长等施测设置的冻结、问卷预测试及新版头显整体验收；本机人工验证不覆盖完整自然模拟和全程头显体验，工程测试不证明问卷的心理测量效度。

**访谈保持可选。** 第 10 节提供五道候选问题，每位愿意参与访谈者随机抽两道；用于报告/presentation 的案例解释、局限性和未来方向补充，不作为主实验完成条件。

## 9. 编制依据

- 当前任务内容沿用并整合 [60 题草案](TASK_BANK_60_DRAFT.md)，保留同一任务 ID。
- 原四策略含义核对 [旧外观研究协议第 3 节](../../AppearanceExperiment/Study/materials/protocol.md) 与 [Backend/core.py](../../../Backend/core.py)。仅沿用策略定义，不沿用旧固定输入、初始一次 gate、修复次数及超时限制。
- 最新决定：四属性 32 题、四次属性偏好和一次比较总体偏好；自然情境仅 S。2026-11-16 确认采用四属性 5 题和自然模拟 26 题，逐题来源与评分见第 6、11.4、12 节。旧三策略轮、六评分和五次方向偏好材料仅供历史追溯。


## 10. 可选访谈：五道候选问题，每人随机两道

用户已决定从五题中为每位参与者随机选择两题。**本节为此前候选池，尚需围绕本次 Selective 连续体验改写，尤其 I4 不再适合作为假设问题；此步保留记录，不将旧题直接作为最终主持稿。** 以下题干为建议，访谈在 VR 实验后进行、整体可选；参与者可以不回答或表示记不清，不为得到预期内容而反复换题。

| ID | 英文建议问题 | 中文含义 | 主要用途 |
| --- | --- | --- | --- |
| I1 | Can you describe one interaction that stood out to you, positively or negatively? What made it stand out? | 请描述一次让你印象深刻的交互，可以是好的或不好的经历。它为什么让你印象深刻？ | 获取具体案例，解释量化评分背后的体验。 |
| I2 | In what situations would you prefer the tutor to ask first, and in what situations would you prefer it to act directly? | 什么情况下你希望 tutor 先询问，什么情况下希望它直接修改？ | 了解询问与执行的适用边界；允许始终偏好某一种，不要求必须各举一例。 |
| I3 | How, if at all, did what you were adjusting affect which approach you preferred? | 调整的内容是否影响你偏好的策略？如果有，是怎样影响的？ | 补充语速、回答结构、语气、声音和外观之间的偏好差异；不预设一定不同。 |
| I4 | How do you think your experience would change if you used just one approach in a normal conversation with the tutor, instead of comparing four approaches side by side? | 如果正常对话中只使用一种策略，而不是同时比较四种，你觉得体验可能有什么不同？ | 探讨并行比较与实际使用的差别，为局限性与未来验证提供线索；回答是推测，不是已观察到的单策略效果。 |
| I5 | What is the most important change you would suggest for a future version of this system or study, and why? | 对未来版本的系统或实验，你最希望优先改变什么？为什么？ | 识别未来改进方向，允许涉及功能、交互或研究流程。 |

实施建议：

- 在查看该参与者评分/偏好前，从 I1–I5 无放回随机抽两题，按抽出顺序询问；不根据是否喜欢 S 临时选择或换题。此处只规定抽取方法，没有在人数未知时生成分配表。
- 保存抽中题号、实际提问题号、回答/跳过情况及必要的中性追问，避免未被问到误记成没有该意见。五选二共十种组合，但不在当前方案中强迫每组合固定人数；实际覆盖如实报告。
- 两题是两个主要话题，可用简短澄清如 “Could you give an example?”，不借追问再把其余三题全部问一遍。先自由回答，不先提供有利于某策略的例子。
- I1 可以引用此前参与者自己的备注帮助回忆，不能只展示支持 S 的案例；I3 若需要解释范围，可统一列出五个方向，不提示哪个方向应该喜欢哪种策略。
- I4 的内容用于提出局限性和未来研究问题，不能当作本实验已证明独立使用效果的证据。I5 不自动等同具体功能确实提升表现。
- 沿用口述/STT 文本记录，不保存访谈原始音频；未确认或不清楚的转写需标记，不当作精确逐字引语。访谈不传入 tutor 对话上下文。
- 访谈是定性补充，不把自选/随机抽到两题的回答频次直接当所有参与者的总体比例，也不因未参加访谈判主实验未完成。


## 11. Selective 自然情境模拟（2026-11-11）

### 11.1 研究目的与交互范围

只启用 S，一段连续自由交流，评估其在完整使用中的体验、问题及改进方向。参与者从一开始即可调整语速、音色、语气、回答内容构成及外观，随时修订选择；不设“先属性、后外观”阶段，不规定具体数值、外观目标或固定口述。

四属性比较与此前外观研究分别提供比较证据，本模块不声称 Selective 优于其他策略。旧外观研究的参与者、版本和条件不同，保持独立报告。本模块属于熟悉操作后的连续使用评估，不称初次接触研究。

### 11.2 英文引导工作稿

> Imagine you are getting to know a tutor that you would be comfortable continuing to use. Start a conversation about a topic or question of your choice. As you talk, explore how the tutor communicates and how it looks, and make any adjustments that suit you. You may change its speaking rate, voice, tone, level of detail, or appearance at any time. Keep talking with the tutor and revise your choices whenever you wish. Use your own words; there is no single correct final setup.

不强制逐一改变所有属性，不强制制造含糊表达或错误。记录实际尝试的属性、外观与修复；未涉及某能力既不是失败，也不是成功证据。明确提供系统支持范围，不暗示 Selective 是更优策略。

### 11.3 连续会话及结束规则

在四属性总体偏好提交后，提供休息并进入一个独立的 S 会话。清空此前比较的 tutor 对话、偏好及修改状态，加载可追溯的共同起点；保留已采集的研究记录。重置不能消除参与者学习效应，记录实际模块顺序及既往参与情况。

本段只按 S 的真实决策询问或执行，不创建 E/A/N 分支，也不等待四分支统一展示。段内持续保留历史和设置，支持后续修改/修复。四属性部分的统一展示屏障不因此取消。

交流过程中不逐次弹问卷。进入反馈时固定本段所评价的最终状态与过程范围；尚未完成的请求必须明确解决或停止并记录，不能悄悄把迟到结果混入已评价状态。暂停/退出随时可用；不以达到满意为结束条件，也不自动把结束等同成功。

自然情境时长、统一结束触发规则和具体共同起点仍待在自然情境接入前确定，作为配置项保留；本步不任意指定分钟数或固定对话次数。

### 11.4 自然情境问卷（2026-11-16 已确认：26 题扩展版）

只评价刚完成的 Selective 连续交流。段内不逐次弹问卷，段末一次填写，分屏呈现三个模块；在可选访谈之前完成。不要评价前面 E/A/N/S 并行比较，也不另问自然模块策略偏好。

英文引导：

> Please answer about the natural conversation you have just completed. Consider your overall experience with this tutor during that conversation, including any adjustments you chose to make.

#### B1：目标符合程度与交互诊断，8 题

| ID | 角度 | 英文施测候选题干 | 来源及设计理由 | 作答及方向 |
| --- | --- | --- | --- | --- |
| N0 | 个人目标符合程度 | To what extent did the tutor’s final setup match what you wanted by the end of the conversation? | 项目自编；自然情境没有统一正确终态，结束不等于达标 | Fully / Partly / Not at all / Unable to judge；分类，不平均 |
| N1 | 意图理解 | The tutor’s responses reflected the meaning of what I was trying to communicate. | 受 [SASSI] System Response Accuracy 启发；关注感知的意思理解，不是客观 STT 准确率；本题为概念改写，不是原题照用 | 七点同意度；高分更积极 |
| N2 | 表达方式清楚程度 | I knew how to phrase my requests so that the tutor could respond to them. | [SASSI] Habitability 相关内容改编；识别参与者是否不断猜测应该怎么说 | 七点同意度；高分更积极 |
| N3 | 修改控制感 | I felt in control of the changes made to the tutor throughout the conversation. | [SASSI] 控制感内容改编；评价整段交流而非一个修改回合 | 七点同意度；高分更积极 |
| N4 | 澄清决策合适程度 | The tutor’s decisions about whether to ask for clarification suited my needs during the conversation. | 项目专用；包括决定不询问的情况，不预设询问越少越好 | 七点同意度；高分更合适 |
| N5 | 不必要的打断 | The tutor’s clarification questions disrupted the flow of the conversation more than I wanted. | 项目专用，非 SASSI 原题；将打断对象限定为澄清问题，区分可接受澄清与非期望打断 | 七点同意度；高分更多非期望打断；另设 No clarification questions occurred |
| N6 | 心理需求 | How much thinking and concentration did interacting with the tutor require during this conversation? | 参考 [NASA-TLX] Mental Demand 改写；以整段交互所需思考/注意力替代旧省力题；不是完整工作负荷工具 | 1 Very low—7 Very high；高分需求更高 |
| N7 | 总体满意度 | Overall, I am satisfied with my experience of personalizing the tutor during this conversation. | 项目自编；保留定制体验满意度，不能把 SUS 的整体可用性等同满意度 | 七点同意度；高分更满意 |

N1–N5/N7 使用第 6.2 节完整七点同意度；N6 使用低—高端点，不能使用同意度。七项评分均可独立选择 Unable to judge；N5 未发生澄清时选 No clarification questions occurred，与发生但不打断、无法判断和未回答分开保存，不转成最低分。

这些是单项诊断结果：不报告“SASSI 子量表分数”“NASA-TLX 总分”或“Raw TLX”。N6 与 A1 不是同一构念，也不因均为七点而混算。N5/N6 的高分方向与其他题不同，但不为拼接总分自动反向加总。识别、模型质量、延迟和 UI 可能共同影响体验，问卷不能单独归因到策略。

#### B2：完整 SUS，10 题

原版英文题干按 [SUS] 原文问卷页使用；保持全部十题、原顺序、正反向措辞和五点同意度。明确 system 指刚才自然模拟中使用的整个 VR tutor 系统。下表为教授审核用的**逐题题意摘要，不是施测译文或改写后的英文问卷**；本次认可的是完整原版 SUS，不是这些摘要组成的新量表。

| 本文 ID／原题号 | 题意摘要 | 来源 | 纳入理由 | 作答与计分贡献 |
| --- | --- | --- | --- | --- |
| S1／1 | 愿意经常使用 | [SUS] 原题 1 | 覆盖继续使用倾向 | 1–5；原分−1 |
| S2／2 | 不必要的复杂性 | [SUS] 原题 2 | 覆盖系统复杂负担 | 1–5；5−原分 |
| S3／3 | 使用是否容易 | [SUS] 原题 3 | 覆盖整体易用性 | 1–5；原分−1 |
| S4／4 | 是否依赖技术人员帮助 | [SUS] 原题 4 | 覆盖独立操作能力 | 1–5；5−原分 |
| S5／5 | 各功能是否协调 | [SUS] 原题 5 | 涵盖语音、调整与界面的整体配合 | 1–5；原分−1 |
| S6／6 | 系统是否缺乏一致性 | [SUS] 原题 6 | 覆盖整体行为一致性 | 1–5；5−原分 |
| S7／7 | 其他用户能否较快学会 | [SUS] 原题 7 | 覆盖感知易学性 | 1–5；原分−1 |
| S8／8 | 使用过程是否繁琐 | [SUS] 原题 8 | 覆盖操作繁琐程度 | 1–5；5−原分 |
| S9／9 | 使用时是否有信心 | [SUS] 原题 9 | 覆盖使用信心 | 1–5；原分−1 |
| S10／10 | 开始前是否需要大量学习 | [SUS] 原题 10 | 覆盖入门学习负担 | 1–5；5−原分 |

量尺端点为 1 Strongly disagree—5 Strongly agree；保留原版五个位置。计分为十项贡献之和乘 2.5，范围 0–100，非百分比或任务成功率。上述理由用于说明完整量表覆盖，不把各原题拆成十个经过验证的独立子量表。

SUS 在全部前置属性任务之后采集，代表已熟悉操作后的系统体验，不能解释为首次使用体验。其分数同时受语音识别、模型、界面和策略影响，不证明 S 优于 E/A/N。

**缺失规则（2026-11-16 固定）：** 不将第 6 节的 Unable to judge 加入 SUS 五点量尺。允许参与者显式跳答，保存 skipped 而非中点；原文关于不能回答时选择中点的指引不能授权程序自动填值。十题数值完整才计算 SUS；任一缺失则总分为 null 并标记 insufficient_items，不插补。显式跳答后的问卷可以正式提交但标为 partial，未触碰空白不自动当跳答。此为本项目保守处理规则，见[数据契约 §4–5](STUDY_DATA_PERSISTENCE_CONTRACT.md)，不宣称是原工具缺失插补方法。

#### B3：完整 UEQ-S，8 题（本次已选择保留）

采用 [UEQ-S] 手册的原版英文词对、顺序和七个作答位置，左负右正；不是同意度量尺。评价对象同 B2，是刚完成自然交流时的整个系统体验。以下为实际词对及每题用途；用途不表示该题自身是独立有效子量表。

| ID／原位置 | 左端 | 右端 | 归属及来源 | 设计理由 |
| --- | --- | --- | --- | --- |
| U1／1 | obstructive | supportive | 实用质量；[UEQ-S] 第 1 组 | 是否妨碍或支持活动 |
| U2／2 | complicated | easy | 实用质量；[UEQ-S] 第 2 组 | 使用的复杂/容易程度 |
| U3／3 | inefficient | efficient | 实用质量；[UEQ-S] 第 3 组 | 感知效率 |
| U4／4 | confusing | clear | 实用质量；[UEQ-S] 第 4 组 | 理解系统的清晰程度 |
| U5／5 | boring | exciting | 享乐质量；[UEQ-S] 第 5 组 | 体验是否有吸引力 |
| U6／6 | not interesting | interesting | 享乐质量；[UEQ-S] 第 6 组 | 体验是否引起兴趣 |
| U7／7 | conventional | inventive | 享乐质量；[UEQ-S] 第 7 组 | 感知创新性 |
| U8／8 | usual | leading edge | 享乐质量；[UEQ-S] 第 8 组 | 感知前沿性 |

原始位置 1–7 映射为 −3、−2、−1、0、+1、+2、+3。分别计算 U1–U4 的实用质量均值、U5–U8 的享乐质量均值；本项目不再求八题或跨工具总体分。缺失单独记录，不自动当作 0。按数据契约，仅在对应维度四项均有数值时计算该维均值；否则该维为 null／insufficient_items。允许显式跳答并提交 partial 问卷，不自动插补；两维及整体完整性分别保留。

UEQ-S 只提供两个较宽的体验维度，不报告完整 UEQ 的六个细分维度。采用短版是考虑前置 32 题及整体负担；其享乐质量可能受 VR 场景、外观和声音影响，不可归因为 Selective 单独造成。

#### B4：题量、可选备注与提交边界

已确认版本为 **B1 八题＋B2 十题＋B3 八题＝26 题**，仅在自然模拟结束填写一次；18 题基础版是此前备选，不是当前采用版本。若预测试后需要缩减，应另行讨论整块是否移除 UEQ-S，在正式采集前冻结；不自动删题，也不擅自删减 SUS/UEQ-S 后继续使用原名称。

保留可选口述：`Was there a moment when the tutor’s handling of a change helped or disrupted the conversation? Please describe it if you wish.` 只保存确认后的 STT 文本，不保存音频、不进入 tutor 上下文，不自动改评分。

无预填分数；数字、无法判断、未发生澄清、跳答和技术缺失分开。常规提交按[数据契约](STUDY_DATA_PERSISTENCE_CONTRACT.md)：N0–N7 均有有效正常作答，S1–S10／U1–U8 均为数值作答或明确跳答；有跳答则提交为 partial，量表分数另判有效性。不能沿用旧六题门槛，也不能把 SUS/UEQ-S 套进统一七点题模板。暂停、退出始终允许，不以问卷完整或达到满意为条件。

## 12. 工具来源、混合问卷边界与后续审核

| 工具／文献 | 原工具范围 | 本项目采用方式 |
| --- | --- | --- |
| SEQ：Sauro 与 Dumas（2009）的任务后单题评价研究；题干演变参考 Sauro 与 Lewis（2024） | 七点任务难易度 | A1 改编；注明 adapted from SEQ，不直接引用原常模 |
| SUS：Brooke（1996），SUS: A quick and dirty usability scale | 十题、五点、整体可用性 | 自然模拟原版完整块 S1–S10；独立计分 |
| NASA-TLX：NASA 官方 Paper and Pencil Package | 心理、身体、时间需求、表现、努力、挫折六维及加权程序 | 仅 N6 参考 Mental Demand 改写；不使用完整 TLX，不报告 Raw TLX |
| SASSI：Hone 与 Graham（2000），Towards a tool for the Subjective Assessment of Speech System Interfaces | 原研究筛选后 34 项、六因子；适用范围仍需考虑 | A2/N2/N3 内容改编，N1 为维度启发；不移植原信效度或计算 SASSI 分数 |
| UEQ-S：Schrepp、Hinderks 与 Thomaschewski（2017），Design and Evaluation of a Short Version of the User Experience Questionnaire；操作参照 Schrepp 手册 v11 | 八组词对、两个宽泛体验维度 | 自然模拟完整块 U1–U8；分别计算两维均值 |

SASSI 的 Speed 指系统响应速度，不是本项目可调 speech rate；NASA-TLX 的 Temporal Demand 指时间压力，不是说话速度。使用语音使 SASSI 相关，但不证明它在本 VR/LLM 场景自动有效。问卷中的请求理解也不能直接作为客观语音识别准确率。

研究报告应称“由标准工具完整模块、改编条目和项目专用条目组成的问卷”，不能称整份问卷已验证、全部题目取自标准量表或新标准短版。来源明确不等于本项目已获信效度证据。SUS、UEQ-S、各诊断题、分类及偏好分别报告；不合成系统质量总分。

预测试重点：能否分清 A0 的需求满足程度、A1 的难易与 A2–A4 的同意程度；能否区分 A0 的结果判断与 A4 的总体满意度；能否理解控制感/澄清的含义；N2 是否被理解为交流表达而非学科能力；N5 的未发生选项；N6 的心理需求；SUS 五点及反向措辞；UEQ-S 词对；26 题结束问卷的负担。先记录理解问题和时间，再决定措辞/模块变化；预测试数据与正式数据分开。不得把程序测试通过当作心理测量验证，也不按正式结果挑选有利条目。

**2026-11-16 编制阶段历史说明：** 当时仅记录已确认方案，尚未修改程序；其后接入状态以文首及第 6.5 节为准。逐题量尺和缺失类型需明确，完整 SUS 原文与 UEQ-S 词对保留，旧题意/量尺的答案不自动转换为新版。采集缺失状态与标准分完整性规则已在数据契约固定；主要分析结果、各分析的缺失分母／样本纳入规则、重复测量处理及是否进行多重比较校正仍需在正式采集前确定。

[SEQ]: https://measuringu.com/evolution-of-seq/ "Sauro & Lewis: The Evolution of the Single Ease Question"
[SUS]: https://hci-studies.org/methods-and-measures/downloads/SUS_Brooke1996.pdf "John Brooke (1996): SUS — A quick and dirty usability scale"
[NASA-TLX]: https://www.nasa.gov/wp-content/uploads/2026/03/nasa-tlx-v1-0-searchable-text-and-forms.pdf "NASA-TLX official paper and pencil package"
[SASSI]: https://bura.brunel.ac.uk/bitstream/2438/3077/1/SASSI%20Paper%202000.pdf "Hone & Graham (2000): SASSI original study"
[UEQ-S]: https://www.ueq-online.org/Material/Handbook.pdf "UEQ Handbook, version 11; UEQ-S English items and guidance"
