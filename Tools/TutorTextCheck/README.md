# 批量文本请求辅助检查

这是现有系统的文本请求辅助检查工具。它复用项目当前 `TutorComparisons`、固定任务材料、四策略规则、统一揭示及 TTS，供研究者绕过麦克风／STT 检查效果。2026-11-27 按用户要求将当前试听页面的问卷从逐任务填写改为逐属性填写，详见[属性级问卷修订](../../Docs/TutorPersonalization/Study/ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)。该问卷修订没有改变任务；随后按用户要求更新了资源题库的起点、目标与参考材料，并改为连续显示编号，详见[任务对比与编号修订](../../Docs/TutorPersonalization/Study/TASK_CONTRAST_AND_NUMBERING_REVISION.md)。当前工具不会创建正式参与者记录或自动填写评分，资源变更也不代表头显已重新验收。

## 用户填写

默认文件：`StudyData/text-check-v3/TASK_REQUESTS.md`，共 32 题。每个情境按 1／2 连续显示；内部检查点和日志仍使用原 task_code。上一批 `StudyData/text-check/` 保留，不能把它的结果视为新版任务输出。

当前 v3 文件已从之前确认的口语化请求预填，音色名称已同步。2026-11-27 经用户授权已完成 32 题真实 API 执行与 128 个实际回复音频生成；试听与空白属性问卷位于 `StudyData/text-check-v3/REVIEW_AND_QUESTIONNAIRE.html`，41 次实际澄清记录位于同目录 `CLARIFICATION_LOG.md`。本批使用 `--request-source assistant_revised_user_authorized` 保留代拟／修订请求来源；用户自行重写的输入则使用默认来源。需要更改已提交请求时创建新批次，不改写本批结果。

每题三个区域：Request（用户填写）、Clarify（脚本填写）、Clarification（用户后续填写）。在对应 HTML 注释之间输入自己的英文，保留注释与任务正文。可以先填全部请求，也可以留空部分；空白不会被当成请求。任务卡只显示 Task goal、Keep unchanged、Request example。音色使用 Female voice 1/2/3、Male voice 1/2；没有固定试听或参考音频。

多个策略提问时，例如在 Clarification 区填写：

```text
A: <your own answer to A>
S: <your own answer to S>
```

这里的尖括号内容只是说明，不是默认答案。不要将上面的占位内容作为请求提交。只有一个策略提问时，也可直接填写原文。脚本不会把一个回复广播给多个策略。若继续出现澄清，保留历史后更新该题的 Clarify，再填写新的回复。

处理过的 Request 不能原地改写；若需要重做，使用新检查目录。原文件回填前会保存完整副本，已提交澄清另有逐轮记录。问卷与音频输出不写进 Request 文件，以免提前影响澄清。

2026-11-27 本批执行时，用户进一步授权助手按任务目标代拟口语化澄清。仅在这种明确授权下使用 `process --clarification-source assistant_authored_user_authorized`；实际问题、回复、策略和来源均保存，不冒充用户亲自说过的话。新版发布保留跨后续回答轮次的全部澄清记录，不能因为检查回答内容而丢掉此前问答。

## 调用顺序

在仓库根目录运行。无模型调用的检查可直接使用 Python 3.10+：

```sh
python3 Tools/TutorTextCheck/workbook.py check StudyData/text-check-v3/TASK_REQUESTS.md
python3 Tools/TutorTextCheck/batch.py status
```

需要真实模型／语音的命令由 `run.sh` 读取现有私有 `.env` 和课程密钥文件，不将密钥写入 notebook、问卷或结果。使用与项目一致的 DeepSeek／Qwen 实现；不会调用 ASR。可以通过 `APPEARANCE_PYTHON` 指定 Python。

```sh
# 默认每次最多处理四题；题内四策略并行，题间顺序执行。
bash Tools/TutorTextCheck/run.sh process --limit 4

# 填完实际澄清后，执行同一命令；原请求及已提交回复不会重复执行。
bash Tools/TutorTextCheck/run.sh process --limit 4
```

多次调用会继续处理尚未执行的输入。可以显式使用 `--limit 32`，并不同时发起 32 题的全部云端请求。模型调用可能耗时，命令进程需要保持运行。

只有本文件所有非空请求均已执行、所有实际澄清已处理，且没有待提交回复，才允许发布结果。每题原有屏障仍然生效。先完成的分支不会被提前生成可播放结果。

```sh
# 全批澄清完成后，按需要分批合成并保存结果。
bash Tools/TutorTextCheck/run.sh publish --codes R1-1 R1-2
```

四个属性全部播放模型针对本次真实交互生成的回复。单独修改属性后，由模型根据实际执行结果和当前配置生成回应；未修改或未解决的分支也必须如实回应。没有新回复时禁止用固定句或历史起点替代。`publish` 只对新的回复做 TTS，不再生成 Starting sample / Reference，也不生成逐任务 `feedback.json`。

需要额外学习问题时仍可显式使用 `followup --text-file ... --codes ...`，它作为独立交互记录；不再是发布四属性结果的默认前置步骤。

## 保存位置和反馈

本批检查数据位于被 Git 忽略的 `StudyData/text-check-v3/`：

- `TASK_REQUESTS.md`：可填任务表，使用参与者显示编号。
- `catalog.json`：本批冻结的任务材料快照，按 batch 内 SHA-256 校验；报告优先使用此快照，避免题库后续更新改变旧批次的含义。
- `worksheet-history/`：每次回填前的原始文件副本。
- `tasks/<code>/checkpoint.json`：带摘要的稳定状态、原输入、澄清对应关系及操作记录。
- `logs/`：同一核心引擎产生的原始文本与策略执行记录。
- `audio/<code>/`：WAV 与 JSON 元数据，包含文本、设置、策略、结果身份、TTS 模型及 SHA-256。重听复用文件，不重新生成。生成／保存不表示用户已听完。
- `results/<code>/<release-id>/result.json`：对应这次结果版本的文本、完整可见状态、四策略实际回复音频和澄清记录。新版本不含固定起始／参考音频。
- 旧批次中的 `feedback.json`：原逐任务 `attribute-feedback-v3` 模板，只作旧格式兼容；新版本不会创建它。
- `feedback/`：已有逐任务反馈。旧记录保留，不自动平均、改写成属性级答案或删除。
- `attribute-feedback/<domain>/<sha>.json`：校验保存后的属性级反馈；修改后的版本另存并通过 `supersedes` 关联前一份，不覆盖旧回答。

当前问卷版本为 `attribute-summary-feedback-v3`，每个属性一份记录：四策略各回答 A0–A4，加一次属性内策略偏好。A0 继续为 1–7 分的需求满足程度，A0–A4 各自的 Unable to judge 保留。偏好支持 1–4 个唯一 E/A/N/S，或互斥的 No preference；新偏好不再提供无法判断。已答偏好为数组（如 `["N","S"]`），未答仍是 `unanswered/null`。记录包含批次、属性以及该属性八道任务的结果版本映射；某道任务结果发生变化时，旧属性答案不能静默用于新结果。页面支持下载单个属性和已完成属性集合，二者均可通过以下命令校验保存：

```sh
python3 Tools/TutorTextCheck/batch.py attribute-feedback --file /absolute/path/to/attribute-feedback.json
```

可在新位置生成空白多选页并复用已发布音频（先创建目标目录），不改旧批次元数据或旧 HTML：

```sh
python3 Tools/TutorTextCheck/report.py --directory /absolute/path/to/source-batch --output /absolute/path/to/new-folder/REVIEW_AND_QUESTIONNAIRE.html --questionnaire-version attribute-summary-feedback-v3
```

`--questionnaire-version` 也接受 v1/v2，以原量尺和偏好格式读取历史结果。新页面使用独立版本草稿键，不自动复制已有评分。外置页面通过相对路径引用源音频；移动或分享时保留两者的相对目录结构。

`Download all drafts (backup)` 导出的未完成草稿仅作备份，不作为最终完成记录导入。旧 `feedback --file` 命令仍用于原有逐任务记录，不能把新属性记录传给旧入口。

这些是辅助检查记录，不冒充原 StudyStore 的正式问卷提交或完整实验导出。不会为了批处理而伪造问卷、跳过 VR 流程门槛或恢复旧 `effort_ease` 量尺。工具内执行壳保留内部旧版本标识；新发布与属性问卷明确使用属性级版本和保存结构，旧发布保留原版本，不能与逐任务 `attribute-feedback-v3` 混称同一测量单位。

同一份反馈重复保存返回原文件；同一问卷版本内修改后的反馈另存并关联 `supersedes`，不覆盖旧评分。旧 `attribute-summary-feedback-v1` 的 A0 分类答案仍按其版本验证；v2 的 A0 保持数值、偏好保留单选标量与旧 unable 状态。旧版不会自动升级为多选，分类答案不能转换为数值或合并分析，跨版本也不关联为互相替代的评分。每批固定非敏感模型配置及 TTS／音色配置指纹，换模型时拒绝混入；不保存密钥。

## 中断与并发

同一目录一次只允许一个 CLI 进程。稳定的待澄清／结果状态可在下一次命令中恢复。每次模型或 TTS 操作先持久记录 pending，再执行；若进程被杀、调用异常或写盘失败，保留原输入并停止，不能自动重放不确定的模型请求。TTS 未知结果也不能伪装成已缓存。此类情况需人工核对日志或在新的检查目录明确重做；没有“清空后自动再试”的后备操作。

回填时检查文件是否在处理期间被编辑；发现变化时拒绝覆盖，执行结果仍保留。`sync` 可以在核对后重新回填。备用原文和结果不会自动删除。

若引擎已明确记录为 failed（不同于结果未知的 pending），研究者可以仅重试失败部分，不重跑其它已完成题目。例如：

```sh
# 已知失败的共同解释步骤
bash Tools/TutorTextCheck/run.sh retry --task R1-1
# 或已知失败的特定分支
bash Tools/TutorTextCheck/run.sh retry --task R1-1 --condition S
```

retry 是显式模型调用，不自动执行；未知 pending 会拒绝此操作。它不改变其它策略的结果，也不替参与者选澄清答案。

明确重试仍失败时，可用 `stop-failed --task TASK_CODE` 保留错误快照并停止失败分支。发布时这些分支的 `audio` 为 null，必须同时有 stopped 状态和 `technical_failures` 证据；不能把起点 sample 伪装成有效结果。其他有效分支仍可试听。统一后续学习问题跳过这些失败分支，不偷偷修复失败的调整。

## 本地试听与属性级问卷

```sh
python3 Tools/TutorTextCheck/report.py
```

生成 `StudyData/text-check-v3/REVIEW_AND_QUESTIONNAIRE.html`。打开后可按连续显示编号浏览每个情境的两道任务。每题显示三个任务字段，再比较四策略实际生成的输出。旧批次的固定音频和原始记录仍保留于原目录，不能作为新版结果。新页面不展示 Starting sample / Reference。

当前页面使用 A0 七点评分的 v2 问卷。改版前的分类问卷页面保存在同目录 `REVIEW_AND_QUESTIONNAIRE_v1.html`，继续使用原浏览器草稿标识；需要回看旧答案时打开该文件。两个版本共享已生成的音频，评分草稿相互独立。

每个策略旁显示实际澄清问题、答复及其来源，并显示 **Recorded result** 和目标属性起始→最终值。`Unresolved`、`No setting change` 或 `Settings changed` 来自真实 outcome／settings，`ready` 不代表成功。合法的未修改／未解决结果仍保留其真实音频；技术错误另行处理，不能用起点伪装失败输出。四策略没有被强制调成同一目标，也不为制造差异而反复生成。原始 Request 与统一学习问题分开显示，评分仍由用户自行判断。

旧批次可显式运行 `python3 Tools/TutorTextCheck/report.py --directory StudyData/text-check`，读取其冻结题库与旧结果；不要对旧目录执行新版 API 批处理。

按任务试听后，进入该属性的问卷，对这个属性八道任务的整体表现进行评价。每个属性有四策略 × 五题 = **20 个核心答案**，再填写 **1 个策略偏好**；四属性合计 **80 个核心答案＋4 个偏好＝84 项**。32 道任务、每道任务的四策略音频与澄清仍保留，任务页不再附带逐任务问卷。

A0 使用需求满足程度七点量尺，保留原英文题干，端点为 **1 Not at all（完全未满足）—7 Completely（完全满足）**；A1 保留难—易七点量尺；A2 控制感、A3 澄清决策合适程度、A4 总体满意度保留同意度七点量尺。五题各有独立的 `Unable to judge`，不记作 4。A0 评价结果对具体要求的符合程度，A4 评价整体使用满意度，分别报告且不合成总分。题干评价范围为“该属性的整组任务”，不是把旧逐任务分数取平均。偏好为单选 E/A/N/S，也可选择 `No preference` 或 `Unable to judge`，后两者分别表示没有明确偏好与无法判断。所有题均无默认答案。

完成一个属性的 20 项和偏好后，可下载该属性的 feedback JSON，再用 `attribute-feedback --file` 校验保存。页面也能下载全部草稿或已完成属性集合；v2 浏览器草稿使用独立版本标识，旧逐任务与属性级 v1 草稿保留但不自动迁移。当前 v2 页面继续引用原有冻结的回复及音频版本，更改量尺不重新调用 API。下载不等于正式实验后端提交。所有按钮均不调用模型、TTS 或 STT。

本工具不提供跨设备研究续接。正式 Unity 新建运行也已接入属性级问卷，但本辅助工具的 JSON 下载不等同正式提交。批量功能仅使用每题独立基线，因此不需要实际完成前一题来建立下一题的历史。

## 验证

本次新版本的验收与限制见 [生成回复与属性确认修订](../../Docs/TutorPersonalization/Study/GENERATED_REPLY_AND_ATTRIBUTE_CONFIRMATION.md)。以下为此前各版本的历史验证记录，不能作为新版本的云端输出验收。

2026-11-27 新版起点／参考和编号展示：24 项 report 离线测试通过，覆盖冻结题库、连续显示编号与稳定内部 ID、起始／参考音频来源和摘要校验、合法 unresolved 音频保留及实际设置差异。模拟数据浏览器检查覆盖起始样例＋两个参考＋四策略共七个音频的 metadata、21 组空白属性问卷、未发布内容隔离和窄屏布局；记录在 `StudyData/validation/listening-material-report-20261127/`。这些模拟检查不代表新版真实 API 批次已全部生成，真实批次结果另行记录。以下旧批次验证仅描述其当时状态。

2026-11-27 属性级改版：46 项离线检查通过，包含四属性共 80 个核心答案和 4 次偏好、未完成状态拦截、实际页面脚本导出结构、旧逐任务草稿隔离、全部任务结果版本绑定、修订保留及单属性／集合导入。核对 370 个原音频、结果及任务状态文件摘要均未变化。新检查记录在 `StudyData/text-check/execution/attribute-feedback-tests.txt` 和 `attribute-feedback-verification.json`。

2026-11-27：属性级问卷修改前的 33 项离线检查通过，覆盖全部 32 题起点／历史、原文与目标隔离、分支澄清、批次揭示门槛、稳定恢复与未知调用阻断、音频校验与复用、配置冻结、v3 反馈幂等／修订及试听页面。测试使用显式模型 fixture 与合成 WAV，网络被禁止；这些测试本身不调用云端。另核对多行原文、CRLF 保留及题目正文变更拒绝。属性级版本的验证需以本次更新后的检查结果为准，不将旧验证直接当作新问卷验收。

同日另按用户授权执行本批 32 题真实 API 请求，保存 34 次澄清与 121 段 TTS 音频，7 个失败分支保留技术异常。实际报告的 121 段音频均通过浏览器 metadata 解码检查；页面无脚本错误，问卷全部保持空白。本批执行摘要、逐条澄清及文件核验分别在 `StudyData/text-check/EXECUTION_SUMMARY.md`、`CLARIFICATION_LOG.md`、`execution/final-verification.json`。这不代表已由用户听评或已完成正式实验。

```sh
python3 -m unittest discover -s Tools/TutorTextCheck/tests -v
```
