# 四策略比较 HTTP 契约

2026-11-17 增量：共同后续轮次新增 `round_request` / `round_settings` / `round_undo`、`latest_reveal` 与每轮展示屏障，详见 [交互模式契约](INTERACTION_MODES.md)。下文为早期接口背景；当前面板不使用分支 request/settings/undo 路由普通请求。

更新日期：2026-11-08。执行版本：`tutor-comparison-execution-v6`。实现：`Backend/tutor_comparison_service.py`。暂停、评价、提交、新题及展示记录详见 [生命周期契约](TASK_LIFECYCLE_API.md)。

本接口只允许 debug，当前支持五方向执行；Reply length＋Tone 影响文字生成，Speech rate＋Voice 保存为各分支输出参数，外观通过 Unity 的公开投影应用到已有模型。视图提供 `audio_available:false`，不能把参数完成当成音频达标。[Unity 比较界面](UNITY_COMPARISON.md) 已有接线，历史字段显示已修正；四控件及按字段撤销选择仍待阶段三第六步，尚无 STT/TTS 或正式问卷。新增能力见 [外观接入记录](STAGE_3_APPEARANCE.md)。

## 1. 创建与开始

`POST /tutor/comparisons`，返回 200 和参与者视图：

```json
{
  "request_id": "create-demo-001",
  "participant_id": "ENGINEERING",
  "task_code": "RL-C1-01",
  "domain": "reply_length",
  "scenario": "C1",
  "phase": "debug",
  "settings": {"reply_length": "balanced"},
  "soft_preferences": [],
  "public_setup": []
}
```

仅 request_id 必填；其他字段有工程默认值。ID 使用匿名 ASCII 字母、数字、下划线或连字符（request_id/participant_id 最长 80 字符）。不接受评分、私有目标等额外字段。公开初始历史最多 30 条，顺序应用，可使用：

```json
[
  {"kind":"setting","patch":{"reply_length":"brief"},"query":"Only key points please."},
  {"kind":"exchange","user":"What is active recall?","assistant":"Retrieving information from memory."}
]
```

这些内容必须确为公开起点；不能把研究者目标混入历史。四分支从其深拷贝开始。

`POST /tutor/comparisons/{task_id}/start`：

```json
{"request_id":"start-demo-001","expected_revision":0,"query":"Explain active recall and include more supporting detail."}
```

所有任务/分支操作成功返回 **202** 和当时视图，表示命令已接受，不表示模型完成或参与者目标已达成。轮询 `GET /tutor/comparisons/{task_id}`（200）获得后续状态。不需要另外调用 generate 或 reveal。

## 2. 版本与幂等

- 任务操作：start、select、close、retry_shared、retry_reveal；传当前任务 `expected_revision`。
- 分支操作：answer、request、settings、undo、retry、stop；传对应分支 `expected_branch_revision`。其他分支的完成不会使这个版本过期。
- 每条新命令使用新的 request_id。网络响应丢失时，用原 ID、原正文重发；返回当前安全视图及 `idempotent_replay:true`，不重复执行。
- 创建请求 ID 在服务进程内去重；后续命令 ID 在任务内去重，不能将同一 ID 用于另一个分支或正文。
- 同 ID 不同内容返回 409 `request_id_conflict`。过期版本返回 409；刷新后以新 request_id 提交修正的命令。已记录的错误请求也会去重。
- 缓存与活跃任务仅存内存，重启后不能恢复或保证跨进程去重。

## 3. 澄清与回答

当 `branches.A.status == "awaiting_clarification"`，从该分支 question 读取 question_id、问题和选项。多个分支可同时等待，但分别回答，不自动向其他分支复制。

`POST /tutor/comparisons/{task_id}/branches/A/answer`：

```json
{
  "request_id":"answer-demo-001",
  "expected_branch_revision":2,
  "question_id":"COPY_CURRENT_QUESTION_ID",
  "response":{"text":"Please include the reasons as well."}
}
```

版本号仅为示例，始终使用 GET 中的实际版本。`response` 三种形式：

| 形式 | 示例 | 用途 |
| --- | --- | --- |
| 自然语言 | `{"text":"Only the essential points."}` | 后续接入 STT 后传入转写文本；现在可由本地客户端提供文本 |
| 选项 | `{"option_id":"c1"}` | 使用当前问题实际返回的 ID，也支持 cancel |
| Other | `{"option_id":"other","text":"Include reasons but no example."}` | 以补充说明解析选择 |

未能解决歧义时可再提出问题，新问题具有新 ID。旧问题/版本不能重放到新问题上。进入 ready 只表示处理完成，不代表问卷中的任务达标。

## 4. 首次统一展示与后续修复

前端必须以 `results_visible` 作为结果入口：

| 返回内容 | 首次展示前 | 首次展示后 |
| --- | --- | --- |
| baseline | 共同起点，可渲染 | 保留供比较 |
| branches.*.question | 当前澄清，可显示 | 后续修复中的澄清 |
| branches.*.result | 全部 null | 各自 outcome、message、state、版本 |
| first_reveal | null | 固定 reveal_id 和四份首次快照 |
| 已准备/停止分支的 status | 中性 waiting | ready / stopped |

展示前不返回隐藏设置、回答、候选、生成队列或私有会话 ID。错误响应和幂等重放也遵守此规则；私有会话未注册在 `/tutor/sessions`，不能从旧端点取出。

实际澄清全部处理、生成完成，或相应分支明确 stop 后，服务自动记录并统一开放。失败本身不满足开放条件。`completed/cancelled/unresolved/incomplete` 为工程结果分类；用户是否满意由后续问卷另行记录。

前端展示前应固定属性、Tutor 外观、对话和修改历史在 baseline；未来音频也必须等统一开放。不能只隐藏文本而提前应用设置。`can_reveal` 为内部就绪信息，不能取代 results_visible。

切换：`POST .../{task_id}/select`，正文通用字段加 `"condition":"A"`。只改变所选标识，不重置分支、不绕过展示。

首次开放后，可向单个分支提交：

| 路径（前缀 `/tutor/comparisons/{task_id}/branches/{E\|A\|N\|S}`） | 额外正文 |
| --- | --- |
| `/request` | `{"query":"Could you explain why?"}` |
| `/settings` | `{"patch":{"reply_length":"detailed"}}` |
| `/undo` | field 可为 speech_rate、voice、reply_length、tone、avatar_id、outfit、jacket_color、accessory、scale 或 all |

每项仍须带 request_id、expected_branch_revision。后端 settings 接受非空四项对话属性子集（例如 `{"patch":{"speech_rate":1.08,"voice":"voice_b"}}`），撤销支持上述字段；Unity 控件另行接线。首次开放前拒绝这些操作，避免绕过澄清。修复使用当前分支历史，不复用初始解释；first_reveal 不随修复改写。相同文本可共享生成，但各分支语速与 Voice 快照独立，不共享未来音频。

## 5. 失败、重试与结束

| 情况 | 操作 | 语义 |
| --- | --- | --- |
| shared_preparation.status 为 failed | 任务 `/retry_shared`，加 `expected_attempt` | 一次重试全部仍等待共同解释的分支；attempt 从当前视图读取 |
| 某分支 status 为 failed | 分支 `/retry` | 重试该分支；共同解释失败必须走上一行 |
| publication_error 为 audit_unavailable | 任务 `/retry_reveal` | 重写首次展示记录，不重新调用模型 |
| 明确不再处理某未完成分支 | 分支 `/stop` | incomplete，保留已提交状态，使在途结果失效 |
| 退出任务 | 任务 `/close` | 终止所有更新，不强制展示，也不是可恢复暂停 |

以上均须通用 ID/版本字段。没有自动“失败即成功”，没有超时后自动 stop。全部分支已停止后，共同重试会被拒绝。stop/close 不能保证撤回已发送的 provider 请求，但迟到回包不会应用。

## 6. 生成一致性和日志

初始解释每题共享一次，N 的策略判断单独执行。相同题内，相同实际回答上下文（问题、reply_structure、已完成公开对话、模型/生成版本）复用一次有效生成；各分支独立保存回答历史。不同上下文分别生成，不人为制造四种不同措辞。未来新增会影响回答的属性时必须加入生成上下文。

日志：`{log_dir}/comparisons/debug/{task_id}.jsonl`。包含 task_code、匿名 participant_id、执行版本、UTC/monotonic 时间以及：

- comparison_created / command_received：共同起点及收到的操作。
- provider_started / provider_finished：规范的实际适配器调用记录；provider 的内部重试详见 model_calls。其他事件复制/引用的调用记录不重复计数。
- shared_prepared / branch_gate_plan：共同解释及 shared_id 引用、各分支计划。
- engine_event：执行尝试；不单独视为已经提交。
- branch_checkpoint：写入成功后才应用的私有会话检查点。
- generation_reference：生成上下文键及是否复用。
- first_reveal：先写日志再公开的首次结果快照。

这些调试日志包含公开输入/转写文本与隐藏过程，不能作为参与者 API 返回。不记录音频。日志文件不是活跃会话恢复数据库；当前未实现断电一致性或进程重启恢复。模型返回后、进入缓存前的日志故障可能导致明确重试再次调用模型，不承诺所有故障下零重复费用。

## 7. 已验证和后续接入

2026-11-07：27 项新增服务/HTTP 测试通过，完整后端 205 项通过；全部 fixture、本地 HTTP，付费调用 0。覆盖统一展示、独立澄清、并发、缓存与重试、日志失败、停止/关闭的旧结果拒绝及旧 API 兼容。

Unity 三页界面的比较模式已在第 4 步接入，第 5 步已实现生命周期与问卷版本绑定接口。第 6 步组合验收现已完成，见 [验收记录](STAGE_2_ACCEPTANCE.md)。比较创建支持部分 settings，以新默认值补齐并校验完整组合；完整后端现为 233 项通过。正式问卷页面、Next question 按钮及方向偏好调度仍待后续实现，不能据此启动正式收集。全部本地实现完成后再进行 VR 实机测试。

阶段三第七步：baseline/result.state 的 `tutor-state-v2` 快照增加公共 `task_start_settings`，在新题公开 setup 完成后捕获，四分支一致且不会随修改/撤销变化。用于解释“恢复本题起点”，不等同 capabilities.defaults。详见[验收与真实模型修复](STAGE_3_ACCEPTANCE.md)。
