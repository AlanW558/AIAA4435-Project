# 外观实验：八题 Request 填写表

日期：2026-11-28。材料版本：`appearance-request-workbook-v1`。
关联：[八题设计与问卷建议](APPEARANCE_PARALLEL_STUDY_REDESIGN.md)。

八题目标与保持要求已确认。你可以一次填写全部八题，也可以先填部分题目。请用自然的英文填写 **Request**，不必照抄例句，也不必故意省略信息或制造歧义。

- **Request**：你现在填写的原始请求。每题只需一条，之后同一条请求将用于四种策略。
- **Clarify**：暂时留空；实际调用后填写模型提出的澄清问题，并标明对应策略。
- **Clarification**：看到实际问题后再填写；不同策略分别记录，例如 `A: ...`、`N: ...`、`S: ...`，不提前猜写问题或答案。

请在对应注释之间填写；Request example只是参考，不会自动当作你的请求提交。任务目标和保持要求只给参与者看，不自动作为模型输入；你可以在请求中表达任何你认为必要的细节。四策略结果会等全部澄清完成后统一开放。

**共同人物模型：** 当前Unity场景中已有的男性人物模型（Liang）。人物身份不变，但每题的初始外观不同；各题独立开始，不继承上一题结果。四项对话属性保持共同配置，不随外观任务改变。

## 填写时参考的初态与历史

实际实验将提供Unity真实起点图与必要历史图；下表仅用于本次准备请求，不是要恢复任务卡的“Supplied Starting Context”字段。

| 题号 | 当前外观 | 本题共同公开的示例偏好或历史 |
| --- | --- | --- |
| P1-1 | 蓝色西装、帽子、大小1.00 | 无附加历史 |
| P1-2 | 绿色西装、帽子、大小0.95 | 旧软偏好：“I normally prefer to keep the hat.” |
| P2-1 | 红色西装、帽子、大小0.90 | 无附加历史 |
| P2-2 | 灰色西装、眼镜、大小1.10 | 无附加历史 |
| P3-1 | 蓝色西装、眼镜、大小1.00 | 无附加历史；“更休闲”由你判断，不限定运动服 |
| P3-2 | 灰色西装、无配饰、大小0.95 | 无附加历史 |
| P4-1 | 绿色西装、帽子、大小1.00 | 蓝色／无配饰 → 紫色／无配饰 → 绿色／无配饰 → 绿色／帽子；始终为西装、大小1.00 |
| P4-2 | 橙色西装、帽子、大小1.10 | 橙色西装／无配饰／大小1.00 → 大小1.10 → 加帽子 |

上述初态、示例偏好和历史将在实际运行时同样提供给四个策略；历史不冒称来自你之前真实完成的任务。

**运行方式：** 本文件用于收集请求与记录实际澄清；八题使用独立的外观辅助入口，不混入之前的32题批次。实际执行状态以批次记录为准，Unity截图与问卷另行生成。目前尚无独立的日常休闲服资源；P3-1按你的真实风格需求填写，不能把“休闲”自动改写为“运动服”。

## P1-1 · 明确改单一颜色

**Task goal:** Change the jacket colour to orange.

**Keep unchanged:** The outfit, hat, overall size, tutor identity and conversation settings.

**Request example:** “Could you make the jacket orange and leave the rest as it is?”

**Request — 你填写:**

<!-- request:AP-C1-01 -->
Could you only change the color of jacket to orange?
<!-- /request:AP-C1-01 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C1-01 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C1-01 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C1-01 -->

<!-- /clarification:AP-C1-01 -->

## P1-2 · 明确组合修改与覆盖旧偏好

**Task goal:** For this task, switch to the sport outfit and replace the hat with glasses, overriding the usual hat preference.

**Keep unchanged:** The green colour, overall size, tutor identity and conversation settings.

**Request example:** “I usually keep the hat, but today I'd like the sport outfit and glasses. Keep the colour and size.”

**Request — 你填写:**

<!-- request:AP-C1-02 -->
I want to switch to the sport outfit and replace the hat with glasses.
<!-- /request:AP-C1-02 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C1-02 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C1-02 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C1-02 -->

<!-- /clarification:AP-C1-02 -->

## P2-1 · 略放大

**Task goal:** Make the tutor a little larger. A small change is enough.

**Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.

**Request example:** “Could you make yourself a little bigger? Keep the same outfit and accessories.”

**Request — 你填写:**

<!-- request:AP-C2-01 -->
Could you make yourself a little bigger without changing other things?
<!-- /request:AP-C2-01 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C2-01 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C2-01 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C2-01 -->

<!-- /clarification:AP-C2-01 -->

## P2-2 · 略缩小

**Task goal:** Make the tutor a little smaller. A small change is enough.

**Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.

**Request example:** “You look a little too big. Could you make yourself slightly smaller and keep everything else?”

**Request — 你填写:**

<!-- request:AP-C2-02 -->
Could you make yourself a little smaller without changing other things?
<!-- /request:AP-C2-02 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C2-02 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C2-02 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C2-02 -->

<!-- /clarification:AP-C2-02 -->

## P3-1 · 更休闲的外观

**Task goal:** Give the tutor a more casual look than the starting suit. Choose the casual style you want; it does not have to be sportswear.

**Keep unchanged:** The blue colour, glasses, overall size, tutor identity and conversation settings.

**Request example:** “I'd like you to look a bit more casual.”

**Request — 你填写:**

<!-- request:AP-C3-01 -->
I want your appearance to look more casual.
<!-- /request:AP-C3-01 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C3-01 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C3-01 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C3-01 -->

<!-- /clarification:AP-C3-01 -->

## P3-2 · 更显眼的外观

**Task goal:** Make the tutor more noticeable. For this task, you prefer an orange jacket rather than a larger body.

**Keep unchanged:** The suit, absence of accessories, overall size, tutor identity and conversation settings.

**Request example:** “Could you make your appearance stand out a bit more?”

**Request — 你填写:**

<!-- request:AP-C3-02 -->
I want you to make your appearance more conspicuous.
<!-- /request:AP-C3-02 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C3-02 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C3-02 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C3-02 -->

<!-- /clarification:AP-C3-02 -->

## P4-1 · 多个历史颜色中的指代

**Task goal:** Return to the first blue jacket colour shown in the history.

**Keep unchanged:** The newly added hat, outfit, overall size, tutor identity and conversation settings.

**Request example:** “Can you go back to that earlier colour, but keep the hat?”

**Request — 你填写:**

<!-- request:AP-C4-01 -->
Can you go back to that earlier color, but keep the hat?
<!-- /request:AP-C4-01 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C4-01 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C4-01 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C4-01 -->

<!-- /clarification:AP-C4-01 -->

## P4-2 · 唯一的大小修改与局部恢复

**Task goal:** Undo the most recent size change, returning to 1.00.

**Keep unchanged:** The subsequently added hat, orange colour, outfit, tutor identity and conversation settings.

**Request example:** “Undo the last size change, but keep the hat and everything else.”

**Request — 你填写:**

<!-- request:AP-C4-02 -->
Undo the last size change, but keep the hat and everything else.
<!-- /request:AP-C4-02 -->

**Clarify — 实际调用后记录问题与策略，先留空:**

<!-- clarify:AP-C4-02 -->
No clarification is currently pending. Results remain withheld until batch release.
<!-- /clarify:AP-C4-02 -->

**Clarification — 看到澄清后再填写:**

<!-- clarification:AP-C4-02 -->

<!-- /clarification:AP-C4-02 -->
