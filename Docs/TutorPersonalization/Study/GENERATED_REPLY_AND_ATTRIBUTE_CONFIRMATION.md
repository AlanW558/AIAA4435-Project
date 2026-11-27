# 生成回复、属性确认与属性级问卷修订

> **2026-11-28 版本补充：** 新建四属性问卷使用 `attribute-summary-feedback-v3`（每属性20项A0–A4七点评分＋一项多选偏好），Unity偏好单独使用 `strategy-preference-v2`。E/A/N/S可选1–4项，No preference互斥；偏好题移除无法判断，A0–A4的独立无法判断保留。manifest显式固定 `attribute_questionnaire_version` 和 `preference_questionnaire_version`。旧属性v1分类、v2数值A0/单选偏好和偏好v1按原版本恢复导出，不自动转换。以下早期字段/题量记录以[当前属性问卷修订](ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)为准；32题仍保存独立完成证据，当前最终问卷为16份属性策略评价＋1份自然评价。

更新：2026-11-27。适用于新建运行。实现阶段先完成本地验证；随后按用户新授权完成 v3 真实 API 批次，见文末执行记录。旧批次输出、原始请求、澄清、音频和问卷不重写、不迁移为新实验数据。

## 任务与音频

- 四属性各 4 个情境 × 2 题，共 32 题。参与者编号在每个情境中连续为 1、2；内部 task_code 保持稳定，避免历史数据错位。
- 任务卡只显示 **Task goal、Keep unchanged、Request example**。例句仅供参考，不自动替参与者提交。历史恢复题所需的历史目标写入 Task goal。
- `context_text`、`public_start` 保留用于独立题目的起点与审计，不再展示 Supplied Starting Context。私有任务目标和例句不作为模型意图判断的输入；四策略仍接收同一请求与公开起点。
- 不再提供固定 Play sample、Starting sample 或目标参考音频。四属性都播放本次 API 生成的回复；TTS 读取该回复及其设置快照。
- “仅下一次回答”的配置作用于紧接着生成的真实回复，随后恢复持久配置；重试该回复沿用同一设置快照，不再次应用。
- 单独的调整请求也会生成回应。生成器接收实际执行结果，不能把“没有修改”“未解决”说成修改成功。混合了学习问题的请求保留正常学习回答。
- 保留统一揭示屏障：需要澄清的策略回答完毕、所有分支生成完成或被明确停止后，才能展示结果。技术失败单独保留，不用固定例句冒充结果。
- 自然模拟中的 Selective 澄清同时显示文本并用 TTS 询问。四策略比较的澄清可保持文本；澄清音频绑定实际 question_id，过期、暂停、切换或开始录音时停止，避免旧问题迟到播放。

## 属性控制面板

语速、回答长度、语气、音色先保存在本地待确认配置中。点击 **Confirm changes** 后，一次将四项配置发送给 API。未确认时不触发模型或 TTS；切换策略、任务或运行后不能把旧草稿误提交给新对象。

控件直接提交记录为控件操作，不能冒充参与者口头表达。自由测试与正式实验仍遵守既有模式限制；正式实验模式由任务固定。

| 界面名称 | 稳定内部 ID | 原界面名称 |
| --- | --- | --- |
| Female voice 1 | voice_a | Voice A |
| Female voice 2 | voice_b | Voice B |
| Female voice 3 | voice_c | Voice C |
| Male voice 1（默认） | voice_d | Voice D |
| Male voice 2 | voice_e | Voice E |

供应商音色 ID 和默认选择不变。名称是目录中标注的声音类别，不是对参与者的声学感知作推断。Female voice 2 对应 `longanhuan_v3.6`，女性标签已核对[阿里云官方音色列表](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list)；其它四项沿用项目已保存的官方目录证据。新显示名作为明确音色请求别名传给意图解析器，历史字母别名仍可识别。

## 正式 Unity 保存流程

新建 manifest 使用 `attribute_feedback_unit = attribute`，缺省值仍为 `task` 以识别旧运行。新版 Unity 另显式设置 `attribute_questionnaire_version = attribute-summary-feedback-v2`；缺少该字段的旧属性级 manifest 继续使用 v1，不静默改写已有版本。A0–A4 的题干范围是整个属性的八道任务；自然模拟仍是 `natural-selective-feedback-v2` 的 26 题。

1. 每题完成后 `finish_task` 冻结实际结果与 revision，保存 completion_id；不生成逐任务问卷、不伪造最终问卷提交。
2. 第 8 题完成后，生成该属性的四份策略问卷。每份 5 道 1–7 评分，共 20 个答案。A0 题干保持不变，评价需求满足程度，端点为 1 Not at all、7 Completely；其余四题量尺不变，每题仍可独立选择 Unable to judge。
3. 问卷引用该属性全部八题的结果版本。保存草稿与最终 `submit_attribute` 分开；缺项或过期版本不能进入下一属性。
4. 属性问卷最终提交后填写一次策略偏好，再进入下一属性。原正式流程中的四属性总体偏好保留；辅助试听文件只包含已约定的 4 次属性偏好，共 84 个必答项目。
5. 自然模拟继续独立保存 Selective 对话和 26 题最终问卷。

新运行的四属性最终问卷导出应有 **16 条策略问卷记录**（4 属性 × 4 策略），另有 32 条任务完成证据。旧运行的逐任务问卷与属性级 v1 分类答案仍按旧版本导出；不将 A0 分类转换为分数或与 v2 合并。事件、草稿、最终提交、未完成记录、任务结果引用与参与者／运行编号保留区分。

## 辅助脚本与下一次运行

`Tools/TutorTextCheck` 默认使用新目录 `StudyData/text-check-v3/`。旧 `text-check` 与 `text-check-v2` 保留为各自版本的记录。下一次生成会重新得到正常回复，不能继续使用 v2 的固定句音频。

v3 的 `TASK_REQUESTS.md` 使用此前确认的 32 条口语化请求，仅同步音色名称。现已全部提交 API；澄清已处理，完整历史问题及回答保存在 `CLARIFICATION_LOG.md`、检查点和原始执行日志中。

新发布只合成四策略实际回复，保留每个回复的澄清状态、问题、答案、来源及音频摘要；属性问卷仍绑定全部八题的 release_id。没有新回复或版本不匹配时拒绝发布。

下面的实现验证使用本地模型与 TTS fixture，不填任何参与者评分。后续真实批次另列于文末；主观输出质量、头显听感和自然模拟连续使用仍需人工验收。

## 本机验证结果（A0 七点改版前的历史记录）

- 后端完整回归 494 项通过；随后针对澄清语音选项、音色标签和对话导出的 95 项检查通过。
- 辅助工具 56 项通过，覆盖真实回复绑定、拒绝固定样例替代、问卷版本、旧结果兼容及新结果校验。
- Unity 编译及完整流程 794 项断言通过：32 题、16 份属性策略问卷、1 份自然问卷、5 项偏好，完整导出无未完成记录。包含回顾该属性八题、只读策略切换和 20 项答案保留。
- 三阶段中断恢复 197 项断言通过；控制面板 45 项、音频回放 55 项通过。修复了统一揭示后旧草稿未清除的问题，并通过重新确认提交和布局截图复查。
- 全程使用本地 fixture，没有真实模型／TTS 调用、真人麦克风或头显验收。验证汇总保存在 `StudyData/validation/generated-reply-confirmation-20261127/verification.json`；实际参与者数据未改写。

## v3 真实 API 批次执行记录

2026-11-27，按用户追加授权，使用 `deepseek-v4-flash` 与 `qwen-audio-3.0-tts-plus` 完成新版 32 题、四策略共 128 个实际回复音频；本批没有固定试听句、STT 调用或技术失败。32 条请求沿用已确认版本；41 次实际澄清由助手按任务目标代拟口语化回答，记录来源为 `assistant_authored_user_authorized`，不是参与者原话。澄清次数为 Execute-first 0、Always-ask 31、Native-gate 2、Selective 8；不为策略补造未发生的问题。

- 试听与属性问卷：`StudyData/text-check-v3/REVIEW_AND_QUESTIONNAIRE.html`。
- 逐策略实际澄清：`StudyData/text-check-v3/CLARIFICATION_LOG.md`。
- 执行及验收记录：`StudyData/text-check-v3/EXECUTION_SUMMARY.md`。
- 每属性保留 20 个策略答案加 1 个偏好，四属性共 84 个必答项目，未自动填写任何评分或偏好。

这次调用用于用户授权的辅助试听及反馈，不自动创建正式参与者记录，也不代表主观任务效果或头显体验已经通过验收。

## A0 七点评分修订

同日后续按用户要求将 A0 从分类题改为 1–7 分，题干仍为 `Overall, to what extent did this approach’s outcomes meet your requirements across the tasks for this attribute?`。1 表示 Not at all（完全未满足），7 表示 Completely（完全满足）；Unable to judge 独立保存，不能记为 4。A0 是项目自编的需求满足程度题，与 A4 的整体满意度分别分析，不合成总分。

本次更新问卷页面、资源及版本校验，不重新执行上述 API 批次。旧 `attribute-summary-feedback-v1` 的分类答案及已发布回复保持原版本；当前页面用 v2 问卷评价同一组冻结音频结果，并保留它们的来源版本。v2 使用独立浏览器草稿，不把旧分类答案自动转换、迁移或覆盖。详细题干与分析边界见[属性级问卷修订](ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)。
