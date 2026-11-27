# 四属性问卷填写单位修订

> **2026-11-27 最新实现修订：** Unity 新建运行与辅助工具统一为每属性八题后填写 20 项评价及一次属性偏好；任务卡采用三字段，移除固定试听，属性通过 Confirm changes 统一提交。详见[本次实现契约](GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)。下文较早日期的逐任务流程与试听设计为历史记录，不作为当前实现要求。

日期：2026-11-28（更新）。当前辅助试听页面从“每道任务评价四策略”改为“每个属性整体评价四策略”。随后按用户要求，将 A0 从完成情况分类改为 1–7 分的需求满足程度。当前问卷为 `attribute-summary-feedback-v3`，题量与策略比较内容不变；旧运行保留原版本和保存单位。

## 填写安排与题量

| 方向 | 保留的任务 | 问卷填写时点 | 核心答案 | 策略偏好 |
| --- | --- | --- | --- | --- |
| Speech rate | 4 种情境 × 2 题＝8 题 | 回顾该属性全部任务后 | 4 策略 × 5 题＝20 项 | 1 项 |
| Reply length | 4 种情境 × 2 题＝8 题 | 回顾该属性全部任务后 | 20 项 | 1 项 |
| Tone | 4 种情境 × 2 题＝8 题 | 回顾该属性全部任务后 | 20 项 | 1 项 |
| Voice | 4 种情境 × 2 题＝8 题 | 回顾该属性全部任务后 | 20 项 | 1 项 |
| 合计 | 32 题 | 4 次属性问卷 | 80 项 | 4 项 |

当前四属性页面合计 **84 个必答项目**，不含可选文字备注。旧方式的 640 个逐任务核心答案降为 80 个属性级核心答案。当前每策略五题均使用 1–7 评分，每属性共 20 道评分题；每题另有独立的 Unable to judge。

每道任务仍展示各策略的音频、原请求、是否澄清、实际澄清问题与回复及来源。用户可以反复试听与回顾，不需每听完一道任务就填写问卷。技术失败继续单独标示；不补造音频、默认评分或偏好。

## 五个维度与策略偏好

五题保留 A0–A4 的测量意图，题干评价范围为“这个属性的整组任务”。A0 的原英文题干不变，回答方式改为需求满足程度的七点评分；A1–A4 量尺不变。页面的准确英文题干由 [`attribute_feedback.py`](../../../Tools/TutorTextCheck/attribute_feedback.py) 维护。

| 题号 | 英文题干 |
| --- | --- |
| A0 | Overall, to what extent did this approach’s outcomes meet your requirements across the tasks for this attribute? |
| A1 | Overall, how difficult or easy was it to make adjustments to this attribute using this approach? |
| A2 | Across the tasks for this attribute, I felt in control of the changes made to the tutor with this approach. |
| A3 | This approach’s decisions about whether to ask for clarification suited my needs across the tasks for this attribute. |
| A4 | Overall, I am satisfied with my experience of adjusting this attribute using this approach. |

| 题号 | 评价内容 | 来源与本次改编 | 作答方式 |
| --- | --- | --- | --- |
| A0 | 整组任务结果满足要求的程度，兼顾目标变化与应保持不变的设置 | 项目自编；评价该属性整体结果，分类改为七点程度评分 | 1＝Not at all（完全未满足），7＝Completely（完全满足）；另有 Unable to judge |
| A1 | 使用该策略调整这个属性的整体难易度 | 既有 SEQ 改编题进一步扩大评价范围 | 1＝Very difficult，7＝Very easy；另有 Unable to judge |
| A2 | 调整这个属性时的控制感 | 既有 SASSI 控制感内容改编题 | 1＝Strongly disagree，7＝Strongly agree；另有 Unable to judge |
| A3 | 该策略在这组任务中决定是否澄清的合适程度 | 项目自编；包括询问与不询问 | 同意度 1–7；另有 Unable to judge |
| A4 | 使用该策略调整这个属性的总体满意度 | 项目自编单题满意度 | 同意度 1–7；另有 Unable to judge |

每种策略各答五题；随后回答一次该属性的策略偏好。偏好为多选 **E / A / N / S**，可选 1–4 个唯一策略；另设 **No preference**，必须单独选择。新偏好题不再提供 Unable to judge / Unable to compare。无默认答案，全部取消恢复未作答；不要求排序，也不自动从评分计算偏好。A0–A4 自己的 Unable to judge 选项继续保留。

这些题是项目适配的组合，尤其 A1 已从单次任务改为整组任务的回顾评价；不能宣称使用了原版完整 SEQ 或 SASSI，也不套用标准工具常模。A0 关注结果满足具体要求的程度，A4 关注整体使用体验的满意度，两者分别报告。A0 的七点程度评分仍是项目自编题，不因改用数字而成为标准量表。各维度分别分析，不自动合成一个总分。

## 结果解释与保存

新评价单位是“参与者 × 属性 × 策略”，四属性对应 16 组五题回答。它反映用户对整组任务的综合判断，不能由此还原某一道任务或某一种情境的单独评分。32 道任务的音频与执行日志仍可用于检查具体错误和解释整体评价；它们不会变成 32 份主观评分记录。

当前问卷版本为 `attribute-summary-feedback-v3`，记录 `collection_unit: attribute`、批次、属性、八道任务及其结果版本、四策略答案与一次偏好。偏好已答保存为 `{"status":"answered","value":["N","S"]}` 或单独 `["no_preference"]`；未答保存为 `{"status":"unanswered","value":null}`。不允许重复策略、未知策略或策略与 No preference 混选。A0–A4 已作答值保存为 1–7 的整数。只有 20 个核心答案及偏好均完成，才列为已完成属性；未完成内容可另存草稿。`Unable to judge` 是独立类别，不等于中点 4。

旧属性级 `attribute-summary-feedback-v2` 的 A0 继续为 1–7 数值，偏好继续按旧单选标量和旧 unable 状态读取；不转换为分类题、不自动改成多选。旧任务结果及 `attribute-feedback-v3` 模板保留；旧属性级 `attribute-summary-feedback-v1` 的 A0 仍为 Fully met / Partly met / Not met / Unable to judge。已有反馈和浏览器草稿不删除、不自动平均、不重命名为新版本；分类答案不转换为 1–7 分，也不与新版 A0 合并分析。新版本使用独立的草稿标识和校验，修订关联限于同一问卷版本。下载的单份属性记录或已完成属性集合可用 `batch.py attribute-feedback --file` 校验保存，旧记录按其声明的旧版本验证。草稿备份不能作为最终完成记录导入。

校验后的属性记录保存到当前批次的 `attribute-feedback/<domain>/<sha>.json`（明确指定所检查批次，已有批次及已填写页面不覆盖）。重复导入相同内容返回同一记录；同版本修改后的回答另存并关联 `supersedes`，以保留修订历史。

## 本次边界

本次只升级问卷偏好及保存版本，不重新调用模型或 TTS，不修改既有批次音频、冻结结果、已填写页面或评分。可用 `report.py --directory SOURCE --output NEW_PAGE --questionnaire-version attribute-summary-feedback-v3` 在新位置生成引用旧音频的空白多选页。旧页面与新页有不同版本的浏览器草稿标识，不自动复制旧答案。助手代拟澄清的来源继续明示。

自然情境的 Selective 单策略评估与 26 题问卷不在本次调整范围。原完整协议中的四属性总体偏好也未由本次需求新增到当前辅助页面；本页收集四次属性内偏好。Unity 新建属性级运行显式设置 `attribute_questionnaire_version: attribute-summary-feedback-v3` 与 `preference_questionnaire_version: strategy-preference-v2`，并保留原正式流程的比较总体偏好；缺少该字段的旧属性级 manifest 按 v1 识别，不静默升级。流程、保存与导出按版本区分，正式施测仍需预测试和头显整体验收。

## 多选分析口径

每个属性仍只有一项偏好，最多勾选四种策略。按策略报告被选择的人数或参与者比例，分母为完成该属性偏好的参与者；总选择数可超过人数、各策略百分比可超过 100% 之和。No preference 单独报告，不分摊到四种策略。旧版 unable 状态单列为不可比较的历史状态；不自动改成 No preference。若研究者经参与者明确更正旧答案，保留原始文件、修订依据与版本，不由程序猜测选择。
