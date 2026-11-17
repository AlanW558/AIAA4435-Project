# 阶段四第三步：Unity 录音、STT 与对话提交

日期：2026-11-10。实现和本机模拟联调完成；真实麦克风、标准工作空间云端识别和 VR 头显验收仍待进行。本步骤不包含 Tutor 回答音频或 Play sample 播放。

## 参与者流程

Conversation 页底部沿用原有玻璃面板，在同一行放置 Record、识别文本和 Send。

1. 点击 **Record**。先检查后端是否启用识别，再申请系统麦克风权限。
2. 讲话后点击 **Stop**。最长录制约 119 秒；过短、无设备或权限未授权会显示错误，不提交 Tutor 请求。
3. 等待识别。**Cancel** 可以放弃；取消不保证已经发到提供商的请求停止计费。
4. 检查只读识别文本，点击 **Send** 提交，或者 **Record again** 重新录制。VR 路径不需要键盘；desktopDebugInput 仍保留工程文本输入。
5. 初始输入只调用一次 STT，随后使用原有 start 请求将同一份文本交给四策略。每次澄清回答只进入录音开始时对应的问题和策略分支。

识别完成本身不会执行任务，也不会向对话历史写入草稿。四策略结果仍必须等所有必要澄清和生成完成后统一显示。选择 Other 后仍可直接说话；自由语音回答由既有自然语言澄清解析器处理。

## 代码与接口

- `Assets/Project/Scripts/Tutor/TutorSpeechInput.cs`：权限、录音、单声道 PCM16 WAV 编码、STT 请求、识别预览、取消和提交。运行时由 TutorPanel 添加，无需修改已有场景组件。
- `Assets/Project/Scripts/Tutor/TutorPanel.cs`：录音按钮、只读预览及 Send，保留三页结构和现有风格。
- `Backend/tutor_transcription.py`：会话绑定、识别前后状态检查、重复请求去重、容量限制。
- `Backend/server.py`：语音状态与识别路由；`--speech-mode disabled|qwen`，默认 disabled。
- `ProjectSettings/ProjectSettings.asset`：填写麦克风用途说明。Android 走显式运行时权限请求，其他平台走 Unity 授权接口；平台最终权限和打包结果需要真机确认。

```text
GET  /speech/status
POST /tutor/comparisons/{task_id}/transcribe
POST /tutor/sessions/{session_id}/transcribe
```

识别请求字段：`request_id`、`expected_revision`、`condition`、`question_id`（无问题时空字符串）、`audio_base64`。返回仅包含最终 `text` 和应用请求 ID，不返回提供商原始响应、密钥或音频地址。此接口不自动触发模型对话；Send 使用既有 request/start/answer 接口。

只有这两个识别端点放宽 JSON 大小至 10,700,000 字节，其他接口仍为 65,536 字节。WAV 限制继承 speech.py：8 MB、120 秒、单声道 PCM16、16/24/48 kHz。Unity 请求 16 kHz 录音，并将设备返回的多声道样本混为单声道。

## 状态与重复提交保护

- 录音绑定服务器地址、任务/会话 ID、revision、所选策略及 question ID。切页、离座、暂停、退出、客户端停用或状态变化会取消录音/识别并清空预览。
- 当前采用保守的整任务 revision 检查：其他分支推进导致任务版本变化时，也可能要求重新录制。优先避免过期输入错配；真实实验前应观察是否频繁触发，再考虑引入独立输入上下文版本。
- 后端在识别前和返回前各检查一次；不在云端调用期间持有任务锁，因此暂停/结束无需等识别完成。
- 每次录音使用唯一 request ID。相同 ID、音频摘要和上下文的并发/重复请求只识别一次；失败也保留结果，不自动重试。复用 ID 传入不同音频/上下文报冲突。
- 每个服务器进程最多保留 4096 条识别结果/失败记录，达到上限拒绝新识别；不会通过淘汰旧 ID 导致重复计费。实验会话之间可重启服务器；该去重不跨服务重启。
- Unity 超时或取消后不自动重发、不回退其他模型；参与者可主动重录。请求已到提供商时，客户端取消无法保证停止计费。
- 此步骤没有 TTS 路由，`audio_available:false` 和禁用的 Play sample 保持准确。

## 记录范围

录音 AudioClip、PCM/WAV 和 Base64 仅用于内存内传输，不写音频文件或 JSONL。后端去重记录仅保留音频 SHA-256 摘要、上下文、识别文本或脱敏错误。结束/取消后释放录音对象及客户端引用；不承诺底层内存立即安全擦除。

点击 Send 后的最终 STT 文本进入已有对话日志，Tutor 输出继续按原有流程记录。放弃的预览不会进入对话日志。问卷 STT 尚未接入本入口，不能将问卷回答发到 Tutor 对话接口。

## 本机启用与验证

常规后端启动默认禁用语音，不会自动加载 `.env.qwen-token-plan`。真实识别需要在原有外置私有环境文件中配置标准工作空间的 `QWEN_API_KEY`、`QWEN_BASE_URL`，以及 `.env.example` 中的模型变量，然后给原启动脚本追加 `--speech-mode qwen`。密钥不放进 Unity 或聊天。现有私有 Token Plan 配置未改动、未再次调用；本次没有验证标准工作空间的实际模型授权。

本次验证：

- 363 项后端回归通过，其中新增 11 项识别边界/HTTP 测试；验证重复识别去重、暂停/恢复失效、错误处理、分支隔离、初始文本共享，以及提交文本入日志而音频不入日志。
- Unity 编译通过；26 项真实面板＋模拟 STT 检查通过，包含 WAV 编码、只读预览、手动提交、迟到响应隔离、切换策略/页面与暂停取消，以及最后一次澄清完成后统一显示结果。
- 原有 101 项 Unity 控件回归也通过，覆盖五音色、四属性、撤销和单会话路径。模拟服务故意丢弃一次控制请求响应产生 Curl error 52，恢复检查通过；未出现编译错误。
- 语音检查复跑时曾在其他分支尚未结束更新时过早选择策略，触发既有 revision 冲突保护；测试已改为等待所有初始分支离开 processing 后继续，随后 26 项通过。保留整任务 revision 保护的使用限制见上文。
- 模拟 fixture 使用 PCM 标记返回预设文本，不是语音识别准确率测试，没有调用麦克风或付费 API。
- `Backend/tests/unity_speech_fixture_server.py` 仅作工程测试，端口 8772。Unity Play 模式下在新建未连接的比较会话中添加 `TutorSpeechChecks` 运行；不得用于参与者实验。

证据保存至 `StudyData/validation/stage4-step3-20261110/`。原始面板结果位于 `StudyData/macos/tutor-speech-unity/`。

下一步为阶段四第四步：接入 Tutor 回答与 Play sample 的 TTS 播放，并按各回答的设置快照合成，结合统一展示限制避免提前播放任何策略结果。
