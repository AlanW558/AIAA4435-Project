# 阶段四第四步：Tutor 回答与 Play sample 播放

日期：2026-11-10。完成本地实现与模拟验证。真实云端 TTS、人工听感和 VR 头显测试尚未进行；本轮没有付费 API 调用，也没有采集真实麦克风录音。

## 1. 面板行为

- **Controls / Play sample**：使用当前已确认的 speech rate、tone、voice，朗读固定句子 “Let's explore this idea together, one step at a time.”。Reply length 不影响这句话。试听行仍保持原有高度与右侧按钮，未压缩四属性控件。
- **Conversation / Play reply**：播放当前所选策略的最新教学回答，使用该回答生成时保存的属性快照。后续修改当前设置，不会重配旧回答的声音；包括仅下一回答生效的临时设置。
- 点击播放后显示准备状态，按钮变为 **Cancel audio**；播放时变为 **Stop sample / Stop reply**。失败显示提示，参与者可主动重试；不自动换模型或音色。
- 暂时采用参与者主动点击播放，不在四策略揭示时自动按某个顺序朗读。这样可自行反复比较，也不会让四份音频重叠。
- 切页、切换策略、属性提交、暂停、结束、离座、组件停用或开始录音会停止播放/准备，并丢弃迟到结果。Resume 不自动播放旧音频。
- 澄清期间不播放未揭示的回答，也不使用分支私有设置试听。澄清问题本步仍保持文字显示；Play reply 只对应已生成的教学回答，不是所有界面消息的通用朗读器。

五音色保持 A/B/C/D/E，默认 **Voice D**。Reply 音频状态显示实际快照中的音色、语气和语速，Sample 显示当前设置。Unity 的 pitch 固定为 1，语速只在模型合成参数中应用一次。音频使用统一的 2D AudioSource，以减少空间位置对比较造成的影响；头显输出效果待验证。

## 2. 后端接口与统一展示限制

```text
POST /tutor/comparisons/{task_id}/audio
POST /tutor/sessions/{session_id}/audio
```

请求只接受：`request_id`、`expected_revision`、`condition`、`purpose`（sample/reply）、`exchange_id`（sample 为 0，reply 指定历史回答 ID）。服务器不接受客户端提供朗读文字或设置，避免绕过正式记录生成不一致的音频。

成功返回 `audio/wav`，`Cache-Control: no-store`；失败返回既有 JSON 错误格式，不包含提供商响应、地址或凭证。

`Backend/tutor_audio.py` 从权威公开视图解析音频目标：

1. 检查任务版本、当前策略与生命周期。
2. 初始任务仅允许公开 baseline 的试听；进入策略执行后，必须 results_visible 且当前分支 ready/stopped，才能试听或播放回答。
3. Reply 只能引用当前可见分支 conversation 中的回答；文字和设置均从该条记录取值。
4. 合成后再次检查上下文。等待期间暂停、切换或更新状态时，不把过期音频发给 Unity。

统一展示保护直接覆盖音频路由，不只依靠隐藏按钮。没有预先合成/播放隐藏回答，也不读取其它策略的私有 TutorSession。

## 3. 合成、缓存与资源

- 复用已有 `SpeechService.synthesize`，模型仍为 `qwen-audio-3.0-tts-plus`，voice/rate/tone 映射继承阶段四第二步。
- 相同文字、音色、语速、tone 指令、模型、端点及固定参数使用已有 32 条/32 MB 内存缓存；Reply length 只有改变实际回答文字时才影响音频。缓存命中前仍执行可见性检查。
- 不重新调用 DeepSeek，不改写已提交的回答，不修改任务 revision 或对话历史。合成失败不回滚/替换文字结果。
- 缓存淘汰或服务器重启后，再次点击播放可能需要重新合成。失败不会自动重试；明确重试可能产生新的提供商调用。客户端取消无法保证终止已开始的云端计费。
- Unity 仅保留一份活动 AudioClip；停止时销毁，并中止未完成的 UnityWebRequest。WAV 解码检查 RIFF/chunk 边界、mono PCM16、16/24/48 kHz、数据完整性与 8 MB 上限，拒绝坏音频。
- 本步不保存 WAV 文件。模拟检查使用静音 WAV，因此只能证明播放状态/资源流程，不能证明人耳实际听感。

## 4. 状态与日志

只有后端实际注入可用的合成服务时，HTTP 会话视图的 `audio_available` 才为 true；Unity comparison projection 已传递此标记。无服务时试听/回答播放禁用，并继续显示 Audio not connected。

单会话生成结果中的 `audio_status` 在服务启用时为 `available_on_request`；这不代表已合成，更不代表参与者已听完。

后端记录 `audio_requested`、`audio_ready`、`audio_failed`、`audio_discarded`，关联 task/session、condition、exchange ID、音频请求 ID、revision、文字 SHA-256、三项语音设置和缓存命中状态。日志不包含音频、Base64、提供商原始响应或密钥。

**audio_ready 只能证明服务器已准备音频，不能当作参与者已经播放或听完的证据。** 客户端播放开始、主动停止、播放结束及其与反馈的关联，留待阶段四第五步的日志联调补齐。

## 5. 配置与验证

保留上一阶段启用方式：在外置私有配置中准备标准工作空间的 QWEN 配置，再用原启动脚本追加 `--speech-mode qwen`。默认 disabled。没有自动载入或使用 `.env.qwen-token-plan`，没有把凭证放入 Unity。当前真实标准 API 可用性仍待配置后验证。

实现文件：

- `Backend/tutor_audio.py`：权威目标解析、前后状态检查、日志。
- `Backend/server.py`、`tutor_session.py`、`tutor_comparison_service.py`：路由、运行时能力标记和生成状态。
- `Assets/Project/Scripts/Tutor/TutorAudioPlayback.cs`：下载、PCM WAV 解码、单音频播放、取消与释放。
- `TutorPanel.cs`、`TutorComparisonClient.cs`、`TutorSpeechInput.cs`：面板入口、能力透传及录音互斥。

验证：

- 375 项后端测试通过，其中本步新增 12 项 TTS 边界/HTTP 测试；包含隐藏结果拒绝、客户端伪造目标拒绝、单次回答临时设置快照、旧回答与当前试听分离、暂停期间合成结果丢弃及日志字段。
- Unity 编译通过，43 项静音音频检查通过：实际 AudioSource 播放/停止、WAV 解码、缓存复用、无自动播放、切换策略/页面取消、失败提示、STT 互斥、暂停与结束等。
- 原有 101 项 Unity 控件检查通过，包括五音色和四属性、撤销、单会话，以及模拟丢失控制请求响应后的恢复。该故障注入产生预期的 Curl error 52，恢复后检查通过。
- 原有 26 项 STT 流程检查再次通过：录音文本预览、初始文本共享、澄清分支隔离和迟到结果取消不受播放功能影响。
- 已查看 Controls 播放截图，试听行高度与四属性布局保留，播放状态和五个音色按钮可见。
- 工程 fixture：`Backend/tests/unity_audio_fixture_server.py`（8773），Voice C 人为延迟，Voice E 人为失败；这些故障仅在模拟服务中注入，不代表真实音色不可用。只供 `TutorAudioChecks`，不得用于参与者实验。

证据目录：`StudyData/validation/stage4-step4-20261110/`；原始 Unity 检查与截图在 `StudyData/macos/tutor-audio-unity/`。

收尾已停止 Unity Play mode 和本轮三个本机 fixture。无 Git 提交/推送，未修改私有凭证。

下一步：阶段四第五步的四策略语音联调与播放日志，补齐客户端播放事件，并验证语音输入、澄清、统一揭示、反复比较和后续反馈之间的关联。VR 实机与真实听感验收继续按既定安排留到本地实现之后。
