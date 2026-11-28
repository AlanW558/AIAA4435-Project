# 参与者、会话、问卷与数据保存契约

> **当前研究规范（2026-11-28）：** 四属性＋外观共40题，每模块20项评分和一项多选偏好，自然模拟不再施测。准确题干、当前独立网页的版本/身份/缺失/汇总规则见[当前问卷与数据范围](CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)。本文件以下保留 `study-data-contract-v1` 的旧Unity实现与兼容读取规则，其中自然26题、逐任务评分及671项计数不作为新研究要求。

版本：`study-data-contract-v1`；契约日期：2026-11-16；实现状态核对：2026-11-17。对应研究设计 `study-protocol-v1.7`。

**以下为旧Unity实现状态：保存层、当时新版问卷、自然会话及实验控制器已接通。** 当前仍限工程/练习验证，不表示正式采集或头显验收已完成。旧记录字段含义以其产生时的本文契约为准；新研究设计以[主设计](FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)及当前问卷规范为准，实际路径和实现差异见[保存层说明](../STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md)和[流程接入](../STUDY_FLOW_INTEGRATION.md)。旧[流程契约 v1.5](STUDY_PROTOCOL_AND_QUESTIONNAIRE_CONTRACT.md)仅供历史追溯。

## 1. 旧实现固定的范围（保留用于解释已有记录）

- 四属性各八题，共 32 题；每题 E/A/N/S 四份反馈，共 128 份；每份五题。
- 四次属性末偏好及一次四属性总体偏好，共五份，均在自然情境之前。
- 自然情境为独立的一段 S 连续交流，结束后一份 26 题问卷；没有自然模块策略偏好。
- 核心题位数为 640＋26＋5＝671，不等于独立参与者数，也不保证 671 项均为可计分答案。可选原因、文字和访谈另计。
- 持久化、匿名身份注册、恢复、CSV 导出及新问卷已实现；本文保留契约版本，工程可用性与正式研究开放分开判断。

## 2. 身份层级与编号

| 层级 | 字段与格式 | 创建及用途 |
| --- | --- | --- |
| 研究项目 | `study_id = aiaa4435-final-user-study` | 固定命名空间，与第一次外观实验分开 |
| 参与者 | `participant_id`：`P0001` 起；编号为 P 加至少四位数字 | 研究者通过后端注册，项目内唯一、递增、不回收；不可由姓名、邮箱、声音或模型推断 |
| 整场实验 | `study_run_id`：32 位小写十六进制 UUID | 后端创建；关联一次完整实验尝试中的所有模块、任务、问卷、偏好和日志 |
| 模块实例 | `module_instance_id`：同上 UUID | 四个 `attribute_comparison`（各带 domain）和一个 `natural_selective`；正常完整流程五个实例 |
| 受控任务实例 | `task_id`：沿用现有 UUID 格式 | 一次任务执行；`task_code` 是题库代码，不是唯一执行编号 |
| 单策略对话 | `session_id`：沿用现有 UUID 格式 | 自然模拟使用独立 S 会话；比较分支如有 session_id，必须附 task_id 与 condition，不能冒充整场实验编号 |
| 问卷实例 | `questionnaire_id`：UUID | 对应一个 task_id＋condition，或一个自然 module_instance_id＋session_id；版本和评价对象固定 |
| 偏好实例 | `preference_id`：UUID | 四个 attribute 范围、一个 comparison_overall 范围 |
| 原始事件／操作 | `event_id`／`request_id`：UUID | event_id 标识证据事件；request_id 标识可安全重试的操作，不混用 |
| 最终提交 | `submission_id`：UUID | 后端正式接受时生成；同一次提交重试返回同一编号 |

UUID 示例为无连字符形式；内部按项目范围校验唯一性，不依赖时间戳生成身份。`questionnaire_id` 等采集对象由后端创建；`request_id`、客户端事件 ID 可由客户端创建后先落盘。任何离线记录只能绑定已注册并缓存在本机的研究身份，不临时猜测编号。

### 2.1 同一人、恢复与重做

- 同一人在本次研究再次参加，复用 participant_id，但新建 study_run_id，记录 `repeat_of_study_run_id` 和原因；不把同一人当独立新增样本。
- 暂停、断网、App／后端重启后的恢复继续使用原 study_run_id、模块和任务 ID；另记恢复事件及新 `connection_id`。连接或进程 ID 不能替代研究 ID。
- 恢复失败后研究者明确决定重做，才创建新任务／模块实例，写入 `replaces_task_id` 或 `replaces_module_instance_id` 及理由。旧记录保留；导出不自动把重做算作另一位参与者或任意取最高分。
- `prior_participation` 记录 `yes / no / not_reported`，另存自愿报告的既往研究类型。参加过第一次研究的人也使用本研究编号，不自动关联旧姓名或旧记录。
- 研究记录仅保存编码身份。若研究者另需编号对照表，独立保管，不放进 APK、对话日志或分析导出。

### 2.2 工程、练习与正式数据隔离

新增 `collection_kind = engineering / practice / pilot / formal`；预测试与正式数据不可混合。运行方式另记 `execution_mode = mock / live`，真实模型调用不自动意味着正式数据。正式任务禁止 mock，缺配置时不自动降级后继续标 formal。

旧 `phase=debug`、`run_kind`、`UNITYDEBUG`、ENGINEERING 等只作历史字段；不能直接重命名为正式参与者记录。工程匿名标识使用 `ENG-…`，未注册参与者的练习用 `PRACTICE-…`，均不可混入 P 编号正式数据。已注册参与者的熟悉练习可复用 participant_id，但用独立 practice study_run_id，不计入 formal 的 32 题。

## 3. 版本固定与记录头

| 字段 | 本版目标值／规则 |
| --- | --- |
| `data_contract_version` | `study-data-contract-v1` |
| `protocol_version` | `study-protocol-v1.7`，对应主设计 v1.7 |
| `questionnaire_version`（四属性） | **`attribute-feedback-v3`** |
| `questionnaire_version`（自然模拟） | **`natural-selective-feedback-v2`** |
| `questionnaire_version`（偏好） | `strategy-preference-v1`，题意与选择规则未改 |
| `answer_schema_version` | `study-answer-v1`，下节统一答案结构 |
| `dialogue_schema_version` | 保留实际产生记录的版本，不将现有日志强制重标 |
| `task_manifest_version / task_manifest_sha256` | 从实际加载的 32 题材料获取，不在本文伪造已冻结正式材料版本 |
| `questionnaire_manifest_sha256` | 冻结后的英文题干、顺序、量尺、选项和字段映射的内容哈希 |
| `app_build_id / backend_build_id / configuration_sha256` | 实际构建与非敏感配置版本；配置摘要不得包含 API 密钥 |

每场开始保存版本清单、实际模块／任务顺序和共同起点引用。记录实际使用的模型 ID、音色映射版本、speech rate 基准及策略配置；采集答案不根据模型输出更改。正式开始后不原地替换题干、量尺、任务材料或策略配置。需变更时结束该次尝试、保留数据，再用明确新版本开始；不能在一次运行中无记录地切换。

`attribute-feedback-v2` 的 effort_ease 是旧同意度题，不能复制为新版 A1 难易度。`natural-selective-feedback-v1` 是旧六题格式，不能补空列后宣称完成 26 题。旧记录保持原版，不自动换算或补答。

## 4. 答案结构、题目映射与缺失

### 4.1 通用答案结构

每个核心题位显式保存 `{status, value}`。题 ID 在各问卷版本中固定，不按界面第几页临时编号。

| status | value | 含义 |
| --- | --- | --- |
| `answered` | 该题允许的整数或分类字符串 | 参与者实际选择的有效答案 |
| `unable_to_judge` | null | 参与者明确无法判断，仅用于允许的题位 |
| `not_applicable` | null | 本版仅自然 N5 的未发生澄清；附 `reason=no_clarification_questions` |
| `skipped` | null | 参与者明确选择跳答；不能从空白推断 |
| `unanswered` | null | 尚未作答；默认草稿状态，无预填中点 |
| `technical_missing` | null | 技术原因未能获得；附 reason／相关事件 ID，不能覆盖已可靠保存的答案 |

除 N5 的明确不适用原因外，status 与 value 互斥校验；不把 0、空字符串或布尔值当合法分数。`unable_to_judge` 可用于完成情况，不能同时又在 value 中保存同名分类。导出必须同时给出 value 和 status，禁止把 null 一律解释为失败。

`skipped` 是作答状态，不是 SUS／UEQ-S 新增的量尺位置；不在标准五点／七个位置之间插入此值。四属性和自然诊断核心项正常路径要求有效作答；参与者始终可暂停／退出，退出时保留已填部分。

### 4.2 四属性：attribute-feedback-v3

| 题 ID | 稳定字段语义 | answered 允许值 | 其他有效正常作答 |
| --- | --- | --- | --- |
| A0 | completion | `fully_met / partly_met / not_met` | unable_to_judge |
| A1 | perceived_ease | 整数 1–7；Very difficult → Very easy | unable_to_judge |
| A2 | control | 整数 1–7；同意度 | unable_to_judge |
| A3 | clarification_appropriateness | 整数 1–7；同意度 | unable_to_judge |
| A4 | satisfaction | 整数 1–7；同意度 | unable_to_judge |

题干及完整锚点见主设计 §6。正常提交需五项 answered／unable_to_judge，四策略均满足才可正常进入下一任务。无法判断在程序上是有效作答，在数值分析中单列；不记为 4 或 0。评分分别报告，不计算五题总分。

可选 `reasons` 为去重集合：target_mismatch / unwanted_change / not_maintained / hard_to_verify / interaction_problem / other。A0 非 fully_met 时适用；not_maintained 仅在实际有后续交流时提供。所有答案均可另附确认后的 STT 备注。原因／备注不计五个题位，不阻塞继续。

### 4.3 自然模拟：natural-selective-feedback-v2

| 题 ID | 稳定字段语义 | answered 允许值／方向 | 其他有效正常作答 |
| --- | --- | --- | --- |
| N0 | goal_fit | `fully_met / partly_met / not_met`；显示 Fully / Partly / Not at all | unable_to_judge |
| N1 | perceived_understanding | 整数 1–7，同意度，高分积极 | unable_to_judge |
| N2 | expression_clarity | 同上 | unable_to_judge |
| N3 | control | 同上 | unable_to_judge |
| N4 | clarification_appropriateness | 同上 | unable_to_judge |
| N5 | unwanted_interruption | 整数 1–7，同意度，高分更多打断 | unable_to_judge／not_applicable |
| N6 | mental_demand | 整数 1–7，Very low → Very high，高分更多需求 | unable_to_judge |
| N7 | satisfaction | 整数 1–7，同意度，高分积极 | unable_to_judge |
| S1–S10 | sus_01–sus_10 | 各整数 1–5；保留完整 SUS 原文与顺序 | 仅显式 skipped；不加 unable_to_judge 量尺选项 |
| U1–U8 | ueq_s_01–ueq_s_08 | 各整数 1–7；原词对左负右正 | 仅显式 skipped；不加 unable_to_judge 量尺选项 |

英文题干及 UEQ-S 原词对见主设计 §11.4。SUS 的中文摘要不是施测题干，接线时必须使用原版英文；本文不授权改写原题。

**缺失协议在本步固定为保守规则：** N0–N7 正常提交要求有效正常作答；SUS／UEQ-S 每题须 answered 或主动 skipped，未触碰的空白不算已处理。允许显式跳答后提交问卷，记录 `completeness=partial`，不强迫填中点。技术缺失／其他空白不能自动变成 skipped 以放行；异常结束走未完成流程。此规则是本项目采集与分析约定，不声称是量表原作者的缺失插补方法。

- SUS：十题全部数值有效才计算，奇数题 x−1、偶数题 5−x，贡献和×2.5；任何缺失则 `sus_score=null`、`score_status=insufficient_items`。
- UEQ-S：原位置减 4；U1–U4 全部有效才计算实用质量均值，U5–U8 全部有效才计算享乐质量均值。分别记录各维 n_answered 和 score_status；不全则该维 null。两维完整性另记，不把单维有效说成完整 UEQ-S。
- 不插补，不自动反向合成诊断总分，不计算跨工具总分。派生分与原始答案分开；保存 `scoring_version=natural-scoring-v1`，永不覆盖原答案。

### 4.4 策略偏好

沿用 strategy-preference-v1：`scope=attribute / comparison_overall`；attribute 必须指定 domain，总体 domain=null。`choice_kind=selected / no_clear_preference / none_acceptable / unable_to_compare`；selected 时 selected_conditions 是 E/A/N/S 中 1–3 个的去重集合，其他分类时为空。无默认选择，不从评分推算偏好。

偏好关联其实际比较的 module_instance_id、task_id 和最终 submission_id 列表；正常属性偏好对应八题，总体对应四属性及其偏好。若中途退出，不伪造缺失偏好，不用 S 自然模拟补足比较范围。

## 5. 保存状态必须分开

### 5.1 记录阶段、同步状态与完整性

三者是独立字段，不用一个 completed 布尔值代替。

| 字段 | 取值 | 说明 |
| --- | --- | --- |
| `record_stage` | draft / submitted | draft 可多次修改；submitted 是后端接受的不可变最终快照 |
| `sync_state`（客户端） | local_only / pending / acknowledged / conflict | 描述是否同步，不表示满意、任务成功或问卷完整 |
| `completeness` | complete / partial | 所有核心题位均为该版本允许的 answered／unable_to_judge／not_applicable 才 complete；skipped 或其他缺失使整份 partial |
| `evaluation_status` | current / stale | 草稿是否仍对应当前结果／过程；历史提交的评价绑定不因后续状态改变而被重写 |

有效 Unable to judge 和 N5 not_applicable 不使采集完整性变成 partial，但相关数值仍不可计分。自然显式跳过 S/U 的问卷允许 submitted＋partial；提交不是“全部可计分”。

**“下一题”操作：** 先校验并请求提交，收到后端持久保存确认后再推进；不能先切题再异步赌保存成功。ack 丢失时显示待同步，使用同一 request_id 查询／重试，不重复建立任务或提交。断网时仍允许暂停、退出，已落盘草稿保留。

### 5.2 任务、模块与整场结束

- 生命周期使用 `active / paused / ended`，与问卷 record_stage 分开。终止时保存 `end_reason=normal_completion / participant_exit / technical_abort / researcher_stop`。
- 进程突然消失：先标记 `recovery_state=needs_reconciliation` 及最后可靠状态；不知道原因时保留 unknown，不捏造参与者主动退出或已正式提交。恢复后继续原身份；研究者明确终止才落结束事件。
- 普通暂停不等于 ended；实验暂停也不触发自动提交。
- 正常四属性任务完成要求四份当前有效反馈、冻结结果和任务提交事务全部落盘。结果 not_met 仍可正常完成实验步骤；提交不能改写 A0。
- 整场正常完成要求 32 个当前纳入的任务提交、四次属性偏好、一次总体偏好、自然会话明确结束及一份自然反馈提交。自然问卷的标准量表显式跳答可使整场流程 normal_completion，但问卷 completeness 仍 partial、量表分数可缺失。
- 中途退出不撤销已提交的前面任务；整场标未正常完成并导出实际覆盖范围。主分析是否纳入部分数据另由分析计划决定，导出不先删除。
- `consent_withdrawal` 如发生，作为独立研究管理状态处理，不把普通退出自动当撤回授权；按项目另行确定的数据处置流程操作。

## 6. 评价对象、修订和对话证据

四属性每份反馈固定绑定 participant_id、study_run_id、module_instance_id、task_id、condition、questionnaire_version，以及 `branch_revision / state_revision / reveal_id / feedback_revision`。任务最终提交保存四份问卷快照、共同 first_reveal 和最终各分支结果；不只保存指向可变草稿的指针。

改变分支结果、修复请求或被评价过程后，旧草稿标 stale；保留旧内容但要求重新确认当前 revision，不能自动沿用。单纯重看／重听不清空答案。提交后不原地覆盖；如确需研究者更正，通过附加 amendment 记录原 submission_id、理由、操作者与变更，不自动由“最后时间戳”替代原答案。

自然反馈绑定独立 S session_id、module_instance_id、evaluation_revision、最终状态快照及有序的 `evaluation_event_start / evaluation_event_end`。进入反馈前解决或明确停止在途请求，冻结范围。返回交流须显式重新打开，生成新 evaluation_revision 并使未提交旧反馈 stale；已经提交后的重做用新的模块实例，不悄悄续写到旧评价。

对话事件至少包含：身份关联、event_id、客户端顺序、服务端顺序、客户端 UTC 与服务端接收 UTC、说话者、事件种类、确认／提交后的 text、输入来源（STT／选项等）、request_id、condition（如适用）、question_id／exchange_id（如适用）与结果 revision。服务器排序与客户端发生顺序分别保留，不靠两台设备墙上时钟推定因果关系。

- 同一四策略初始请求保存一次原始 participant utterance，并由四分支引用；不能在分析中算成四次参与者发言。
- Tutor 模型生成、控制器澄清、结果呈现、音频播放分别记录。生成文本不是已听到的证据；共享请求之后的澄清回复必须绑定实际分支。
- 不保存参与者原始音频，不持久化中间 ASR 假设；保存最终实际提交文本。若 UI 允许修订，则记录最终提交文本和修订事实，不能伪装成未经修改的逐字录音转写。
- 可选问卷／偏好／访谈文字单独归类并绑定对象，只有确认的 STT 文本才进入正式记录；不进入 tutor 上下文，不自动影响数值答案。无备注与未确认转写不混为已提交备注。

## 7. 持久保存、幂等与恢复的实现要求

本节定义下一步验收边界，不声称现有 JSONL 写入已满足这些要求。

1. 客户端在发送已确认文本、草稿变更、提交／偏好请求之前，将内容和固定 request_id 写入应用持久目录；不得仅依赖内存字典。落盘失败需明确呈现失败，不显示“已保存”。
2. 后端确认前必须将身份、对象版本、操作结果、原始事件、最终快照及幂等回执可靠提交到持久存储。四策略任务最终提交与四份反馈快照是一个原子事务，不允许半份成功却返回整题成功。
3. 同 study_run_id 下同 request_id＋同规范化载荷重试返回相同结果和 submission_id；同 request_id 不同载荷返回冲突。幂等索引需跨后端重启保留，不能只存在缓存。
4. ACK 至少回传 request_id、对象 ID／revision、payload_sha256、submission_id（如为最终提交）、server_saved_at；客户端核对对应关系后才 acknowledged。哈希不把真实文本或密钥编码进文件名。
5. 客户端 ACK 后可移除待发队列项，但保留本场本地数据副本至研究者确认导出；不能因为已同步就把头显唯一备份一起删除。后端与头显的未确认数据都不可静默清空。
6. 重启恢复应重建对象状态、草稿、提交、导航、会话历史和待同步操作；优先与后端回执核对。恢复不能未经参与者操作重新调用模型、重放录音或再次执行调整。
7. 模型请求已发送但结果未知时保留 pending／unknown 操作证据，先核对后恢复；不可将结果未知当 not_met 或已成功。此契约保证研究提交幂等，不假定外部模型 API 支持严格一次调用。
8. 身份／版本／revision 不符时保留冲突数据供核对，不自动覆盖。断电或截断文件须可检测、可报告；不能静默跳过坏行后声称导出完整。

计划布局：后端按 collection_kind／participant_id／study_run_id 管理权威记录；头显使用 Application.persistentDataPath 下的 StudyData／study_run_id 保存本地副本及待同步队列。实际数据库／文件布局、原子写入和恢复技术在下一步选择；路径不是实验身份来源，不把 API 密钥打包到头显。

## 8. 导出契约

每个研究运行可独立导出，另支持多个运行的批量汇总；工程、练习、pilot、formal 默认分开。导出目录必须是新目录，保留原始日志，不覆盖旧导出。

| 文件 | 粒度与必要内容 |
| --- | --- |
| `session.json` | 研究身份、版本、实际顺序、生命周期、结束原因、恢复／重做关系与覆盖计数 |
| `attribute_feedback.csv` | 每个已提交 task_id＋condition 一行；A0–A4 的 value/status、原因、确认备注、questionnaire_id/version、submission_id 与评价 revision |
| `natural_feedback.csv` | 每个已提交自然问卷一行；N0–N7、S1–S10、U1–U8 的 value/status，SUS 与 UEQ-S 两维派生分、有效题数及 score_status |
| `preferences.csv` | 每份最终偏好一行，保留范围、集合／特殊选项与所评价任务提交引用 |
| `dialogue.jsonl` | 文本与呈现／播放证据，保留可追溯身份、顺序和源事件引用 |
| `events.jsonl` | 完整研究审计事件，含暂停、错误、重试、最终提交及更正；不等同只提取对话的 export_rows |
| `incomplete_records.jsonl` | 未提交草稿、stale 评价、异常结束、尚未同步／无法核对的对象；不伪装成最终问卷行 |
| `export_manifest.json` | 导出 schema 版本、生成时间、来源清单、各文件哈希、行数、提交／缺失计数、冲突／待同步情况 |

CSV 每个核心题同时含 `<ID>_value`、`<ID>_status`；空值字段为空单元格而非 0，原因另列。所有行携带 participant_id、study_run_id、module_instance_id、collection_kind 和各相关版本。字符串按 CSV 规范转义；可选 STT 文本不在表格中作为公式执行。

正式分析表只取最终提交快照，不能直接把所有 feedback_saved 草稿行倒入。自然问卷 submitted＋partial 保留在最终表，同时标注缺失／不可计分；不能因为它有跳答而丢弃整份已提交问卷。修订与重做另有关系字段，不默认择优取一次。

整场未完成时也允许导出，manifest 明确 complete／partial／unreconciled。正常完整采集预期为 128 份属性反馈、1 份自然反馈、5 份偏好；只有实际满足才报告这些计数。导出时无法联系头显而存在未知待同步量，必须写明未知，不用后端“当前没有待发项”推断头显已同步完。

## 9. 记录示例（目标格式，不是当前 API 请求）

以下示例仅示意一份**已被任务最终提交包含**的属性反馈。A0 为未达到仍可正式提交，A3 的无法判断不转中点；submitted 与研究结果成功分离。

```json
{
  "data_contract_version": "study-data-contract-v1",
  "protocol_version": "study-protocol-v1.7",
  "participant_id": "P0001",
  "study_run_id": "11111111111141118111111111111111",
  "module_instance_id": "22222222222242228222222222222222",
  "task_id": "33333333333343338333333333333333",
  "condition": "S",
  "questionnaire_id": "44444444444444448444444444444444",
  "questionnaire_version": "attribute-feedback-v3",
  "answer_schema_version": "study-answer-v1",
  "record_stage": "submitted",
  "completeness": "complete",
  "submission_id": "55555555555545558555555555555555",
  "answers": {
    "A0": {"status": "answered", "value": "not_met"},
    "A1": {"status": "answered", "value": 3},
    "A2": {"status": "answered", "value": 4},
    "A3": {"status": "unable_to_judge", "value": null},
    "A4": {"status": "answered", "value": 2}
  }
}
```

完整存储还必须有 study_id、collection_kind、时间、评价绑定和运行版本引用；示例省略这些值以免虚构实际采集事实。实际实现不得将此示例填为真实数据。

## 10. 后续实现的验收清单

1. 同一参与者恢复不新增样本；再次实验明确创建新运行并关联旧运行；各层 ID 不混用。
2. 新版拒绝旧 effort_ease／旧自然六题载荷；未知题、越界值、布尔分数和错误量尺不能提交。
3. Unable to judge、N5 未发生、跳答、未答与技术缺失分别往返保存／导出；缺失不补 0／中点。
4. 结果 not_met 可正常提交；退出不提交；已保存草稿不变成最终结果；整场退出保留前面已提交任务。
5. 四分支修订后旧评价失效；原子任务提交不产生仅一部分分支进入最终表的状态。
6. 自然段评价范围固定；迟到结果不混入；26 题混合量尺正确；不完整标准量表不被错误计分。
7. 客户端／后端重启、ACK 丢失、重复发送、断网恢复、写盘失败可检验；重复操作不重复计数。
8. 完整模拟运行导出 128＋1＋5 份预期记录；部分运行导出实际数量与缺失；每条评分可回溯对应对话与结果。
9. 头显原始音频不留存，问卷 STT 不进入 tutor，对话／问卷日志不包含 API 密钥。
10. 最后才开放正式采集；文档冻结和工程测试通过都不等于已完成真实头显验收。

尚不在本步确定：自然模拟具体时长、统一终止触发和共同初始值；正式任务顺序／休息安排；样本量与主要统计检验。这些不阻塞数据结构实现，但必须在相应正式流程开放前落实。下一步先实现保存、恢复和导出，再接新问卷及自然模块。
