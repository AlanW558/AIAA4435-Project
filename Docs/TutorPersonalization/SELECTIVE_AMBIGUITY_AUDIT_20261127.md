# Selective 歧义与澄清链路核查

日期：2026-11-27。核查对象为 `StudyData/text-check-v3` 的 32 题实际回复，以及用户下载的 `completed-attribute-feedback.json`。原批次、评分、请求、澄清与音频保持原样；修复后的行为必须使用新的验证记录。

## 1. 反馈与证据边界

用户提交的是四份**属性级**问卷，没有逐任务评分或文字备注。四份反馈已经按 `attribute-summary-feedback-v2` 校验并导入批次的 `attribute-feedback/`，原下载文件保留。因此下述案例是任务材料与执行日志的对照发现，不能写成“用户明确给这些单题低分”。

| 属性 | Selective A0：需求满足程度 | Selective A3：澄清合适程度 | 属性偏好 |
| --- | ---: | ---: | --- |
| Speech rate | 6 | 6 | Selective |
| Reply length | 6 | 5 | Unable to judge |
| Tone | 6 | 5 | Selective |
| Voice | 7 | 7 | Selective |

这些是本次个人辅助检查的回答，不用于推断总体显著性或宣称策略优越。配置符合目标也不等于声音质量、感知效果或主观任务成功。

## 2. 三个具体案例

### R3-2：改善要求被压缩为保持原状

实际请求：`I want your explanation to be much easier to follow, but keep all the details.`

任务目标是保持 Detailed 内容、将 1.20× 语速降到 0.75–0.80×。共享解析器只提出 `reply_length=detailed`，由于当前已经是 Detailed，规范化后唯一候选为 `{}`。Selective 得到 `ACT / NO_TRIGGER`，没有澄清，最终语速仍为 1.20×。

这里不能要求模型猜出未说出的目标数值。可修复的问题是：“easier to follow”可能指语速或讲解组织方式，而解析器把“keep all the details”当成唯一修改目标，丢失了尚未解决的改善意图。当前 gate 仅看到单一无变化候选，无法识别遗漏。

### L3-2：理解支持误判为情绪鼓励

实际请求：`I want the way you explain things to give me more support with understanding, not just make me feel better.`

任务目标是补充解释和例子，并保持原语气。解析器仅提出 `tone=encouraging`；Selective `ACT / NO_TRIGGER`，最终 Reply length 仍为 Brief，Tone 从 Professional 变为 Encouraging。

这不是“已经识别多种解释却没询问”，而是共享解析器遗漏了 `understanding` 与 `not just make me feel better` 的对比关系，将认知理解支持压缩为鼓励语气。需要改进语义解释；若确有多种有效含义，再保留歧义并询问，不机械增加所有任务的询问次数。

### T3-1：一个推测语速候选使整个请求失效

实际请求：`I want talking to you to feel much less intimidating.`

任务目标是 Friendly wording，并保持原语速和音色。共享解析涉及 `tone`、`speech_rate`，但规范化结果为 `supported=false`、候选为空，原因是语速不能以 0.01 步长表示。四策略均为 `UNRESOLVED / COMMON_UNSUPPORTED`，没有澄清；最终仍为 Professional、1.10×。

现有规范化代码遇到任一候选的 `RateLimitError` 会清空所有候选。离线 fixture 可复现：一个有效 Friendly 候选和一个推测的 `current × 0.95` 候选，在 1.10× 起点下因 1.045 不合法而整体拒绝。**0.95 是复现用例，不是已证实的原模型候选**；原记录只保存了规范化后的结果。

需区分用户明确给出的不可实现精度与模型自行推测的定性调整。定性建议应直接使用受支持的绝对档位；不能让模型猜出的非法数值冒充用户的明确要求，也不能静默舍入用户明确提出的数值。

## 3. 另一个独立问题：问了但丢失回答

R3-2 的 Always Ask 确实询问过，但完整澄清回答为：

`Keep all those details, but slow the speaking pace down to eighty percent of your default speed. Leave everything else as it is.`

日志显示该回答被识别为选择 `c1`（已有的 Detailed），`free_text` 为空，未进入完整文字重新解析流程。新增的明确语速要求被丢弃，最终仍为 1.20×。

因此仅让 Selective 多问一次仍不足以解决问题。口头／文字澄清必须保留原话及新增约束；不能因为前半句像在确认某个候选，就忽略后半句。该链路供所有策略及自然会话共用。

## 4. 修复范围与设计约束

已实现版本为 `tutor-interpretation-v8` 与 `tutor-gates-v3`，重点为：

1. **歧义独立于候选数量保存。** 表示仍未明确的调整对象、幅度或要求，避免“只生成一个候选”被误当作“需求明确”。Selective 读取该证据，明确请求仍可直接执行。
2. **保留语义对比与保持要求。** 区分解释支持、鼓励语气、语速、音色；对改善请求被解释为无变化的情况保留未解决意图，不直接宣称已满足。
3. **完整处理口语澄清。** 自然语言回答进入完整解析，保留新增的速度、保持条件等；按钮选择与简单确认仍应有明确绑定，不混淆为新的任务。
4. **定性语速使用合法档位。** 对模型提出的“更慢”等候选使用支持范围内的绝对 0.01 档位；明确数值请求仍按其原义校验，不偷偷截断或四舍五入。

绑定问题的非简单口头／文字回答会完整进入 resolver；只有单一候选下的简单确认可直接匹配。直接点击选项仍按选项 ID 执行。resolver 仍有歧义时保留待澄清状态，不因只剩一个候选而提交。跨属性歧义的问题文本列出所有实际候选涉及的属性，避免只写模型首先标注的一个维度。

新增的 `ambiguities` 包含类型、字段及来自公开请求的原文证据，所有策略共用。小幅可逆语速／缩放的程度调整保留原例外，明确数字、类别、唯一历史引用仍可直接执行。元数据中的 requested/preserved 重复标签仅在每个候选显式保留当前精确值、且还有其它修改字段时规范化；不推测缺失值、不改写 patch、不舍入数字、不丢弃矛盾候选。

这些改动不能读取私有任务目标、题号或已填问卷来决定 ASK/ACT，不能把所有 C3 题硬编码为必问，也不能把错误结果反复重跑到达标。四策略继续共享同一初始请求和解析证据；Selective 的作用是按不确定性选择是否询问。

现有成功案例也应保留：明确 Friendly／Professional、明确音色、可唯一定位的历史恢复无需人为制造歧义；Voice 的 V3-1、V3-2 已能识别调整属性的歧义并询问。T3-2 的“更有动力继续”可合理映射 Encouraging，不能仅凭情境分类判为漏问。

## 5. 实施与验证状态

已完成第一轮修复，但**不能宣称任意新表达的全部候选质量已经解决**。

- 最终解释／策略／会话／四策略服务回归 133 项通过。另有归一化真实捕获与边界测试通过；这些均使用本地 fixture，不是参与者数据。
- 首轮真实验证为 14 次 DeepSeek 文本调用、13 个检查案例：3 个旧问题及 2 个新措辞均触发 ASK；7 个明确、保持或幂等请求仍 ACT；R3-2 的绑定回答进入全文解析后得到 0.80×，保留 Detailed、原语气及其它配置。没有 TTS 调用。这个首轮通过只表示当时定义的决策／设置检查通过。
- 人工复核发现首轮遗漏的质量问题：新措辞“without losing any of the information”的一个候选会从 Detailed 降到 Balanced；舒适感请求还可能被赋予无依据的具体音色。因此增加候选约束检查，保留首轮全部原始输出，未把它们当成全面语义正确。
- 强化保持约束与音色依据提示后，追加 4 次真实文本调用：保留信息的新措辞正确保留 Detailed；R3-2 返回了显式保持内容的候选，但 requested/preserved 重复标签导致格式校验失败。对这项纯元数据重复进行了严格规范化，使用该**原始返回离线重放**后正确 ASK 并保留 Detailed；该重放不是新的模型样本。
- 追加调用中的两例舒适感表达仍含缺乏依据的 Female voice 2 候选，扩展质量检查未通过。两例都先 ASK，未自动应用音色；问题已列为剩余限制，不删除、不修改返回，也不反复调用直到通过。

合计 18 次真实文本调用，分两次独立工程验证；旧批次 32 题的音频、模型结果、问题、回答及用户反馈未改写。当前代码版本及实际 provider 输出的摘要均保存在各验证目录。问卷只导入用户提交的原始答案，不重新评分，也不与新版本结果拼接。

下一次正式重做比较前，应先处理下面的候选质量问题，再用新批次生成四策略结果并重新收集评价；不能仅替换 Selective 音频后沿用这批评分。

## 6. 本次未解决的输出质量问题

- **舒适感到具体音色的无依据映射。** “less intimidating / more comfortable”仍可能附带 Female voice 2。目录没有证据支持该声音更温和；提示约束尚不足以稳定消除该候选。后续需要约束音色候选的依据或在确定调整音色前采用更开放的澄清，不能把目录性别当成感知音质证据。
- V1-1、V1-2、V3-1、V3-2 的 Selective 回复声称下一 session 会自动恢复旧音色，当前权威上下文未提供该承诺。需后续约束生成器的未来状态说明。
- L2-1、L3-1 等 Brief 回复可能只确认设置，没有提供可体现内容结构的正常教学回应。属于回复生成与实验可观察性问题，不能归因为澄清 gate。

以上记录为后续事项，本次不声称已修复。

## 7. 证据索引

- [用户下载的四属性反馈](</Users/alanwong/Desktop/IAI/completed-attribute-feedback.json>)；导入位置：`StudyData/text-check-v3/attribute-feedback/`。
- [Speech rate／Reply length 对照证据](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-audit-20261127/rate-length-audit.json>)。
- [Tone／Voice 16 题证据](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-audit-20261127/tone-voice-evidence.json>)及[详细核查](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-audit-20261127/tone-voice-audit.md>)。
- 原检查点：`StudyData/text-check-v3/tasks/R3-2/checkpoint.json`、`L3-2/checkpoint.json`、`T3-1/checkpoint.json`。
- R3-2 回答路由证据：[日志第 40 行](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/text-check-v3/logs/comparisons/debug/2d7eaaacdf894576ae5809ddb7537620.jsonl:40>)及紧随的解析记录。
- [首轮 14 次真实调用](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-repair-live-20261127-v1/run.json>)。
- [追加 4 次候选质量检查](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-repair-live-20261127-constraints/run.json>)，包含未通过项。
- [元数据修复后的离线重放](</Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project/StudyData/validation/selective-audit-20261127/post-normalization-replay.json>)；这些记录不覆盖原 provider 响应。
