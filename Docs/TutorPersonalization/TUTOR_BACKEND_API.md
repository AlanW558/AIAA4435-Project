# Tutor 后端接口

更新日期：2026-11-08；解释版本：`tutor-interpretation-v4`；策略版本：`tutor-gates-v2`；回答生成版本：`tutor-answer-v4`。最新范围见 [阶段三验收](STAGE_3_ACCEPTANCE.md)，末尾保留阶段一历史验收。

新增接口与已有外观 `/sessions` 共用 `Backend/server.py`，使用独立的 `/tutor/sessions` 命名空间。已有启动脚本继续可用，已启动的旧进程需要重启才会加载新代码。本次验证没有留下常驻服务器。

当前只支持 **debug**，已接通五方向的策略决策、澄清、取消及局部撤销。Tone/Reply length 进入英文回答生成，Speech rate/Voice 保存为设置及输出快照参数，外观使用已有场景模型；尚无音频。后端直接控件仅开放四项对话属性，Unity 四控件及按字段撤销选择待阶段三第六步。参见[外观接入记录](STAGE_3_APPEARANCE.md)。[四策略比较 API](COMPARISON_BACKEND_API.md) 及 [Unity 比较界面](UNITY_COMPARISON.md) 支持共同解释、异步执行及首次统一展示；创建四个独立单会话不会自动获得这些比较语义。

## 1. 请求与响应

所有 POST 请求均使用 `Content-Type: application/json`。创建后，每次写入必须发送唯一 `request_id` 和最近响应最外层的 `expected_revision`。

| 方法 / 路径 | 内容 | 行为 |
| --- | --- | --- |
| POST `/tutor/sessions` | `{condition:"E/A/N/S", phase:"debug", participant_id?:"ENGINEERING", settings?:完整设置, soft_preferences?:[]}` | 创建独立会话；默认 S、debug 和工程编号。省略 settings 使用标准基线，提供时必须完整。 |
| GET `/tutor/sessions/{id}` | 无 | 获取当前设置、澄清、历史和待生成问题；可用于网络错误后的同步。 |
| POST `…/request` | `{request_id, expected_revision, query, question_id?}` | 解释英文请求或口头回答的 STT 文本；普通问答不经过修改策略。若带 question_id，必须匹配当前待确认问题。 |
| POST `…/generate` | `{request_id, expected_revision, job_id}` | 为指定已入队问题生成实际回答；未完成问题按入队顺序处理，已完成问题复用原回答。不能提交任意 prompt、设置或私有目标。 |
| POST `…/answer` | `{request_id, expected_revision, question_id, option_id, free_text?}` | 选择当前澄清选项；`other` 要有 free_text；`cancel` 取消；其他选项不接收 free_text。 |
| POST `…/cancel` | `{request_id, expected_revision, question_id}` | 取消当前待确认修改。 |
| POST `…/settings` | `{request_id, expected_revision, patch:{speech_rate:1.08, voice:"voice_a/voice_b/voice_c", reply_length:"brief/balanced/detailed", tone:"professional/friendly/encouraging"}}` | patch 为四字段非空子集；语速必须为 0.70–1.30 的 0.01 网格绝对值；直接提交，不调用策略或模型。相对表达式通过 request 解析。 |
| POST `…/undo` | `{request_id, expected_revision, field:九个已支持字段之一或"all"}` | 撤销指定字段最近修改，或最近一次修改；无关的新设置保持。外观恢复若产生非法组合则整体拒绝。 |
| POST `…/reset` | `{request_id, expected_revision, settings?:完整设置, soft_preferences?:[]}` | 恢复指定起点；省略 settings 使用标准基线。清空澄清、历史、单次覆盖与待生成问题；保留会话条件及请求去重记录。 |

请求和模型输出不允许携带研究者私有目标、问卷评分等额外字段。参与者最终使用语音；这里的文本接口供 STT/客户端连接和工程检查，不构成正式实验中的手动打字要求。

响应主要字段：

- `revision`：**客户端并发版本**，每次成功操作均增加，包括 ASK、取消和普通问题入队；客户端下次发送的 expected_revision 使用这个值。
- `state_revision`：内部设置/对话记录版本，ASK 可能不改变它；不能用它代替客户端并发版本。
- `settings / changes / conversation`：持久设置、修改历史、成功生成的实际问答历史。每次问答记录当时真正使用的设置，包括单次覆盖；失败不写入半次对话。
- `question`：待确认问题，包含稳定的 `question_id`、原请求、英文题干和共同选项；无待确认问题时为 null。
- `decision`：READY、ASK、ACT、UNRESOLVED、CANCELLED、CHAT_QUEUED、ANSWER；错误响应为 ERROR。
- `generation_available`：模型适配器是否提供回答生成；当前 live 适配器为 true，旧 mock 不伪造生成能力。
- `audio_available`：当前固定 false；生成 response 的 `audio_status` 为 not_connected。参数提交与文字生成都不代表已经产生或播放音频。
- `generation_jobs`：问题及绑定设置；具备生成能力时初始为 `queued`，成功后为 `completed`，包含 answer、exchange_id 及生成版本。没有生成能力的测试适配器仍使用 `awaiting_generator`。完成文本生成不代表已经播放语音。
- `response`：ANSWER 时提供 job_id、text、实际使用的 settings 与 exchange_id。`generation_replay:true` 表示返回该 job 已有回答，没有重新调用模型。
- `next_turn_override`：尚未绑定到具体问题的单次设置；`deferred_questions`：尚未解决的混合请求中保留的学习问题。

## 2. 四策略边界

四种条件共用同一解释器、候选校验、问题构建和选项规则。当前一次会话固定一种策略。每条新的自然语言定制/修复请求均重新走该条件；不是旧外观研究的“仅首次走策略”。

| 条件 | 行为 |
| --- | --- |
| E | 执行共同默认候选。 |
| A | 每条独立定制请求先询问；明确单候选也确认。 |
| N | 调用模型选择 ACT / ASK / UNRESOLVED；不能更改候选或范围，不接收 S 的规则。 |
| S | 按下面顺序检查，再执行或询问。 |

共同不支持的请求直接 UNRESOLVED，所有条件均不提交，也不会多调用 N。

S 的 Reply length 规则：

1. R1：有尚未消解的历史引用，且有多个不同候选 → ASK；没有可区分候选 → UNRESOLVED。
2. R2：存在相关公开软偏好冲突、解释器报告可能未经授权覆盖、且未明确授权覆盖 → ASK。结构化偏好检查实际改变的字段；无变化不触发覆盖；文本偏好仍依赖模型解释。延续现有策略的证据与授权语义，不把所有偏好差异都视为必须询问。
3. R3：存在多个不同的内容结构结果 → ASK。三个离散长度档位不使用外观 scale 的“小幅可逆”阈值。
4. 其他受支持情况 → ACT。

结果相同的候选先去重。四种条件使用共同英文问题，选项排序由公开请求、设置、范围及标签确定，不把默认选项固定排第一。

## 3. 澄清、取消与修复

- ASK 不改变设置。控件、撤销及新定制请求在该问题待确认时统一受限；应先解决或取消。新的定制请求可被识别，但不会暗中替换旧问题。
- 普通知识问题可保留到生成队列，使用当时已提交的设置；原待确认问题继续存在。
- 明确选项答案直接完成原请求，不再触发 A 或 N。语音回答通过 `/request` 解释；UI 选项通过 `/answer`，二者进入同一个确认处理路径。
- `other` 自由表述结合原请求、范围和当前问题进行一次解析。唯一且受支持的结果可提交；仍含糊、不支持或试图改变范围时保持原问题和设置，不擅自挑选答案，也不再次运行策略 gate。
- 取消仅取消修改。若原请求还包含学习问题，将该问题按已有效设置交给生成队列，再经 generate 生成答案。
- 不支持的混合请求保留学习问题到 `deferred_questions`，后续新的可执行修复可以释放该问题；明确控件不会自动宣布不支持的组合要求已经解决。reset 可明确清空这类未完成请求。
- 已取消、已确认或重置前的旧问题 ID 不可再次使用。

## 4. 单次与持久设置

`scope=session` 才写入持久设置和可撤销修改历史；`scope=turn` 只建立下一条回答的覆盖。

混合请求已包含学习问题时，将单次覆盖直接绑定到该问题的 generation job。单纯“下一次简短回答”则保存在 next_turn_override，等下一条知识问题到来再绑定。后续其他问题恢复使用持久设置，原设置没有被临时写坏再恢复。

单次覆盖支持四项对话属性的任意组合，被绑定后随 job 保存，失败后重试同一个 job 仍使用绑定设置，不会把它移给其他问题。生成成功只写入一次问答历史，记录该覆盖，但持久设置不变。新单次请求替换尚未绑定的覆盖；新的持久设置操作或撤销取消尚未绑定的覆盖；已入队的问题保留各自快照。Speech rate/Voice 此时只是未来语音输出参数，尚无播放。

## 5. 实际回答与客户端衔接

正常流程是 `/request` → 如有 ASK，先 `/answer` 或口头回答 → 得到 queued job → `/generate` → 显示 ANSWER。这些是客户端内部调用步骤；第 5 步的 Unity 客户端应自动衔接，不要求参与者再按一次“生成”按钮。

生成与修改分成两次提交：设置一旦确认，不会因为随后生成超时而撤销；生成失败仅保留待重试的问题。客户端检查 response/job 的真实状态，不能把 ACT 的确认文本当成知识回答。

- 同时有多个问题时只允许生成最早的未完成 job，越序返回 409 `generation_order`。生成时读取最近六次**已完成**的问答，让追问看到此前真实回答。
- 模型上下文仅有当前学习问题、该 job 的 Reply length 结构指导、Tone 措辞指导及公开问答；不含策略、研究者私有目标、评分或未回答的排队问题。
- 模型输出只接收三个英文文本字段：`key_answer`、`reasoning`、`example_or_steps`。程序按档位组合：Brief 只用 key_answer；Balanced 加 reasoning；Detailed 再加适用的 example_or_steps。关键答案必需，可选的理由或例子字段省略时按空内容处理；字段类型错误或含设置 patch 等额外字段均失败。
- 模型各组成部分保存在工程日志中；客户端和实际对话历史仅接收按档位组合后的回答，不能把 Brief 未展示的理由或例子当成已经告诉参与者的内容。问“为什么”时直接原因属于关键答案，不会因为选了 Brief 而删除问题本身要求的信息。
- Brief / Balanced / Detailed 按内容组织控制，不按句数或词数截断；安全的传输大小及模型 token 上限不是实验中三个长度档位的定义。模型仍可能偏离指导，需要观察实际内容，研究中的达标判断仍由参与者提供。
- 文字生成使用 Reply length 与 Tone；Professional/Friendly/Encouraging 影响措辞要求。Voice/speech_rate 已接通设置流程，但不进入文字生成上下文，尚不产生音频。
- 生成使用原有模型配置和调用记录，不新增固定模型名称。版本为 `tutor-answer-v4`，日志保留实际返回模型标识。内容分段及风格仍依赖模型理解，不把格式校验或测试替身输出视为语义达标证明。
- 已完成的 job 即使使用新 request_id 请求，也直接复用其答案，不追加历史。要提出新问题，应发起新 request，而非重新生成旧 job。

## 6. 错误、并发与日志

- 同一会话操作串行；模型调用期间，同会话其他操作会等待，随后检查 revision。当前不是可中途打断的异步生成系统；不会让迟到操作覆盖较新版本。
- 相同 request_id＋相同请求重试，不再调用模型，返回**当前视图**和 `idempotent_replay:true` / `original_decision`；同 ID 不同内容返回 409。
- 模型失败或输出非法返回 502；同 ID 重试复用失败，不重复付费调用。明确再次尝试需新 ID。
- 可解析的语速意图超出范围/精度时，解释器返回有说明的 unresolved，所有设置保持；不会以 502 代替数值限制，也不执行请求中的其他属性。非法模型结构仍按 502 处理，直接 settings 的非法数值返回 400。
- 生成失败后 job 保持 queued，失败原因由 HTTP 错误和日志提供，不标为 completed；新请求 ID 可重试同一 job，保留其单次覆盖。之前已确认的修改不回滚。客户端遇到网络断连先 GET，同步后检查 job 是否已完成，避免误认为没有结果。
- 过期 revision、旧 question_id、未解决问题的冲突操作返回 409；输入不合法或未支持控件通常返回 400。
- 默认旧 `MockModel` 不伪装成 tutor 解释器；其自然语言 tutor 请求返回 503。固定测试模型只在工程测试中显式注入。
- 修改先在独立工作副本执行，结果日志成功写入后发布。日志写入失败返回 503，工作副本不会覆盖当前会话。
- 日志路径为启动时 log-dir 下的 `tutor/debug/{session_id}.jsonl`，包含请求、解释、模型调用元信息、决策、澄清和操作结果；不记录密钥或授权头。仅内存保存活跃会话和去重缓存，重启不能从日志自动恢复会话。

## 7. 验证

第 4 步：完整后端 **133 项测试通过**，最终真实 HTTP 验收的六个流程通过；三档回答、追问及单次覆盖的实际内容见 [生成样例与工程检查](REPLY_LENGTH_GENERATION_REVIEW.md)。阶段进度见 [实施计划](STAGE_1_IMPLEMENTATION_PLAN.md)。以下保留第 3 步的历史验证范围。

2026-11-07：完整后端 **112 项测试通过**，包括策略、撤销、错误回滚、并发/去重、作用范围、澄清及 localhost HTTP 流程。原外观接口回归通过。

真实模型工程验证使用 **8 次调用、5 个流程**：E 执行与撤销、A 单次请求及口头确认、N 自主决策、S 明确执行与重复请求、S 含糊请求及自由表述澄清；全部通过预期检查。报告为 `StudyData/macos/tutor-session-validation.json`，日志与报告均属于本地工程记录。此结果不是研究效果、语言理解普遍准确率或 VR 可用性证据。

## 默认对话文本证据（2026-11-08）

对话文本随原审计日志默认保存，新增 `tutor-dialogue-v1` 的 `dialogue_entries`，不改变参与者响应结构或 VR 界面。四策略与单会话均适用；原始提交、模型回答、控制器澄清和问卷/展示证据分开标记。详情及导出命令见[对话日志说明](DIALOGUE_LOGGING.md)。STT 尚未接通，当前输入源标为 submitted_text，不录音。

任务起点补充：`tutor-state-v2` 快照增加 `task_start_settings`，区分应用默认、任务起点和当前值。创建/reset 确定起点，后续修改及撤销不改变它；模型解释上下文使用同一公共快照。
