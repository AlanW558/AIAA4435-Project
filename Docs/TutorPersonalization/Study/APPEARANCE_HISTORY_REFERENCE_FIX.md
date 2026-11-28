# 外观 P4-1 历史指代与澄清修复

日期：2026-11-28。关联：[外观八题设计](APPEARANCE_PARALLEL_STUDY_REDESIGN.md)。

本文记录生成本地实验输出时的实现与验证版本。此次资料发布包含研究文档和反馈，不表示GitHub运行源码已同步至这些本地实现版本；输出的版本与摘要按真实执行证据保留。

## 原运行证据

原批次为 `appearance-text-check-v1`，批次编号 `a75427c7c3af4444b0861c346d8b3ef6`。原请求、API结果、澄清记录、截图及页面保留原样。

P3-2的Selective实际已作出 `ASK / R4_EXPLICIT_AMBIGUITY`，并收到授权代拟的橙色要求；用户确认无需针对这题修改策略。

P4-1的请求为：`Can you go back to the previous color, but keep the hat?`。本题独立示例历史为：

| 顺序 | 颜色 | 配饰 | 含义 |
| --- | --- | --- | --- |
| 1 | Blue | None | 示例历史最早显示的状态 |
| 2 | Purple | None | 第一次颜色修改 |
| 3 | Green | None | 第二次颜色修改 |
| 4 | Green | Hat | 加帽子；参与者提出请求之前的共同起点 |

模型收到完整的 `change_history[].before/after`。从准备状态重建的公开上下文摘要与实际API调用一致；蓝色存在于第一条修改的before中，紫色存在于第一条after与第二条before中。不存在跨题继承或客户端漏传蓝色。

共享解释将 `previous color` 理解成最近的前一颜色，因此只提供紫色，没有报告指代歧义。E直接采用默认值，N自主选择ACT，S因无歧义触发条件而ACT。该紫色有公开历史依据；不能因为研究者的任务目标是蓝色，就把目标作为模型输入或强制其它策略改成蓝色。

## 确认的缺陷

Always Ask首次澄清回复为：`I meant the blue you had at the start, not purple. Keep the hat and leave everything else as it is.`

模型错误地把准备结束时的 `task_start_settings=green` 当成唯一有效起点，虽然承认首条before为蓝色，仍返回无可追溯蓝色的UNRESOLVED结果，导致重复显示紫色选项。第二次直接要求蓝色才成功。这是澄清解释错误，并非Selective门控没有识别已报告的歧义。

## 修复范围

- 区分参与者请求前的任务起点与所提供示例历史的最早状态；before和after均可作为公开历史依据。
- 当澄清明确指定受支持的类别值时，优先使用这一明确修改要求；不能仅因附带的时间描述不精确而丢弃指定颜色，也不能把旧选项当成可选值上限。
- 保持范围及其它属性的保留约束，不把恢复颜色扩大为回滚整个状态。
- 保持四种策略的差异。唯一的最近一次修改可直接恢复；确实存在多个合理指代的模糊请求仍应保留歧义供Selective判断。
- `tutor-interpretation-v11` 增加从公开before/after机械汇总的逐字段历史索引；对于存在多个历史值、未指定时点或值的直接earlier请求，补充reference不确定性。此保护不改模型候选与默认值，不读取任务目标；它覆盖可确认的有限句式，不能声称解决所有自然语言歧义。
- 比较页面把P4历史移到结果之前，显示每一步的颜色、配饰及初始/当前位置，澄清问答直接展开。

## 验证与重跑

使用原先失败的同一句澄清和同一公开状态做真实API回归检查；另检查最近一次、历史首次及含糊的更早状态三种表达。v10试验修复了明确蓝色，但仍遗漏earlier歧义，该失败记录保留。v11四项真实API检查全部通过，相关130项后端测试通过。验证记录位于 `StudyData/validation/appearance-history-fix-v2/`，与参与者数据分开保存。

用户随后确认仅重跑P4-1，并批准将请求改为 `Can you go back to that earlier color, but keep the hat?`，使其更符合多个历史颜色之间的指代澄清任务。目标、起点和公开历史不变。新执行位于 `StudyData/appearance-p4-1-retest-v2/`，使用独立comparison/session；其它七题未调用API。此前八题准备目录 `appearance-text-check-v2` 未执行，已标记为NOT_RUN。

新P4-1的E不澄清，采用默认紫色；A/N/S各澄清一次，收到同一句口语化蓝色要求后执行蓝色，四者均保留帽子。澄清来源仍为 `assistant_authored_user_authorized`；修订请求来源为 `assistant_revised_user_authorized`。旧P4-1的两轮A澄清保留在旧证据中，不混入新题。

比较材料位于 `StudyData/appearance-p4-1-review-v2/`，由七份未改动旧trial和一份P4-1新trial组成，明确记录为review composition，不冒充八题全部重新执行。页面按用户要求直接替换P4-1，不显示重跑标记；逐题来源、请求授权和实现版本保留在内部证据与下载JSON中。问卷仍为20项评分和一次多选偏好，未自动填写任何答案。

此文记录工程修复，不证明任何策略的总体优劣；重跑中的具体选择与澄清次数以新批次实际记录为准。
