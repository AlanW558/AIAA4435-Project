# 阶段四第五步：四策略语音联调与播放日志

日期：2026-11-10。完成本地实现与模拟验收；没有付费 API 调用、真实麦克风录音或 VR 头显测试。本步骤没有修改研究问卷的题目或任务数量。

## 1. 新增记录及其含义

原有服务器记录 `audio_requested / audio_ready / audio_failed / audio_discarded` 保持独立。新增客户端 `playback_report`，包括：

| report.event | 含义 |
| --- | --- |
| started | 客户端调用 AudioSource 播放并报告开始 |
| stopped | 主动停止，或页面、任务、策略、录音、暂停等上下文变化导致中断 |
| completed | 客户端播放位置到达音频末尾并报告结束 |
| failed | WAV 解码失败，或播放非预期结束 |

所有报告显式标记 `client_reported_not_verified_hearing`。服务器准备好音频不等于客户端已播放；客户端播放结束也不能证明参与者实际听到、听清、理解或认同结果。这里的 completed 只指音频结束，不能替代参与者对任务完成情况的问卷回答。

事件包含稳定 event ID、原 audio request ID、客户端 UTC 时间、播放位置、经过时间和停止原因。任务、策略、回答 exchange ID、文字摘要、实际语音设置、task/branch/state revision 及 reveal ID 由服务器从原始 `audio_ready` 记录绑定，客户端不能自行指定这些归属。

播放结束判断已修正：Unity 的音频线程和主线程墙钟结束时间可能存在差异，不能只用“已过时长”判断。现在结合实际播放位置确认到达末尾；保留经过时间作为客户端运行记录，不用它测量实际 speech rate，也不把它当作问卷评分。

## 2. 可靠送达与跨任务隔离

新增接口：

```text
POST /tutor/comparisons/{original_task_id}/playback
POST /tutor/sessions/{original_session_id}/playback
```

请求字段固定为 `event_id`、`audio_request_id`、`event`、`reason`、`position_seconds`、`elapsed_seconds`、`client_time_utc`。未知字段、非法事件、无对应 ready 记录、越界位置和错误顺序均拒绝。相同 ID/内容的补传返回成功但不再次写日志；相同 ID 改内容则拒绝。

每次点击播放对应新的音频请求与播放生命周期；复播不能在同一个 audio request ID 下追加第二个 started。正常生命周期为一个 started 加一个 completed/stopped/failed；解码失败可以直接 failed。取消尚未准备完的音频不会伪造 started；继续由原有合成日志表示准备情况。

播放报告不修改任务状态，也不授予播放权限。允许在切换策略、暂停、提交/关闭任务或进入下一题后，向**原任务**补传已有播放事实。服务器仍独立阻止获取隐藏、过期或已关闭任务的新音频。

客户端使用持久待传队列：

- 每个事件保存为独立 JSON 文件，先写临时文件并 flush，再原子重命名，然后发送。重载时恢复完整临时文件及未确认事件。
- 成功确认后才删除本地待传文件；确认响应丢失时，使用完全相同的事件 ID 和内容重传。
- 队列对象跨场景保留；文件可在应用重启后重新载入。每条事件保留原后端地址和原任务路径，不跟随当前选中策略/任务重新绑定。
- 网络或存储失败会显示操作错误并保留待传记录，阻止开始新的音频播放，避免静默积累未记录的比较；正常情况下不增加日志开关、同意提示或额外操作。
- 队列达到 4094 条时暂停开始新播放，给已有播放的终止事件留出空间。失败请求以约 3 秒间隔重试，单次 HTTP 超时 8 秒。
- 本地仅保存事件标识、端点、路径和时间等元数据，不保存录音、WAV、Base64、对话文本或 API key。

Editor 的待传文件位于 `StudyData/macos/playback-outbox/`；打包后位于 `Application.persistentDataPath/TutorPlaybackOutbox/`。手机/头显上的持久目录和断电行为尚待实机验收。

服务器从原始 JSONL 恢复 audio 绑定和已接受 event ID。因此即使服务器正常重启、内存实验会话已经消失，只要使用原日志目录，仍可以接收历史补传。发现损坏/截断日志时返回错误，不跳过损坏行或伪造成功。此机制不恢复原任务的可交互状态。

无法保证应用崩溃前尚未形成的终止事件存在。只有 started 而没有终止事件时，应标为“播放结局缺失”，不能自动补成 completed。未完成的临时文件或损坏待传文件会阻止加载并提示研究者处理，原文件保留。

## 3. 对话、播放与反馈的关联

现有 `Backend/export_tutor_dialogue.py` 已扩展，导出结果同时包含音频准备事件与客户端播放报告，无需另建一套调查数据。

关联时建议使用：

1. `task_id / session_id`、`condition`：参与者对应任务与策略；`purpose` 区分 sample 和 reply。
2. `audio_request_id`：从合成准备到播放开始、结束/停止的完整链；`event_id` 用于事件去重。
3. `exchange_id`、`text_sha256`、`speech_settings`：确定播放了哪一份回答，以及使用何种语音设置。
4. `branch_revision / state_revision / reveal_id`：与 `feedback_saved` 导出的 draft 对照，区分首次揭示及后续修改后的结果。

固定 sample 不能算作参与者已听过该策略的回答。多次试听和复播也不能当成不同参与者或独立任务数据。反馈是否合理、一致仍需研究分析，不由播放日志自动判定。

延迟上传时，服务器接收时间不等于客户端发生时间。保留 `client_time_utc`；`receipt_run_id` 区分接收进程，不能跨进程直接比较 `monotonic_seconds`。客户端时钟也不是已校准的独立测量仪器。

本次工程导出样例：`StudyData/validation/stage4-step5-20261110/dialogue-playback-evidence.jsonl`，共 63 条证据行；`playback-summary.json` 汇总了 12 条不重复播放事件（6 started、5 stopped、1 completed）、四份工程反馈和一次任务提交。全部为模拟验证数据，不能混入正式参与者分析。

## 4. 实现文件

- `Backend/tutor_playback.py`：持久日志绑定、校验、顺序约束、幂等接收和历史补传。
- `Backend/tutor_audio.py`：补充回答/揭示版本与音频长度元数据，不测量合成语速。
- `Backend/tutor_dialogue_log.py`、`server.py`：统一导出与播放报告路由。
- `Assets/Project/Scripts/Tutor/TutorPlaybackOutbox.cs`：本地持久队列与确认后清理。
- `TutorAudioPlayback.cs`、`TutorPanel.cs`、`TutorSpeechInput.cs`：播放事件、停止原因、录音互斥和传输异常提示。

## 5. 验证结果

- 386 项后端测试通过，新增 11 项播放日志测试。覆盖重复/并发补传、关闭后归属、服务重启后的绑定恢复、错误顺序/时长/字段拒绝、损坏日志保护、单会话与四策略路径、统一导出。
- Unity 编译通过，51 项整段联调检查通过：模拟 STT 初始输入共享、分别语音回答 A/S 澄清、统一揭示、四策略播放比较、自然结束/主动停止/暂停、工程反馈提交和进入下一题。
- 原有 43 项播放回归检查通过，包含缓存复用、旧回答设置快照、合成失败、迟到音频丢弃与录音互斥；回归后待传队列为 0，最终 Unity Console 没有错误。
- 特意丢弃第一次播放报告确认，观察到预期 Curl error 52；随后销毁并重建客户端待传组件，两个事件由磁盘重新载入，重传后只记录一次。
- 最终原任务有 12 个唯一播放 event ID，新任务没有接收到旧任务的播放事件，所有待传 JSON 文件已确认清空。
- 首轮联调发现正常结束判断过于依赖墙钟，修正后整段联调通过。失败运行的原始日志仍保留，不作为通过证据。

模拟服务为 `Backend/tests/unity_playback_fixture_server.py`（8774），对应 `TutorPlaybackChecks`。输出使用静音 WAV，问卷使用明确标记的工程测试值；不调用云端，不采集真实音频。

证据目录：`StudyData/validation/stage4-step5-20261110/`。

收尾已停止 Unity Play mode 与 8773/8774 临时模拟服务。未修改私有凭证，没有 Git 提交或推送。

## 6. 后续边界

本地语音输入、回答/试听播放、四策略展示限制和文本/播放日志已经连通。真实标准工作空间的模型授权、真实麦克风识别、五音色的实际听感、语气差异，以及 VR 权限/音频输出仍未验收。澄清提问目前仍为文字，参与者的回答使用 STT；本步没有擅自加入提问自动朗读或四策略自动播放。

下一步适合做本机真实语音链路验收与剩余功能清单核对，继续遵守“先本地实现，再 VR 实机测试”的顺序。任务库和问卷缩减方案仍需后续单独确认，不在本轮改动。
