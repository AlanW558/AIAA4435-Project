# 阶段三第六步：四属性控件、撤销选择与状态展示

日期：2026-11-08。本步骤将既有后端能力接入共享 Unity 面板，沿用 Conversation / Controls / History 三页、暖色半透明玻璃及右侧紧凑 Play sample 按钮。没有新增外观编辑页。

## 已实现的交互

- Speech rate：0.70–1.30，最终以 0.01 为步进保存；滑块拖动期间只预览数值，松手提交一次。数字表示所选模型/声音的默认速度倍率，不是实测音频速度。
- Reply length：保留 Brief / Balanced / Detailed 滑块，对应关键答案、关键答案加理由、再加入相关例子/步骤；不按句数限制。
- Tone：Professional / Friendly / Encouraging 单选，确认成功后更新选中状态。
- Voice：Voice A / B / C 单选，目前只保存参数，尚未绑定真实音源。显示 `Audio not connected`；Play sample 保持禁用，不伪装试听成功。
- 控件显示当前策略分支的持久设置。修改不影响其他分支，点击相同已选值不创建重复记录。
- History 下方新增撤销字段选择：左右切换到仍有可撤销记录的字段，包含四个对话字段及五个外观字段；`Latest change · all remaining fields` 撤销最近一次修改的剩余字段，不是重置整题。撤销目标保持明确且稳定，不因撤销成功自动改选其他字段。

后台轮询不覆盖正在拖动的值。切换策略、切换页面、暂停、操作进入忙碌或分支状态改变时会取消旧手势；随后松手不会把旧值提交到另一分支。单会话页签切换同样恢复服务端确认值，不依赖轮询。

## 状态限制与设置作用域

四项控件和撤销采用同一套客户端可编辑状态：未连接、首次结果隐藏、等待当前分支澄清、处理中、失败、暂停、已关闭/提交或请求结果未知时禁用。首次统一揭示后才允许修复当前结果；明确停止后的分支沿用既有修复入口。直接控件不再次经过自然语言策略确认。

请求结果未知时保留原请求 ID 与正文，通过 Retry 恢复；不能仅凭后续轮询看见目标值就解除不确定状态。单会话若还有失败后待生成的回答，也先恢复该回答，再启用属性控件。

Conversation 中的每条已完成回答附带它实际使用的设置快照，避免把一次回答专用设置误认为已永久改变。比较模式显示既有操作说明（例如保留给一次回答），并在回答完成后显示对应快照；单会话模式还列出 `NEXT REPLY ONLY` 的待使用字段。Controls 明示显示的是 session settings。

当前比较公共结果没有单独导出待使用覆盖字段，因此比较模式在回答前仅展示后端的作用域说明，不列出私有分支缓存或推测临时值。所有结果、历史和回答快照仍来自统一的 baseline / visible-result 投影，遵守首次揭示屏障。

## 本地验收

使用显式 fixture，未读取或调用课程 API 密钥。桌面输入仍为工程文字入口，未接 STT/TTS，也未执行头显测试。

- 后端：309 项回归测试通过。
- 新增 Unity 控件检查：83 项通过，包含真实 HTTP、丢失响应重试、单/四会话接口、状态禁用、滑块手势取消、外观字段撤销与一次回答设置展示。
- 原有四策略生命周期检查：93 项通过，覆盖首次统一揭示、澄清、滑块、历史、暂停、问卷版本和提交/下一题。
- Unity 编译无错误。故意丢弃响应的测试会产生 `Curl error 52: Empty reply from server`，对应重试检查通过；这不是未处理的运行故障。
- 截图检查：Controls 与 History 继续使用原三页布局；实际桌面画面保存在 `StudyData/macos/tutor-controls-unity/`。头显可读性与手柄手感留待本地实现完成后测试。

可复现入口：

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_controls_fixture_server.py
```

打开 `TutorComparisonDesktop`，进入全新未连接的 Play mode，再执行菜单 `AIAA4435 > Tutor > Comparison > Run Controls Checks (Play mode)`。服务仅监听 `127.0.0.1:8771`，第一次比较控件成功响应会被故意丢弃；完整重跑前重启 fixture。检查结果写到 `StudyData/macos/tutor-controls-unity/checks.txt`，不能混入正式研究数据。

原有 93 项回归使用独立的 `unity_comparison_fixture_server.py`（8768）及 `Run Local Checks (Play mode)`；同样需使用新 fixture 进程和未连接的 Play mode。

## 下一步

阶段三第七步：五方向组合验收、有限真实模型验证及遗留项记录，检查相同输入下的策略分歧、语速基准解释、多属性保持、作用域和恢复。真实语音输入、音源绑定、TTS、试听、正式任务库调度和 VR 问卷仍属于后续实现，不计入本步完成项。

验收结束已停止 Play mode 和两个本地 fixture 服务。源码保留在本地，未提交或推送 GitHub。
