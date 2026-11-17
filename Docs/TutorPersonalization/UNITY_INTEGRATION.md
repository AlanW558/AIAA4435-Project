# Unity tutor 接入：阶段一第 5 步

日期：2026-11-07。状态：实现、桌面故障注入及真实模型组合检查完成；头显仍待实测。详见 [第 6 步验收记录](STAGE_1_ACCEPTANCE.md)。

## 场景与运行

- 桌面：`Assets/Project/Scenes/TutorPersonalizationDesktop.unity`。
- VR：`Assets/Project/Scenes/TutorPersonalizationVR.unity`。
- Unity 菜单：`AIAA4435 > Tutor > Open Desktop Integration` / `Open VR Integration`。
- 首次重建缺失场景使用 `Create Integration Scenes`。已存在的目标场景会保留；当前场景有未保存修改时会停止，避免丢失编辑。原来的 CloudConversationRoom、AppearanceDesktopDemo、AppearanceVR 保留。

从仓库根目录启动现有真实后端：

```bash
bash Tools/AppearanceExperiment/macos.sh live --timeout 60
```

然后打开桌面接入场景，进入 Play mode。客户端默认连接 `http://127.0.0.1:8765`，创建单个 S / debug 会话；成功后右上角显示 DEBUG / S / LIVE。未启动服务时显示连接错误，可以启动服务后按 Connect。界面出现 Ready 不代表语音功能已可用。

模型仍由后端本机私有配置指定，Unity 不保存密钥或固定模型名称。此单会话场景切换策略时，在进入 Play mode 前修改 `Tutor personalization client` 上的 `TutorClient.condition`（E/A/N/S）；新会话才使用新条件。另已新增 [四策略比较场景](UNITY_COMPARISON.md)，支持运行时切换与首次统一展示。

`TutorClient.endpoint` 或进程环境变量 `TUTOR_BACKEND_URL` 可设置后端地址。头显中的 localhost 指头显自身；实际设备网络地址、HTTP 配置及部署在第 6 步检查，本次未写入设备配置。

## 已连接的交互

| 页面 | 行为 |
| --- | --- |
| Conversation | 显示后端实际完成的问答、待生成问题和澄清；请求或确认后自动调用 generate，不需要再按生成按钮。桌面工程文本框可发送请求，参与者语音仍待接入。 |
| Controls | Reply length 三档可调，释放滑块后提交，后端确认后同步。Brief 仅关键点；Balanced 加简短理由；Detailed 加说明和适用例子/步骤。忙碌、待确认或请求结果未知时禁用。 |
| History | 显示后端实际修改及来源、前后值、撤销记录；可撤销最近一项仍可撤销的 Reply length 修改。外观作为当前结果摘要显示在此页。 |

四属性共用 Controls 页。Speech rate、Tone、Voice 和右侧 Play sample 尚未连接，控件禁用；试听句保留紧凑单行布局。面板沿用暖色半透明背景与柔和光晕，所有文本为英文。

`TutorClient.SubmitUserUtterance(string)` 是后续 STT 文本接入口，自动带入当前待确认 question_id。`SubmitClarification(string)` 用于 Something else 自由表述。没有录音、STT、TTS 或麦克风调用；VR 隐藏工程文本框，不能据此执行完整参与者实验。

## 状态与失败处理

- 设置、对话与历史仅采用后端 snapshot。使用顶层 revision 发送 expected_revision，拒收旧版本或其他会话快照。滑块预览不写入历史。
- ASK 时保留已提交设置，显示后端共同选项；取消不修改设置。后续选项提交包含 question_id。
- 同一客户端串行发送；自动按队列顺序生成，保留各 job 的生成时设置。失败不补造回答。
- 已知 502/503 可通过 Retry 使用新 request_id 重试；结果未知的网络中断保留原 request_id 和原始请求体，重复请求由后端去重。Sync 不清除未知请求，也不自动重新解释或重复生成。
- 409 冲突显示后端错误，使用 Sync 查看当前状态；不自动把过期答案提交到新问题。后端重启后会话失效，目前通过重新进入 Play mode 创建新会话；不提供跨进程历史恢复。
- 第 6 步已验证已知生成失败、未知结果恢复、原 ID 重放、过期问题冲突、旧快照拒绝及组件禁用恢复。Sync 后若仍需恢复，面板持续显示提示；未支持的属性请求显示后端原因。

## 免费模拟联调复现

fixture 只支持明确列出的测试语句，不是自然语言模型，也不作为 live 故障时的替代回复。每次检查前重启 fixture，以重置“一次故意失败”。停止占用 8765 的服务，避免客户端先创建 live 会话。

```bash
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_fixture_server.py
```

1. 打开桌面接入场景，进入 Play mode，等待默认 8765 连接失败。
2. 执行 `AIAA4435 > Tutor > Run Local Fixture Checks (Play mode)`。菜单在当前未连接会话中临时切换到 8766；已连接或忙碌时拒绝运行。
3. 查看 Console 的 `TUTOR_UNITY_CHECKS PASS: 26 checks`。包括 14 项行为断言与 12 次 HTTP 等待检查。
4. 检查 `StudyData/macos/tutor-unity/checks.txt` 和 controls/history/clarification/conversation 四张 PNG。
5. 退出 Play mode，终端 Ctrl+C 停止 fixture。Play mode 中临时 endpoint 修改不会写回场景。

自动检查脚本在 `UNITY_EDITOR` 条件内，不进入设备构建，也未作为组件保存到场景。2026-11-07 已通过客户端和 UI 回调检查，检查了实际渲染截图及滑块鼠标射线命中；未声称真人交互、头显舒适度或模型语言质量通过。

## 下一步

本单会话的桌面与真实模型组合检查已完成，头显上的网络、射线、拖动、滚动与可读性检查按最新要求延后。四策略比较已有独立场景及本地 fixture 检查；其他对话属性、语音与研究问卷仍属于后续实现范围。
