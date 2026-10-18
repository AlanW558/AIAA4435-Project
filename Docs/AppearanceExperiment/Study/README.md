# 外形实验材料与现场运行

本目录把已确定的研究材料带入队友的 Unity 项目，开发不依赖 Pico 已经连接。当前桌面原型与真实头显采集必须分开报告；Pico 的沉浸式显示、追踪与控制器尚待本项目真机验收。

参与者池是原问卷的同一批 **22 人**，其中 `PILOT01`、`PILOT02` 做预实验，`P001`–`P020` 做正式探索性实验。正式每人四个 block，每个 block 四项任务，计划 320 项试次；这些是计划数量，当前材料不是已收集数据。

- [RUNBOOK.md](RUNBOOK.md)：主持、任务时序、问卷转换、导出与现场检查。
- [materials/protocol.md](materials/protocol.md)：保存的研究协议；旧阶段状态描述保留供溯源，当前实现状态以项目运行结果为准。
- [materials/policy.json](materials/policy.json)：原设计阈值和冻结字段。实际后端规则、模型标识与 prompt 哈希需一起记录；此文件中的早期未验证标记不会因为复制而自动成为验证结论。
- [materials/tasks_private.json](materials/tasks_private.json)：16 项私有评分目标；**不能传给模型或 Native gate**。
- [materials/public_task_resets.json](materials/public_task_resets.json)：16 项公开上下文的后端 reset 格式。去掉客户端提供的 revision，历史转换为 `{"state": ...}`；公开偏好转换为 `field/value/text`，不含私有目标。
- [materials/participant_schedule.csv](materials/participant_schedule.csv)、[materials/trial_schedule.csv](materials/trial_schedule.csv)：冻结前的 20 人分配与 320 项计划试次。
- [survey/README.md](survey/README.md)：英文问卷、本地可填写 HTML、问卷星导入草稿和导入器。
- [source_material_manifest.json](source_material_manifest.json)：从原工作目录复制的研究材料、来源与 SHA-256。
- [analyze_trials.py](analyze_trials.py)：原研究的参与者内客观指标分析器，不自动分析主观评分。

日志导出器位于 [Tools/AppearanceExperiment/export_study.py](../../../Tools/AppearanceExperiment/export_study.py)。导出器只在本地读取私有目标进行评分，不发起模型调用。缺少 renderer、探针、实际时长或构建证据时保留空值与问题报告，不将 JSON 状态猜成真实显示结果。

[tests/test_exporter.py](tests/test_exporter.py) 是临时目录中的工程测试，使用明确标记的 `mock/debug` 事件与渲染消息夹具；它们不是参与者回答、真实 Unity 渲染验证或真人实验结果。
