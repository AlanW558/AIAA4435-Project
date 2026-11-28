# 四属性与外观辅助实验：材料、反馈与汇总

这里集中保存四属性实验的文本 API 调用入口、可移植试听问卷、参与者反馈和分析 notebook。四策略规则、对话生成、澄清、统一展示屏障与 TTS **继续复用仓库中的权威实现**，不在本目录复制一套策略算法。

**2026-11-28设计更新：** [主实验v2.0](../Docs/TutorPersonalization/Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)已改为四属性＋外观40题；自然情境只保留为后续Unity/VR demo，不再收实验问卷。`runs/text-check-v4/`、原有scripts及results/P001继续表示此前32题四属性辅助评价。新增[appearance/](appearance/README.md)单独发布四位参与者的外观原始反馈、总数据汇总、问卷快照与可复算脚本；四人评价同一套Unity图像输出。五模块统一调度和总体偏好尚未接入，不把这两类记录合称完整40题样本。

当前发布包 `runs/text-check-v4/` 包含 **32 道任务、128 段实际回复音频**。每个属性8题（4情境×2题），每个属性填写四策略×5个评分，共20格，再选择一次策略偏好；全四属性共80个评分和4次属性偏好。评分对象是某个属性下的整体表现，不能把它解释成单题评价。

## 外观结果入口

- [外观说明与复算步骤](appearance/README.md)：P001–P004的四份原始最终JSON及独立汇总；其编号不自动对应四属性同名编号。
- [外观总数据汇总](appearance/results/aggregate_results.json)：逐人来源、每策略各题的描述统计与多选偏好计数。
- [当前40题任务库](../Docs/TutorPersonalization/Study/CURRENT_TASK_BANK_40.md)和[当前问卷与数据规范](../Docs/TutorPersonalization/Study/CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)：五方向任务、两套准确英文题干、来源与评分方式。

下文命令与P001更正记录继续只适用于原四属性数据包；外观使用其独立README中的脚本，不导入旧四属性汇总。

## 四属性材料与参与者1

| 内容 | 位置 |
| --- | --- |
| 默认空白 v3 多选偏好页面 | [runs/text-check-v4/REVIEW_AND_QUESTIONNAIRE.html](runs/text-check-v4/REVIEW_AND_QUESTIONNAIRE.html) |
| 参与者1使用的原始 v2 页面，逐字节保留 | [runs/text-check-v4/REVIEW_AND_QUESTIONNAIRE_v2.html](runs/text-check-v4/REVIEW_AND_QUESTIONNAIRE_v2.html) |
| 32题题目、request、各策略实际回复、澄清及设置 | [runs/text-check-v4/review-data.json](runs/text-check-v4/review-data.json) |
| 来源、版本及每个音频的 SHA-256 | [runs/text-check-v4/manifest.json](runs/text-check-v4/manifest.json) |
| 参与者1完整原始下载、规范化数据及更正 | [results/participant_001.json](results/participant_001.json) |
| 总汇总（含逐人明细与可复算统计） | [results/aggregate_results.json](results/aggregate_results.json) |
| 已执行、嵌入三组图表的分析 | [analysis/analyze_results.ipynb](analysis/analyze_results.ipynb) |

参与者1编号为 `P001`，显示名为“参与者1”。数据来自原始 **attribute-summary-feedback-v2**，不是重新填写的 v3。其 tone 原偏好 `unable_to_judge` 经本人明确说明，更正为同时偏好 **N 与 S**，各计 **1票**；speech rate、reply length、voice 的偏好均为 S。**其余80项评分未修改**。原 JSON 值完整保存在 `source_export`，原始文件字节保存在 `results/source_exports/`；[明确更正记录](results/amendments/P001-tone-preference.json)与[来源说明](results/provenance/P001.json)单独保留。这个更正不会自动应用到其他参与者。

本批请求与澄清由助手经用户授权代拟或修订，评分由参与者填写；不将这些文本冒称为参与者口述。音频产生于本次后续澄清修复之前，打包没有重新调用模型或更正旧输出，不能以本批评分验证之后的修复效果。

## 环境与下载

从**仓库根目录**执行下文命令。Python 3.10+ 可运行 API 和数据脚本；Bash 包装脚本适用于 macOS/Linux。notebook 使用独立虚拟环境。

```bash
git lfs install
git lfs pull --include='Experiments/runs/**/*.wav'

python3 -m venv Experiments/.venv
Experiments/.venv/bin/python -m pip install -r Experiments/requirements.txt
```

WAV 通过 Git LFS 管理。只下载源码 ZIP 或只拿到 LFS 指针时，页面可能出现播放器但无法播放；先获取真实音频。已有环境无需重复创建。`.venv`、`incoming`、`local-runs`、私有配置均被忽略，不提交到仓库。

## 打开页面、填写与下载

试听已发布材料**不需要密钥、Unity 或模型 API**，也不会调用 STT。

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory Experiments/runs/text-check-v4
```

浏览器打开 `http://127.0.0.1:8000/REVIEW_AND_QUESTIONNAIRE.html`。保持整个文件夹结构不变，HTML 和128段 WAV 使用相对路径，可以在克隆仓库后直接使用。

1. 为每个参与者使用新的浏览器隐私会话或清除该站点存储，避免继承上一人的草稿。页面不会预填 P001 分数，但同一浏览器会恢复它自己保存的草稿。
2. 选择属性，阅读8题的 Task goal、Keep unchanged、Request example 与实际 request，试听四策略输出。每个回复旁保留是否澄清、实际问题、回答和所属策略；不会播放固定样本替代生成回复。
3. 完成该属性的20项评分与策略偏好。五项评分都为1–7分，仍可选 `Unable to judge`，该状态不等于4分或0分。v3 的偏好可选择一个或多个 E/A/N/S；`No preference` 与策略互斥，偏好不再提供无法判断。
4. 四属性全部完成后，点击页面顶部下载已完成反馈的按钮。浏览器下载文件名为 `completed-attribute-feedback.json`。该按钮也能导出仅已完成的部分属性，因此交给研究者前检查四属性都已完成。草稿备份不能作为最终评分导入。
5. 将下载文件**重命名**为 `participant_002-feedback.json`（之后依次003、004……），不要改 JSON 内容。放入 `Experiments/incoming/`。网页只在浏览器暂存和下载，**没有自动上传或自动写入仓库**。

保存单属性下载用于备份时，可用 `participant_002-speech_rate.json` 等文件名；本目录的导入入口要求使用“已完成属性集合”下载，便于保持同一参与者身份。首次录入可为部分属性，但结果会明确标为 `partial_attributes`；补齐后需要研究者显式处理版本更新，不能静默覆盖原记录。

## 导入参与者与重新汇总

```bash
python3 Experiments/scripts/import_feedback.py \
  Experiments/incoming/participant_002-feedback.json \
  --participant-id P002 --display-label '参与者2' \
  --review-data Experiments/runs/text-check-v4/review-data.json

python3 Experiments/scripts/aggregate_results.py
Experiments/.venv/bin/python Experiments/scripts/execute_notebook.py
```

`P002` 写入 `results/participant_002.json`。相同编号、相同数据再次导入不会重复计数；相同编号的不同内容会被拒绝，不覆盖已收集记录。相同原始下载即使改用另一参与者编号，导入与汇总也都会拒绝重复计人：按完整源 JSON 的规范化 SHA-256 检查，其中包含 `exported_at`；独立导出即使评分恰好相同，也不会仅因答案相同被拒绝。不要修改时间戳或另造编号绕过检查；需要更正时，先保留旧版本并由研究者明确确定哪个记录有效。

若参与者明确补充偏好，使用和 `results/amendments/P001-tone-preference.json` 相同结构的 JSON，通过 `--amendments 文件路径` 在首次规范化时导入；`previous` 必须与原下载一致，必须填写更正理由、授权来源和日期。仅支持偏好更正，**不会改写评分**。不要把其他参与者的 unable 自动推断为 N/S。

精确复建 P001 的命令（现有相同内容会返回 Already imported）：

```bash
python3 Experiments/scripts/import_feedback.py \
  Experiments/results/source_exports/P001-$(python3 -c 'import json; print(json.load(open("Experiments/results/participant_001.json"))["source"]["sha256"])').json \
  --participant-id P001 --display-label '参与者1' \
  --review-data Experiments/runs/text-check-v4/review-data.json \
  --amendments Experiments/results/amendments/P001-tone-preference.json \
  --provenance Experiments/results/provenance/P001.json
```

## 数据契约与分析规则

`participant-results-v1` 包含 `participant_id`、`display_label`、`cohort_id`、`source_export` 全文、源 SHA-256、源问卷版本、显式 amendments、provenance、80条 ratings、4条 preferences 及可选 comments。评分每行保留 `domain / condition / item_id / status / value`；偏好同时保留源值与修正后 choices。

`aggregate-results-v1` 按 **batch ID＋源问卷版本＋任务 release 映射＋采集方式** 分 cohort，保留每个参与者每个属性每个策略每道评分的明细，提供各格有效 n、缺失原因、原始数值、1–7分布、均值与中位数。偏好每个选中策略记1票，No preference 单独记录；多选时票数总和可大于参与人数。

v2 与 v3 不会自动合并为同一 cohort；不同批次同样分开。一个人四个属性的记录仍然是 **n=1**，不能当作四个独立人。当前 notebook 只做描述，不作显著性检验、不声称策略对总体更优，也不把五个不同构念平均为“标准总分”。A0需求满足、A1易用、A2控制感、A3澄清适切、A4满意度分别解释；具体题文及改编来源保存在 `review-data.json.items`。它们不是完整 SUS 或 SASSI 量表。

汇总时会从 `source_export + amendments` 重算规范化字段，拒绝被手动改写的评分；不会把无法判断或缺失当作0分。notebook 读取相对路径，并按 cohort 分别绘图。每次导入后重新汇总与执行 notebook；GitHub/支持 notebook 的编辑器可直接查看已嵌入图表，交互编辑可另行安装 JupyterLab。

## 创建另一批文本请求与调用 API

仅在需要生成**新的请求输出**时运行本节。若参与者只是评价上述同一批刺激材料，直接填写现有页面即可。新批次会生成新的结果版本，不能套用已有反馈。

```bash
python3 Experiments/scripts/prepare_batch.py \
  --directory Experiments/local-runs/new-batch-001
```

填写新目录的 `TASK_REQUESTS.md` 中 Request 区域；Clarify 与 Clarification 暂留空。保持 HTML 标记不变，题号连续显示，内部 task_code 仍用于追溯。准备脚本只生成32题材料，不发请求，且拒绝已有目录。

私有配置沿用仓库 [.env.example](../.env.example) 与 [权威 API 工具说明](../Tools/TutorTextCheck/README.md)：设置 `DEEPSEEK_API_KEY / DEEPSEEK_MODEL / DEEPSEEK_BASE_URL` 及匹配账户的 `QWEN_API_KEY / QWEN_BASE_URL / QWEN_TTS_MODEL`。文本辅助流程不需要 ASR。把配置放在本机私有文件，设置 `APPEARANCE_ENV_FILE` 指向它；没有指定时权威脚本读取根目录 `.env`。本目录不提供密钥。

```bash
export APPEARANCE_PYTHON="$PWD/Experiments/.venv/bin/python"
export APPEARANCE_ENV_FILE="$HOME/.config/aiaa4435/appearance.env"

bash Experiments/scripts/run_api.sh Experiments/local-runs/new-batch-001 status
bash Experiments/scripts/run_api.sh Experiments/local-runs/new-batch-001 process --limit 4
```

包装脚本将 **directory 与 workbook 都显式传给 `Tools/TutorTextCheck/run.sh`**，避免误用旧默认批次。权威脚本可读取已有课程密钥文件，且不自动切换第二账户。`process` 会产生真实模型调用费用；`publish` 会产生 TTS 调用费用。

每次 process 后在 worksheet 的 Clarify 中查看真实提问，按策略分别填写口语化英文回复，例如 `A: ...`、`S: ...`。再运行同一 process 命令可继续处理，多轮澄清同样保留；不要提前猜写澄清，也不要把一个回复自动广播给其他策略。需要研究者或助手代拟时，必须已有参与者授权并使用来源参数：

```bash
bash Experiments/scripts/run_api.sh Experiments/local-runs/new-batch-001 process \
  --limit 32 \
  --request-source assistant_revised_user_authorized \
  --clarification-source assistant_authored_user_authorized
```

全部实际澄清完成后再发布音频，避免结果影响仍待回答的澄清；publish 保留现有统一展示屏障。已提交请求不要原地修改，需要修改时创建新批次。

```bash
bash Experiments/scripts/run_api.sh Experiments/local-runs/new-batch-001 publish

python3 Experiments/scripts/build_review.py \
  --directory Experiments/local-runs/new-batch-001 \
  --output Experiments/runs/new-batch-001
```

打包脚本不会发 API 请求，也不会复制密钥、debug、检查点或运行环境；只打包已发布的实际回复、澄清和音频。目标目录必须不存在。`--preserve-v2` 仅用于同时保留该批原始 v2 页面；当前 v4 包已完成此操作。调用脚本依赖整个仓库，试听发布包自身可单独复制使用。

## 本地验证

```bash
python3 -m unittest discover -s Experiments/tests -v
```

测试使用合成变体覆盖幂等导入、身份冲突、多选完整票、无法判断、部分缺失、多参与者、版本分组、重复编号、评分篡改、旧 release 与错误更正的拒绝；不调用模型、不修改参与者结果。API 程序本身的策略及澄清测试仍由 `Backend/tests` 与 `Tools/TutorTextCheck` 维护。
