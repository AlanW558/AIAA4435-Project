# 外观并行比较：情境、八题与问卷审核

日期：2026-11-28。关联[主设计v2.0](FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)。

**已确认：** 外观替代自然情境成为第五实验模块；四类情境×两题；E/A/N/S共享一次文本请求、分别澄清、统一开放结果；Unity只显示一个tutor，切换保存状态并采集真实图像；HTML比较；整个模块结束后20项评分及一次多选偏好。

**2026-11-28确认：八题的目标与保持要求已获用户认可；全部采用当前场景已有的男性人物模型。P3-1的“更休闲”不限定运动服，是否符合目标风格由参与者判断。** 用户已在[八题Request填写表](APPEARANCE_TASK_REQUESTS.md)自行提供全部请求，原请求已通过本地独立外观辅助流程完成API调用及经用户授权的助手代拟澄清；后续P4-1按用户批准修订，见下文。现已根据用户要求采集Unity真实截图并生成比较页面，采用下文每策略五题，共20评分及一次多选偏好。现已收集四位参与者对同一套冻结材料的最终回顾反馈，见[外观原始结果、汇总与使用说明](../../../Experiments/appearance/README.md)。自然情境只用于后续demo，不再收26题实验问卷；历史回答保持原样。

### 执行与版本边界

每题单独新建comparison与四个策略会话；同一批次编号仅用于归档，不建立前后题状态承接。四策略共享该题的只读初始解释，但执行状态、澄清和答案独立；P4仅重建各自给定的示例历史。所有澄清完成前不导出参与者结果。首次调用得到10个待回复问题（A=8、N=1、S=1、E=0）。随后按用户明确授权，由助手根据原请求和任务要求代拟并提交答案；P4-1/A追加一次澄清，因此最终共11次回复（A=9、N=1、S=1、E=0），无待回复问题。八题请求未改写或重放，未提问的22个分支状态保持不变。来源明确记为assistant_authored_user_authorized；P2的0.95/1.05是依据“小幅”作出的代拟选择，P3-1试用运动装不等于用户已判定风格符合。以上为初版执行记录。当前发布材料替换了P4-1，现有四份反馈评价替换后的同一结果版本；辅助运行不等于正式Unity实验流程已验收。

### 图像与页面实现记录

当前P4-1已按用户确认的“that earlier color”重跑并替换，其他七题结果保留。[修复与验证记录](APPEARANCE_HISTORY_REFERENCE_FIX.md)区分了明确的previous与多义的earlier，及历史最早状态与准备结束起点。当前比较材料有12次澄清（A8/N2/S2/E0）；上文11次为初版实际运行记录，不予覆盖。

实际采集47张1200×1000 PNG：8张共同起点、32张策略结果和7张P4历史。使用Unity 2022.3.62f3c1、真实Metal GPU、同一Liang资源与AppearanceAvatar，在临时预览场景固定正面镜头、姿态、光照及地面尺度参照；不是头显截图。每次切换应用完整状态，五个外观字段经Unity实际观察值核对。PNG与输入结果、资源及渲染组件摘要绑定，未修改模型决策。

HTML提供单策略大图、并排比较、起点/历史图、当前12条实际澄清与授权代拟来源，问卷采用独立appearance-summary-feedback-v1格式和appearance-module-A0-A4-v1版本。支持浏览器草稿、下载/恢复、New response及最终JSON下载；不会把空白、草稿或模拟检查评分当成参与者最终数据。

## 1. 适配外观的四类情境

| 情境 | 外观中的决策问题 | 两题覆盖 | 调整理由 |
| --- | --- | --- | --- |
| C1 明确局部与组合修改 | 已清楚指定字段/值，能否按要求修改并保持其他设置 | 单改颜色；同时换服装和配饰并明确覆盖旧软偏好 | 外观容易出现附带修改，也需要“虽然有旧偏好但已明确覆盖”的反例 |
| C2 程度未量化的整体大小调整 | 方向清楚，幅度尚不精确，是否需要追问 | 小一点的角色略放大；大一点的角色略缩小 | 用真实连续程度字段承载“小幅”，不把离散颜色或衣服硬解释成连续强度 |
| C3 整体印象可能对应不同字段 | 同一句风格描述可通过衣服、颜色、配饰或大小实现 | 更休闲；更显眼 | 关注不同解释和用户指定意图，不是测角色审美或模型美术质量 |
| C4 历史引用与局部恢复 | 能否找到正确历史对象，且不回滚其他最新变化 | 多个旧颜色中的指代；唯一上一次大小修改的撤回 | 同时包含需消歧和可直接确定的情况，避免所有历史题都预设应询问 |

C1/C4覆盖偏好与历史，C2/C3的歧义来源不同；它们是覆盖性任务分类，不是已证明独立或互斥的实验因子。每类只有两题，模块末问卷不能推断每类情境各自的满意度。

## 2. 能力与共同起点

核对当前[能力表](../../../Backend/capabilities.py)、[Tutor能力](../../../Backend/tutor_capabilities.py)和[外观测试](../../../Backend/tests/test_tutor_appearance.py)：

- 采用当前场景已有的同一男性人物模型Liang，不加入角色身份切换。统一的是人物模型，不是把八题的颜色、服装、配饰和大小也设为相同。
- 当前服装能力支持suit/sport/none；[美术资源说明](../../../Art/AppearanceAvatars/README.md)中的none为裸上身加训练短裤，并非另一套日常休闲装，尚无独立casual资源。任务起点均用suit，P1-2明确要求sport。P3-1不预设唯一服装枚举作为正确答案：从西装变为参与者认可的休闲装即可，但仍须满足保持要求。现有能力枚举不等于已经有任意休闲服资源；正式运行前需核对实际可展示的服装，不把所有“休闲”静默解释为sport，也不把未支持的服装称为已实现。
- 配饰为none/hat/glasses，互斥；换为glasses会替换hat，不是叠加两种配饰。
- 整体比例0.85–1.15，步长0.05。表示等比例缩放，不是独立身高。
- 当前有七种离散衣服颜色；本草案使用已有蓝、橙、绿、灰、红、紫范围，不要求连续亮度或饱和度。
- 四项对话属性在每题共同起点一致，外观请求不应修改它们。具体声音等采用届时冻结的共同配置，不复制旧历史文档的音色占位。

以下初态、历史和明确的旧软偏好属于四策略共同可见的上下文。Task goal与Keep unchanged是参与者任务卡，不自动发送给模型；参与者愿意在实际请求中表达的信息才进入对话。例句只是表达示例，不是要求照读或省略细节。

当前显示P1-1至P4-2，内部ID为AP-C1-01至AP-C4-02；五模块Unity接入时继续核对唯一性。不复用旧研究A_T1等ID或旧十二题AP1-1等ID，以免混入旧结果。

## 3. 已确认的八题目标与保持要求

### P1-1／AP-C1-01：明确改单一颜色

- **共同初态：** Liang，蓝色西装，帽子，整体大小1.00；无附加历史。
- **Task goal:** Change the jacket colour to orange.
- **Keep unchanged:** The outfit, hat, overall size, tutor identity and conversation settings.
- **Request example:** “Could you make the jacket orange and leave the rest as it is?”
- **观察角度：** 明确请求是否正确执行，是否误改其他字段，额外确认是否有必要。

### P1-2／AP-C1-02：明确组合修改与覆盖旧偏好

- **共同初态：** Liang，绿色西装，帽子，整体大小0.95。
- **共同公开软偏好：** “I normally prefer to keep the hat.” 参与者与四分支都能看到，明确标为本题示例偏好。
- **Task goal:** For this task, switch to the sport outfit and replace the hat with glasses, overriding the usual hat preference.
- **Keep unchanged:** The green colour, overall size, tutor identity and conversation settings.
- **Request example:** “I usually keep the hat, but today I'd like the sport outfit and glasses. Keep the colour and size.”
- **观察角度：** 两字段一起执行且保持其他内容；不应仅因为存在旧软偏好，就把参与者已明确表达的覆盖误判为冲突。

### P2-1／AP-C2-01：略放大

- **共同初态：** Liang，红色西装，帽子，整体大小0.90。
- **Task goal:** Make the tutor a little larger. A small change is enough.
- **Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.
- **Request example:** “Could you make yourself a little bigger? Keep the same outfit and accessories.”
- **观察角度：** 不要求参与者先给精确倍数；比较直接小步执行与量化追问的适切性。

### P2-2／AP-C2-02：略缩小

- **共同初态：** Liang，灰色西装，眼镜，整体大小1.10。
- **Task goal:** Make the tutor a little smaller. A small change is enough.
- **Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.
- **Request example:** “You look a little too big. Could you make yourself slightly smaller and keep everything else?”
- **观察角度：** 与上一题方向相反，但不让不同策略面对不同目标；保留小幅调整机制，不为了图片差异显著而强制大幅变化。

P2两题的可接受幅度由参与者评估，不预设0.05就是所有人的正确答案，也不另造自动成功阈值。预测试重点是同镜头、地面参照下能否看清实际差异；看不清时先改善呈现，不静默改变任务含义。

### P3-1／AP-C3-01：更休闲的外观

- **共同初态：** Liang，蓝色西装，眼镜，整体大小1.00。
- **Task goal:** Give the tutor a more casual look than the starting suit. Choose the casual style you want; it does not have to be sportswear.
- **Keep unchanged:** The blue colour, glasses, overall size, tutor identity and conversation settings.
- **Request example:** “I'd like you to look a bit more casual.”
- **观察角度：** 整体描述是否被合理理解，澄清是否有助于明确参与者想要的风格。由参与者判断结果是否足够休闲并符合自己的要求；不以是否换成sport作为自动成功标准。仍须检查蓝色、眼镜、大小、身份和对话设置是否保持。

### P3-2／AP-C3-02：更显眼的外观

- **共同初态：** Liang，灰色西装，无配饰，整体大小0.95。
- **Task goal:** Make the tutor more noticeable. For this task, you prefer an orange jacket rather than a larger body.
- **Keep unchanged:** The suit, absence of accessories, overall size, tutor identity and conversation settings.
- **Request example:** “Could you make your appearance stand out a bit more?”
- **观察角度：** 换色、增加配饰、放大等不同理解是否需要区分，以及实际结果是否达到参与者的指定意图。

P3-1的具体休闲风格由参与者决定，不存在隐藏的“必须是运动服”答案；P3-2仍按已确认任务给出偏好橙色而非放大的私人目标，这不意味着所有“显眼”请求都应改为橙色。参与者可在首次请求中把目标和保持要求说全；不能强迫其使用例句、隐藏意图或重说得含糊。若实际输入已明确，仍保留该试次并记录其明确程度。

### P4-1／AP-C4-01：多个历史颜色中的指代

- **共同公开历史：** 同一Liang西装依次为蓝色／无配饰→紫色／无配饰→绿色／无配饰→绿色／帽子；全过程大小1.00。参与者看到同镜头历史图及标签；四策略收到一致历史，不冒称这是上一道题的真实操作。
- **当前状态：** 绿色西装，帽子，整体大小1.00。
- **Task goal:** Return to the first blue jacket colour shown in the history.
- **Keep unchanged:** The newly added hat, outfit, overall size, tutor identity and conversation settings.
- **Request example:** “Can you go back to that earlier colour, but keep the hat?”
- **观察角度：** 先前有多个颜色时如何处理指代；恢复颜色时是否错误移除最新帽子。

### P4-2／AP-C4-02：唯一的大小修改与局部恢复

- **共同公开历史：** 橙色西装、无配饰、大小1.00 → 放大至1.10 → 加帽子。提供对应真实历史图与一致公共历史。
- **当前状态：** 橙色西装，帽子，整体大小1.10。
- **Task goal:** Undo the most recent size change, returning to 1.00.
- **Keep unchanged:** The subsequently added hat, orange colour, outfit, tutor identity and conversation settings.
- **Request example:** “Undo the last size change, but keep the hat and everything else.”
- **观察角度：** 明确的last size change只能指向一次大小修改；不能误撤销最近加帽子，不能仅因出现历史引用就预设必须询问。

历史题必须从各自指定的共同起点开始，不能承接四策略已分叉的上一题。首次澄清完成后的结果冻结后再生成Unity截图；若记录修复结果，另存阶段和版本。

## 4. 外观五题问卷与来源

当前四人实际填写的是冻结输出回顾版；页面说明为：

> Give one set of five ratings for each approach. Consider the recorded requests, clarification exchanges and actual appearance results. You can return to any task while answering.

页面同时说明请求由用户提供或确认、澄清经用户授权由助手代拟，不能把四人评分说成四次独立请求/澄清。当前问卷和保存规范见[当前问卷与数据范围](CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)。

以下为将来参与者亲自提供请求和澄清时适用的引导，未套用于本批回顾数据：

> Please evaluate each approach across all eight appearance tasks. Consider the requests and clarifications you provided and the actual appearance results. Use the review pages to revisit any task before answering.

此引导用于参与者本人提供请求和澄清的流程。若只是观看他人或助手完成的现成结果，须另标为回顾性输出评价，不能套称亲自完成交互；既有辅助结果保持其原始来源。

| ID | 当前英文题干 | 量尺 | 来源、改编与设计理由 |
| --- | --- | --- | --- |
| A0 | Overall, to what extent did this approach’s outcomes meet your requirements across the appearance tasks? | 1 Not at all—7 Completely | 项目自编；结果是否符合目标及保持要求，不从“好看”推断是否正确 |
| A1 | Overall, how difficult or easy was it to adjust the tutor’s appearance using this approach? | 1 Very difficult—7 Very easy | 参考[SEQ作者说明][SEQ]的感知任务难易度；改为八题模块回顾，不使用原常模或称完整SEQ施测 |
| A2 | Across the appearance tasks, I felt in control of the changes made to the tutor with this approach. | 1 Strongly disagree—7 Strongly agree | 参考[SASSI原研究][SASSI]Table 4的交互控制内容，限定为外观修改；原控制条目属于Likeability因子，不是独立Control子量表 |
| A3 | This approach’s decisions about whether to ask for clarification suited my needs across the appearance tasks. | 同意度1–7 | 项目专用；评价询问与不询问的决定，不能以打断少或问题数少替代 |
| A4 | Overall, I am satisfied with my experience of adjusting the tutor’s appearance using this approach. | 同意度1–7 | 项目自编总体满意度；区别于A0要求达标，也不称SUS或SASSI总分 |

A0帮助语：

> Consider both the changes you wanted and the features you wanted to keep unchanged.

五项分别分析，不自动合成总分。评分独立保留Unable to judge；它与未作答、技术缺失、中点4不同。每个策略五题，四策略共20项，模块结束一次多选偏好，与主设计一致。题号与文本已固定为 `appearance-module-A0-A4-v1`；任何后续修订另发版本，不修改已经填写的外观或四属性问卷记录。

## 5. 是否增加评分：建议暂不增加

| 可能增加的角度 | 本次判断 | 理由与文献边界 |
| --- | --- | --- |
| 保持无关外观不变 | 不另加必答题 | A0已明确同时考虑目标与保持要求；A2补充过程控制。可选备注可说明具体误改 |
| 系统是否理解意图 | 暂不增加 | SASSI的System Response Accuracy提供相关依据，但在本流程主要依靠同一结果推断，容易与A0重复；不能把自述理解当成客观识别准确率 |
| 打断、对话顺畅 | 不加入 | 当前为并行澄清与统一展示，不能代表连续单策略对话。自然情境已退出实验 |
| 外观漂亮、吸引力、角色偏好 | 不加入核心评分 | 目标是按请求个性化，而不是评选最好看的模型；主观美感会把资源与颜色偏好混入策略评价 |
| 完整UEQ-S | 不加入 | [官方手册][UEQ]说明短版是宽泛的pragmatic/hedonic评价，不提供完整UEQ各细分维度；它不会自动补出一个外观修改正确性指标 |
| 原自然模块的SUS或心理需求题 | 不转移 | 原本评价整段真实系统使用；此次没有要补测的对应研究目标，增加题数不能替代适配性 |

以上“不增加”是本项目对研究目标和题量的选择，不是声称这些工具普遍不适用。若预测试确认某个关键问题确实被五题遗漏，再单独审查原条目、施测对象和量尺，决定是否增加，不把任意自拟题加上工具名字就视为标准题。

一个有条件的未来候选是错误恢复：若正式加入参与者实际修复/撤销任务，可参考SASSI错误恢复内容，改编为“When an appearance change did not meet my needs, it was easy to correct it using this approach.”，并另设No correction was attempted / Not applicable。它会增加到每策略六题、模块24项评分，且需新版本；**当前没有共同修复环节，因此本次不加入。** 它不是对未经历能力的假设评分，也不能把单题称为SASSI总分。

保留可选备注即可：

> If you wish, describe a task where an appearance result or clarification did not match what you wanted.

这是项目自编解释性备注，不是新增标准量表分数，不作为继续或提交的必答项。可保留任务ID帮助回查；不根据备注自动补分。

## 6. 预测试需解决的具体问题

- 模型/服装/配饰是否正确加载，绿色在换运动服后是否真实保持；状态JSON正确不等于图像正确。P3-1需核对现有服装能否提供有意义的休闲变化；没有对应资源时记录能力限制，不静默把参与者要求改成运动服。
- P2小幅差异在固定相机与参照物下是否可辨；必要时各策略统一增加同一近景，不改变相机比例来伪造大小差异。
- 参与者能否理解P3私人目标和P4历史，而不认为必须照读例句或刻意省略信息。
- A0是否考虑保持要求，A1是否评价自己的调整过程，A4是否被误读成“角色好不好看”。
- 所有结果是否在实际澄清完成后才公开；切换是否只读取正确版本的完整状态。
- 五模块问卷保存、部分完成、总体偏好与旧数据隔离，需后续真实接入测试；当前文档不能作为已完成验收的证据。

[SEQ]: https://measuringu.com/evolution-of-seq/ "Sauro & Lewis (2024), The Evolution of the Single Ease Question"
[SASSI]: https://bura.brunel.ac.uk/bitstream/2438/3077/1/SASSI%20Paper%202000.pdf "Hone & Graham (2000), Towards a tool for the Subjective Assessment of Speech System Interfaces"
[UEQ]: https://www.ueq-online.org/Material/Handbook.pdf "Schrepp, User Experience Questionnaire Handbook, version 11, short version guidance"
