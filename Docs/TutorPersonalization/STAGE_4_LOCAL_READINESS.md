# 阶段四：本地完整性核对与真实语音格式验证

日期：2026-11-10。范围：核对剩余实现、验证实际服务商音频格式和一次工具内 ASR 请求；不进行头显测试，不修改实验题目，不更换模型或五种音色。

**后续实现进展：** 共享准备阶段已完成，支持确认前四属性调节/试听、共同起点锁定与确认后语音提问。验收及接口见 [SHARED_PREPARATION.md](SHARED_PREPARATION.md)；下文功能表中“准备流程未完成”为初次核对记录。

**最新配置状态（用户后续明确要求沿用原密钥）：** 已把本机 `.env.qwen-token-plan` 中的现有凭证及配套 Endpoint 配置到 Git 忽略的 `.env`，权限 0600，DeepSeek 配置保留。`speech-check` 的技术配置检查通过，临时以 `live --speech-mode qwen` 启动后端后，`/speech/status` 返回 `configured: true`、`audio_available: true`。检查后已停止临时服务，新增云调用为 0。下文“缺少标准配置/保持关闭”描述初次核对及前一次用户选择，不再代表技术配置缺失。

本地配置成功不改变 Token Plan 官方规定的使用范围，也不证明此次已完成真实 Unity 云端联调。检查器将官方用途限制作为独立 `warnings` 报告；缺字段、密钥/Endpoint 套餐不配套、格式错误仍作为 `errors` 阻止通过。没有更换凭证、将 Token Plan 冒充标准工作空间、修改 Unity Assets 或绕过服务商鉴权。

本次配置补充的 6 项检查器测试全部通过。启动证据：`StudyData/validation/stage4-readiness-20261110/existing-key-config-check.json`。后续启动仍需显式使用 `bash Tools/AppearanceExperiment/macos.sh live --speech-mode qwen`；默认启动方式的语音开关没有被自动开启。

## 本次结论

核心四策略、语音输入/输出及播放日志已有工程实现与模拟联调证据，但不能据此宣称正式实验或真实后端已就绪。本次发现并修复实际 TTS WAV 格式与严格解码器不兼容的问题；正式运行仍缺标准工作空间语音配置及参与者实验流程界面。

## 真实音频兼容修复

第一次工具内 TTS 调用已返回音频，但 `SpeechService` 在校验阶段报 `truncated_audio`，因此没有缓存或交付该音频，也未自动重试。原始失败证据保留在 `StudyData/validation/stage4-readiness-20261110/interactive-speech-check.json`。

检查此前保存的 25 份合成样本，发现它们均采用同一 44 字节 PCM16 WAV 头：RIFF 长度为 `0x7fffffbf`，data 长度为 `0x7fffff9b`，均不是文件实际长度。Python 会读取出虚假的帧数，Unity 严格解码器会拒绝容器长度。

`Backend/speech.py` 现在只对服务商 TTS 输出中的这一特定头部进行规范化：确认 mono PCM16、合法采样率/字节率、完整样本对，再以已下载字节数修正两处长度。PCM 数据不变，音高、语速和音色不变。标准 WAV 不变；未知占位格式、普通截断文件、奇数 PCM 字节、错误格式仍拒绝。参与者 STT 输入不使用此修复。

下载时额外校验 HTTP Content-Length（如有），并将不完整分块响应转换成不含内容的错误；不会把不完整传输当作有效样本，也不自动重试。未知长度流本身不能证明上游语音在语义上完整，不能用本次兼容修复替代用户对结果的评估。

## 验证与调用记录

| 检查 | 结果与边界 |
| --- | --- |
| 后端完整回归 | 392 项通过，含新增 6 项音频格式/传输回归测试；使用模拟服务，无付费模型调用 |
| 已有真实样本 | 25/25 通过后端规范化，25/25 PCM 字节保持不变 |
| Unity 解码 | 25/25 通过现有 `TutorAudioPlayback.DecodeWav`；未播放、未修改场景 |
| 工具内真实 ASR | 使用旧 Voice G（现默认 Voice D）的一份规范化合成短句，返回 `Let's explore this idea together, one step at a time.`，与预期一致 |
| 新增云调用 | 本次共尝试 1 次 TTS、1 次 ASR；TTS 首次本地校验失败，ASR 成功；没有第二次 TTS 或自动重试 |
| 麦克风只读检查 | macOS 授权已开启，Unity 枚举到 EDIFIER Lolli ANC、MacBook Pro Microphone、WeMeet Audio Device；没有实际录音 |

ASR 使用合成样本，只验证请求/响应适配，不代表真实参与者英语识别准确率。原始 TTS 调用没有重新运行，因此修复后证据是历史真实样本兼容验证，不能写成“真实 TTS 端到端复测通过”。

证据目录：`StudyData/validation/stage4-readiness-20261110/`。

- `interactive-speech-check.json`：首次 TTS 失败记录。
- `interactive-asr-check.json`：一次 ASR 调用结果。
- `wav-normalization-check.json`：25 份样本来源、PCM 哈希与规范化文件路径。
- `local-validation-summary.json`：测试与 Unity 解码结果摘要。
- `normalized-synthetic-samples/`：仅为已有人工试听合成样本的规范化副本；没有参与者录音。

## 当前实现对照

| 内容 | 当前状态 | 后续动作 |
| --- | --- | --- |
| 同一初始输入共享给 E/A/N/S；澄清结束后统一揭示 | 已实现，前序工程联调通过 | 新增界面保持同一共享基线与揭示屏障 |
| 四项属性、五种音色 A–E / 默认 D、固定 sample、回答播放 | 已实现；本次补齐实际 WAV 格式兼容 | 标准工作空间配置后做真实后端联调 |
| STT 转录、确认发送、澄清归属 | 已实现 | 实际麦克风及噪声环境待测；目前录音选择枚举的第一台设备，本机为蓝牙耳机，后续补设备选择/默认输入处理 |
| 对话文字与播放日志 | 已实现，含待传队列、去重、原任务归属与导出 | 后续将问卷/偏好界面关联到现有 ID，不保存参与者音频 |
| 开始前调整属性并试听 | 尚未形成完整参与者准备流程；比较客户端 `CanEdit` 要求结果已揭示 | 增加共享准备状态，准备结束时把同一设置传给四策略 |
| 参与者信息、任务说明、五方向任务导航 | 当前仍为调试入口与接口 | 接入正式实验外层流程；不得照搬旧 60 题任务库 |
| VR 内逐任务问卷 | 反馈保存/提交/下一题接口已有；正式问卷 UI 未接入 | 内容待讨论后配置化渲染；问卷未完成不可进入下一题 |
| 评分题数、可选口述原因 | 后端现为工程版 `task-feedback-q1-q7-v1`，含六个评分项 | 后续按确认结果减少题数；增加独立问卷 STT 入口，禁止进入 Tutor 上下文 |
| 每方向及总体策略偏好 | 尚无正式参与者采集流程 | 增加偏好记录与导出关联 |
| 模拟自然情境 | 已有对话/属性/外观能力，不等同于连续自然实验流程已完成 | 情境细节确定后扩展，保留四属性 32 题与自然场景分开配置 |
| Pico 打包 | 当前 `build_pico.sh` 调用 `AppearanceVRSetup.BuildAndroid`，构建旧 `AppearanceVR.unity` | 本地流程完成后更新最终场景入口，再做头显验收 |

本次未更改用户已确认的研究范围：四属性 × 四情境 × 两题 = 32 个任务；第五方向为模拟自然情境，其题量和流程尚未最终确定。不得把旧问卷六个评分项或旧 60 题重新视为最终方案。

## 本机配置与正式语音接入

本机仓库根目录 `.env` 存在 DeepSeek 配置；`macos.sh live` 已能加载该文件。没有必要因默认 home 配置文件缺失而重新填写 DeepSeek 密钥。

目前语音凭证仅见于被 Git 忽略的 `.env.qwen-token-plan`；标准 `QWEN_API_KEY` / `QWEN_BASE_URL` 未配置。按官方当前说明，Token Plan 用于 AI 工具交互，不适用于自建应用后端；本次云调用只在 Codex 工具内完成，未将其加载到 Unity 服务端。[官方 Base URL 与适用范围](https://help.aliyun.com/zh/model-studio/base-url)

用于正式后端的配置需来自标准工作空间，并在该工作空间确认已开通对应模型。保持现有模型名：

```dotenv
QWEN_API_KEY=''
QWEN_BASE_URL=''
QWEN_ASR_MODEL='qwen-audio-3.0-asr-flash'
QWEN_TTS_MODEL='qwen-audio-3.0-tts-plus'
QWEN_TIMEOUT_SECONDS='30'
```

Endpoint 使用该工作空间提供的 HTTPS Base URL，例如 `https://WORKSPACE_ID.cn-beijing.maas.aliyuncs.com`，不自行猜工作空间 ID。标准 API 路径见 [TTS 文档](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api) 与 [ASR 文档](https://help.aliyun.com/zh/model-studio/qwen-audio-asr-http-api)。

取得配置后可填入现有 Git 忽略的本地 `.env`（保持权限 0600），或提供包含 DeepSeek 和 QWEN 配置的私有文件并通过 `APPEARANCE_ENV_FILE` 指定。显式以 `bash Tools/AppearanceExperiment/macos.sh live --speech-mode qwen` 启动语音后端。当前没有执行这一启动操作，也没有更改密钥。

## 额外观察与下一步

### 用户确认后的离线接入准备

用户确认目前没有标准工作空间配置，先完成本地核对和接入准备。保持语音后端关闭，不再进行云调用。

新增离线命令：

```bash
bash Tools/AppearanceExperiment/macos.sh speech-check
# 如使用其他私有配置文件：
bash Tools/AppearanceExperiment/macos.sh speech-check --env-file /absolute/path/private.env
```

该命令按启动入口的配置文件选择顺序读取 `APPEARANCE_ENV_FILE`、仓库 `.env` 或默认 home 配置；显式 `--env-file` 优先。只接受目标变量的字面量赋值，不执行文件中的 shell 指令，不展开变量，不打印密钥或配置原文。检查 Endpoint 格式、必需字段、既定两个模型、超时范围，以及密钥与 Endpoint 是否属于配套方案；Token Plan 的官方用途限制单独列为提示。检查命令本身不修改配置文件。

退出码 0 仅表示离线配置检查通过；不能证明账号已开通模型、额度充足或网络可达。报告始终注明 `provider_access_verified: false` 与 `network_calls: 0`。缺配置或待复核时退出码为 1，不启动服务。

本机运行结果符合预期：缺少 `QWEN_API_KEY` 和 `QWEN_BASE_URL`。新增 5 项测试全部通过，覆盖密钥不回显、文件不修改、错误配置、Token Plan 排除、shell 表达式拒绝和文件缺失；入口脚本语法检查通过。此补充未调用 API，也未改变 Unity 场景或实验设计。

Unity Console 留有一条 `KeyNotFoundException`，栈定位到 XR Interaction Toolkit 3.0.8 的 `TrackedDeviceGraphicRaycaster.OnDisable`（PackageCache 文件第 322 行）。当前解码检查通过且未切换 Play；本次不能确定该异常的完整触发条件。后续面板生命周期检查应验证并处理，不能宣称当前 Console 无错误。本次未改动 PackageCache。

推荐下一步先实现**共享准备阶段**：参与者开始前调节四属性/试听，确认后冻结共同起点，再进入四策略比较。这不依赖问卷最终措辞。随后推进实验导航、问卷与偏好采集；问卷内容和自然情境设计继续按用户要求另行讨论。取得标准配置后可插入真实后端验证，头显测试仍排在本地功能完成之后。
