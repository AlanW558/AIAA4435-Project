# Interaction modes — 2026-11-17

本次落实用户确认的规则：自由测试可切换模式，研究任务固定模式。此文覆盖早期文档中“后续输入/控件只作用于当前分支”的旧行为。

## 使用入口

Unity 菜单 `AIAA4435 > Tutor > Free Testing > Open Desktop / Open VR` 打开自由测试场景。进入 Play，点击 Connect；比较模式按提示确认共同初始设置，再开始对话。模式按钮位于控制面板顶部，不增加主页面。

研究仍使用 `TutorComparisonDesktop.unity` / `TutorComparisonVR.unity` 及已有 Study 流程；不从自由测试场景收集正式问卷。自由测试场景不创建问卷面板或研究会话，避免混入已有参与者记录。新增场景未改变打包入口配置。

| 模式 | 普通请求与后续对话 | 控件 | 四策略按钮 |
| --- | --- | --- | --- |
| Four-strategy comparison | 同一次输入发给 E/A/N/S，各自保留上下文 | 同一次改动应用于四分支 | 选择查看哪份结果、历史和设置，不选择执行策略 |
| Selective conversation | 仅 S 连续对话 | 修改 S 会话 | 隐藏 |

澄清回复是例外：仅回答当前显示的提问分支，不复制给其他策略。比较模式每轮都等待所有分支结束，再统一显示新结果。研究中的四属性任务固定比较模式，自然模拟固定 Selective；顶部显示只读模式名称。

自由测试在请求、澄清、待恢复命令、录音或语音处理期间锁定模式切换。切换会停止播放并清空未提交输入，两个模式已完成的对话和设置在当前运行中分别保留。自由测试会话仍是进程内运行状态，不承诺退出应用或重启后端后恢复；研究会话继续使用已有持久化链路。

## 后端契约增量

任务端点 `POST /tutor/comparisons/{task_id}/{operation}` 新增：

- `round_request`: `request_id`, `expected_revision`, `query`。
- `round_settings`: `request_id`, `expected_revision`, `patch`（四项对话属性）。
- `round_undo`: `request_id`, `expected_revision`, `field`；必须每个分支均可撤销该字段，否则整条命令拒绝。

首次输入仍用 `start`。后续共同轮次要求上一轮全部完成/停止并已揭示，四个工作票在同一锁内创建，不能重叠启动。显示条件仍是 `results_visible`；新增 `round_index`、`round_query` 和 `latest_reveal`。原 `first_reveal` 保持不变，保留研究绑定和首次快照的语义。后续揭示记录 `round_reveal`；对话日志继续记录输入及各分支模型输出。研究 checkpoint 保存新字段，并兼容旧 checkpoint。

旧分支 request/settings/undo API 保留以兼容已有工具；面板的普通输入和控件改用上述共同轮次接口。澄清、失败重试和停止仍绑定具体分支。

## 本机验证

- 后端完整测试：468 项通过，其中比较服务 51 项；新增共同追问、澄清展示屏障、checkpoint 恢复、共同控件及撤销测试。
- Unity 编译/控制台：无错误。
- Unity 独立 mock fixture（8779）：四分支初始对话和后续对话、共同语速设置、切换后的历史隔离、澄清时禁用模式切换、澄清完成后统一揭示均通过。
- Unity 研究面板：比较模式及自然模式均不能通过自由模式接口切换，已有 StudyFlow 保留；未创建/提交研究记录。
- 已检查顶部两种模式及四策略选择按钮截图：`StudyData/validation/interaction-modes-20261117/`。

本次模式验证使用合成文本和 mock 输出，没有重新进行真实麦克风、付费语音调用或头显实测。已有语音链路通过同一客户端提交入口使用新的模式路由；仍需后续实际操作确认。

## 面板布局补充（2026-11-17）

按用户反馈向上延长玻璃背景，比较面板画布高度 920 → 1040，背景 quad 高度 1.01 → 1.20；考虑 shader 实际可见范围，顶部模式按钮完整留在背景内。拖动区域独立放在模式按钮上方。属性标题 32 → 36、选项 28 → 32、模式文字 26 → 30、对话/历史正文 22 → 28；底部按钮加宽，连接前隐藏无用的同步/重试入口，避免重叠。透明与发光风格沿用原设计。

Unity 实际渲染检查包括未连接和已连接的 Detailed 属性页，固定字号文本未出现高度裁切；截图 `controls-expanded-verified.png` 与 `controls-expanded-populated.png` 位于上述验证目录。最终仍需佩戴头显判断字号和观看舒适度。
