# Appearance experiment results

本目录保存 **4位参与者对同一套外观实验结果的评价**：8道独立任务，每题包含Always Act (E)、Always Ask (A)、Native Gate (N)、Selective (S)四个策略结果。参与者看完外观模块后，对每个策略回答A0–A4五题，共20项1–7评分，并选择一次可多选的策略偏好。

数据采集方式为 `api_assisted_output_review`：API输出和Unity截图已冻结，四位参与者评价的是同一套材料；澄清回复由助手按用户授权代拟，不是四位参与者各自与agent独立完成的澄清对话。自然情境模拟退出当前实验，只保留为后续demo。完整任务和设计见[外观实验设计](../../Docs/TutorPersonalization/Study/APPEARANCE_PARALLEL_STUDY_REDESIGN.md)与[主实验设计](../../Docs/TutorPersonalization/Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)。

## 文件与版本

- [results/participant_001.json](results/participant_001.json) 至 [participant_004.json](results/participant_004.json)：原下载文件的逐字节副本，匿名编号分别为P001–P004，没有改写评分或偏好。
- [results/aggregate_results.json](results/aggregate_results.json)：总数据汇总，包含完整参与者记录、80行参与者×策略×题目评分、逐策略逐题描述统计、多选偏好计数和来源摘要。
- [source_manifest.json](source_manifest.json)：保存原下载文件名、仓库文件名和SHA-256，便于确认复制后数据未被修改。
- [materials/questionnaire.json](materials/questionnaire.json)：本次实际采用的五道英文题、锚点、来源及计分定义。
- [materials/review_evidence.json](materials/review_evidence.json)：冻结的材料与结果版本；所有参与者必须与此证据完全一致才能汇总。
- [scripts/aggregate_results.py](scripts/aggregate_results.py)：仅依赖Python标准库的校验与汇总工具，不调用API，也不依赖Unity、私有数据目录或未发布的后端工具。

问卷版本为 `appearance-module-A0-A4-v1`；原导出格式为 `appearance-summary-feedback-v1`。当前材料release为 `66a014509679f46aabcf63763a308b84de5327a731fe9ad6f198ec5ac1456639`。内部来源保留七道原结果及用户确认后替换的P4-1结果，不把它表述成四位参与者各自重新调用了八道任务。

同样叫P001的四属性实验记录与这里的P001**不自动认定为同一个人**。本次汇总与旧四属性、第一次外观User Study的数据分开保存。

## 问卷与评分

| 题号 | 评价角度 | 来源与1–7锚点 |
| --- | --- | --- |
| A0 | 要求达成程度 | 项目自编；1 Not at all，7 Completely |
| A1 | 调整容易程度 | 参考SEQ，将单任务容易程度改编为模块回顾；1 Very difficult，7 Very easy |
| A2 | 控制感 | 参考SASSI交互控制内容；1 Strongly disagree，7 Strongly agree |
| A3 | 澄清决策适当性 | 项目自编；1 Strongly disagree，7 Strongly agree |
| A4 | 总体满意度 | 项目自编；1 Strongly disagree，7 Strongly agree |

完整题目原文在questionnaire.json。A1和A2是适配项目的改编题，不将五题组合声称为完整、经过验证的SEQ/SASSI量表；不计算五题总分，不套用标准量表常模。

每个策略×题目单独报告总人数、有效数字评分人数、Unable to judge人数、均值、中位数、样本标准差和1–7分布。Unable to judge保存为null，不替换成4或0；全缺失时统计为null，只有一份数字评分时样本标准差为null。

策略偏好允许多选；每个策略按“有多少参与者选择”计数，分母为全部有效最终问卷人数。No preference与策略选择互斥。各策略比例之和可以超过100%。

## 当前描述统计

四位参与者全部提交final，80项评分均为有效1–7分，没有Unable to judge。以下是逐题均值，分母均为4：

| 策略 | A0 | A1 | A2 | A3 | A4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| E — Always Act | 5.25 | 6.50 | 4.25 | 3.50 | 5.00 |
| A — Always Ask | 6.75 | 4.25 | 6.50 | 4.00 | 4.75 |
| N — Native Gate | 6.75 | 6.25 | 5.50 | 5.25 | 6.00 |
| S — Selective | 6.75 | 6.25 | 6.00 | 6.25 | 6.25 |

偏好选择：E=0/4，A=0/4，N=2/4，S=4/4；No preference=0。P003和P004同时选择N与S，分别给这两个策略各计一次。

这些结果是小样本、同人重复评价的描述性反馈，不是总体显著性或策略优越性的结论。模块评分不能反推出每一道任务或每个情境的主观评分；`review_opened`仅表示图片曾在页面打开，不证明参与者仔细看完或完成任务。

## 重新生成汇总

在仓库根目录运行（Python 3.9及以上，无第三方依赖）：

```sh
python3 Experiments/appearance/scripts/aggregate_results.py
python3 -m unittest discover -s Experiments/appearance/tests -v
```

脚本每次从原始参与者文件完整重建aggregate_results.json，不累加旧汇总，不修改源文件。它会拒绝重复编号、草稿、缺题、越界评分、不同材料release和不合法偏好。结果确定性生成，相同输入得到相同汇总。

## 添加后续参与者

1. 在同一版本的HTML问卷中输入新的匿名编号，例如P005；完成全部20项评分与多选偏好，点击Download completed feedback。
2. 保留下载名称，例如 `P005_appearance_feedback_66a0145096.json`，放到本目录的results文件夹。新文件可直接保留下载名称，不必手工编辑JSON。
3. 运行上面的汇总脚本。默认读取 `participant_*.json` 和 `P*_appearance_feedback_*.json`；同一个参与者只保留一份文件，不能同时放原下载名和改名副本。
4. 检查命令输出人数、评分数和偏好计数，再提交新参与者文件与更新后的aggregate_results.json。来源摘要会记录新文件名及SHA-256。

不同release、修订过的问卷或不同施测方式应另建数据集，不能修改evidence锁来让它们混入本批。重复提交也不能直接换个编号当成新参与者；需由研究者明确选择保留版本并保留更正记录。
