# Unity 四策略比较接入

2026-11-17 行为更新：新增自由测试双模式；普通追问和控件现在作用于四分支，策略按钮只切换查看。当前规则和验证见 [交互模式](INTERACTION_MODES.md)。下文保留早期阶段的验收背景。

创建日期：2026-11-07；更新：2026-11-08，阶段三第六步。本地 debug 界面及生命周期接线已实现，尚非正式研究系统。评价和新题接口见 [生命周期契约](TASK_LIFECYCLE_API.md)。

## 场景与使用入口

- 桌面：`Assets/Project/Scenes/TutorComparisonDesktop.unity`
- VR：`Assets/Project/Scenes/TutorComparisonVR.unity`
- Unity 菜单：`AIAA4435 > Tutor > Comparison > Open Desktop / Open VR`
- 创建工具：`Create Scenes` 从已有单会话场景生成独立副本，遇到现有比较场景会保留，不覆盖。

比较场景只使用 TutorComparisonClient，避免原单会话客户端同时控制 Tutor。连接默认手动触发：启动后端，进入 Play mode，点击 Connect。默认地址 `http://127.0.0.1:8765`，可用 Inspector 或 `TUTOR_BACKEND_URL` 设置；头显最终需使用可访问的本机局域网地址。模型及密钥仍只保存在后端配置中。

本步没有真实模型调用；对四策略的实际语言表现仍需后续组合验收。直接使用 `server.py --mode mock` 不等于下面的专用 fixture，自定义工程用语仅由 fixture 支持。

## 交互流程

1. Connect 创建一个比较任务。默认 Reply length 为 Balanced，四分支使用相同公开起点。
2. 在 Conversation 输入一次共同请求。桌面暂用工程文字输入；预留 `SubmitUserUtterance(transcript)` 给后续确认后的 STT 文本。
3. 顶部 E/A/N/S 显示 Waiting、Preparing、Ask 或 Needs attention。选择 Ask 分支，回答它自己的问题。一个分支的回复不自动复制给其他分支。
4. 首次结果隐藏期间，只显示共同设置、公开初始历史、用户请求和澄清。即使某分支已完成，也不应用其设置、外观或回答。此阶段不可直接调整任何对话属性、撤销或向无待答问题的分支发出新请求。
5. 后端全部准备完成后，一次开放四份结果。此后通过顶部按钮切换查看；Controls 修改和 History 撤销只作用于当前分支。修改后的对话/历史更新，首次快照仍保存在后端。
6. Retry 恢复失败；Pause / Resume 保留当前题并冻结展示；Stop branch 明确停止所选未完成分支并记为 incomplete；End task 无需填写问卷即可退出为 aborted。End task 不创建下一题，也不提交问卷。

没有增加第四个主页面。仍为 Conversation / Controls / History；外观概况和修改记录在 History。Controls 保留四属性布局及短句右侧 Play sample，四属性均可保存；真实声音未接入，Play sample 仍禁用。

## 输出限制与恢复

`TutorComparisonClient.Project()` 是共用面板和模型外观的唯一展示数据入口。results_visible=false 时始终使用 baseline；开放后才使用当前分支 result.state。未来 TTS/试听或新增外观组件也必须经过相同限制，不能旁路读取原始分支结果。

客户端明确处理 JsonUtility 的空对象行为：后端的 null 可能反序列化为没有内容的嵌套 DTO，因此隐藏时显式清空 result 和 first_reveal，并以真实 question_id 判断澄清。

客户端每约 0.5 秒轮询一次；用户命令会使较旧轮询失效。任务命令使用任务版本，分支回答/修改使用分支版本。版本冲突时以服务端当前视图同步，重新操作；不盲目重放旧指令。

创建、start 或 answer 的响应丢失时，保留原路径、request_id 和正文。Retry 重发同一请求；轮询成功并不证明原命令已得到确认，所以未知结果期间仍阻止新的修改。已知 502/503 拒绝则显式使用新 ID 重试。禁用组件时中断在途网络请求，并保留未知命令供恢复。

切换分支/澄清问题后清除输入草稿，避免将旧补充说明交给新的问题。拖动滑块时，轮询保留未提交的滑块位置，松手后才提交；切换分支或失去可编辑状态时恢复服务端值。

## 本地复现

在仓库根目录运行：

```bash
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_comparison_fixture_server.py
```

该 fixture 仅监听 `127.0.0.1:8768`，故意丢弃首次创建、start、answer、submit 和 next 的成功响应。每次完整重跑前重启 fixture，使故障注入状态重置。

Unity 打开 Desktop 比较场景，进入 Play mode，保持尚未连接，然后选择：

`AIAA4435 > Tutor > Comparison > Run Local Checks (Play mode)`

验收脚本会自行连接 fixture 并操作面板。第 5 步扩展后输出 `TUTOR_COMPARISON_CHECKS PASS: 93 checks`；本轮后端 unittest 为 230 项通过。原单会话的 26 项回归已在第 4 步通过。检查次数含 HTTP 等待断言，不等于独立研究任务数。

| 检查内容 | 本轮结果 |
| --- | --- |
| E/N 已完成，A/S 仍有澄清 | 设置/对话/历史保持 baseline |
| A 选 Detailed，S 尚未回答 | 仍不显示 A/E/N 结果 |
| S 通过文字转写入口选择 Brief | 四策略统一开放；A Detailed、S Brief 分别显示 |
| 丢失 create/start/answer 响应 | 原 ID 恢复；未重复创建/提交 |
| 分支切换、控件、撤销、后续回答 | 互相隔离；首次 reveal_id 保持不变 |
| 生成故障 | 无伪造回答；Retry 仅增加一次完成的对话 |
| 轮询期间拖动 | 不覆盖用户正在选择的位置 |
| Stop / End task | incomplete / closed，关闭后控件禁用 |
| 隐藏结果防御性投影 | 即使 DTO 意外携带结果，仍选择 baseline |
| 编译与单会话兼容 | Unity 编译通过；原场景 26 项回归通过 |

结果与截图：`StudyData/macos/tutor-comparison-unity/checks.txt` 及同目录 6 张 PNG（新增 06-paused）。审计：`StudyData/macos/comparison-fixture/comparisons/debug/`。最近成功运行第一题记录一次 shared_prepared、一次 first_reveal、一次 task_submitted 和一次 task_advanced；独立第二题只暂停后退出，没有提交。这些都是工程测试数据，不纳入 user study。

## 当前范围与下一步

本步完成桌面 Play-mode 流程及截图检查，并生成对应 VR 场景；没有执行头显/手柄实测、真实 STT/TTS 或付费模型调用。阶段三已将五方向接入比较执行，并接通四项对话控件及按字段撤销；实现和边界见[控件与状态展示](STAGE_3_CONTROLS.md)。Speech rate / Voice 仍仅更新参数，未播放真实音频。桌面截图不能证明头显中文字大小、射线与拖动体验已经达标。

第 5 步接口已实现：SaveFeedback、SubmitTask、AdvanceToTask，及实际页面/版本展示记录。暂不提供完整问卷 UI 或正式 Next question 按钮。第 6 步组合验收也已完成，含部分初始设置修复与 93 项 fixture 重跑，见 [验收记录](STAGE_2_ACCEPTANCE.md)。接下来补齐其余属性、语音与完整问卷/任务库。End task 始终不等于正式任务提交。

阶段三补充：Controls 的语速与回答长度在松手时提交，Tone / Voice 直接单选；首次揭示前或当前分支不可编辑时全部锁定。History 左右切换撤销字段，默认 Reply length，支持外观字段和最近一次完整修改。一次回答的实际设置显示在 Conversation，不替换持久控件值。Play sample 在真实音频接入前禁用。
