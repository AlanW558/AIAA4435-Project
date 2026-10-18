# 外形实验原型

本模块在队友原仓库内增加独立桌面场景 `AppearanceExperiment.unity`。原 `CloudConversationRoom`、Pico 配置和既有交互保持原样。当前验证的是 Ubuntu 桌面 Unity 客户端；这版外形 UI 尚未接入 XR 射线输入，也没有声称在 Pico 上验证。

## 台式机直接运行

```bash
cd /home/enjixiong/academics/AIAA4435/AIAA4435-Project
bash Tools/AppearanceExperiment/run_desktop.sh
```

脚本使用现存后端或启动本地 `127.0.0.1:8765` 服务，再打开 Unity 独立程序。DeepSeek 密钥只由后端读取用户目录下的私有配置文件；客户端、Git 和实验日志不含密钥。停止客户端不会停止后端；已有会话只存在后端内存中，重启后请重新建会话，JSONL 审计记录仍保留。

首次使用选 `debug`、条件 `S`，点击 **Start manual session**，发送任务的初始请求。`F1` 隐藏研究者设置；之后可以回答澄清、输入修复、撤销全次修改或指定属性。角色支持六种衣服颜色、三种配饰和 0.85–1.15 的比例，步长 0.05。不会执行模型生成的任意代码。

正式分配模式需要明确选择 `formal` 和 `P001`–`P020`，按冻结 CSV 自动运行四个 block、每 block 四项任务。两个 pilot 单独使用 `pilot` 和不同编号，不能占正式编号。正式采集前先完成两人预实验并冻结规则、材料、超时和版本；原型工程测试不计入22名参与者。

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

- [Study/RUNBOOK.md](Study/RUNBOOK.md)：22人流程，建议2pilot+20formal，以及桌面/Pico实验边界。
- [Study/survey/questionnaire.html](Study/survey/questionnaire.html)：实验开始前、每轮结束后、全部结束后的中文问卷；本地导出 JSON，不自动上传。
- [Study/survey/README.md](Study/survey/README.md)：问卷星导入文本和真实回答导入器。

主持人先建立分配会话以生成编号，再让参与者填写开始前问卷；阅读任务卡不开始计时，点击 Send 才开始。问卷使用界面底部的研究级 `Study` 编号，贯穿四个 block；它不同于每个条件的后端 session ID。问卷只显示 block 编号，不显示策略标签。四项 1–7 评分是自拟单项，不合成未经验证的总分。

`StudyData/` 被 Git 忽略，保存 JSONL、实际角色截图、客户端日志和私有导出。完成后的三个固定中性回合分别读取材质、配饰 active 状态和 transform；端到端时间不含随后探针。构建 manifest 对实际二进制、数据和运行库逐文件计算 SHA-256，构建指纹随任务事件记录。

```bash
python3 Tools/AppearanceExperiment/export_study.py \
  --logs StudyData/logs --out-dir StudyData/export-formal
```

默认只导出 live/formal；debug、mock、pilot 都不混入正式结果。缺失探针/渲染/版本证据保留空值，不能把未测量写成成功。图表和结论必须等待真实参与者数据。

Codex 内置浏览器目前在执行前报工作目录 URI 错误，所以没有创建线上问卷。现成 HTML 与问卷星导入稿可用；具体错误和续作步骤见 [browser_creation_status.md](Study/survey/browser_creation_status.md)。

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
