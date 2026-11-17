# 默认对话文本日志与分析证据

日期：2026-11-08；格式版本：`tutor-dialogue-v1`。

用户决定：对话文本记录默认开启，实验前由研究者告知参与者，VR 场景不增加提示或开关。用途是将参与者实际请求、tutor 输出与问卷评价对照，支持报告分析；不自动把评分与系统结果不一致判定为无效回答。

## 当前实现

日志随现有后端审计默认写入，无需启用参数。`dialogue_entries` 与原事件保存在同一条 JSONL 记录中，避免另写第二份文件导致源日志与对话副本部分成功。不会保存原始录音，也不会将问卷解释、研究者私有任务目标或分析日志重新送入 tutor 上下文。现有研究者日志不通过参与者 API 暴露，首次结果展示规则不变。

记录内容：

- 参与者实际提交的初始请求、后续请求及自由文本澄清；保存原提交文本，不用模型改写后的问题替换。
- 共同请求只记录一次，scope 为 shared；E/A/N/S 的澄清和后续输入归各自分支。提交相同 request_id 的重试不重复记录输入。
- tutor 最终生成的回答文本，以及实际回答设置、job_id、exchange_id。相同文本在不同策略中仍保留各分支记录；复用一次模型生成不代表只展示一个分支。
- 澄清问题与选项、设置修改说明；标为 controller 来源，与模型回答区分。点击选项只记 option_id 和 question_id，不编造参与者口述。
- 匿名参与者编号、会话/任务、方向/情境、策略、请求 ID、时间和版本。生成任务与请求通过 queued/completed job IDs 及检查点关联。
- 问卷反馈、首次揭示及页面展示单列为 evidence，保留版本关联；问卷备注不是 tutor 对话输入。

STT 尚未接通，因此目前记录的是现有 `SubmitUserUtterance` / 澄清接口提交的工程文本，input_source 为 `submitted_text`，不声称这些数据来自真实语音。后续 STT 接入时，最终提交给 tutor 的识别文本通过同一接口记录；尚未提交的识别片段、不采用的候选和原始音频不纳入本功能。问卷 STT 仍走独立反馈路径。

## 如何判断记录代表什么

| 记录 | 含义 | 不代表 |
| --- | --- | --- |
| request / clarification_answer | 收到了该文本，状态为 received_not_acceptance | 操作一定成功或目标已达成 |
| answer | 模型已生成该回答，状态为 generated_not_presentation | 参与者已看到或听到该回答 |
| clarification / setting_message | 控制器检查点已保存该内容 | 内容已经显示在头显中 |
| checkpoint | 状态版本及 queued/completed job IDs；比较模式另记 processing_branch_revision | processing 版本等同最终结果版本 |
| first_reveal | 四策略首次结果开放及其版本 | 四份结果已逐一阅读/听完 |
| panel_presented | 客户端报告选中分支和当前页面可见 | 用户阅读了整段文字、看到了滚动区域全部内容或完成音频播放 |
| feedback | 反馈版本、被评结果版本和答案 | 自动的客观成功判定 |

对照问卷时，以 task_id、condition、branch/state revision、reveal_id 关联原始反馈与展示证据；再通过检查点、job_id、exchange_id 和 request_id 找到对应文本。completed_answers 中的文本摘要用于区分同一生成任务在失败重试中产生的不同输出，不把未提交的旧尝试当成最终回答。失败保留已收到的输入；若生成后落盘/提交失败，不能把 generated 记录算作已提交或已呈现的回答。音频播放完成证据要等语音模块实现。

## 保存位置与导出

路径相对于后端启动时使用的日志目录：

- 单会话：`tutor/debug/<session_id>.jsonl`
- 四策略：`comparisons/debug/<task_id>.jsonl`

目前 tutor 系统仍只开放 debug，不因新增日志而自动成为正式研究版本；工程 fixture 不能混入正式数据。实际日志目录沿用启动脚本/服务配置。

在项目根目录运行：

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/export_tutor_dialogue.py \
  '/absolute/path/to/task-audit.jsonl' \
  '/absolute/path/to/new-dialogue-export.jsonl'
```

导出按稳定 entry_id 去重，附原文件名、行号及事件名；只导出对话和明确的分析证据，不复制提供商提示词、配置密钥、内部决策过程或预置演示对话。原审计日志不变。已有目标文件拒绝覆盖；源文件损坏或最后一行未写完时明确报错，不静默漏掉记录。建议结束任务后导出。

旧日志可以投影兼容事件，但缺失的字段不会补造；特别是旧单会话 operation_started 未保存原输入，不能据此声称可完整恢复原提交措辞。新增格式从更新后的后端进程起生效，已运行的旧后端需要重新启动。

## 验证

新增 13 项固定模型测试：原始文本与改写分离、澄清和选项、请求/生成重放、模型失败、日志失败后的未发布回答、四分支隐藏屏障及首次揭示关联、问卷/展示分类、配置/预置历史排除、异常输入、导出溯源与禁止覆盖、截断文件报错、同一生成任务不同尝试的精确文本关联。

最终全量后端 **322 项测试通过**（含新增 13 项）。新增功能未改 Unity 面板，未调用课程 API，未录音，未执行真实 STT 或头显测试。

本地固定文本示例：`StudyData/macos/dialogue-logging-check/`，仅用于验证记录与导出，不是参与者数据。
