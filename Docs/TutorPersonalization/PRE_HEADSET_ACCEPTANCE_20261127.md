# 打包前本机自动验收

日期：2026-11-26–27（Asia/Shanghai）。对象：当前工作区的 Tutor 实现，包含本次任务页收紧／问卷页展开的布局修改。

> 同日后续：本页记录当时的打包前检查。新版构建入口、USB 网络配置和设备数据工具现已补齐，两套测试 APK 已生成并检查；最新结果见 [USB 接入前准备验收](USB_DEVICE_PREPARATION_20261127.md)。头显运行验收仍待完成。

**结论：本机流程、真实 API 代表性用例、数据导出和故障恢复检查通过；尚未完成新版 Android 构建与头显验收。** 本轮没有生成 APK，也没有采集参与者数据。研究入口仍为 `engineering`。

## 1. 实际完成的检查

| 检查 | 结果 | 能支持的结论 |
| --- | --- | --- |
| 后端全量回归 | 468 项通过 | 检查时版本的后端自动测试通过；不调用付费模型 |
| 工具及研究材料回归 | 60＋11 项通过 | 相关导出工具和材料检查通过 |
| Unity 完整研究流程 | 855 个检查点通过 | 32 道属性任务、4 次属性偏好＋1 次总偏好、Selective 自然模块及 26 题问卷可走完并保存 |
| Unity 中断恢复 | 3 次独立进程、69 个检查点通过 | 丢失回执、断线、重启、未提交草稿和部分运行导出按预期处理 |
| 真实 API 代表性语音用例 | 33 个检查点通过 | API 合成英文→真实 ASR→实际对话／策略服务→真实 TTS 可运行 |
| 本轮音频的 Unity 解码 | 19／19 WAV 通过 | API 输入、五音色 sample 和回复可被 `TutorAudioPlayback.DecodeWav` 读取；没有据此认定真人听感合格 |
| 文案修复后专项回归 | 28 项通过，含新增 1 项参数化测试 | 音频可用／不可用时，设置与撤销的状态提示正确 |

855 个检查点包含重复的逐题 UI 与保存断言，**不是 855 个独立用户情境**。完整流程使用固定模型 fixture，每题使用相同工程请求来测试流程；不能表述为正式题库全部经过真实模型语义验证。真实语音部分另外覆盖 10 组合成输入。

本机普通编辑器已重新打开，退出 Play，未继承测试后端或测试 journal 的环境变量覆盖；恢复后 Console 错误查询为空。

## 2. 真实 API 语音与策略

本轮使用现有私有配置：`deepseek-v4-flash`、`qwen-audio-3.0-asr-flash`、`qwen-audio-3.0-tts-plus`。输入由 Qwen API 合成，不是参与者录音，不启动麦克风。

- 五种音色 A–E 都成功返回音频。
- 从初始语速 1.20 出发，“默认语速的 0.9 倍”得到 0.90，“当前语速的 0.9 倍”得到 1.08。
- brief、friendly、Voice E 的明确语音请求正确更新对应属性。
- 连续追问保留对话历史；外套改绿只修改外套颜色；调用字段撤销后颜色恢复，四项交流属性保留。这里的撤销通过生产服务操作调用验证，未模拟手柄点击。
- Always Ask 等待语音确认时，各策略结果保持隐藏，提前播放请求被拒绝且不触发 TTS；确认后四策略统一显示。
- 普通语音追问使四分支更新，首轮 `first_reveal` 保持不变。
- 10 条识别文本均能在对话证据中找到；语音请求重放没有再次调用 ASR。

实际调用量：输入 TTS 10 次、ASR 10 次、输出 TTS 9 次（含五种音色 sample）、文本模型 21 次；无自动重试。没有做音频语速测量、主观语气／音色评价或真实人声识别率统计。

真实云端用例直接使用生产 Python 服务类；Unity HTTP 流程由独立 fixture 测试覆盖，真实返回的全部 WAV 又经过 Unity 解码。**本轮不是一次连续的“头显麦克风→云端→头显扬声器”测试。**

## 3. 保存、导出和恢复

完整运行导出：

- `attribute_feedback`：128 条，即 32 任务×4 策略；版本 `attribute-feedback-v3`。
- `natural_feedback`：1 条；版本 `natural-selective-feedback-v2`，含 26 题。
- `preferences`：5 条；`incomplete_records`：0；`export_status=complete`。
- 8 个导出文件的大小与 SHA-256 核对一致。
- 提供的本地 journal 副本有 2043 个文件，273 个请求匹配，无 pending、conflict 或缺失回执；`provided_copy_reconciled`。这是本机冻结副本核对，不是头显文件核对。

故障测试实际注入：

1. 设置已经执行但响应被丢弃：按原请求回执恢复，不重复执行操作。
2. 问卷提交已完成但响应被丢弃：客户端先保留 pending；重启后只保留四份最终策略评价，只打开一个下一题。
3. 第二题只填部分答案后断线／重启：本地草稿保留，未自动变成服务器最终反馈；未答完时不能提交。
4. 暂停请求发出前停止后端：记录待同步操作并锁定交互；恢复后应用原暂停意图，再显式继续。
5. 两题后中止：导出 8 条属性反馈和 32 条未完成记录，状态为 `partial`；本地副本核对通过。
6. 自然问卷保存后强制重启后端：26 题答案保持，之后可提交。这个额外自然模块由缩短前置流程的 HTTP fixture 驱动，没有 Unity journal 副本，因此其导出明确为 `unreconciled`，不计入完整双端验收。

问卷口述说明保存在问卷 extras，没有混入 tutor 对话。所有本轮数据与音频均位于忽略的工程测试目录，不能并入正式参与者数据。

## 4. 本轮修正

- `Backend/tutor_session.py`：真实音频可用时，修改／撤销语速或音色不再附加旧提示 `Audio playback is not connected yet.`；不可用时仍保留提示。新增回归覆盖两个可用性状态、两个属性和字段／全部撤销。
- `TutorStudyFlowChecks.cs`：更新为当前共享属性控件逻辑，重新填写四策略评价；加入每题紧凑／展开尺寸、隐藏／显示尺寸和根位置不变检查。这些断言不代表头显上的视觉和射线验收。
- `verify_study_speech_recovery.py`、`TutorStudyRecoveryChecks.cs`：故障注入匹配新的 `/round_settings`，并等待共享轮次完成后再采集评价。
- 新增 `verify_live_tutor_voice.py`：需显式 `--live` 才调用供应商，有调用上限、无自动重试、仅接受新的输出目录；报告不保存密钥或带签名音频 URL。

完整流程最初两次启动遇到 Unity 项目被普通编辑器占用，未执行检查；退出空闲编辑器后第三次通过。批处理日志仍包含 XR Device Simulator UI 的既有无设备初始化异常，发生在检查组件启动前；不能将批处理报告写成“所有 Unity 日志零异常”。恢复普通编辑器后的错误查询为空。

## 5. Android 准备情况与尚未通过项

已确认本机安装 Android Build Support、SDK 33／34、NDK 23.1.7779620、JDK 11.0.14.1 和 adb。真实工具链根目录：

`/Applications/Unity/Hub/Editor/2022.3.62f3c1/PlaybackEngines/AndroidPlayer`

两个新版 VR 场景各自的 84 个直接 GUID 引用均可解析，包含 16 个脚本引用，Liang／Nailong 为实际 FBX 资源。Android 录音授权／拒绝处理代码与 Player journal 路径已存在。这些都是静态核对，不能代替 Android 编译。

| 打包前待办 | 已确认的当前状态 | 下一步验收目标 |
| --- | --- | --- |
| 最新场景构建入口 | `EditorBuildSettings.asset` 仍启用 `CloudConversationRoom`；旧 Pico 菜单固定旧场景 | 固定研究版 `TutorComparisonVR`／自由版 `TutorFreeTestVR` 的构建入口 |
| 网络配置 | `insecureHttpOption: 0`，本机 Unity 枚举中为 `NotAllowed`；新版场景 endpoint 为 `http://127.0.0.1:8765` | 明确 USB reverse 或无线后端方案，使 endpoint 与 HTTP／HTTPS 设置一致 |
| Android 版本与权限 | target SDK 为 Auto（值 0），并未固定为 34；INTERNET 的最终合并结果未检查 | 生成 APK 后核对实际 SDK 与合并 manifest、录音及联网权限 |
| 头显日志取出 | Player 写入 `Application.persistentDataPath/StudyData/journal`；`ExportLocalCopy` 目前只有 Editor 检查调用 | 在头显上实际取出 journal，与后端导出对账；可以采用研究者 adb 操作，不必要求参与者导出 |
| 设备性能与操作 | 尚未生成本版 APK | 安装后验证 IL2CPP 启动、材质、射线点击／拖动、录音／播放、休眠／退出恢复及持续使用 |

`ForceInternetPermission: 0` 本身不能证明最终 APK 缺少 INTERNET；需看合并 manifest。已扫描 1148 个 Git 跟踪文本文件，未找到本机配置中的两个 API key，`.env` 被忽略；本轮没有 APK 可检查。

下一步顺序：**补齐新版构建入口与后端连接配置 → 构建测试 APK 并检查 manifest → 头显安装和数据取回验收 → 小规模真人预测试。** 真实麦克风、回声、可读性、舒适度、任务时长和语音主观效果保留到设备／真人验收。

## 6. 本地证据与复跑

所有原始证据位于 `StudyData/validation/pre-headset-20261126/`，不提交 Git：

- `summary.json`：本轮汇总。
- `full-flow-03/unity-flow.json` 及 `export/`：完整流程与导出；`client-journal/`：本地日志。
- `recovery-01/acceptance.json`：三阶段恢复；`interrupted-export/`、`natural-export/`：部分／自然运行导出。
- `live-voice-1/summary.json`：真实 API 用例与调用账本；`inputs.json`：合成原文／识别文本。
- `live-voice-1/unity-decode.json`：实际 Unity 解码；`audit-and-regression.json`：对话日志核对与修复专项回归。
- `credential-scan.json`、`unit-tests/`：本机配置匹配扫描与单元测试日志。

Unity 批处理检查前须退出普通编辑器；每次使用全新输出目录。完整流程入口为 `verify_study_flow.py --out <new-directory>`，无云调用恢复入口为 `verify_study_speech_recovery.py --fixture-speech --out <new-directory>`。真实 API 脚本为 `verify_live_tutor_voice.py --live --output <new-directory>`，会消耗 API 额度，查看已有证据不需要重跑。
