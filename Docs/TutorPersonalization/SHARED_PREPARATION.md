# 共享准备阶段

> 2026-11-11 实现更新：任务说明/提交已迁入独立左前方纸质实验面板，四属性新版问卷及独立备注 STT 已接入。见[实验面板实现与验收](STUDY_QUESTIONNAIRE_PANEL.md)。下文“没有问卷 UI”为当时阶段记录；偏好及跨方向导航仍待接入。

> 2026-11-11 设计对齐：后续接入以[实验流程与问卷字段对照表](Study/STUDY_PROTOCOL_AND_QUESTIONNAIRE_CONTRACT.md)为准。四属性分类＋四评分、四次属性偏好＋一次比较总体偏好；自然情境仅 S、结束分类＋五评分。正式任务指定起点与练习自由准备须分开。本文件下文记录已有工程实现，不代表新版问卷或自然情境已接入。

日期：2026-11-10。状态：本地实现与模拟联调通过；真实麦克风、真实云端整段对话与头显验收未执行。当前仍使用既有 debug 比较入口，不宣称已接入正式参与者采集。

后续已接入任务卡与方向内导航，默认先看练习任务说明再进入共享准备，详见 [TASK_NAVIGATION.md](TASK_NAVIGATION.md)。问卷和偏好采集仍待接入。

## 参与者流程

1. Connect 后自动进入 Controls。策略按钮的位置显示 `Shared starting settings` 与 `Confirm settings`，保留暖色半透明面板、三个页签和紧凑试听条。
2. 可调 Speech rate、Reply length、Tone、Voice，并播放固定 sample。默认 Voice D；原有五种音色、三档长度/语气与 0.70–1.30 语速范围不变。固定 sample 不评估 reply length。
3. 这时四策略尚未接收任务请求。录音、发送和分支撤销不可用；每次控件修改均更新四策略的共同起点，不属于某一策略的独立结果。
4. 点击 `Confirm settings` 停止当前试听并确认共同起点，成功后进入 Conversation、显示策略按钮，开放语音输入。确认后的初始设置锁定，提交同一条请求后进入原有并行处理。
5. 必要澄清结束、结果准备好后统一揭示。之后四项控件恢复为所选策略分支的调整，原有日志与反馈接口继续有效。

准备阶段可暂停、恢复或结束；恢复不重置设置，也不自动重播。界面切换、参数更新、确认或暂停会取消过期试听，迟到音频不得播放。网络状态不确定时使用原请求 ID 重试，不重复写入确认记录。

## 服务端状态与接口

新 Unity 比较客户端及桌面比较场景默认开启 `requirePreparation`，创建请求发送 `require_preparation: true`。返回值增加 `preparation_required`、`preparation_confirmed`。为了兼容旧工程测试，未传该创建字段的 debug API 仍使用旧流程；旧分支测试显式关闭准备，新流程有独立验收。

在 `/tutor/comparisons/{task_id}/` 下新增：

| 操作 | 请求 | 行为 |
| --- | --- | --- |
| `prepare` | `request_id`、`expected_revision`、`patch` | 仅允许四项对话属性；提交共同 baseline，并给四个核心分支及四个运行会话各自建立独立副本 |
| `confirm_preparation` | `request_id`、`expected_revision` | 记录完整 baseline 并锁定；同一请求重放幂等 |

服务端在确认前拒绝 `start` 和 STT，暂停/关闭状态拒绝准备修改，确认后拒绝再次修改 baseline。日志写入失败则不发布新设置或确认。共享设置修改推进任务/分支版本，旧音频上下文因此失效。

准备过程不调用解释、策略决策或回答生成模型。试听仅在明确点击时走现有 TTS 接口。这里验证使用模拟服务，并未调用付费 TTS。

下一题继承“需要准备”的流程要求，但不继承上一题的确认状态或结果。它从自身任务设置重新建立 baseline。后续正式任务导航可根据研究设计决定哪些阶段呈现准备流程；本次没有制定五方向的最终任务安排。

## 证据与日志

- `shared_settings_updated`：保存共同 baseline 与请求 ID。
- `preparation_confirmed`：保存四策略实际采用的共同起点。
- 上述事件进入现有对话证据导出，scope 为 shared，不伪造用户发言。
- 音频与播放日志增加 `settings_scope`，准备试听标记为 `shared_preparation`，确认后初始试听为 `task_baseline`；可与分支结果播放区分。
- 不保存参与者录音；没有新增问卷、偏好或知情同意界面。

## 验证

- **402 项后端测试通过**，新增 10 项准备测试：四份状态隔离、确认前拦截、确认锁定、字段与版本校验、暂停/退出、幂等与导出、日志失败保护、STT 调用拦截、试听设置/迟到音频，以及下一题独立准备。
- **65 项 Unity 准备流程检查通过**：真实面板控件、默认 Voice D、页面跳转、共享调整、旧试听取消、播放暂停/确认停止、分支统一起点与澄清屏障。
- **43 项原有 Unity 播放回归检查通过**，包括缓存复播、版本绑定、分支切换、迟到音频、失败处理、暂停与结束。
- 本次云调用 0，真实麦克风录音 0；输出为模拟静音 WAV。播放待传队列最终为 0。

首轮准备联调在回答 A 后立即切换 S，测试脚本撞上后台提交产生的版本变化；已让测试等待后台提交完成再切换，重跑通过。未放松服务端版本校验。失败运行保留在原 fixture 日志中，下面的验收证据仅来自通过运行。

证据目录：`StudyData/validation/shared-preparation-20261110/`，包含 `summary.json`、`unity-checks.txt`、`audio-regression-checks.txt`、`comparison-audit.jsonl` 和 `dialogue-evidence.jsonl`。

重跑：先启动 `Backend/tests/unity_audio_fixture_server.py`（8773，仅模拟）；打开 `TutorComparisonDesktop` 的新 Play 会话，再使用菜单 `AIAA4435 > Tutor > Comparison > Run Preparation Checks (Play mode)`。旧播放回归需另一个新 Play 会话。

## 后续

下一步接入任务说明与任务导航框架，让每个任务可进入准备、共享请求、比较结果和反馈环节。问卷题数、具体措辞、自然情境任务仍按用户要求留待讨论；本次没有恢复旧 60 题或把旧六个评分项当作最终方案。真实云端联调和头显测试单独记录，不用模拟验收替代。
