# Tutor 实现与研究导航

更新：2026-11-17。研究入口当前创建 engineering 运行，最新头显整体验收和正式采集设置尚未完成。

## 当前入口与行为

启动、依赖和新 VR 构建步骤见[根 README](../../README.md)。优先使用 `TutorFreeTestDesktop/VR` 自由测试；`TutorComparisonDesktop/VR` 为研究控制流程。`TutorPersonalizationDesktop/VR` 保留为早期单会话入口。

[双模式说明](INTERACTION_MODES.md)：自由测试可切换 Four-strategy comparison / Selective conversation，研究按任务锁定。比较模式每次普通输入/追问/手动控件作用于全部分支；按钮只选查看视图，澄清答复仍绑定自己的提问。每轮等所有分支结束后统一揭示，首轮快照保持不变。

## 有效的研究与问卷版本

- [主设计](Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)：v1.7，四属性各四情境×两题＝32 题，之后一段 Selective 自然交流；5 次比较偏好及可选五选二访谈。
- [数据契约](Study/STUDY_DATA_PERSISTENCE_CONTRACT.md)：study-data-contract-v1。
- 运行资源：[任务](../../Assets/Project/Resources/Tutor/StudyTaskSequence.json)、[练习](../../Assets/Project/Resources/Tutor/PracticeTaskSequence.json)、[问卷](../../Assets/Project/Resources/Tutor/StudyQuestionnaires.json)。
- 四属性：attribute-feedback-v3，5 题（分类＋四项七点评分）。
- 自然模拟：natural-selective-feedback-v2，26 题（8 项项目反馈＋完整 SUS 10 题＋UEQ-S 8 题）。
- UI 资源：study-questionnaire-ui-v1；研究运行记录真实材料哈希。不把历史问卷答案重新解释为新版答案，也不计算混合总分。

## 实现说明

| 内容 | 文档 |
| --- | --- |
| 实验流程及问卷接线 | [Study flow](STUDY_FLOW_INTEGRATION.md) |
| 保存、导出、恢复与缺失 | [Persistence](STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md) |
| 对话记录 | [Dialogue logging](DIALOGUE_LOGGING.md) |
| 独立任务/问卷面板 | [Study panel](STUDY_QUESTIONNAIRE_PANEL.md) |
| 当前双模式与面板扩高 | [Interaction modes](INTERACTION_MODES.md) |
| ASR/TTS 与播放审计 | [Backend speech](STAGE_4_BACKEND_SPEECH.md)、[STT](STAGE_4_UNITY_STT.md)、[TTS](STAGE_4_UNITY_TTS.md)、[Playback](STAGE_4_PLAYBACK_AUDIT.md) |
| 自动真实语音/中断恢复 | [Recovery acceptance](STUDY_SPEECH_RECOVERY_ACCEPTANCE.md) |

最新本机人工检查包括 EDIFIER 麦克风转写、试听/播放、问卷保存并下一题、暂停/继续及口述备注确认。双模式路由/历史隔离与澄清屏障通过本机 fixture 检查；这不等于完整 32 题＋自然模拟的真人研究或头显全程测试。

## 历史材料阅读规则

Study 中的 PLANNING、THREE_STRATEGY、TASK_BANK_60、APPEARANCE_SCENARIO、QUESTIONNAIRE_CONTENT_PLAN、旧 v1.5 协议等保留设计演变；不得据此恢复已删题目或旧施测流程。STAGE_*、UNITY_COMPARISON、TASK_LIFECYCLE 等为阶段实现记录，可能含旧 UI、旧 API 使用方式与当时待办。遇冲突，研究内容以主设计/数据契约为准，当前运行行为以此导航、INTERACTION_MODES 和实际资源/代码为准。问卷预测试、正式时长/分配冻结和头显验收仍需后续完成。
