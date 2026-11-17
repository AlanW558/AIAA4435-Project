# Reply length 实际生成样例与工程检查

日期：2026-11-07；实现版本：`tutor-answer-v3`；本轮实际返回模型：`deepseek-flash`。

以下摘录来自本地真实 HTTP 验收输出，不是预先编写的演示回答。通过查看实际内容检查结构；不是参与者问卷、用户偏好或正式研究效果数据。

最终验收：六个流程通过 HTTP、状态、历史与去重检查。共 14 次模型调用尝试，其中 13 次成功、1 次 HTTP 503；该暂时性故障用新请求 ID 重试后成功。重复获取已完成回答未产生额外模型调用或历史条目。

本步骤开发过程中累计 43 次真实调用尝试，包含早期提示版本、连接超时、503、结构校验诊断和最终复测；未切换备用账户。先前失败或内容不足的运行保留，不记为通过。

## 1. 同一问题的三种结构

Question: What is an effective way to check whether I understand a concept?

### Brief：关键答案

实际使用：`brief`；持久设置：`brief`。

> Explain the concept in your own words, without looking at your notes, as if teaching it to someone else. If you can do that clearly and answer a follow-up question about it, you understand it.

工程观察：展示复述概念的方法及必要判别条件，没有展示单独的支持理由或扩展示例；关键点不等同于固定一句话。

### Balanced：关键答案＋简短理由

实际使用：`balanced`；持久设置：`balanced`。

> A reliable way to check your understanding of a concept is to explain it in your own words, without notes, as if teaching it to someone who doesn't know it.
>
> Explaining forces you to retrieve the idea and connect its parts, so gaps or fuzzy spots show up immediately; if you can only repeat memorized wording, that signals recognition rather than real understanding.

工程观察：先给方法，再解释主动提取和组织知识为什么能暴露理解缺口，没有展示具体训练步骤。

### Detailed：关键答案＋解释＋步骤

实际使用：`detailed`；持久设置：`detailed`。

> An effective way to check whether you understand a concept is to explain it in your own words, without notes, as if teaching it to someone who doesn't know it.
>
> Explaining forces you to retrieve the idea from memory and organize it into a clear sequence, which reveals gaps that rereading or recognition can hide. If you can only repeat memorized phrases or get stuck when connecting parts, that signals where your understanding is still incomplete.
>
> Try this: pick the concept, close your notes, and give a two-minute spoken or written explanation to an imagined beginner. Then note where you hesitated, used vague words, or couldn't answer a follow-up question like 'why does that work?' or 'what happens if we change this?' Those weak spots are what to review next, and repeating the explanation after studying shows whether the gaps have closed.

工程观察：包含方法、机制解释及闭上笔记进行讲解、标记犹豫处等实际步骤。

## 2. 追问、单次覆盖与恢复

### Brief 下的追问

实际使用：`brief`；持久设置：`brief`。

Question: Why would the method you just suggested help me find gaps?

> Because explaining it without notes forces you to retrieve and rebuild the idea yourself, so any part you can't put into clear words or answer a follow-up on shows up immediately as a gap.

工程观察：回答对应此前推荐的复述方法，直接解释它为什么能发现缺口；“为什么”的直接原因属于该题关键答案。

### 仅本次使用 Brief

实际使用：`brief`；持久设置：`detailed`。

Question: For this answer only, give just the key point: how should I begin a revision session?

> Start by recalling what you already know about the topic from memory, without opening your notes, then check what you missed and focus the session on those gaps.

工程观察：回答本次复习开场问题，历史记录使用 Brief，但持久设置保持 Detailed。

### 随后恢复 Detailed

实际使用：`detailed`；持久设置：`detailed`。

Question: Why would that be a useful first step?

> Because recalling from memory first shows you what you can already retrieve and exactly where the gaps are, so the rest of the session targets your weak points instead of re-reading material you already know.
>
> Retrieval is harder than recognition, so it gives you a more honest picture of your knowledge than simply looking at notes, which can feel familiar without being recallable. It also strengthens memory: the effort of pulling information out makes it stick better than passive review. Starting this way means your limited time and attention go to the gaps you just identified, which is more efficient than reviewing everything evenly.
>
> For example, before revising cell division, close your notes and write down or say aloud everything you remember about the stages. Suppose you can describe mitosis but draw a blank on meiosis. You then open your notes, check what you missed, and spend most of the session on meiosis, using the recall attempt as your starting checklist.

工程观察：继续解释上一次建议，从原因展开到具体细胞分裂复习例子；使用 Detailed 且正确延续上一题。

## 3. 验证边界与记录

三种档位选择不同内容组成部分，不按句数或字数裁剪。模型仍决定哪些内容属于关键答案，因而这些样例不证明所有表达都能严格遵循结构；正式实验仍由参与者评价是否达到预期。

自动化回归：完整后端 133 项通过，包括 21 项新增生成测试。真实验收经 localhost HTTP 使用现有课程模型配置，工程单次超时 60 秒，未改常规启动超时。临时服务已结束。

本地报告：`StudyData/macos/tutor-generation-validation.json`。旧记录分别保存在 `tutor-generation-validation-attempt1.json`、`tutor-generation-validation-v2.json`、`tutor-generation-validation-v3-interrupted.json`、`tutor-generation-validation-v3-schema-check.json`；字段诊断为 `tutor-answer-schema-diagnostic.json`。这些工程文件均由 Git 忽略。

尚未进行 Unity 面板同步、语音播放或头显验证；下一步连接 Unity。
