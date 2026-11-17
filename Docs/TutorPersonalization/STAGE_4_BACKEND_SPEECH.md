# 阶段四第二步：五音色与后端语音服务模块

日期：2026-11-10。本步骤完成内部 Python STT/TTS 适配和五音色状态/面板调整。Unity 录音、播放及对外语音 HTTP 路由尚未接入，不将本模块完成等同于整条语音交互可用。

## 1. 已确认的最终五音色

用户确认保留此前 B/C/D/G/H，并要求重新依次编号 A/B/C/D/E。默认选择此前 G，因此现在默认 **Voice D**。下面按音色身份映射，不能将旧记录里的字母当作新字母解释。

| 当前名称 / ID | 原试听编号 | 音色 | 提供商 voice ID |
| --- | --- | --- | --- |
| Voice A / voice_a | B | Long An Lingxin | longanlingxin |
| Voice B / voice_b | C | Long An Huan | longanhuan_v3.6 |
| Voice C / voice_c | D | Olivia Lin | qwen-audio-3.0-tts-plus-loongolivialin |
| **Voice D / voice_d（默认）** | **G** | Adrian Gao | qwen-audio-3.0-tts-plus-loongadriangao |
| Voice E / voice_e | H | James Zhao | qwen-audio-3.0-tts-plus-loongjameszhao |

原始试听音频、JSON、旧页面和阶段记录保持原编号，不覆盖历史证据。当前映射版本为 `speech-selected-v2`，状态 schema 升级为 `tutor-state-v3`，能力版本 v2，解释器 v5。旧会话为内存状态；更新服务后应新建会话，不能将旧 ID 数据直接导入当前 schema，也不做隐式重命名迁移。

后端枚举和新会话默认值、自然语言解释提示、单会话及四策略客户端、面板按钮与选中态已同步。五按钮沿用原有 Voice 行，在同一宽度内等分，没有改变三页结构、颜色或玻璃样式。选择音色不修改 Tone/rate/Reply length。

权威执行映射：[tutor_voice_catalog.py](../../Backend/tutor_voice_catalog.py)。文档映射：[STAGE_4_SPEECH_PROFILE.json](STAGE_4_SPEECH_PROFILE.json)。音色偏好已确认，G/H 等新声音在 Friendly/Encouraging 下的可辨识度尚未进行人工验收，不虚构“温暖”“低沉”等自然语言匹配依据。

## 2. 服务模块接口

[speech.py](../../Backend/speech.py) 提供：

```python
config = SpeechConfig.from_env()
speech = SpeechService(config)
transcript = speech.transcribe(wav_bytes, cancel=cancel_event)
rendered = speech.synthesize(answer_text, answer_settings_snapshot, cancel=cancel_event)
audio_bytes = rendered['audio']
speech.clear_cache()
```

这是服务器内部接口，不是直接暴露给头显的无鉴权音频端点。后续 HTTP 接线必须绑定会话、请求和分支，经过统一结果展示限制后才能发送音频。当前旧接口仍返回 `audio_available:false`，Play sample 仍禁用。

### STT

- `qwen-audio-3.0-asr-flash`，DashScope HTTP 协议；仅提交一次，不自动重试。
- 本步骤接受非空、单声道 PCM16 WAV，16/24/48 kHz，上限 8 MB、120 秒；这是应用侧限制，不声称是模型的最大能力。
- 显式英语识别；返回最终文本及脱敏请求 ID/用量，不把录音、Base64、签名链接或提供商完整响应返回到上层日志。
- 识别为空时报 `no_speech`；损坏/截断音频、超限录音、异常响应不会变成有效参与者请求。
- 录音仅存在于调用所需的内存中，不写文件、不放入缓存；Python 内存释放不等同于内存安全擦除。提供商保留政策仍需在部署时核对。
- 本步尚未自动向 Tutor 发送识别文本；第三步统一接入一次识别、一次用户提交、四策略共享，并关联已有文本日志。

### TTS

- `qwen-audio-3.0-tts-plus`，五音色映射、三种 instruction 模板，直接提交已算好的语速倍数。
- 校验应用的 0.70–1.30/0.01 精度；固定 pitch=1、WAV 24kHz，其余参数继承第一步选型配置。
- 从传入的回答设置快照复制参数，不读取随后变化的当前面板设置；不重新调用 DeepSeek，不重写回答文字。
- 下载提供商生成音频时不携带 API key。只接受阿里云域名的资源 URL；HTTP 返回地址升级到同一资源的 HTTPS；禁止重定向。下载大小及 WAV 完整性均验证后才返回。
- LRU 内存缓存上限 32 条/32 MB；缓存包含 endpoint、model、profile version、text、voice、rate、Tone 指令、seed、音频格式等全部实际合成参数。相同文本但不同声音/语气/语速不能混用。Reply length 改变但实际文字完全相同，则可以复用音频。
- 缓存响应和设置脱离内部对象；并发相同请求只合成一次。本版本串行化 TTS 合成以确保去重，性能优化留待实际延迟证据。

## 3. 错误、取消与配置

- `SpeechError.code` 表达连接、HTTP、格式、取消等错误；不输出密钥、签名 URL 或原始错误正文。HTTP 状态可用于区分认证失败与限流。
- 没有自动重试、备用账户或模型降级。失败后由后续交互层明确重试。
- 取消在调用前、等待缓存锁期间、提供商返回后、音频下载后生效；取消结果不进入缓存，也不返回可播放音频。
- 取消不保证中断已经发出的网络请求，亦不保证免计费；单个网络操作有 1–60 秒可配置超时，默认 30 秒。生成和下载分别受超时限制，不是整个流程只需 30 秒。
- 新变量：`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_ASR_MODEL`、`QWEN_TTS_MODEL`、`QWEN_TIMEOUT_SECONDS`，模板见仓库 `.env.example`。普通工作空间地址与密钥必须匹配地域。
- 现有 `.env.qwen-token-plan` 只用于已授权工具内试听；正式服务不自动读取它。本轮没有替换、输出或再次使用真实密钥，没有新增付费调用。
- 标准工作空间凭证尚未配置，内部适配器已用模拟传输验收；不声称标准 API 的五音色和参数已实际调用通过。

## 4. 验证

[test_speech.py](../../Backend/tests/test_speech.py) 覆盖五音色/default、旧选项拒绝、缓存隔离与淘汰、快照不可变、并发去重、取消前后、空/坏音频、英文识别请求、错误脱敏及下载凭证隔离。

系统自带 Python 3.9 不满足项目原有 Python 3.10+ 要求；本轮使用已安装的 Python 3.12 运行。回环 HTTP 测试需要允许本机端口。初次环境失败未记作测试通过。

最终测试结果在本文件末尾记录。后续第三步为 Unity 麦克风/STT 和文本提交接线，第四步接正式回答与 Play sample 播放，第五步再完成四策略音频展示限制及日志联调。

### 最终结果

- 352 项后端测试通过（原 331 项迁移到当前编号/默认值，新增 21 项语音服务检查）。
- Unity 当前项目编译通过，运行时目录返回 A/B/C/D/E。
- 101 项真实面板＋本机模拟 HTTP 控件检查通过，包含五个选项逐一选择和高亮、默认值、四策略隐藏状态、丢失响应恢复、切换/暂停、撤销及单会话路径。
- 已查看本轮 Controls 截图：五个按钮在既有 Voice 行内可见，无横向溢出；原有三页和玻璃样式保留。截图显示测试中切换到 A 的状态，不是默认值截图；默认 D 由后端及分支隔离检查确认。
- 模拟后端故意丢弃一次响应，因此出现一次 Curl error 52，随后恢复检查通过。没有编译错误或其它未处理运行错误。
- 证据：`StudyData/macos/tutor-controls-unity/checks.txt`、`controls.png`、`history.png`；后端运行摘要另存 `StudyData/validation/stage4-step2-20261110/`。
- 验收结束已停止 Play mode 与 8771 模拟服务。无 VR 头显测试，无新增云端调用，无 Git 提交/推送。
