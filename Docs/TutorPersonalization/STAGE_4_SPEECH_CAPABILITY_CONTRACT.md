# 阶段四第一步：语音能力与参数映射

日期：2026-11-10。状态：参数映射与 15 个样本已交付；技术检查通过，人工试听待完成。交付范围：模型能力核对、候选参数、真实短句样本与试听方法。后端适配、Unity 播放、头显测试属于后续步骤。

## 1. 模型与接入边界

- ASR：`qwen-audio-3.0-asr-flash`。一次录音结束后提交，得到最终英文文本，再送入现有 DeepSeek 和四策略流程；不是边说边识别的承诺。
- TTS：`qwen-audio-3.0-tts-plus`。先用 HTTP 完整音频返回，后续是否改流式单独评估。
- DeepSeek 继续负责对话、请求解释、澄清、Reply length 和措辞 Tone。
- 本次样本通过已验证的北京 Token Plan 端点在工具内交互生成。正式自定义 VR 后端的标准凭证、工作空间和地域应单独配置验证，不能把工具内调用成功等同部署许可或标准端点可用。
- 私有凭证不进入 Assets、APK、文档、版本库或日志。不在本步骤更改运行中的模型适配器、Voice 解释器和 `audio_available`。

## 2. 候选 Voice 映射

| 应用字段 | 候选提供商 ID | 选择依据 | 当前限制 |
| --- | --- | --- | --- |
| voice_a | longanlufeng | Plus 官方列表支持英文与指令控制，男声；作为默认候选 | 尚未完成主观试听，不承诺特定口音或低沉程度 |
| voice_b | longanlingxin | Plus 官方列表支持英文与指令控制，女声 | 同上；音色描述不能直接进入自然语言语义匹配 |
| voice_c | longanhuan_v3.6 | Token Plan Plus 示例及前次真实调用使用该 ID | 音色总表将其列于 Flash，属于文档差异；仅作经调用验证的候选，不能宣称 Plus 正式音色表已列出 |

三个候选均保留固定身份；改变 Tone 不应换 Voice。选择男女声会带入性别偏好，因此研究分析不将声音偏好简单归因于策略。是否与 Liang 外观匹配由后续试听/实验设计决定，不在本步骤擅自修改外观或减少选项。

## 3. 属性对照

| 应用内容 | 请求位置/实现规则 | 验证边界 |
| --- | --- | --- |
| speech_rate | 原值写入 `input.rate`，应用 0.70–1.30、步进 0.01；提供商文档 0.5–2.0 | 本轮只覆盖 0.70/1.00/1.30；不宣称已遍历全部档位 |
| 默认语速 | 所选音色下 `rate=1.00` | 不要求不同音色在 1.00 时具有相同速度；不按字数/秒测量 |
| 相对当前调整 | 沿用现有确定性计算、范围和精度规则，将最终数值交给 TTS | 不再让 TTS 指令重复计算 0.9 倍等含义 |
| voice | 通过候选映射写入 `input.voice` | 实际音色可辨识度由试听确认 |
| tone | 使用 `input.instruction`；三个固定模板见 JSON | 同一句短句只展示声音表达，不代表完整措辞 Tone |
| reply_length | 由现有 DeepSeek 文本生成控制；TTS 逐字朗读最终文本 | 不通过缩短音频、加速或裁剪实现 Brief |

固定参数：WAV、24000 Hz、volume=50、pitch=1.00、seed=4435、language_hints=[en]。种子用于减少无关变化；提供商模型别名可能更新，不能承诺跨版本完全复现。`pitch` 不随 Voice 或 Tone 改动，Unity 后续也不能通过 AudioSource.pitch 实现调速。

Tone 模板（工程候选，不是模型内置枚举）：

- Professional：professional, composed and matter-of-fact delivery。
- Friendly：warm, approachable and conversational delivery。
- Encouraging：supportive, reassuring and gently motivating delivery。

三个模板均要求保留说话者身份与请求语速，只读给定文字，不添加拟声效果或额外内容。模板中不设置快慢、音高或音量，减少属性混淆；仍不能保证模型完全隔离这些感知维度。

完整机器可读配置：[STAGE_4_SPEECH_PROFILE.json](STAGE_4_SPEECH_PROFILE.json)。状态为 `candidate_pending_listening`，`live_runtime_enabled=false`。

## 4. 样本设计与试听

固定句使用现有 Unity Controls 的原文：**Let's explore this idea together, one step at a time.**

每个声音 5 个样本：Professional/Friendly/Encouraging 各在 1.00 生成一份，再生成 Professional 的 0.70 与 1.30。共 15 个，不是全部 27 种交叉组合。复用 Professional/1.00 基线，避免为三个比较组重复付费。

本地样本及独立播放器：`StudyData/validation/stage4-speech-step1-20261110/index.html`。无自动播放、无外部依赖，播放一个音频时暂停其它音频。只是开发试听页，不更改用户已接受的 VR 面板设计。

建议试听顺序：

1. 对比 A/B/C 的 Professional、1.00：英文是否清楚自然；是否能辨认声音差异；是否适合作为 Tutor。
2. 每种声音对比三个 Tone、1.00：是否分别体现专业/友好/鼓励；Friendly 与 Encouraging 是否太接近；是否换了说话者、增添文字或明显改变速度。
3. 每种声音对比 Professional 的三档语速：能否感到慢/正常/快；两端是否仍舒适、清楚。
4. 有问题时记录样本 ID 与具体原因，再定向修改；不重新生成整组来掩盖失败。

当前不采集正式用户问卷，也不自动判定实验任务成功。主观试听由用户/组员完成；助手只核验请求成功与音频容器，不声称已经听出差异。不计算实际语速、声学指标或音频时长倍数。

试听反馈建议格式：`样本 ID / 可接受或需调整 / 发音、音色、语气、速度或其它原因`。所有反馈为开发记录，不混入研究数据。

## 5. 后续实现必须保留的规则

- 一次参与者音频只做一次 STT，确认的最终文本共用至四策略；澄清回答只路由对应分支。识别失败不得变成空请求或四次重新识别。
- 参与者录音仅作必要的短期传输/内存处理，完成后释放；日志保存最终提交 STT 文本和 Tutor 输出。云服务自身的数据保留需在正式部署配置时核对，不能把应用不落盘描述为提供商零保留。
- 本次保存的 WAV 是模型生成的开发样本，不是参与者录音；正式回答缓存同样需与参与者输入录音区分。
- 问卷 STT 不进入 Tutor 对话上下文。
- Play sample 不追加对话、不修改设置、不消耗一次回答 override；使用当前可见设置。
- 每条正式回答使用当时的 settings 快照；重播不能按后来修改的设置重新合成。
- 四分支澄清和生成完成前，不播放或展示任何隐藏分支结果；失败保持明确失败状态，不静默降级到另一模型。
- 同时只播放一个结果；切换、暂停、结束、设置变化时停止旧试听。
- 音频缓存键至少包含 provider、endpoint scope、model、profile/instruction version、voice、rate、Tone 指令、text、format、sample_rate、volume、pitch、seed 和 language。音频重试不重新调用 DeepSeek。

## 6. 工具与验证证据

样本工具：[prepare_speech_samples.py](../../Tools/AppearanceExperiment/prepare_speech_samples.py)。默认仅离线输出计划，只有显式 `--execute` 才调用。最多 15 次 TTS、不自动重试、不切换模型；已有 evidence 时默认拒绝重跑；显式 `--resume` 只处理没有请求记录的样本，失败样本不自动重新计费。凭证请求禁止重定向；下载生成音频不携带 API key。证据不保留临时签名音频 URL。

样本 JSON 记录请求参数、HTTP 状态、request_id、usage、文件路径、哈希及 WAV 格式。这些可以证明参数传入和音频保存，不证明主观可辨识度。此前 ASR/TTS 连通验证见 [QWEN_TOKEN_PLAN_CHECK.md](QWEN_TOKEN_PLAN_CHECK.md)。本轮不重复 ASR 调用。

## 7. 官方依据（核对日期 2026-11-10）

- [音色列表](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list)：模型音色与能力须对应；Plus 两种英文系统音色及候选 C 的差异。
- [TTS HTTP 参数](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api)：rate、pitch、seed、音频格式和指令入口。
- [风格指令](https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide)：3.0 Plus 支持自然语言指令。
- [Token Plan 合成接入](https://help.aliyun.com/zh/model-studio/token-plan-speech-synthesis)：3.0 Plus 示例和候选 C。
- [Token Plan 识别接入](https://help.aliyun.com/zh/model-studio/token-plan-speech-recognition)：3.0 ASR 非实时接口。

后续进入第二步可以实现服务适配和失败处理；在实际声音语义与最终实验素材冻结前，需完成本轮人工试听。

## 8. 本次实际验收与问题记录

- 最终保存 15/15 个真实 WAV；三种候选音色均成功提交三种 Tone 及语速端点。
- 离线核验：15 个文件均为非空、单声道、PCM16、24000 Hz WAV；文件哈希与结果 JSON 一致；15 份音频字节均不同（不代表听感差异已达标）。试听 HTML 的 15 个本地音频引用全部有效；样本脚本语法通过。
- 第一轮 15 次请求均 HTTP 200，但提供商返回 HTTP 下载 URL；初版工具只接受 HTTPS，拒绝下载。该轮已产生合成用量，本地未保存音频，不能当作零成本或成功交付。
- 工具已修复：将提供商返回的同一音频地址升级为 HTTPS 下载，且任何样本失败即停止后续生成。先用 1 次验证成功，再显式继续剩余 14 次。没有更换模型、静默切换账户或把失败证据覆盖。
- 本步骤实际共 **30 次 TTS 调用**，包括首轮 15 次下载失败；累计提供商报告 **1590 characters、390 input tokens、1272 output tokens、1662 total tokens**。这些字段按原样记录，不据此估算套餐 Credits 或金额；以控制台账单为准。本步骤无新增 ASR/DeepSeek 调用。
- 原始失败：`StudyData/validation/stage4-speech-step1-20261110/results-initial-download-failure.json`；最终记录：同目录 `results.json`；离线验收：`acceptance.json`。
- 候选 C 的 Plus 调用再次成功，但文档分类差异仍保留；不据此假定在所有账户、标准端点或未来版本都可用。
- 尚未完成：人工判断发音自然度、三个 Tone 的区别、音色稳定性及语速舒适度；没有修改现有 `voice_a/b/c` 语义解释、Unity Play sample、实验问卷或运行配置。

## 9. 第二批音色候选与用户偏好（2026-11-10）

用户明确保留 B（longanlingxin）为首选，C（longanhuan_v3.6）为备选。原 A/B/C 编号不变；本步骤不更改 Unity 默认设置。新增 D/E/F 仅用于试听选择，不作为实验面板的新选项。

从官方 Plus 基础音色目录筛选三种标注英文的女声，兼顾接近 B 的温柔风格及不同表达风格。描述仅为供应商目录标签，非助手试听结论：

| 候选 | 名称 | Provider ID | 目录描述 | 来源 |
| --- | --- | --- | --- | --- |
| D | Olivia Lin | qwen-audio-3.0-tts-plus-loongolivialin | 温柔知性音 | Sheet1!B578:H578 |
| E | Luna Wang | qwen-audio-3.0-tts-plus-loonglunawang | 智能助手音 | Sheet1!B579:H579 |
| F | Nora Hu | qwen-audio-3.0-tts-plus-loongnorahu | 活泼灵动音 | Sheet1!B581:H581 |

目录入口：https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list 。只读原件保存在 `StudyData/validation/stage4-voice-candidates-20261110/official-plus-voice-catalog.xlsx`，未修改工作簿。

三个候选各生成一次 Professional/1.00 固定句，HTTP 200，WAV 保存成功；本轮无失败、无重试，3 次调用、159 characters。B/C 复用第一批原文件，不新增调用。比较页：`StudyData/validation/stage4-voice-candidates-20261110/compare.html`。独立候选配置：`STAGE_4_EXTRA_VOICE_CANDIDATES.json`。

五个音频文件的格式与本地页面引用均通过检查；D/E/F 的主观音色偏好、其它 Tone 和语速效果等待用户挑选后再验证。不能从提交 Professional 指令成功推断三种 Tone 均有明显效果。

## 10. 保留 D 与新增男性候选（2026-11-10）

用户保留 D，B 仍为首选、C 仍为备选；未指定 C/D 排序，不擅自重排。不改变原音色编号或 Unity 默认值。E/F 本轮未保留，原始样本仍保存。

新增 G：Adrian Gao（`qwen-audio-3.0-tts-plus-loongadriangao`），官方目录 Sheet1!B582:H582 标注男、英文、沉稳大气音，作为稳重风格候选。
新增 H：James Zhao（`qwen-audio-3.0-tts-plus-loongjameszhao`），官方目录 Sheet1!B583:H583 标注男、英文、新闻播报音，作为播报风格候选。

选择依据是官方目录标签，非助手主观试听结论。与原 A（longanlufeng）是不同声音。源目录仍为上一节保存的官方工作簿。

两者各生成一次 Professional/1.00 固定句，HTTP 200，WAV 均已保存。共 2 次调用、106 characters，无失败或重试。B/C/D 直接复用原音频，不新增调用。5 个 WAV 格式与页面引用通过检查。

试听页：`StudyData/validation/stage4-male-candidates-20261110/compare.html`；调用证据：同目录 `results.json`；复用记录及检查：`comparison_manifest.json`；候选参数：`STAGE_4_MALE_VOICE_CANDIDATES.json`。

G/H 主观听感和三种 Tone 的可辨识度尚未评估；选中后再测试其它 Tone/语速。保留 D 只代表音色偏好，不等同其 Tone/语速已验收。
