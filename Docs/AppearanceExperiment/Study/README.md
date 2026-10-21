# 外形实验材料与现场运行

本目录把已确定的研究材料带入队友的 Unity 项目，开发不依赖 Pico 已经连接。当前桌面原型与真实头显采集必须分开报告；Pico 的沉浸式显示、追踪与控制器尚待本项目真机验收。

2026-10-18，用户更新招募情况：原先希望安排22人，但已有部分人无法到场，实际人数未定。保留2个预实验和20个正式槽位作为准备容量，按实际参加与完成情况报告。每名正式参与者仍体验四轮、每轮四项任务；320项只是所有正式槽位填满时的计划数量。少于22人不阻止收集或导入，预实验和调试不补入正式样本。未分配编号者按 [recruitment_order.csv](materials/recruitment_order.csv) 的固定顺序领取现有槽位，保留每个槽位的原分配。

旧问卷的录入记录显示，22 份回答中包含 19 份模拟回答和原有的 3 份；原有 3 份的来源也尚未核实。因此不能把旧问卷的 22 份记录当作 22 位真人样本，也不能据此认定与本次招募池重合。模拟或来源未核实的回答不进入真人研究结果。旧回答须逐条核实真实来源，并取得本人关联同意、核对已有匿名编号后，才能与本次记录关联。详见 [研究协议](materials/protocol.md)。

- [RUNBOOK.md](RUNBOOK.md)：主持、任务时序、问卷转换、导出与现场检查。
- [materials/protocol.md](materials/protocol.md)：保存的研究协议；旧阶段状态描述保留供溯源，当前实现状态以项目运行结果为准。
- [materials/policy.json](materials/policy.json)：原设计阈值和冻结字段。实际后端规则、模型标识与 prompt 哈希需一起记录；此文件中的早期未验证标记不会因为复制而自动成为验证结论。
- [materials/tasks_private.json](materials/tasks_private.json)：16 项私有评分目标；**不能传给模型或 Native gate**。
- [materials/public_task_resets.json](materials/public_task_resets.json)：16 项公开上下文的后端 reset 格式。去掉客户端提供的 revision，历史转换为 `{"state": ...}`；公开偏好转换为 `field/value/text`，不含私有目标。
- [materials/participant_schedule.csv](materials/participant_schedule.csv)、[materials/trial_schedule.csv](materials/trial_schedule.csv)：冻结前的 20 人分配与 320 项计划试次。
- [survey/README.md](survey/README.md)：中文问卷、本地可填写 HTML、问卷星导入草稿和导入器。
- [source_material_manifest.json](source_material_manifest.json)：从原工作目录复制的研究材料、来源与 SHA-256。
- [analyze_trials.py](analyze_trials.py)：原研究的参与者内客观指标分析器，不自动分析主观评分。

日志导出器位于 [Tools/AppearanceExperiment/export_study.py](../../../Tools/AppearanceExperiment/export_study.py)。导出器只在本地读取私有目标进行评分，不发起模型调用。缺少 renderer、探针、实际时长或构建证据时保留空值与问题报告，不将 JSON 状态猜成真实显示结果。

[tests/test_exporter.py](tests/test_exporter.py) 是临时目录中的工程测试，使用明确标记的 `mock/debug` 事件与渲染消息夹具；它们不是参与者回答、真实 Unity 渲染验证或真人实验结果。
