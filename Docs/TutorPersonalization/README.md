# Tutor 实现与研究导航

更新：2026-11-27。研究入口当前创建 engineering 运行，最新头显整体验收和正式采集设置尚未完成。此前[打包前本机验收](PRE_HEADSET_ACCEPTANCE_20261127.md)覆盖完整流程、真实 API 代表性用例及中断恢复。本次[生成回复与属性确认修订](Study/GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)采用本地 fixture 验证，尚未重跑真实四属性输出。

## 当前入口与行为

启动、依赖和新 VR 构建步骤见[根 README](../../README.md)。优先使用 `TutorFreeTestDesktop/VR` 自由测试；`TutorComparisonDesktop/VR` 为研究控制流程。`TutorPersonalizationDesktop/VR` 保留为早期单会话入口。

[双模式说明](INTERACTION_MODES.md)：自由测试可切换 Four-strategy comparison / Selective conversation，研究按任务锁定。比较模式每次普通输入/追问/手动控件作用于全部分支；按钮只选查看视图，澄清答复仍绑定自己的提问。每轮等所有分支结束后统一揭示，首轮快照保持不变。

## 有效的研究与问卷版本

- [主设计](Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)：v1.9，四属性各四情境×两题＝32 题，之后一段 Selective 自然交流；5 次比较偏好及可选五选二访谈。
- [数据契约](Study/STUDY_DATA_PERSISTENCE_CONTRACT.md)：study-data-contract-v1。
- 运行资源：[任务](../../Assets/Project/Resources/Tutor/StudyTaskSequence.json)、[练习](../../Assets/Project/Resources/Tutor/PracticeTaskSequence.json)、[问卷](../../Assets/Project/Resources/Tutor/StudyQuestionnaires.json)。
- 四属性：`attribute-summary-feedback-v3`，每个属性八题后填写四策略 × 5 道 1–7 评分（A0–A4），再提交一项可多选的属性偏好。偏好可选1–4个E/A/N/S或互斥No preference；A0–A4自己的Unable to judge保留。Unity偏好版本为`strategy-preference-v2`。
- 自然模拟：natural-selective-feedback-v2，26 题（8 项项目反馈＋完整 SUS 10 题＋UEQ-S 8 题）。
- UI 资源：study-questionnaire-ui-v2；研究运行记录真实材料哈希及问卷/偏好版本。旧属性v1分类、v2数字A0与单选偏好仍按原版本读取；当前v3多选不自动转换旧答案。不把历史问卷答案重新解释为新版答案，也不计算混合总分。

控件先选择、再点击 **Confirm changes** 一次提交四项配置；不再提供固定 Play sample。音色显示为 Female voice 1/2/3、Male voice 1/2，默认 Male voice 1。任务卡使用 Task goal、Keep unchanged、Request example。

## 实现说明

| 内容 | 文档 |
| --- | --- |
| 实验流程及问卷接线 | [Study flow](STUDY_FLOW_INTEGRATION.md) |
| 保存、导出、恢复与缺失 | [Persistence](STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md) |
| 对话记录 | [Dialogue logging](DIALOGUE_LOGGING.md) |
| 独立任务/问卷面板 | [Study panel](STUDY_QUESTIONNAIRE_PANEL.md) |
| 左侧自适应尺寸与暖色风格（2026-11-26） | [Adaptive study panel](ADAPTIVE_STUDY_PANEL.md) |
| 当前双模式与面板扩高 | [Interaction modes](INTERACTION_MODES.md) |
| ASR/TTS 与播放审计 | [Backend speech](STAGE_4_BACKEND_SPEECH.md)、[STT](STAGE_4_UNITY_STT.md)、[TTS](STAGE_4_UNITY_TTS.md)、[Playback](STAGE_4_PLAYBACK_AUDIT.md) |
| 自动真实语音/中断恢复 | [Recovery acceptance](STUDY_SPEECH_RECOVERY_ACCEPTANCE.md) |
| 打包前本机验收（2026-11-27） | [Pre-headset acceptance](PRE_HEADSET_ACCEPTANCE_20261127.md) |
| 新版 USB 构建及 APK 检查 | [TutorBuild](../../Tools/TutorBuild/README.md) |
| 头显连接、安装、日志取回与联合导出 | [TutorDevice](../../Tools/TutorDevice/README.md) |
| USB 接入前准备与 APK 交付结果（2026-11-27） | [USB device preparation](USB_DEVICE_PREPARATION_20261127.md) |

最新本机人工检查包括 EDIFIER 麦克风转写、试听/播放、问卷保存并下一题、暂停/继续及口述备注确认。双模式路由/历史隔离与澄清屏障通过本机 fixture 检查；这不等于完整 32 题＋自然模拟的真人研究或头显全程测试。

## 历史材料阅读规则

Study 中的 PLANNING、THREE_STRATEGY、TASK_BANK_60、APPEARANCE_SCENARIO、QUESTIONNAIRE_CONTENT_PLAN、旧 v1.5 协议等保留设计演变；不得据此恢复已删题目或旧施测流程。STAGE_*、UNITY_COMPARISON、TASK_LIFECYCLE 等为阶段实现记录，可能含旧 UI、旧 API 使用方式与当时待办。遇冲突，研究内容以主设计/数据契约为准，当前运行行为以此导航、INTERACTION_MODES 和实际资源/代码为准。问卷预测试、正式时长/分配冻结和头显验收仍需后续完成。
