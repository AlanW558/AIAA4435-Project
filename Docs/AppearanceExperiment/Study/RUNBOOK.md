# 现场运行与导出

## 开发阶段先完成什么

先在台式机桌面运行角色场景、DeepSeek 四策略、澄清选项、局部/整体撤销与日志，再接 Pico。桌面可完成完整交互与数据通路检查，不必等待头显。正式 VR 采集前另验收双眼显示、6DoF、控制器、文字可读性、角色颜色/配饰/比例与记录一致；桌面通过不写成 Pico 已通过。

模型与 API 密钥仅在后端。私有目标卡和评分字段仅在参与者显示/本地 evaluator；请求模块只发送 `public_task_resets.json` 中公开数据。检查模型日志没有目标答案或任务类别。正式图像卡仍需由实际 Unity renderer 生成，并与角色实际比例、颜色、配饰一致。

## 人员与编号

- 两位预实验：`PILOT01`、`PILOT02`，后端 `phase=pilot`，使用真实 API。`mode=mock` 仅供 `phase=debug` 的工程检查，不能进入预实验/正式数据。
- 二十位正式：`P001`–`P020`，`phase=formal`，严格按 `materials/participant_schedule.csv` 的条件、位置和任务集。不要因模型表现或旧问卷偏好调换。
- 原问卷回答和本次记录是同一受访者池的不同阶段，不累加为独立样本。只有取得可选关联同意且存在真实旧匿名代码时才匹配。
- 研究者给每人一个稳定 `study_session_id`，例如程序生成的 `P001_...`。四种条件可各自有后端 `session_id`；问卷里的 `session_id` 填**稳定的 study_session_id**，不是每 block 新建的后端 ID。所有客户端 marker 都保留这个稳定编号。

预实验使用单独练习/试测题，不先让两人看正式目标卡；目前保存的 16 张任务是正式任务草案，不是已验证的预实验题库。两位预实验不进入正式效果分析。正式预约暂按原 45 分钟计划；若试测发现任务、三探针、问卷和休息超时，正式开始前统一调整为 50–60 分钟，保留改动版本。

## 一人一场的操作顺序

1. 说明任务、日志/场景截图、DeepSeek 处理请求、数据用途和退出方式。确认本次新采集同意，填写 `survey/questionnaire.html?form=pre&participant=P001&session=<study_session_id>`。不同意就结束，不继续采集。
2. 用正式任务之外的例子练习：发送请求、选择澄清、其他/取消、查看效果、撤销、完成。确认参与者能理解中文任务和 UI；问卷为英文，预实验核实语言负担，不在条件之间切换语言。
3. 每个 block 按分配表建立/选中对应条件。参与者只看 Block 1–4，不展示 E/A/N/S 或“研究者提出的方法”。不主动解释哪种策略应该好。
4. 每项任务先 reset 规定状态/公开历史/公开偏好，展示私有目标卡和需保持属性。参与者阅读卡片后再发送固定请求；**计时从初始请求提交开始，不包含读卡/reset 时间**。
5. 四条件用相同候选、问题界面、选项顺序规则、外形 renderer、等待反馈与恢复入口。初始政策询问最多一次；后续修复/撤销合计最多两次。初始提交后的状态和截图在修复前保存。
6. 参与者完成或达到冻结的 120 秒上限时发 `completion` marker：`value=participant_done|timeout`，`elapsed_seconds` 为本机单调计时器的真实任务时长。系统等待包含在总时长中，不凭估计扣除。
7. 完成后检查三个固定中性 tutor 文本回合中角色属性是否保持。每次发真实 renderer 的 `probe`：`probe_index=1,2,3`、`revision`、`state`；分别计时后可带 `duration_ms`。探针不再改外形。完成时间与探针时间分开。
8. 一个 block 四项任务结束，填写 `?form=block&participant=P001&session=<study_session_id>&block=1`。四个 block 使用同一表、同一量尺；总共最多四次填写。下载 JSON 后确认实际文件已保存。
9. 四个 block 后填写 `?form=exit&participant=P001&session=<study_session_id>`。自选短答/访谈围绕具体有帮助和无帮助的事件，不引导参与者称赞某策略。现场确认所有实际日志和问卷文件已转存到私有数据目录。

若掉线、模型失败、无法实现、候选遗漏或用户退出，保留事件与剩余空值，不用模拟输出补齐。服务重启后内存中的会话不能恢复；保留原日志，另记中止/恢复过程，不能让重复试次悄悄变成新样本。

## 日志与字段来源

| 字段 | 来源与限制 |
|---|---|
| participant/condition/task/trial | 后端事件信封；block 从正式分配表关联并核对 marker |
| first_commit_success | 第一次修复之前的首次提交及同 revision 的实际 renderer 回执；没有提交记 0，没有视觉证据留空 |
| stable_goal_success | 末态 renderer 回执＋三个不同编号的实际探针，均满足目标、保持属性并与服务器末态一致 |
| collateral_change | 实际 renderer/probe 曾观测到非目标属性变化记 1；全部变化都有回执才允许记 0 |
| policy_questions | 后端初始 ASK 决策数；这是系统产生询问的次数，当前不等同于独立核验“用户确实看到了问题” |
| repair/undo | 已接受的后续请求和撤销事件；被拒绝的操作不计为成功修复 |
| elapsed_ms | Unity `completion.elapsed_seconds`；缺少时不拿跨设备时间戳估算 |
| service_wait_ms | 同一后端 run 的模型调用单调时钟区间并集，含实际重试；不重复加重叠区间 |
| probe_ms | 三次 `duration_ms` 实测之和；没有测量则空 |
| candidate_coverage | 本地 evaluator 将首轮候选结果与私有目标比较；是派生覆盖指标，不是用户成功率 |
| observed_build_sha256 | 客户端 marker 中实际构建 SHA-256；不使用随意填入的标签伪装哈希 |

每次导出有 `export_report.json`，记录源 JSONL 哈希、任务/分配哈希、每项指标来源和缺失原因。`analysis_ready=false` 不代表程序没跑通，而是现有记录不足以支撑预定正式分析；依据报告补齐**之后的真实测量**或显式记录当前缺失，不能补写不存在的过去证据。

## 导出与分析命令

在仓库根目录运行。下列路径是命令模板，不创建或暗示已有真实参与者数据。

```bash
# 默认只取 live/formal；debug、mock、pilot 不进入正式结果。
python3 Tools/AppearanceExperiment/export_study.py \
  --logs Backend/logs --out-dir /path/to/private/export-01

# 单独导出真实预实验，文件名前缀 pilot_。
python3 Tools/AppearanceExperiment/export_study.py \
  --logs Backend/logs --phase pilot --out-dir /path/to/private/pilot-export-01

# 明确选择工程调试；输出名 engineering_debug_trial_results.csv。
python3 Tools/AppearanceExperiment/export_study.py \
  --logs Backend/logs --phase debug --out-dir /path/to/private/debug-export-01

# 实际问卷下载 JSON → CSV；同一 study_session/form/block 重复会拒绝。
python3 Docs/AppearanceExperiment/Study/survey/import_responses.py \
  --input-dir /path/to/private/survey-downloads \
  --schedule Docs/AppearanceExperiment/Study/materials/participant_schedule.csv \
  --out-dir /path/to/private/survey-export-01

# 先核查 export_report 的缺失、重复、版本和完整性，再分析正式数据。
python3 Docs/AppearanceExperiment/Study/analyze_trials.py \
  --trials /path/to/private/export-01/trial_results.csv \
  --out /path/to/private/analysis-01.json
```

原分析器遇到缺失主指标会停止；不将缺失替换为成功/零，不把只成功的任务留下来比较速度。先报告实际完成人数与缺失机制，再决定完整个案/可用数据敏感性分析。问卷四个单项独立分析，不生成总 UX 分数。

所有实际问卷、关联表、API 记录和截图留在私有数据目录，不提交到公开 GitHub；本仓库仅保留空模板、研究材料、源代码和明确的工程验证说明。

## 当前尚需在采集前解决

- Pico 真机链路与对照一致性；桌面开发继续进行，不等于 VR 已验收。
- 实际目标卡截图；单独的练习/预实验题，不混用正式题。
- 记录真实构建 SHA、三探针时长、模型别名/返回版本及冻结时点。
- 将本地 HTML 的 JSON 下载纳入现场收集，或完成在线问卷草稿发布设置；本地页面不是已发布问卷星链接。
- 观察实际 API 的候选遗漏与无效询问；不只演示对 Selective 有利的例子。
