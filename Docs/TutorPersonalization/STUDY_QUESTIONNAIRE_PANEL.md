# 独立实验面板与四属性问卷接入

> 后续实现（2026-11-11）：属性末偏好、四属性总体偏好与跨模块导航已接入，见[偏好与模块导航说明](STUDY_PREFERENCES_AND_MODULES.md)。默认清单现为四属性共八道练习，正式 32 题另行接入；下文未接入偏好的描述为前一阶段记录。

日期：2026-11-11。状态：本地实现、编译、模拟 HTTP/STT 联调及截图检查完成；尚未进行真实麦克风/云端整段联调或头显验收。

## 已完成的参与者流程

- 系统面板继续提供 Conversation / Controls / History、属性调节、语音对话与结果播放。
- 新增独立的 `Study · Task & feedback` 面板，包含 Task instructions / Questionnaire / Optional notes。任务说明、开始/继续任务、逐策略问卷、反馈提交/下一题、暂停和退出均在实验面板上。
- 使用不透明暖白纸色和深色文字，选择项以青绿色强调。面板是系统面板的同级对象，不继承系统玻璃背景。
- 顶部外置 Show/Hide study panel 按钮始终保留（坐下时可用）；隐藏不提交、不清空评分。离开座位时两块面板均停止接受点击。显示位置固定，不跟随头部转动。
- 基于座椅眼点和 tutor 的水平方向定位：左移 0.50 m、前移 1.65 m、中心低于眼点 0.10 m；面板朝向眼点，尺寸约 0.738×0.945 m。偏移可通过 `TutorPanel.studySeatOffset` 调整。
- 已读取实际 VR 场景：座椅眼点 (0, 1.20, -0.80)，计算的实验面板中心约 (-0.84, 1.10, 0.70)；相对正视 tutor 方向约左侧 16.9°，系统面板约右侧 45.4°。此为场景几何核对，不是头显可读性结论。
- 问卷策略选择与系统结果选择同步，避免看着一个策略却给另一个打分。任务详情仍沿用原有输入保护，点击 Continue task 后继续原澄清/交流。

## 四属性问卷

新创建的 Unity 比较任务声明 `attribute-feedback-v2`。每策略必答：完成情况分类＋effort_ease / control / clarification_appropriateness / satisfaction 四项 1–7 评分。每项支持显式 Unable to judge，不预填中点，不加入打断感。

本地未保存草稿按任务和策略区分；可切换、隐藏面板及重看结果，答案保留。每个策略点击 Save this rating 后等待后端确认；四份当前有效评价全部保存，且没有未保存修改，才能 Submit feedback & next task。末题显示 Submit task feedback，随后仍停在偏好环节等待后续实现，不假装实验全部结束。

结果或交互版本变化时，旧评价需要重新确认；重看/重听本身不清空答案。分类未达到要求仍可提交，提交不等于成功。暂停和退出不依赖问卷完整。

Optional notes 提供条件原因和口述备注：非 Fully met 才启用原因；not_maintained 只有实际后续交流后才启用。所有完成类别都可附加评论，原因和备注不强制填写。改选 Fully met 清除不再适用的原因。

## 独立问卷 STT

- 复用瞬时录音与权限处理，但使用独立 `/tutor/comparisons/{task_id}/survey-transcribe` 路径和独立请求去重空间。
- 校验当前任务、选中策略、分支版本、结果已展示且稳定、未暂停/关闭；客户端同时绑定当前反馈版本和备注页。
- 转录返回后先供参与者检查，点击 Use text 才进入问卷草稿，Save this rating 才保存到后端。可重录或放弃。
- 未确认文本不自动保存，问卷文字不调用 SubmitUserUtterance、不进入 tutor 上下文。切策略/任务、隐藏、暂停或失效的迟到返回会取消转录绑定。
- 录音期间暂停 tutor 播放并避免两处麦克风并发。不保存参与者原始音频。

## 版本和后端范围

`Backend/tutor_feedback.py` 支持：

- 旧 `task-feedback-q1-q7-v1`：保留给历史工程测试，未迁移或重标旧记录。
- 新 `attribute-feedback-v2`：新 Unity 比较任务使用，下一题继承同版，反馈/提交日志携带版本。
- `natural-selective-feedback-v1`：已实现 goal_fit＋五项评分的独立校验函数，包含 interruption；**尚未接自然会话提交路由或 VR 会话问卷页面**，由后续自然情境模块接入。不能用它创建四策略比较任务。

后端默认创建版本仍兼容旧工程调用；Unity 明确请求新版。历史六项评分的 Unity 工程检查显式选择旧版本；导航检查改用新版四项字段。正式采集入口依然未开放，本次联调是 debug/practice。

## 验证

- 416 项后端测试通过；新增 11 项覆盖版本混用拒绝、缺答/无法判断、自然问卷与四属性分离、版本继承、评分失效、评论确认及 STT 隔离/过期处理。
- 136 项 Unity 检查通过：独立布局、折叠、无默认评分、保存门槛、策略切换、更新结果重新确认、语音备注确认、迟到转录取消、下一题隔离和可见文本高度。
- 故意丢失一次已成功保存的反馈响应，原请求重试后恢复；没有重复创建反馈版本。Console 中对应一次预期 Curl error 52，不将它描述为真实服务故障或“测试全程零日志错误”。
- 日志检查：四份提交反馈，七次明确保存（包括评分修改和结果重新确认）；备注仅在反馈记录，未进入策略结果/对话；无 audio_base64。
- 截图检查修正完成情况题干裁切、7 与 Unable to judge 按钮间距；按正视 tutor 的方向定位，避免面板遮住 tutor 脸部。截图均为工程模拟答案。
- 新增云调用 0，真实麦克风录音 0；未进行头显测试。

证据：`StudyData/validation/questionnaire-20261111/` 中 summary.json、backend-tests.txt、unity-checks.txt、task-audit.jsonl、questionnaire-panel.png 和 questionnaire-closeup.png。较早的 task-panel.png 是调整布局前的截图，最终布局以 questionnaire 图片为准。

## 重跑与后续

1. 使用项目 Python 运行 `Backend/tests/unity_questionnaire_fixture_server.py`（localhost:8776，纯模拟）。每次测试重新启动，重置一次丢失反馈响应的注入。
2. 新的 TutorComparisonDesktop Play 会话中选择 `AIAA4435 > Tutor > Comparison > Run Questionnaire Checks (Play mode)`。
3. 结束检查后停止 Play 和模拟服务器；不将模拟答案用于研究结果。

下一步：实现四次属性末偏好与一次比较总体偏好、跨模块导航。随后接正式 32 题的起点/历史/音色素材，再接 Selective 自然情境和其专用问卷。

仍有边界：当前仅两题练习清单；草稿保留于本次运行内，整个实验的重启恢复未完成；正式任务准备基线限制、偏好采集和自然情境外层未完成。实际麦克风/服务商识别效果、VR 射线点击和文字舒适度须后续验收。
