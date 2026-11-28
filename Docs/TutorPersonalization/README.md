# Tutor 实现与研究导航

更新：2026-11-28。研究入口当前创建 engineering 运行，最新头显整体验收和正式采集设置尚未完成。此前[打包前本机验收](PRE_HEADSET_ACCEPTANCE_20261127.md)覆盖完整流程、真实 API 代表性用例及中断恢复。已发布的真实四属性辅助输出与本次四人外观反馈见[实验数据入口](../../Experiments/README.md)。历史[生成回复与属性确认修订](Study/GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)记录当时的本机实现验收范围。

## 当前入口与行为

启动、依赖和新 VR 构建步骤见[根 README](../../README.md)。优先使用 `TutorFreeTestDesktop/VR` 自由测试；`TutorComparisonDesktop/VR` 为研究控制流程。`TutorPersonalizationDesktop/VR` 保留为早期单会话入口。

[双模式说明](INTERACTION_MODES.md)：自由测试可切换 Four-strategy comparison / Selective conversation，研究按任务锁定。比较模式每次普通输入/追问/手动控件作用于全部分支；按钮只选查看视图，澄清答复仍绑定自己的提问。每轮等所有分支结束后统一揭示，首轮快照保持不变。

## 当前研究设计与已实现的问卷版本

- [主设计](Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)：v2.0，四属性＋外观五模块各八题，共40题；100项评分、5项模块偏好及1项总体偏好。自然情境仅作demo。此为最新研究范围，**程序仍是32题＋自然评估的旧调度，尚待接入新流程**。
- [外观八题与问卷审核](Study/APPEARANCE_PARALLEL_STUDY_REDESIGN.md)：八题目标与保持要求已确认，统一现有男性模型，“更休闲”不限定运动服；已采集47张Unity真实图像，HTML采用20评分及一次多选偏好。
- [外观独立反馈与汇总](../../Experiments/appearance/README.md)：P001–P004四份最终反馈，评价同一套八题/32结果材料；当前12次澄清来源为用户授权助手代拟。每题四个独立状态、无跨题继承；[P4-1修订记录](Study/APPEARANCE_HISTORY_REFERENCE_FIX.md)保留版本依据。
- [40题完整任务库](Study/CURRENT_TASK_BANK_40.md)：逐题Task goal、Keep unchanged、Request example，前台编号各情境1/2。
- [当前问卷与数据规范](Study/CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)：准确英文题干、独立模块保存与汇总边界；[原Unity数据契约](Study/STUDY_DATA_PERSISTENCE_CONTRACT.md)保留旧实现兼容规则。
- 现有Unity运行资源（仍含旧自然调度）：[任务](../../Assets/Project/Resources/Tutor/StudyTaskSequence.json)、[练习](../../Assets/Project/Resources/Tutor/PracticeTaskSequence.json)、[问卷](../../Assets/Project/Resources/Tutor/StudyQuestionnaires.json)。
- 四属性：`attribute-summary-feedback-v3`，每个属性八题后填写四策略 × 5 道 1–7 评分（A0–A4），再提交一项可多选的属性偏好。偏好可选1–4个E/A/N/S或互斥No preference；A0–A4自己的Unable to judge保留。Unity偏好版本为`strategy-preference-v2`。
- 历史自然模拟资源：natural-selective-feedback-v2，26题；保留旧读取能力，新实验不再施测。Selective conversation功能保留用于demo。
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

Study 中的 PLANNING、THREE_STRATEGY、TASK_BANK_60、APPEARANCE_SCENARIO、QUESTIONNAIRE_CONTENT_PLAN、旧 v1.5 协议等保留设计演变；不得据此恢复已删题目或旧施测流程。STAGE_*、UNITY_COMPARISON、TASK_LIFECYCLE 等为阶段实现记录，可能含旧 UI、旧 API 使用方式与当时待办。遇冲突，研究内容以主设计/当前问卷与数据规范为准，当前运行行为以此导航、INTERACTION_MODES 和实际资源/代码为准。问卷预测试、正式时长/分配冻结和头显验收仍需后续完成。
