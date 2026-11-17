# GitHub main 更新范围清单

整理日期：2026-11-17。目标：`AlanW558/AIAA4435-Project` 的 `main`。

本文件保留上传前的范围清单与初始检查数量。用户后续已授权整理并更新 main；执行后的交付内容与检查见 [GitHub 交付记录](GITHUB_DELIVERY.md)。下文“本轮仅整理”指清单建立时的阶段。

## 1. 已核对的版本状态

- 远程 main：`9b24cc4475efb08c89fca3af5971c47140ab4c36`。
- 远程 `codex/appearance-experiment-prototype`：`2631dded81fd02e59f45a131fe77dcea698a5670`。
- 当前本地分支：`codex/tutor-personalization`，HEAD 同为 `2631dde`。
- main 是当前 HEAD 的祖先。已有外观分支包含 main 尚未收录的 7 个提交、284 个变更文件；不能仅上传最近的 Tutor 文件而漏掉这些场景/模型/脚本依赖。
- 工作区另有 227 个未跟踪文件，约 3.19 MB；19 个已跟踪文件有变化，其中 14 个 Avatar `.meta` 差异仅为空白，实际功能差异集中于另 5 个文件。
- 新增 Assets 文件均找到配套 `.meta`；新增文件中没有大于 10 MB 的文件。现有 138 个 LFS 文件需要保留对应资源对象。

## 2. 应纳入 main 的实现内容

| 范围 | 路径/内容 | 处理方式 |
| --- | --- | --- |
| 最新研究场景 | `Assets/Project/Scenes/TutorComparisonDesktop.unity`、`TutorComparisonVR.unity` | 纳入，作为当前研究流程入口；包含独立任务/问卷面板及固定模式流程 |
| 最新自由测试场景 | `Assets/Project/Scenes/TutorFreeTestDesktop.unity`、`TutorFreeTestVR.unity` | 纳入，支持 Four-strategy comparison / Selective conversation 切换 |
| 早期 Tutor 场景 | `Assets/Project/Scenes/TutorPersonalizationDesktop.unity`、`TutorPersonalizationVR.unity` | 纳入并标记为早期单会话/开发验证入口，不作为最新研究入口 |
| 场景依赖 | 既有房间、Tutor 双模型、材质、纹理、字体、shader、预制体与对应 `.meta` | 随既有外观分支整合，保留 GUID 和 LFS 规则 |
| 新 Unity 功能 | `Assets/Project/Scripts/Tutor/`、`Assets/Project/Scripts/UI/WorldSpacePanelDragHandle.cs` | 四属性、试听、STT/TTS、四策略与澄清屏障、双模式、历史、问卷、保存与恢复、可拖动面板等 |
| 编辑器工具 | `Assets/Editor/Tutor*.cs`、`AppearanceMacSetup.cs` 及 `.meta` | 场景创建、打开与本地检查；保留工具但在使用说明中注明用途 |
| 程序化研究材料 | `Assets/Project/Resources/Tutor/StudyTaskSequence.json`、`PracticeTaskSequence.json`、`StudyQuestionnaires.json` 及 `.meta` | 32 道属性任务、练习材料、当前问卷题干与来源；与设计文档一起交付 |
| 后端 | `Backend/` 新增 Tutor/语音/比较/研究流程/数据存储模块，以及 `server.py`、`model.py` 更新 | 纳入服务实现、测试、fixture、校验和导出脚本，排除缓存与实际输出 |
| 启动与验证工具 | `Tools/AppearanceExperiment/` 下新增启动、语音检查、流程/保存/恢复验证工具 | 纳入脚本和说明，排除 `.runtime/` 等本机环境 |
| 配置模板 | `.env.example` | 仅模板，不包含真实密钥 |
| 项目配置 | `ProjectSettings/ProjectSettings.asset` 中麦克风权限说明 | 纳入实际功能变更；14 个纯空白 `.meta` 不必制造额外提交噪声 |

本次同步是源码与场景交付，不等于最新功能已完成头显构建与验收。当前 `EditorBuildSettings.asset` 仍以 `CloudConversationRoom.unity` 为启用入口，需要在运行说明中明确区分旧构建入口与新研究/测试场景；不能误称克隆后直接 Build 就会得到新实验。

## 3. 应纳入的研究与设计文档

### 当前研究的主要入口

- `Docs/TutorPersonalization/Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md`：四属性×四情境×两题＝32 题；每题四策略；四属性 5 题反馈、Selective 自然模拟 26 题反馈；四次属性偏好、一次比较总体偏好；可选五选二访谈。
- `Docs/TutorPersonalization/Study/STUDY_DATA_PERSISTENCE_CONTRACT.md`：匿名参与者/会话、问卷版本、最终提交与未完成记录、缺失、日志和导出契约。
- `STUDY_FLOW_INTEGRATION.md`、`STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md`、`STUDY_SPEECH_RECOVERY_ACCEPTANCE.md`：实现状态与本机验证记录。
- `INTERACTION_MODES.md`、`STUDY_QUESTIONNAIRE_PANEL.md`、`DIALOGUE_LOGGING.md`：两种模式、面板、对话记录规则。
- 其余 API、四属性、语音接入、UI 方案、阶段实施/验收记录：纳入 `Docs/TutorPersonalization/`，通过索引注明当前说明或历史背景。

程序当前问卷版本：`attribute-feedback-v3`、`natural-selective-feedback-v2`；问卷 UI 资源版本：`study-questionnaire-ui-v1`。保留历史版本记录，不把旧测试记录重标为新问卷数据。

### 需要明确标记为历史的材料

`FINAL_USER_STUDY_PLANNING.md`、`SAME_REQUEST_THREE_STRATEGY_COMPARISON.md`、`TASK_BANK_60_DRAFT.md`、`APPEARANCE_SCENARIO_PLAN.md`、`QUESTIONNAIRE_CONTENT_PLAN.md` 与旧协议契约保留以追溯设计过程，但不能让读者误以为三策略/60 题/独立外观模块仍在施测。

主设计 v1.7 和部分契约仍有“新问卷未实现”“程序未更新”的历史进度描述，与现有实现不一致。上传准备时应补充最新实现状态和有效版本指引，不擅自改动已经确认的题目与研究方案。

### 仓库外建议补入的项目材料

| 当前本地来源（相对于 `/Users/alanwong/Desktop/IAI`） | 建议仓库位置 | 说明 |
| --- | --- | --- |
| `AIAA4435_Initial_Proposal.pdf` | `Docs/Project/Proposal/` | 项目原始目标和计划 |
| `week2/conversational_tailoring_questionnaire_revised.md` | `Docs/FormativeStudy/` | Formative 问卷修订稿；原稿可同目录注明历史版 |
| `week2/conversational_tailoring_questionnaire_researcher_notes.md` | `Docs/FormativeStudy/` | 问卷设计和研究者说明 |
| `week2/PPT materials/conversational_tailoring_formative_study_analysis.md` | `Docs/FormativeStudy/` | 汇总分析；复制前核对不含参与者可识别资料 |
| `week2/Formative Study.pdf` | 待核对内容后决定 | 本轮仅做文件盘点，没有将其认定为可直接发布的研究材料 |

第一次外观实验设计、问卷、操作说明和汇总分析已经在外观分支 `Docs/AppearanceExperiment/` 中，整合到 main 即可，无需复制 `Midterm/` 中所有中间版本。原始纸质问卷、逐人导出、录音/视频不随之上传。

## 4. 排除范围

- `.env`、真实 DeepSeek/Qwen 密钥、本机私有配置和签名证书。
- `StudyData/` 全部参与者/人工测试数据、对话/STT 文本、问卷结果、SQLite、client journal、导出包及恢复快照；上传生成这些文件的代码与数据契约。
- `Backend/logs/`、Unity `Library/`、`Temp/`、`Logs/`、`UserSettings/`、`obj/`、构建输出和 APK。
- Python 虚拟环境、Unity 安装与 Android SDK/NDK、工具缓存、`SetupBackups/`。
- 课程教学幻灯片、外部论文 PDF、教程、所有重复汇报稿，不把整个 IAI 文件夹复制进仓库。
- 头像 `.meta` 的纯空白重写。保留已有真实资源和必要导入配置，不删除用户本地文件。

现有 `.gitignore` 已覆盖主要配置、数据和缓存路径。本轮对新增/修改的文本做了 key 格式初筛，未发现匹配候选；这不替代提交前对最终暂存内容及待整合历史的完整检查。

## 5. 上传前的具体整理顺序

1. 保留当前工作区；按本清单选取实现文件、完整 `.meta` 和已有外观分支成果，不直接 `git add .`。
2. 为最新项目更新根 README，并新增研究文档导航：入口场景、两种模式、后端启动、任务/问卷有效版本、数据保存/导出、尚待头显验证的范围。
3. 复制选定的 proposal/Formative 项目材料；标明历史草案，修正“尚未实现”等过时的工程进度说明。
4. 核对跨电脑依赖：`Packages/manifest.json` 仍指向仓库外 PICO SDK 和 Unity MCP 源码。README 已有外部目录要求，需更新并验证；不把本机 SDK/工具环境整体上传。密钥仍由各机器自行配置。
5. 对最终候选文件做敏感信息、文件完整性、LFS 对象、文档链接和必要运行检查；明确新场景的构建选择方法。
6. 重新核对远程 main，保留其历史，通过正常提交/整合更新 main；不强制推送、不覆盖他人新提交。用户已授权最终更新 main，本轮按其要求仅整理上传范围。
