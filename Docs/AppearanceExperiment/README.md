# 外形实验原型

本模块包括桌面实验场景 `AppearanceExperiment.unity`、PICO 房间 `AppearanceVR.unity` 和固定镜头录制场景 `AppearanceDesktopDemo.unity`。旧版已完成 PICO 实机 debug 验证；本次新增的两套形象正在单独验收，不能沿用旧版真机结论。最新状态见 [PICO 接续记录](PICO_HANDOFF.md)。

新增形象通过 debug 专用 [avatar-demo-v1](Pico/avatar-demo-protocol.md) 启用；默认的 study-v1 继续使用冻结的三字段协议与旧角色。问卷结果阅读见 [11 类结果与人数示例](Midterm/问卷结果解读与人数示例.html)，其中人数均为教学假设。

本次代码与资源交付见 [PR 交付说明](Pico/PR_DELIVERY.md)，可编辑工程见 [Blender 资产说明](../../Art/AppearanceAvatars/README.md)。2026-10-21 新收到的 15 份纸质问卷转录分析在 [真实结果与完整分析](Results/2026-10-21/问卷结果与完整分析.md)，与上面的模拟人数示例分开呈现。用户确认这次实际顺序统一为 N→E→A→S；分析使用该实际顺序，保留原冻结材料用于溯源。

## 台式机直接运行

```bash
cd /home/enjixiong/academics/AIAA4435/AIAA4435-Project
bash Tools/AppearanceExperiment/run_desktop.sh
```

脚本使用现存后端或启动本地 `127.0.0.1:8765` 服务，再打开 Unity 独立程序。DeepSeek 密钥只由后端读取用户目录下的私有配置文件；客户端、Git 和实验日志不含密钥。停止客户端不会停止后端；已有会话只存在后端内存中，重启后请重新建会话，JSONL 审计记录仍保留。

直接运行默认为调试自由交互，启动后自动连接。Unity只显示角色、修改输入、澄清、撤销和完成修改，不显示研究者设置、编号、阶段、策略、题目卡片或轮次；F1不会打开研究面板。角色仍支持六种衣服颜色、三种配饰和0.85至1.15的比例。

需要关联问卷时，先在本地问卷选择实验类型、填写参与者编号，在“研究者：关联记录”下载配置，再运行：

```bash
python3 Tools/AppearanceExperiment/launch_session.py --session-file /path/to/session.json
```

正式模式从既有CSV加载该槽位的16项任务。目标卡与公开历史、偏好由研究者在Unity之外提供；初始请求仍按统一实验脚本预填，后续修复可自由输入。每次完成修改后研究者按F8继续，每四项先暂停填问卷。调试和预实验可用 `--condition E/A/N/S`，指定 `--task` 才加载既有任务，否则自由交互。预实验不应使用正式目标卡作为练习。

22人是原始招募目标，现有2个预实验、20个正式编号是预留槽位，不要求填满。2026-10-21 已收到15份标记为正式的 PICO 体验问卷；其实际顺序和角色版本见本页上方结果报告，不能直接视为冻结日程已执行的证明。调试、预实验、正式日志仍分开；下一轮采集前完成预实验并冻结规则、材料、超时和版本。

## 四条件的公平边界

所有条件调用同一个 proposer，看到同样的公开状态、历史、软偏好和能力表。模型不接收任务私有目标、条件名或标准答案。候选去重、默认修改、澄清选项、视觉反馈、修复预算和撤销一致。

| 条件 | 初次请求的决策 |
|---|---|
| E | 对受支持的请求执行共同默认候选 |
| A | 对受支持的请求提问/确认一次 |
| N | 同一 DeepSeek 自行决定 ACT / ASK / UNRESOLVED |
| S | 按 R1 指代、R2 软偏好覆盖、R3 候选结果实质差异决定；可逆小幅缩放有例外 |

N 是 **Native-gate**，并非完全自由规划的原生 agent。N 的额外模型等待和 tokens 如实计入。S 的结构化证据由共同 LLM proposer 提取，因此不是无模型误差的规则系统。当前实际请求别名与响应别名都写入日志；别名不等于不可变模型快照。

所有条件最多一次初始政策性澄清、两次修复/撤销、120秒任务预算。unsupported、过期 revision、无效输出和 API 故障会明确失败；不会暗中切换 mock。补充解释与修复走共同解析器，不再循环提问。后端拦截超时后的修改提交。

## 任务、问卷与数据

- [Study/RUNBOOK.md](Study/RUNBOOK.md)：按实际到场人数运行，预留2个预实验和20个正式槽位，以及桌面/Pico实验边界。
- [Study/survey/questionnaire.html](Study/survey/questionnaire.html)：实验开始前、每轮结束后、全部结束后的中文问卷；本地导出 JSON，不自动上传。
- [Study/survey/README.md](Study/survey/README.md)：问卷星导入文本和真实回答导入器。

主持人在问卷中生成关联配置，取得参与同意后用同一配置启动互动。阅读独立任务卡不开始计时，点击“发送”才开始。问卷和客户端marker使用相同的 `study_session_id`，贯穿四轮；它不同于每个条件的后端session ID。四项1至7评分是自拟单项，不合成未经验证的总分。

`StudyData/` 被 Git 忽略，保存 JSONL、实际角色截图、客户端日志和私有导出。完成后的三个固定中性回合分别读取材质、配饰 active 状态和 transform；端到端时间不含随后探针。构建 manifest 对实际二进制、数据和运行库逐文件计算 SHA-256，构建指纹随任务事件记录。

```bash
python3 Tools/AppearanceExperiment/export_study.py \
  --logs StudyData/logs --out-dir StudyData/export-formal
```

默认只导出 live/formal；debug、mock、pilot 都不混入正式结果。缺失探针/渲染/版本证据保留空值，不能把未测量写成成功。本次问卷可以支持主观评分分析；成功率、完成时间等结论仍需对应的真实任务日志。

中文六页、32 题问卷已发布；实际链接和发布证据以 [publication_status.json](Study/survey/publication_status.json) 为准。旧草稿及模拟记录不能作为本次真人实验结果。

## 编辑、构建与检查

Unity **2022.3.62f3c1**。建议使用 `bash Tools/AppearanceExperiment/build_desktop.sh`，它在构建后恢复 Unity/PICO 自动改写的原项目设置。也提供菜单 `AIAA4435 > Appearance > Build Linux desktop experiment`。所需外部 SDK 和桌面环境见 [DESKTOP_APPEARANCE_ENV.md](../../Tools/DESKTOP_APPEARANCE_ENV.md)。生成场景与脚本都在当前 Git 分支中；只同步新模块，不覆盖既有场景。

当前 Linux 构建成功，但 PICO SDK 自带、未被本场景使用的 SpatialAudio 样例线框 shader 在 GLCore 下产生一条编译诊断；本角色使用的 URP 材质已实际运行并截图检查。该诊断不等于本项目完全无构建警告，后续 XR 集成应单独处理 SDK 兼容性。

```bash
python3 -m unittest discover -s Backend/tests -v
python3 -m unittest discover -s Docs/AppearanceExperiment/Study/tests -v
python3 Tools/AppearanceExperiment/verify_source.py
bash Tools/AppearanceExperiment/run_desktop.sh -appearance-smoke
```

最后一条使用真实 DeepSeek，产生少量 API 费用，工程记录固定为 debug。验证证据见本目录 `Validation/` 和 `engineering_backend_validation.json`；不能据此宣称 selective 优于其他策略。
