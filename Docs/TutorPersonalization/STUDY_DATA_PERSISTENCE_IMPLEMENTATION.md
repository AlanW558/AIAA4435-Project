# 研究数据保存、恢复和导出：实现记录

> **2026-11-17 后续状态：** 新版已完成部分本机人工麦克风转写、试听/播放、问卷保存/下一题、暂停/继续及口述备注确认；头显整体测试仍待完成。下文按原阶段保留验收范围，最新使用入口见[导航](README.md)。

日期：2026-11-16。依据：[数据保存契约 v1](Study/STUDY_DATA_PERSISTENCE_CONTRACT.md)。

## 1. 本步完成范围及边界

新增研究数据层 `/study`，与旧 `/tutor` 调试执行接口分开。已实现编号注册、研究运行及模块／任务关联、新版答案校验、草稿与最终提交、SQLite 持久事务、跨后端重启回执、恢复读取、头显端本地队列组件、完整／部分数据导出及本地副本核对。

**后续接线已完成：** 新研究模式的 TutorStudyFlowPanel、TutorClient／TutorComparisonClient 与保存层已关联；独立自然 Selective 执行器和新版 5／26 题问卷也已接入。实际操作、检查点恢复与验证见 [流程接入记录](STUDY_FLOW_INTEGRATION.md)。旧独立调试入口仍保留，不能与新研究运行混用。下方未更新的“下一步接线”文字描述最初保存层阶段。

正式 `pilot/formal` 创建继续拒绝，只接受 engineering/practice。新库没有导入／重标任何旧实验记录。此步不改 32 题任务内容、问卷题干、场景布局或音色配置，不使用真实参与者、麦克风或付费 API。

## 2. 已实现组件

| 文件 | 用途 |
| --- | --- |
| `Backend/study_store.py` | SQLite WAL＋FULL 同步；研究快照、事件和幂等回执单事务提交；参与者编号及生命周期 |
| `Backend/study_answers.py` | attribute-feedback-v3／natural-selective-feedback-v2；混合量尺、缺失类别、SUS 与 UEQ-S 分项有效性 |
| `Backend/export_study_data.py` | 每运行或批量导出最终 CSV、对话／审计 JSONL、草稿、运行元数据及哈希清单 |
| `Backend/study_reconcile.py` | 核对客户端副本的包体哈希、请求签名、后端回执、未同步请求和未被最终结果覆盖的草稿 |
| `Assets/Project/Scripts/Tutor/TutorStudyJournal.cs` | 先写盘后发送；不可变包、草稿、服务端快照、回执；临时文件恢复与损坏检测；保留原始本地副本 |
| `Assets/Project/Scripts/Tutor/TutorStudyDataClient.cs` | Unity 新研究接口传输，显式重试原请求和恢复读取；只在回执验证且本地保存成功后触发 Saved |
| `Assets/Editor/TutorStudyPersistenceChecks.cs` | Unity 内真实文件系统恢复与损坏检查 |
| `Backend/tests/test_study_store.py` | 新数据层行为、HTTP、事务失败、进程退出、重复请求及导出验证 |

SQLite 选用 WAL 和 `synchronous=FULL`，提交后才回执；依据 [SQLite 官方 PRAGMA 说明](https://www.sqlite.org/pragma.html#pragma_synchronous)。这不等于已通过真实头显断电／存储损坏验收。

## 3. 保存路径

后端数据库在 `<--log-dir>/study/study.sqlite3`。按现有 start_backend.sh 启动时为项目下：

```text
StudyData/logs/study/study.sqlite3
```

WAL 运行期间可能同时有 `study.sqlite3-wal`／`study.sqlite3-shm`；研究导出使用数据库一致性读取，不能直接只复制正在写入的主数据库文件当成完整备份。

Unity Editor 本地队列：`StudyData/macos/study-journal/`。头显／Player：`Application.persistentDataPath/StudyData/journal/`。每个不可变记录包含 kind、scope、sequence、payload 和 SHA-256；编号在记录中，不依赖文件目录猜测参与者。路径通过 Unity API 获取，见 [Unity persistentDataPath](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Application-persistentDataPath.html)。

此路径使用一个顺序日志，支持多研究运行的 scope；与契约中的“按 study_run_id 子目录”计划布局不同，但仍以 study_run_id／questionnaire_id 做身份关联和按运行导出。所有本地副本在回执后保留，不自动删除研究记录。

## 4. 接口与控制器接线方式

- `POST /study/commands`：统一操作入口。
- `GET /study/runs/<study_run_id>`：恢复研究状态。
- `GET /study/runs/<study_run_id>/snapshot`：界面使用的精简研究状态，不重复复制完整事件。
- `GET /study/runs/<study_run_id>/recovery`：同一数据库读取事务中的 state＋events，包括对话文本；`replay_model_calls=false`。
- `GET /study/receipts/<request_id>`：查询已可靠提交的原回执。

POST 包固定字段：request_id、operation、study_run_id（创建时可空）、expected_revision、payload_json（JSON 字符串）。request_id 为 UUID；请求重试保持整个包一致。服务端用整个包的签名核对幂等，并返回 payload_json 的 SHA-256，供 Unity 在不重排 JSON 字段的情况下验证。

操作顺序：

1. `register_participant` 或明确 ENG-/PRACTICE- 工程身份；`create_run` 保存实际 manifest、版本、任务顺序与集合。
2. `open_module`／`open_task`；题代码从创建时 manifest 查找，不用自然语言猜测。自然模块必须提供完整 initial_state，且比较总体偏好已提交。
3. `dialogue` 保存实际提交的参与者文字或 tutor 文字。共享初始输入只发一次 condition=null；分支澄清绑定对应条件。客户端控制器需将生成与展示／播放证据分别关联；本步不替换旧播放审计。
4. `bind_evaluation` 保存四个已结束／停止分支和 first_reveal_id。发生修复，仅变化分支的旧评价失效。相同 revision 的结果内容不能被替换。
5. `save_feedback` 保存草稿；`submit_task` 单事务冻结四份最终问卷；属性末和比较末使用 `preference`。
6. 自然段记录对话后，解决／停止在途请求，`freeze_natural` 固定事件范围和 final_state；保存一份自然反馈，再 `submit_natural`。
7. `pause`／`resume`／`connect` 保留原运行；`end_run` 明确正常结束、参与者退出、技术中断或研究者停止。

操作字段的可执行校验见 study_store.py；最小完整模拟示例见 test_study_store.py 的 Fixture。验证用 manifest/hash 明确标为工程 fixture，不能复制成正式材料版本。下一步接线须由真实 tutor 执行器提供结果和 revision，不能由参与者或模型填写“已完成”状态。

Unity 使用 `TutorStudyDataClient.Send`；先落盘再发送。离线问卷草稿使用 SaveDraft，JSON 结构为 `{"answers": {...}, "extras": {...}}`，scope 使用真实 questionnaire_id；恢复可从 Journal.RestoreLocal 读取。正文中保留原始数字／状态，不先计算总分。新控制器必须绑定 Saved 回执后才推进，不能收到网络返回前切题。

同一时刻只允许一个未解决的研究命令，避免多个离线操作猜测 revision。离线期间仍可单独保存本地草稿；服务端明确拒绝／冲突的原包保留供检查，不自动改 revision 或新建请求绕过冲突。重启不自动发送或调用模型，用户显式 Retry；恢复整场时同时读取研究快照与事件。后续需在问卷／实验管理界面显示待同步和冲突状态。

## 5. 导出和核对

在项目根目录使用 Python 3.10+：

```sh
python3 Backend/export_study_data.py \
  --data-dir StudyData/logs/study \
  --run STUDY_RUN_ID \
  --destination StudyData/exports/NEW_EXPORT_DIRECTORY
```

以上 STUDY_RUN_ID 和 NEW_EXPORT_DIRECTORY 为需替换的参数，不是已有参与者记录。批量导出使用 `--all` 替代 `--run`；目录按 collection_kind／participant_id／study_run_id 分开。已存在的目标目录拒绝覆盖。

有头显端日志副本时增加 `--local-journal /path/to/copied/journal`。Unity `Journal.ExportLocalCopy(newDirectory)` 可生成独立副本；在真实头显上如何触发导出／拷贝的研究者入口仍需在后续接线和设备测试中完成。

标准输出文件：session.json、attribute_feedback.csv、natural_feedback.csv、preferences.csv、dialogue.jsonl、events.jsonl、incomplete_records.jsonl、export_manifest.json。提供本地副本时另有 local_reconciliation.json。

- 最终表只包含 submitted 快照；不把 feedback 草稿每次保存都计作一个新答案。
- 已提交但量表跳答的自然问卷留在最终表，completeness=partial，相关分数为空并保留原因。
- 未提交、未开始、退出、stale 评价在 incomplete_records 中明确保留；前面已提交任务仍在最终表。
- CSV 保留每题 value/status/reason；原始分数和派生分分开，可选文本按防公式执行规则转义，原文字仍保留在 JSON。
- 没有客户端副本时标记 unknown_client_pending／unreconciled，不宣称头显已同步完。
- 有副本时，逐请求核对服务端持久回执，检查未发送草稿。只证明“提供的这个副本”已核对，不声称是对当前头显的实时检查。未被后端覆盖的草稿也会阻止“已核对”状态，文字保留在核对报告中。
- 程序在生成 manifest 前失败时，该目录不视为完整导出；保留现场，在新目录重试。

## 6. 验证与后续

执行：`python3 Tools/AppearanceExperiment/verify_study_persistence.py --out <新的验证目录>`。使用模拟模型和工程身份，覆盖完整 32 题及中途退出；不调用模型 API。真实输出见项目 StudyData/validation/study-persistence-20261116/ 下的 backend-verification/summary.json 与 unity-journal.json。

本步覆盖数据库持久保存／重启、丢失 ACK 后重复发送、并发同 ID、不同内容 ID 冲突、四策略最终提交原子性、模拟写盘失败回滚、进程在未提交事务中退出、单分支结果变化、未完成导出、SUS／UEQ-S 缺失，以及本地副本损坏／未同步草稿识别。Unity 检查覆盖本地包／草稿重启、临时文件恢复、回执内容核对、保留备份和坏文件阻断。

仍不宣称完成：旧执行器跨重启恢复、新问卷与自然模拟的真实控制器接线、Unity 新传输组件在头显上的端到端网络验收、真实断电验证、正式采集开放。下一步接入问卷／模块控制器时，应把新的研究身份与既有 task/session/revision 显式映射，再验证从 VR 操作到本地队列、后端、导出的一条实际链路。恢复未完成的 tutor 调用须明确核对／停止或由参与者重试，不得后台重放付费调用。
