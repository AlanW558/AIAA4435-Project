# 当前研究任务库：四属性与外观，共40题

版本：current-task-bank-v2.0；日期：2026-11-28。范围以[主设计](FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)为准。自然情境已退出计分实验，仅用于demo。

本文件完整列出当前40张任务卡。每个方向四类情境，每类两题；Task goal、Keep unchanged、Request example为参与者信息，不作为隐藏目标自动发送给模型。参与者可自行表达，不要求照读例句。每题独立起点，同题E/A/N/S四个独立状态，实际澄清结束后才统一开放结果。

## 材料来源与编号

- 四属性32题逐字采用已发布的[review-data.json](../../../Experiments/runs/text-check-v4/review-data.json)中的goal、keep_unchanged、request_example；前台只显示情境内1/2，保留内部旧ID以关联历史音频和结果。
- 外观8题采用已确认的[外观任务设计](APPEARANCE_PARALLEL_STUDY_REDESIGN.md)及当前比较材料的相同题卡。P4-1实际提交请求已获用户确认改为“that earlier color”；本文件不修改任何既有参与者答案。
- 公开基线及示例历史与任务卡分开：四属性可在上述发布材料查到context/结果baseline，外观在任务设计中逐题给出。历史不是上一题执行结果。
- 本文是可阅读的研究材料快照，不表示Unity已接入40题统一调度。当前独立网页分别收集四属性和外观模块，五模块总体偏好仍属规划。

| 方向 | 情境数 | 每情境题数 | 任务数 |
| --- | ---: | ---: | ---: |
| Speech rate | 4 | 2 | 8 |
| Reply length | 4 | 2 | 8 |
| Tone | 4 | 2 | 8 |
| Voice | 4 | 2 | 8 |
| Appearance | 4 | 2 | 8 |
| 合计 | 20 | — | 40 |

## Speech rate

### R1-1 · C1 明确目标

内部ID：`R1-1`。

**Task goal:** Change the speaking speed from 1.20 to 0.80 of the model’s default speed.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want you to speak at eighty percent of your default speed.

### R1-2 · C1 明确目标

内部ID：`R1-2`。

**Task goal:** Reduce the current speaking speed by 25%. The starting speed is 1.20 of default, so your intended result is 0.90 of default.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want you to speak twenty-five percent slower than you are now.

### R2-1 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`R2-1`。

**Task goal:** Starting at the default speed (1.00), make the pace clearly slower. Your preferred range is 0.70–0.75 of the default speed.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want you to speak noticeably more slowly.

### R2-2 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`R2-2`。

**Task goal:** Starting at the default speed (1.00), make the pace clearly faster. Your preferred range is 1.25–1.30 of the default speed.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want you to speak noticeably faster.

### R3-1 · C3 间接表达及跨属性解释

内部ID：`R3-1`。

**Task goal:** You want the delivery to feel calmer by slowing the pace from 1.20 to 0.75–0.80 of default, without changing the tone or voice.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want your response to feel much calmer.

### R3-2 · C3 间接表达及跨属性解释

内部ID：`R3-2`。

**Task goal:** You want the detailed explanation to be easier to follow by slowing the pace from 1.20 to 0.75–0.80 of default. Keep all its detail.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want your explanation to be much easier to follow, but keep all the details.

### R4-1 · C4 历史指代或旧偏好覆盖

内部ID：`R4-1`。

**Task goal:** Restore the previous pace of 0.75 of default from the current 1.25. Leave the other settings as they are now.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I want you to go back to the previous speaking speed and keep everything else the same.

### R4-2 · C4 历史指代或旧偏好覆盖

内部ID：`R4-3`。

**Task goal:** For this task, use 0.75 of the default speed, even though your earlier preference was 1.25. Keep all other settings unchanged.

**Keep unchanged:** Reply length, tone, voice and appearance.

**Request example:** I know I usually prefer a faster pace, but for this task I want seventy-five percent of your default speed. Keep everything else the same.

## Reply length

### L1-1 · C1 明确目标

内部ID：`L1-1`。

**Task goal:** Give only the key answer or recommendation, without explaining the reason or adding an example.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want you to just give me the main point, without explaining why or adding examples.

### L1-2 · C1 明确目标

内部ID：`L1-3`。

**Task goal:** Give the key answer, explain why it makes sense, and add one relevant concrete example.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want you to give me the main point, explain why, and add an example.

### L2-1 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`L2-1`。

**Task goal:** Substantially reduce the amount of detail: keep only the key answer, without the supporting explanation or example.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want a lot less detail. Just give me the essentials.

### L2-2 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`L2-2`。

**Task goal:** Expand the very short answer substantially so you can understand the reasoning and see a concrete example.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want quite a bit more detail so I can understand how this works.

### L3-1 · C3 间接表达及跨属性解释

内部ID：`L3-1`。

**Task goal:** You feel overloaded and want a less overwhelming answer: keep only its key point, rather than changing the speaking speed.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** That's a lot to take in. I want your answer to feel less overwhelming.

### L3-2 · C3 间接表达及跨属性解释

内部ID：`L3-2`。

**Task goal:** You need more support to understand the material: add an explanation and an example, rather than only receiving more encouraging wording.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want the way you explain things to give me more support with understanding, not just make me feel better.

### L4-1 · C4 历史指代或旧偏好覆盖

内部ID：`L4-2`。

**Task goal:** In the supplied example history, the answer formats were key point with a reason, then key point with a reason and an example, then key point only. Restore the middle format, including its reason and concrete example.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want you to go back to the answer format you used in the middle example.

### L4-2 · C4 历史指代或旧偏好覆盖

内部ID：`L4-3`。

**Task goal:** Restore the earlier key-answer-only format, while keeping the friendly tone you now have.

**Keep unchanged:** Speaking speed, tone, voice and appearance.

**Request example:** I want you to go back to just the key answer, but keep your friendly tone.

## Tone

### T1-1 · C1 明确目标

内部ID：`T1-1`。

**Task goal:** Use a Friendly tone for the tutor’s responses.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want you to use a friendly tone.

### T1-2 · C1 明确目标

内部ID：`T1-3`。

**Task goal:** Use a Professional tone for the tutor’s responses.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want you to use a professional tone.

### T2-1 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`T2-2`。

**Task goal:** Make the wording more neutral and matter-of-fact, while keeping the same amount of information.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want your wording to be clearly neutral and matter-of-fact.

### T2-2 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`T2-3`。

**Task goal:** After a practice mistake, change the neutral professional wording to supportive encouragement for another attempt. Keep the same amount of information.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want your wording to help me feel that another try is manageable and that I can make progress.

### T3-1 · C3 间接表达及跨属性解释

内部ID：`T3-1`。

**Task goal:** Make the interaction feel less intimidating by using friendly wording. Keep the current pace and voice.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want talking to you to feel much less intimidating.

### T3-2 · C3 间接表达及跨属性解释

内部ID：`T3-2`。

**Task goal:** You want to feel more motivated to continue: use supportive encouragement, without giving a longer explanation.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want you to help me feel more motivated to keep going.

### T4-1 · C4 历史指代或旧偏好覆盖

内部ID：`T4-1`。

**Task goal:** Restore the friendly style used in the previous response.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I want you to go back to the friendly tone you used before.

### T4-2 · C4 历史指代或旧偏好覆盖

内部ID：`T4-3`。

**Task goal:** For this task, use an Encouraging tone instead of your earlier preference for professional wording. Keep Female voice 2.

**Keep unchanged:** Speaking speed, reply length, voice and appearance.

**Request example:** I know I said I prefer a professional tone, but for this whole task I want you to be encouraging. Keep Female voice 2.

## Voice

### V1-1 · C1 明确目标

内部ID：`V1-1`。

**Task goal:** Switch from Female voice 1 to Male voice 1.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want you to switch to Male voice 1.

### V1-2 · C1 明确目标

内部ID：`V1-2`。

**Task goal:** Switch from Male voice 1 to Female voice 3.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want you to switch to Female voice 3.

### V2-1 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`V2-1`。

**Task goal:** Change from the current female voice to a male voice (Male voice 1 or Male voice 2). Either is acceptable.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I would like a male voice, with the same speed and speaking style.

### V2-2 · C2 方向或类别明确但幅度／具体选择未定

内部ID：`V2-2`。

**Task goal:** Change from the current male voice to a female voice (Female voice 1, Female voice 2 or Female voice 3). Any is acceptable.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I would prefer a female voice. Keep everything else the same.

### V3-1 · C3 间接表达及跨属性解释

内部ID：`V3-1`。

**Task goal:** You want a different feel to the delivery by changing the speaker identity from Female voice 1 to Male voice 1, rather than changing the wording style or speaking pace.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want a different feel to the way you speak.

### V3-2 · C3 间接表达及跨属性解释

内部ID：`V3-2`。

**Task goal:** You want a different feel to the delivery by changing the speaker identity from Male voice 1 to Female voice 3, rather than changing the wording style or speaking pace.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want the way you sound to feel different.

### V4-1 · C4 历史指代或旧偏好覆盖

内部ID：`V4-2`。

**Task goal:** In the supplied example history, the voices were Female voice 3, then Male voice 1, then Female voice 1. Restore the middle voice (Male voice 1).

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want you to go back to the voice in the middle example.

### V4-2 · C4 历史指代或旧偏好覆盖

内部ID：`V4-3`。

**Task goal:** Restore the earlier Female voice 1 from the current Male voice 1, while keeping the current faster pace and friendly tone.

**Keep unchanged:** Speaking speed, reply length, tone and appearance.

**Request example:** I want you to go back to Female voice 1, but keep the faster speed and friendly tone you are using now.

## Appearance

四类情境分别为明确局部/组合修改、小幅整体大小调整、整体外观描述、历史指代与局部恢复。共同使用Liang男性人物；起点的颜色、配饰和大小按题目设定，四项对话属性保持共同配置。

### P1-1 · C1 明确改单一颜色

内部ID：`AP-C1-01`。

**Task goal:** Change the jacket colour to orange.

**Keep unchanged:** The outfit, hat, overall size, tutor identity and conversation settings.

**Request example:** “Could you make the jacket orange and leave the rest as it is?”

本次冻结比较材料的请求：Could you only change the color of jacket to orange?

### P1-2 · C1 明确组合修改与覆盖旧偏好

内部ID：`AP-C1-02`。

**Task goal:** For this task, switch to the sport outfit and replace the hat with glasses, overriding the usual hat preference.

**Keep unchanged:** The green colour, overall size, tutor identity and conversation settings.

**Request example:** “I usually keep the hat, but today I'd like the sport outfit and glasses. Keep the colour and size.”

本次冻结比较材料的请求：I want to switch to the sport outfit and replace the hat with glasses.

### P2-1 · C2 略放大

内部ID：`AP-C2-01`。

**Task goal:** Make the tutor a little larger. A small change is enough.

**Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.

**Request example:** “Could you make yourself a little bigger? Keep the same outfit and accessories.”

本次冻结比较材料的请求：Could you make yourself a little bigger without changing other things?

### P2-2 · C2 略缩小

内部ID：`AP-C2-02`。

**Task goal:** Make the tutor a little smaller. A small change is enough.

**Keep unchanged:** The colour, outfit, accessory, tutor identity and conversation settings.

**Request example:** “You look a little too big. Could you make yourself slightly smaller and keep everything else?”

本次冻结比较材料的请求：Could you make yourself a little smaller without changing other things?

### P3-1 · C3 更休闲的外观

内部ID：`AP-C3-01`。

**Task goal:** Give the tutor a more casual look than the starting suit. Choose the casual style you want; it does not have to be sportswear.

**Keep unchanged:** The blue colour, glasses, overall size, tutor identity and conversation settings.

**Request example:** “I'd like you to look a bit more casual.”

本次冻结比较材料的请求：I want your appearance to look more casual.

### P3-2 · C3 更显眼的外观

内部ID：`AP-C3-02`。

**Task goal:** Make the tutor more noticeable. For this task, you prefer an orange jacket rather than a larger body.

**Keep unchanged:** The suit, absence of accessories, overall size, tutor identity and conversation settings.

**Request example:** “Could you make your appearance stand out a bit more?”

本次冻结比较材料的请求：I want you to make your appearance more conspicuous.

### P4-1 · C4 多个历史颜色中的指代

内部ID：`AP-C4-01`。

**Task goal:** Return to the first blue jacket colour shown in the history.

**Keep unchanged:** The newly added hat, outfit, overall size, tutor identity and conversation settings.

**Request example:** “Can you go back to that earlier colour, but keep the hat?”

本次冻结比较材料的请求：Can you go back to that earlier color, but keep the hat?

### P4-2 · C4 唯一的大小修改与局部恢复

内部ID：`AP-C4-02`。

**Task goal:** Undo the most recent size change, returning to 1.00.

**Keep unchanged:** The subsequently added hat, orange colour, outfit, tutor identity and conversation settings.

**Request example:** “Undo the last size change, but keep the hat and everything else.”

本次冻结比较材料的请求：Undo the last size change, but keep the hat and everything else.

## 模块结束反馈

每个方向看完八题后，按四种策略各回答A0–A4五题，共20项1–7评分，再完成一项多选策略偏好。当前准确题干、来源、评分与数据边界见[问卷与数据规范](CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)。不在每道任务后重复填写20项评分。
