# 实际采集的数据

本目录 CSV 分配表是计划，两个 EMPTY_TEMPLATE 仅有表头，不是已取得的实验数据。私有任务卡禁止发送给 proposer、gate 或 Native-agent。

## 参与者与版本

参与者：匿名研究编号、pilot/formal、到场/退出/完成状态、可选的原问卷匿名关联号、是否接触过该系统、VR 经验（需新问，原 Q1 未测）。姓名与联络信息单独保管，不在模型日志里。

版本：构建 SHA-256、场景/角色/素材许可、Unity/XR/Pico 版本、API endpoint 与请求/响应 model 标识、thinking/采样配置、proposer 和 Native prompt 哈希、policy/task/schedule 哈希、运行平台和时间。API 密钥不写入日志。

## JSONL 事件

每条至少有 `session_id, participant_id, phase, trial_id, event, timestamp_utc, monotonic_ms, condition, state_revision`。事件：trial_start、request_submitted、model_request_start/end、proposer_result、gate_result、question_presented、answer_submitted、commit_attempt/success/failure、first_render_verified、repair、undo、participant_done、probe_result、trial_end。

- 输入：原始文本、实际发送上下文、历史和偏好；不包含私有评分字段。
- 候选：完整候选/排序/默认 patch、引用证据、合并与校验结果；记录候选是否覆盖目标，由独立 evaluator 后算。
- 决策：ASK/ACT/UNRESOLVED、R1/R2/R3 命中证据或 Native 输出、问题及选项顺序、回答；修复和技术澄清另计。
- 执行：expected/actual revision、前后状态、实际 renderer 材质 ID/配饰 active 状态/transform、错误/重试、撤销字段。
- 过程：首次提交与最终截图（只截角色/界面，避免无关人像）、每个探针状态、次数与时段、调用/token/可获得费用、帧时与掉线。

不同设备的 UTC 用来对齐；精确时长用同一设备的单调时钟，不能直接相减未同步设备的时间。`elapsed_ms` 从发送初始请求到声明完成或超时，包含等待与修复，不含随后探针；`service_wait_ms` 是这一时段内等待区间的并集，不能重复相加重叠调用；`probe_ms` 单列。

## 结果表

二值结果用 0/1，未测量用空值并记录原因，不把缺失当成功。stable_goal_success 需要目标允许集合、保持字段和三个探针都通过；first_commit_success 在任何修复之前取值，无提交为 0。collateral_change 指过程中曾有非目标字段误改，修好也仍为 1。

technical_failure、timeout、unresolved 保留在端到端分析。candidate_coverage 来自候选与隐藏目标的比较，不能传回模型帮助其决策。正文报告实际完成人数和每项指标的可用分母。

## 评分与访谈

每个 block 1–7 分：系统的提问打断了我的任务；我能控制哪些外形属性被改变；完成修改需要投入很多精力；我对本轮修改体验满意。1=非常不同意，7=非常同意。这些是自拟单项，不是已验证量表，也不合成总分。

访谈问哪次问题有用、哪次多余、何时更愿意先看结果再改。不要问“我们的选择性方法是不是更好”。用去标识化记录支持解释，不能把观察者推测写成参与者原话。
