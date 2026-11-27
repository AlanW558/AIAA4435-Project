# 新问卷、实验流程与保存链路接入

> **2026-11-27 最新实现修订：** Unity 新建运行与辅助工具统一为每属性八题后填写 20 项评价及一次属性偏好；任务卡采用三字段，移除固定试听，属性通过 Confirm changes 统一提交。详见[本次实现契约](Study/GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)。下文较早日期的逐任务流程与试听设计为历史记录，不作为当前实现要求。

> **2026-11-17 后续状态：** 新版已完成部分本机人工麦克风转写、试听/播放、问卷保存/下一题、暂停/继续及口述备注确认；头显整体测试仍待完成。下文按原阶段保留验收范围，最新使用入口见[导航](README.md)。

更新：2026-11-16。依据 [数据保存契约](Study/STUDY_DATA_PERSISTENCE_CONTRACT.md) 和 [研究设计 v1.7](Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)。这是程序实现记录，不是参与者实验结果。

> 后续自动联调已开展：真实 Qwen 语音、丢失回执、后端／Unity 进程重启与未提交草稿恢复，见 [真实语音与恢复记录](STUDY_SPEECH_RECOVERY_ACCEPTANCE.md)。真人录音和头显检查仍未进行。

## 1. 当前运行流程

`TutorComparisonDesktop` 与 `TutorComparisonVR` 场景中的 TutorPanel 已启用 `durableStudy`，运行时创建独立、不透明纸色的 `TutorStudyFlowPanel`，沿用既定左前方座位偏移。主控制面板保留对话、属性调节和修改历史；实验面板负责说明、问卷、偏好、暂停、恢复和退出，并可隐藏／显示。

1. 开始时登记匿名参与者编号及既往参与情况，建立独立 study_run_id。当前按钮只创建 **engineering** 运行。
2. 按实际加载的 32 题任务材料建立模块、任务和执行器关联。每属性 8 题，共四个属性。每题使用既有公开起点／历史，确认准备后以参与者的一次输入运行 E/A/N/S。
3. 保留澄清屏障：需要询问的策略完成澄清之前，其他策略不提前展示结果。全部完成或明确停止后才能保存该任务结果。
4. 每题 `finish_task` 保存完成证据，不填逐任务问卷。每属性八题完成后，每个策略填写 **attribute-summary-feedback-v3，A0–A4 五道七点评分题**；先逐份保存，再原子提交四份最终结果，收到持久回执后填写属性偏好并进入下一属性。需求满足程度为1–7，不把A0–A4的“无法判断”换成中点；旧v1类别和v2数字A0仍按各自版本恢复。
5. 每完成一个属性收集一次策略偏好；32 题结束后再收集一次四策略比较的总体偏好，共 5 次。当前 `strategy-preference-v2` 可多选1–4个E/A/N/S，或互斥选择No preference；不再提供偏好无法判断，没有预选答案。新run在manifest固定问卷和偏好版本。
6. 比较总体偏好提交后，建立独立 **Selective 单策略自然交流** session。参与者根据方向性说明自由调整交流属性和外观，不强制划分阶段。主面板切换为单策略执行器。
7. “Finish conversation · open questionnaire” 要求没有待回答澄清或待生成回复；保存最终状态及对话事件范围后冻结交流，进入 **natural-selective-feedback-v2，26 题**。
8. 自然问卷保存后单独提交，再将运行标为 normal_completion。自然反馈评价连续 Selective 体验，不混入前面四策略横向评分。

自然模块本次使用后端默认配置作为明确记录的工程起点，没有新增正式时间上限。正式时长、共同起点、休息和分配流程仍需冻结。

## 2. 问卷及局部修订

问卷清单位于 `Assets/Project/Resources/Tutor/StudyQuestionnaires.json`，包含英文题干、量尺、缺失选项和来源注记。创建研究运行时记录该文件及任务材料的真实 SHA-256。

- 四属性：A0 分类；A1 难易度 1–7；A2 控制感、A3 澄清决策适切性、A4 总体满意度均为同意度 1–7。不计算混合总分。
- 自然：N0 分类、N1–N7 项目题；S1–S10 保留完整 SUS 及原 1–5 量尺；U1–U8 保留 UEQ-S 的 1–7 词对。题干来源及改编边界仍以研究设计文档为准。
- 自然 N5 可选“没有发生澄清”；SUS／UEQ-S 可明确跳题，缺题时相应量表分数留空并标 insufficient_items，不补中点。原始值与状态都导出。
- 四属性五题同页，四策略可切换；自然 26 题分页，可返回修改。所有评分默认未作答。
- 可选原因和口头说明独立于核心题。问卷 STT 使用专用研究端点，不进入 tutor 对话上下文；完整转写可滚动复核，确认后才保存文本，不保存参与者录音。
- 修改某分支结果后，提交旧评价会被后端拒绝。刷新结果时仅该分支的本地评分重新置为未答，要求重新填写；未变化的策略保留评分。旧草稿和已保存历史仍在不可变日志中。单纯重听／切换策略不清空评分。

## 3. 已接通的保存关系

`participant_id → study_run_id → module_instance_id → task_id / natural session_id → runtime_id → questionnaire_id → submission_id`。

新增 `Backend/study_flow.py` 将实际比较执行器／单策略执行器绑定到研究对象；`study_runtime.py` 保存可恢复的明确 JSON 检查点。模型输入、参与者输入、澄清、模型输出及既有展示／播放审计，从执行器 JSONL 按偏移导入研究数据库事件，导出时转为带研究身份的 dialogue.jsonl。

Unity 对提交的对话命令也先写本地文本证据，再发送。问卷每次选择先存本地草稿；“保存”及“下一题”通过 `/study/commands` 的不可变包、事务和回执链路。未提交草稿、最终提交、同步状态继续分开。

界面刷新用 `GET /study/runs/<id>/snapshot` 读取精简状态，不在每次答题时重复下载并复制整段历史。界面快照还省略已提交问卷／任务中的大结果正文，保留编号、进度及答案。完整 state＋events 仍由 `/recovery` 和导出提供；两种读取都不自动重放模型调用。

## 4. 暂停、恢复与故障边界

- 暂停阻止新的交互并保留当前结果。退出保留退出意图和已有数据，不把未答问卷填成失败／中点。
- “Restore saved session / retry” 或 “Sync / retry” 使用原运行和原请求编号；服务端已保存但客户端未收到回执时不会重复提交。
- 已完成／等待澄清的执行器可从检查点恢复；不会自动播放旧音频。当前问卷草稿按 questionnaire_id 和评价依据恢复。
- 请求已发送但后端崩溃、结果仍未知，或检查点仍在 processing 时，恢复会阻止自动重跑模型。保留证据，核对或以 technical_abort 结束该尝试；本次没有宣称外部模型调用严格一次执行。
- 4xx 明确拒绝保留原请求及 rejection 记录；网络中断保留待重试包。只有匹配并落盘的保存回执能推进。
- 文件写入失败会阻止提交；不会显示“已保存”然后跳题。

## 5. 保存和导出

实际路径沿用 [保存层实现记录](STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md)：

- 后端：`StudyData/logs/study/study.sqlite3`（默认启动方式）。
- Unity Editor：`StudyData/macos/study-journal/`。
- 头显：`Application.persistentDataPath/StudyData/journal/`。

在项目根目录导出已保存运行，替换下面 RUN_ID、NEW_EXPORT_DIRECTORY 及副本路径：

```sh
python3 Backend/export_study_data.py \
  --data-dir StudyData/logs/study \
  --run RUN_ID \
  --destination StudyData/exports/NEW_EXPORT_DIRECTORY \
  --local-journal /path/to/copied/journal
```

正常导出包含 session.json、attribute_feedback.csv、natural_feedback.csv、preferences.csv、dialogue.jsonl、events.jsonl、incomplete_records.jsonl、export_manifest.json；提供本地副本时另有 local_reconciliation.json。未提交问卷不混入最终评分 CSV。导出目标必须是新目录。没有头显副本时，不宣称已核对头显的未同步记录。

对话与问卷权威数据在后端；头显保留本地证据和待同步副本。**打包进头显不意味着把 Python 后端或密钥放进 APK**：头显仍需连接运行中的后端。Android 联网、应用沙盒实际位置、研究者取出副本及断电验收属于设备部署步骤。

## 6. 验证与剩余工作

验证脚本：`Tools/AppearanceExperiment/verify_study_flow.py`；后端桥接专项测试：`Backend/tests/test_study_flow.py`；Unity 实际控制器检查：`TutorStudyFlowChecks.cs`。

完整流程使用本地 fixture 模型，自动操作真实 Unity 控制器，而不是直接构造最终问卷文件。验证 32 题、澄清屏障、四份问卷提交、五次偏好、自然 Selective 交流、26 题及最终导出；不使用真实参与者，不调用付费模型，不录音。验证结果位于 `StudyData/validation/study-flow-20261116/`：

- `run-05/unity-flow.json`：完整 32 题及自然段通过，571 项运行断言；包含分支结果修改后评分失效、重新填写、恢复草稿和按钮随结果启用的检查。
- `run-05/export/`：128 行属性反馈、1 行自然反馈、5 行偏好；incomplete_records 为 0，提供的本地日志副本核对通过，export_status=complete。这里的数据全为工程合成数据，禁止用于报告中的参与者分析。
- `backend-tests.log`：最终完整后端回归结果。专项覆盖实际结果关联、未知在途请求阻止重放、执行器重启恢复、STT 评论不进入对话／不保存原始音频、幂等重试及精简快照不改变权威记录。
- `final-compile.log`：完整流程验证之后的最终编译检查。后续小修正为省略快照中重复的已提交评价正文，以及问卷录音／转写时禁止试听插播；前者由专项及完整后端回归覆盖，后者编译通过，真实录音与播放互斥仍需设备验证。

初始失败记录 run-01／run-02 也保留，便于追踪已修复的请求句柄和长流程快照问题。run-03／run-04 是较早的完整通过记录，不替代最终版本说明。

本阶段已接线，不等于正式研究验收。仍保持 pilot/formal 禁用；还需真实语音与头显交互验证、网络中断／应用退出／重启和文件取出验证。Build Settings 未在本步切换；正式 APK 构建与安装留给设备部署阶段。
