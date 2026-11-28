# 当前问卷内容、评分与数据范围

版本：研究文档v2.0；日期：2026-11-28。本文对应[四属性＋外观五模块设计](FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)和[40题完整题库](CURRENT_TASK_BANK_40.md)，不另造已实现的API版本。自然模拟及原26题问卷退出本次实验，保留[旧版问卷归档](FINAL_USER_STUDY_DESIGN_v1_9_ARCHIVE.md)用于解释历史数据。

## 1. 填写单位与实际采集范围

每个模块包含八题，每题产生四策略结果。看完该模块八题后，参与者分别对E/A/N/S各填A0–A4五项评分，共20项，再完成一项模块策略偏好。不是每道任务填写20项，也不是让每种策略使用不同请求。

| 范围 | 任务 | 评分 | 偏好 | 当前状态 |
| --- | ---: | ---: | ---: | --- |
| 四属性独立网页 | 32 | 80 | 4次属性偏好 | 已发布的独立辅助评价与数据按原版本保留 |
| 外观独立网页 | 8 | 20 | 1次外观偏好 | 已有P001–P004四份最终反馈，评价同一套冻结输出 |
| 五模块完整方案 | 40 | 100 | 5次模块偏好＋1次总体偏好 | 五模块统一调度及总体偏好尚未接入；不是已收集的完整样本 |

完整方案为106个核心作答项目，当前两个独立网页合计的模块项目为105项。不能从五个模块偏好自动生成尚未填写的五模块总体偏好。旧Unity控制器仍含32题＋自然评估的调度，文档更新不代表其已迁移到新方案。

本次四人外观反馈的采集方式为 `api_assisted_output_review`：参与者查看同一套任务、实际请求、授权助手代拟的澄清及Unity结果，再进行评价。不能表述为四位参与者分别进行了八次独立API交互。A1/A2保留实际施测题干，其分数应结合这种回顾方式解释，不外推为连续使用时的客观难度、打断或自主控制表现。

## 2. 四属性英文评分题

四个属性使用同一组题干，“this attribute”对应当前Speech rate、Reply length、Tone或Voice。题干与已发布的[四属性材料](../../../Experiments/runs/text-check-v4/review-data.json)一致。

| ID | 英文题干 |
| --- | --- |
| A0 | Overall, to what extent did this approach’s outcomes meet your requirements across the tasks for this attribute? |
| A1 | Overall, how difficult or easy was it to make adjustments to this attribute using this approach? |
| A2 | Across the tasks for this attribute, I felt in control of the changes made to the tutor with this approach. |
| A3 | This approach’s decisions about whether to ask for clarification suited my needs across the tasks for this attribute. |
| A4 | Overall, I am satisfied with my experience of adjusting this attribute using this approach. |

A0帮助语：Consider the requested changes and settings that should stay unchanged across all tasks for this attribute. Give one overall judgment; individual outcomes may differ.

## 3. 外观英文评分题

以下为四人实际填写的 `appearance-module-A0-A4-v1`，对应[发布的机器可读问卷快照](../../../Experiments/appearance/materials/questionnaire.json)。外观中同样对四策略分别作答，不因A、N或S提出过澄清而另加分或减分。

| ID | 英文题干 |
| --- | --- |
| A0 | Overall, to what extent did this approach’s outcomes meet your requirements across the appearance tasks? |
| A1 | Overall, how difficult or easy was it to adjust the tutor’s appearance using this approach? |
| A2 | Across the appearance tasks, I felt in control of the changes made to the tutor with this approach. |
| A3 | This approach’s decisions about whether to ask for clarification suited my needs across the appearance tasks. |
| A4 | Overall, I am satisfied with my experience of adjusting the tutor’s appearance using this approach. |

A0帮助语：Consider both the changes you wanted and the features you wanted to keep unchanged.

实际页面说明要求回顾记录中的请求、澄清和外观结果，并明确请求由用户提供或确认、澄清回复经用户授权由助手代拟。不要求回顾者声称这些是本人逐字提供的对话。

## 4. 五项的量尺、来源及设计理由

| ID | 构念与量尺 | 依据与理由 |
| --- | --- | --- |
| A0 | 要求满足程度；1 Not at all，7 Completely | 项目自编。兼顾希望修改的内容和应保持不变的设置；1–7是感知程度，不是客观成功率，也不是把旧分类题机械转换为数字 |
| A1 | 调整难易度；1 Very difficult，7 Very easy | 参考[SEQ内容与七点难易量尺](https://measuringu.com/evolution-of-seq/)，改为八题模块回顾；不使用原单次任务施测的常模 |
| A2 | 修改控制感；1 Strongly disagree，7 Strongly agree | 参考[SASSI原研究的交互控制内容](https://bura.brunel.ac.uk/bitstream/2438/3077/1/SASSI%20Paper%202000.pdf)，限定tutor修改并使用本项目量尺；不称独立Control子量表 |
| A3 | 澄清决策适切性；同意度1–7 | 项目专用。询问和不询问都可能合适或不合适，不能用少提问代替高质量决策 |
| A4 | 总体满意度；同意度1–7 | 项目自编单题。总体体验与A0的具体要求达成分别评价，不称SUS或SASSI总分 |

A2–A4的4为Neither agree nor disagree。五项分别分析，不平均为一个标准总分；本问卷是已有工具内容的适配与项目自编题的组合，不是完整SEQ、SASSI、SUS或UEQ-S，也未验证为新的标准短版。

每道评分另有 **Unable to judge**。它作为不可判断状态、数值为null保存，不等于4、0、失败、未作答或技术缺失。正常提交需要20项均明确选择数字或无法判断。自由备注可空，不由备注推算评分。

自然交流的打断感、SUS、UEQ-S及原诊断题均不挪入外观问卷；本轮受控输出比较不能替代完整连续对话体验的评价。

## 5. 策略偏好

外观页面的实际题干：

> Which approach(es) do you prefer overall for these appearance tasks?

选择一个或多个E / A / N / S，或单独选择No preference；无默认项，不提供Unable to judge或Unable to compare。四属性页面同样每属性八题后收一次多选偏好。模块偏好评价的是整组任务，不能倒推出每道题的选择。

五模块完整方案另外规划：

> Considering all five modules, which approaches would you prefer to use for future tutor personalization? Select all that apply, or choose No preference on its own.

该总体题尚未在当前独立网页统一收集。每个被选策略计一票；分母为完成该模块偏好的参与者，多选比例之和可能超过100%。保留逐人选择集合，No preference不分摊给策略。

## 6. 已实现的外观JSON与汇总规则

| 内容 | 外观记录与含义 |
| --- | --- |
| 原始导出 | `appearance-summary-feedback-v1`，`domain=appearance`，`collection_unit=module` |
| 问卷版本 | `appearance-module-A0-A4-v1` |
| 采集方式 | `api_assisted_output_review` |
| 参与者 | 原导出中的匿名 `participant_id`；本批为P001–P004，不附姓名映射 |
| 结果绑定 | `evidence`固定task ID、分支结果、图像摘要及来源；本批网页release为 `66a014509679f46aabcf63763a308b84de5327a731fe9ad6f198ec5ac1456639` |
| 状态 | `draft`是未最终提交；只有 `final` 且完整通过校验的文件进入本批总汇总 |
| 评分 | `conditions.<E/A/N/S>.answers.<A0…A4>`；answered配整数1–7，unable_to_judge配null |
| 偏好 | `answered`配不重复策略数组，或 `no_preference`配null；与四属性旧JSON的特殊值形状不同，不静默套用 |
| 评论与时间 | 保留原 `comment`、`saved_at`；不新增或改写参与者回答 |
| 图像打开记录 | `review_opened`仅表示页面打开过某个结果，不证明认真看完或完成独立交互 |

新外观的[四份参与者结果与汇总](../../../Experiments/appearance/README.md)单独保存。原始文件保持字节与摘要；汇总保留来源、有效分数、独立缺失计数及多选集合。相同参与者重复文件不能重复计数；版本或evidence不同不得默默合并。问卷均值/中位数/分布是描述统计，不把四人当作128个独立任务样本。

外观P001与四属性P001分属不同数据包命名空间；没有额外身份核对依据，不能只因编号相同就认定为同一人。首次外观研究的15人数据继续独立，不换题号后并入本批。

## 7. 与旧Unity保存契约的关系

[原study-data-contract-v1](STUDY_DATA_PERSISTENCE_CONTRACT.md)描述既有Unity注册、journal、恢复和导出的实现及历史字段。仍保留读取旧数据的能力；其中自然模块、旧逐任务评分和671项计数不再是当前研究要求。

本次公开外观JSON没有补造Unity的study_run_id、设备会话、真实STT或完整五模块完成状态。五模块Unity调度、总体偏好及统一身份导入需另行接线与验证；上传研究资料不等于这些功能已完成。
