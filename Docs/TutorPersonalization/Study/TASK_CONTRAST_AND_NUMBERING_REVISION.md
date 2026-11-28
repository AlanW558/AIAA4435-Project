# 四属性任务：对比幅度、起始材料与连续编号修订

> **历史修订记录；导航更新于2026-11-28。** 下文的当前材料/批次指当时的text-check-v2。现行完整题卡见[40题任务库](CURRENT_TASK_BANK_40.md)，已发布四属性输出为text-check-v4；本文件保留数值与编号调整的来源，不恢复固定试听或旧问卷版本。

日期：2026-11-27。适用范围：当前文本请求／API／TTS 辅助试听批次 `StudyData/text-check-v2/`。本文件记录已写入当前题库的内容，不是尚未采用的任务建议。

当时执行依据为 [StudyTaskSequence.json](../../../Assets/Project/Resources/Tutor/StudyTaskSequence.json)：`task-navigation-v3`、材料版本 `attribute-materials-v2`，当时核对 SHA-256 为 `125c54f99f42685c6653a35d4ec4f14cb2e9c11a9b4b3df564bf847c17060dd5`。逐题填写表由同一题库生成，原始本地路径为 `StudyData/text-check-v2/TASK_REQUESTS.md`（未随仓库发布）。下列 32 行的英文目标直接取自当时题库；“实际起点”通过依次应用 `public_setup` 中的 setting 事件得到，不能把历史题最早的设置当成当前起点。

修订解决三类问题：起点与目标过近导致难以听辨；缺少起始或历史音频导致比较参照不足；删题后参与者看到不连续的 1／3 编号。保留四属性、四类情境、每情境两题、四策略同请求的结构，32 题不变。每属性仍在听完八题后填写四策略各五题，再选一次偏好，即 **20 个核心答案＋1 个偏好；四属性共 84 项**。完整范围与量表来源见[属性级问卷修订](ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)。自然情境模块不在本次辅助试听修订内。

## 当前材料与比较规则

| 内容 | 本次已落实的设置 |
| --- | --- |
| 语速 | 以当前音色模型的默认速度为 1.00×；区分“默认速度的倍数”与“当前速度下降的比例”。明确题、定性题、跨属性解释题和历史恢复题都保留；具体起点与目标见逐题表。 |
| 回答长度 | Brief＝关键点；Balanced＝关键点与理由；Detailed＝关键点、解释与相关例子。主要比较 Brief 与 Detailed，仍按内容构成而非固定字数或句数评价。 |
| 语气 | Professional／Friendly／Encouraging 是风格类别。使用学习遇到困难的共同内容，使中性、友好和鼓励措辞有合适语境；不把它们当成有固定距离的连续档位。 |
| 音色 | 使用登记的 A–E 音色及可试听目标；C2 改用登记声音中的男性／女性选项，允许目标范围内多个声音。C3 仍保留可能涉及音色、语气或语速的自然表达。历史音色题提供对应音频。 |
| 历史与偏好 | 每题重新提供公开示例历史／软偏好；不继承前一题，也不伪称参与者曾说过这些话。局部恢复只改变目标属性，保留表中当前的其它设置。 |
| 任务说明与模型输入 | 英文目标卡和期望范围供参与者／研究者使用；不自动加入模型请求。模型仅获得实际 Request、共有公开起点／历史及后续实际澄清。目标具体不意味着参与者必须照读或必须故意含糊。 |
| 比较公平性 | 四策略从同一当前起点出发，共用原始请求；实际澄清结束后统一开放输出。更大的起点—目标差异用于改善可比较性，不要求四策略都改变，也不重生成直到四策略结果不同或都达到目标。 |

共同学习问题已保存于新批次 `execution/common-learning-question.txt`：

> I tried active recall, but I forgot most of the answer and feel stuck. How should I practise it next time?

它是用于检查调整后回答的统一研究材料，应和用户提出的属性修改 Request 分开显示。起点示例也围绕这同一问题组织；Reply length／Tone 的策略结果仍须由模型在各分支实际生成，不能用起点示例替代。

## 32 道当前任务

表中编号是参与者看到的连续编号；每个情境恰为 1／2。实际起点按 **Rate / Length / Tone / Voice** 排列，所有倍数均相对模型默认速度。除目标属性外保持当前设置；表中的历史、偏好和音频标签都是本题给定材料。

情境含义：C1 明确目标；C2 程度／定性偏好；C3 可能存在不同解释；C4 历史、偏好与局部恢复。后一列与保留的上一批题库快照比较，说明此次已经发生的改动；未列出的字段不声称发生了变化。所有题的示例交流内容同时更新为上面的共同学习问题。


### Speech rate（8 题）

| 显示题号 | 情境 | 当前英文任务目标 | 实际起点 | 历史／偏好／参考材料 | 相对上一批的改动 |
| --- | --- | --- | --- | --- | --- |
| R1-1 | C1 | Change the speaking speed from 1.20 to 0.80 of the model’s default speed. | 1.20× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 更新目标措辞／范围 |
| R1-2 | C1 | Reduce the current speaking speed by 25%. The starting speed is 1.20 of default, so your intended result is 0.90 of default. | 1.20× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 更新目标措辞／范围 |
| R2-1 | C2 | Starting at the default speed (1.00), make the pace clearly slower. Your preferred range is 0.70–0.75 of the default speed. | 1.00× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 更新目标措辞／范围 |
| R2-2 | C2 | Starting at the default speed (1.00), make the pace clearly faster. Your preferred range is 1.25–1.30 of the default speed. | 1.00× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Rate：0.85× → 1.00×<br>更新目标措辞／范围 |
| R3-1 | C3 | You want the delivery to feel calmer by slowing the pace from 1.20 to 0.75–0.80 of default, without changing the tone or voice. | 1.20× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Rate：1.00× → 1.20×<br>更新目标措辞／范围 |
| R3-2 | C3 | You want the detailed explanation to be easier to follow by slowing the pace from 1.20 to 0.75–0.80 of default. Keep all its detail. | 1.20× / Detailed / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Rate：1.15× → 1.20×<br>更新目标措辞／范围 |
| R4-1 | C4 | Restore the previous pace of 0.75 of default from the current 1.25. Leave the other settings as they are now. | 1.25× / Balanced / Professional / Voice A | 历史：0.75× / Balanced / Professional / Voice A → 1.25× / Balanced / Professional / Voice A | 起点 Rate：1.10× → 1.25×<br>更新目标措辞／范围 |
| R4-2 | C4 | For this task, use 0.75 of the default speed, even though your earlier preference was 1.25. Keep all other settings unchanged. | 1.25× / Balanced / Professional / Voice A | 公开偏好：I usually prefer a pace of 1.25 of the default speed. | 起点 Rate：1.10× → 1.25×<br>更新目标措辞／范围 |

### Reply length（8 题）

| 显示题号 | 情境 | 当前英文任务目标 | 实际起点 | 历史／偏好／参考材料 | 相对上一批的改动 |
| --- | --- | --- | --- | --- | --- |
| L1-1 | C1 | Give only the key answer or recommendation, without explaining the reason or adding an example. | 1.00× / Detailed / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Length：Balanced → Detailed |
| L1-2 | C1 | Give the key answer, explain why it makes sense, and add one relevant concrete example. | 1.00× / Brief / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Length：Balanced → Brief |
| L2-1 | C2 | Substantially reduce the amount of detail: keep only the key answer, without the supporting explanation or example. | 1.00× / Detailed / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 更新目标措辞／范围 |
| L2-2 | C2 | Expand the very short answer substantially so you can understand the reasoning and see a concrete example. | 1.00× / Brief / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 更新目标措辞／范围 |
| L3-1 | C3 | You feel overloaded and want a less overwhelming answer: keep only its key point, rather than changing the speaking speed. | 1.00× / Detailed / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| L3-2 | C3 | You need more support to understand the material: add an explanation and an example, rather than only receiving more encouraging wording. | 1.00× / Brief / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| L4-1 | C4 | Restore the middle answer format, which included an explanation and a concrete example. | 1.00× / Brief / Professional / Voice A | 历史：1.00× / Balanced / Professional / Voice A → 1.00× / Detailed / Professional / Voice A → 1.00× / Brief / Professional / Voice A | 保留目标与起点；更新共同示例内容 |
| L4-2 | C4 | Restore the earlier key-answer-only format, while keeping the friendly tone you now have. | 1.00× / Detailed / Friendly / Voice A | 历史：1.00× / Brief / Professional / Voice A → 1.00× / Detailed / Friendly / Voice A | 更新目标措辞／范围 |

### Tone（8 题）

| 显示题号 | 情境 | 当前英文任务目标 | 实际起点 | 历史／偏好／参考材料 | 相对上一批的改动 |
| --- | --- | --- | --- | --- | --- |
| T1-1 | C1 | Use a Friendly tone for the tutor’s responses. | 1.00× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| T1-2 | C1 | Use a Professional tone for the tutor’s responses. | 1.00× / Balanced / Encouraging / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| T2-1 | C2 | Make the wording more neutral and matter-of-fact, while keeping the same amount of information. | 1.00× / Balanced / Friendly / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| T2-2 | C2 | After a practice mistake, change the neutral professional wording to supportive encouragement for another attempt. Keep the same amount of information. | 1.00× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Tone：Friendly → Professional<br>更新目标措辞／范围 |
| T3-1 | C3 | Make the interaction feel less intimidating by using friendly wording. Keep the current pace and voice. | 1.10× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 保留目标与起点；更新共同示例内容 |
| T3-2 | C3 | You want to feel more motivated to continue: use supportive encouragement, without giving a longer explanation. | 1.00× / Balanced / Professional / Voice A | 当前起点示例；无需额外目标／历史音色样例 | 起点 Length：Brief → Balanced |
| T4-1 | C4 | Restore the friendly style used in the previous response. | 1.00× / Balanced / Professional / Voice A | 历史：1.00× / Balanced / Friendly / Voice A → 1.00× / Balanced / Professional / Voice A | 保留目标与起点；更新共同示例内容 |
| T4-2 | C4 | For this task, use an Encouraging tone instead of your earlier preference for professional wording. Keep Voice B. | 1.00× / Balanced / Professional / Voice B | 公开偏好：I usually prefer professional wording. | 保留目标与起点；更新共同示例内容 |

### Voice（8 题）

| 显示题号 | 情境 | 当前英文任务目标 | 实际起点 | 历史／偏好／参考材料 | 相对上一批的改动 |
| --- | --- | --- | --- | --- | --- |
| V1-1 | C1 | Switch from Voice A to Voice D, which you can hear in the target reference. | 1.00× / Balanced / Professional / Voice A | 音频：Target reference · Voice D | 更新目标措辞／范围<br>更新目标／历史音频材料 |
| V1-2 | C1 | Switch from Voice D to Voice C, which you can hear in the target reference. | 1.00× / Balanced / Professional / Voice D | 音频：Target reference · Voice C | 起点 Voice：Voice B → Voice D<br>更新目标措辞／范围<br>更新目标／历史音频材料 |
| V2-1 | C2 | Change from the current female voice to a male voice (D or E in the registered catalog). Either is acceptable; keep speaking rate and wording style unchanged. | 1.00× / Balanced / Professional / Voice C | 音频：Target reference · Voice D；Target reference · Voice E | 起点 Voice：Voice A → Voice C<br>更新目标措辞／范围<br>更新目标／历史音频材料 |
| V2-2 | C2 | Change from the current male voice to a female voice (A or C in the registered catalog). Either is acceptable; keep all other settings unchanged. | 1.00× / Balanced / Professional / Voice D | 音频：Target reference · Voice A；Target reference · Voice C | 起点 Voice：Voice A → Voice D<br>更新目标措辞／范围<br>更新目标／历史音频材料 |
| V3-1 | C3 | You want a different feel to the delivery by changing from Voice A to target Voice D. Keep the current pace and wording style. Listen to the target before making your request. | 1.10× / Balanced / Professional / Voice A | 音频：Target reference · Voice D | 更新目标措辞／范围<br>更新目标／历史音频材料 |
| V3-2 | C3 | You want a different feel to the delivery by changing from Voice D to target Voice C. Keep the current pace and wording style. Listen to the target before making your request. | 1.00× / Balanced / Professional / Voice D | 音频：Target reference · Voice C | 起点 Voice：Voice B → Voice D<br>更新目标措辞／范围<br>更新目标／历史音频材料 |
| V4-1 | C4 | Restore the voice from the middle history entry. | 1.00× / Balanced / Professional / Voice A | 历史：1.00× / Balanced / Professional / Voice C → 1.00× / Balanced / Professional / Voice D → 1.00× / Balanced / Professional / Voice A<br>音频：History 1 · Voice C；History 2 · Voice D；History 3 · Voice A | 更新目标／历史音频材料 |
| V4-2 | C4 | Restore the earlier Voice A from the current Voice D, but keep the current faster pace and friendly tone. | 1.25× / Balanced / Friendly / Voice D | 历史：0.75× / Balanced / Professional / Voice A → 1.25× / Balanced / Friendly / Voice D<br>音频：History 1 · Voice A；History 2 · Voice D | 起点 Rate：1.15× → 1.25×<br>起点 Voice：Voice A → Voice D<br>更新目标措辞／范围<br>更新目标／历史音频材料 |

## 试听页面与真实结果的区分

每题页面先显示 **Starting sample**，再显示该题额外的 **Reference 1／2／3**（有材料时），然后显示四策略的输出。起始样例和参考音频标明为 supplied material，不能计作策略完成任务的结果。

- Speech rate／Voice：起点和四策略输出使用同一固定短句 `Let's explore this idea together, one step at a time.`；比较实际语速／音色变化。Voice 另有上表列出的目标或历史样例。
- Reply length／Tone：起点播放给定的当前示例回答；四策略播放统一学习问题在各分支产生的新回答。因此前后措辞本身可以不同，不能仅凭是否逐字一致判断变化。
- 每个策略保留是否澄清、实际问题、答复和来源。本批若由助手按用户授权代拟澄清，明确标为助手代拟，不记作参与者自然口述。
- **Recorded result** 按真实 outcome 和实际起点／结果 settings 呈现 `Unresolved`、`No setting change`、`Settings changed` 等；还展示目标属性的起始→最终值，可展开查看全部设置和记录消息。`ready` 只表示可以读取结果，不能自动解释为任务成功。
- 合法的 unresolved／未修改结果可以继续播放其真实状态下的声音。这不等于 TTS 失败，也不应删除或强制改到研究者目标。模型接口、结构校验或 TTS 的技术错误则单独处理；不得拿起点音频伪装成失败策略的新输出。
- 评分和偏好没有默认值；是否满足目标仍由实际试听者判断。音频文件数、API 成功数及设置差异不是任务达成率，也不替代问卷。

本轮发布验收目标是 32 题 × 4 个真实策略输出，另附 32 个起始样例和本题库登记的 13 个音色参考。这里记录的是材料数量与验收要求，不宣称云端生成已经全部完成；实际结果以新批次执行摘要及文件校验为准。

## 版本、旧数据与内部编号

新批次使用独立目录 `StudyData/text-check-v2/`。上一批 `StudyData/text-check/` 的请求、音频、结果和反馈保留，不能将旧 121 个输出／7 个技术错误的状态混记成新批次结果。每批保存 `catalog.json` 快照，报告先读取本批快照并与 batch 中 SHA-256 核对；后续题库修订不应让旧报告误用新材料。

显示编号 `display_code` 仅用于任务表、导航、题目标题、试听链接和无障碍音频标签。检查点、音频目录、日志和属性反馈的 `task_releases` 仍使用稳定的 `task_code`，避免旧记录错配。以下映射仅供研究者排查，不在参与者试听页面显示。

<details>
<summary>研究者内部编号映射（32 题；点击展开）</summary>

| 显示编号 | 内部 task_code | 方向／情境 |
| --- | --- | --- |

| R1-1 | `R1-1` | Speech rate / C1 |
| R1-2 | `R1-2` | Speech rate / C1 |
| R2-1 | `R2-1` | Speech rate / C2 |
| R2-2 | `R2-2` | Speech rate / C2 |
| R3-1 | `R3-1` | Speech rate / C3 |
| R3-2 | `R3-2` | Speech rate / C3 |
| R4-1 | `R4-1` | Speech rate / C4 |
| R4-2 | `R4-3` | Speech rate / C4 |
| L1-1 | `L1-1` | Reply length / C1 |
| L1-2 | `L1-3` | Reply length / C1 |
| L2-1 | `L2-1` | Reply length / C2 |
| L2-2 | `L2-2` | Reply length / C2 |
| L3-1 | `L3-1` | Reply length / C3 |
| L3-2 | `L3-2` | Reply length / C3 |
| L4-1 | `L4-2` | Reply length / C4 |
| L4-2 | `L4-3` | Reply length / C4 |
| T1-1 | `T1-1` | Tone / C1 |
| T1-2 | `T1-3` | Tone / C1 |
| T2-1 | `T2-2` | Tone / C2 |
| T2-2 | `T2-3` | Tone / C2 |
| T3-1 | `T3-1` | Tone / C3 |
| T3-2 | `T3-2` | Tone / C3 |
| T4-1 | `T4-1` | Tone / C4 |
| T4-2 | `T4-3` | Tone / C4 |
| V1-1 | `V1-1` | Voice / C1 |
| V1-2 | `V1-2` | Voice / C1 |
| V2-1 | `V2-1` | Voice / C2 |
| V2-2 | `V2-2` | Voice / C2 |
| V3-1 | `V3-1` | Voice / C3 |
| V3-2 | `V3-2` | Voice / C3 |
| V4-1 | `V4-2` | Voice / C4 |
| V4-2 | `V4-3` | Voice / C4 |

</details>

本次目录修订已进入资源题库，但不把“文件已更新”当作 Unity／头显新材料验收完成。当前辅助页面继续使用 `attribute-summary-feedback-v1`；正式 VR 流程和自然模拟的接线、数据格式与实施要求仍参照主设计及既有数据契约。
