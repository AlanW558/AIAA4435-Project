# 五方向 × 四情境 × 三任务：60 题建议稿

> **历史设计/阶段记录；导航更新于2026-11-28：不作为当前施测说明。** 当前研究为四属性＋外观40题，五模块均采用四策略并行及模块末20项评分＋多选偏好；自然情境仅用于demo。请先读[当前主设计](FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)、[40题任务库](CURRENT_TASK_BANK_40.md)、[当前问卷与数据规范](CURRENT_QUESTIONNAIRE_AND_DATA_CONTRACT.md)。下文各日期中的“当前”“最新”仅指当时阶段，保留历史讨论与旧实现，不恢复旧自然问卷、三策略或60题流程。

> 历史档案：2026-11-10 的四属性每情境两题筛选以 `FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md` 第 5 节为准。本稿保留原始候选，不是当前执行题库；旧外观方向、三策略和三音色占位设定不再代表最新方案。

2026-11-05；v0.1。供用户逐项评议，**不是已实现、已冻结或已经验证的正式任务库**。不要求照读，不为 E/A/S 再做不同题目。每题一次自然英文请求，三策略共用同一输入与公开起点，自由比较后填写问卷并 Next question；每方向结束偏好一次，总体结束偏好一次，访谈可选。

## 使用规则与关键区别

- 本文每条英文是**参与者私有任务卡的目标说明**，不是要发送给 agent 的标准请求。共同提示：`Use your own words to ask the tutor for the change. You may mention any details you consider useful. Keep all settings not targeted by this task unchanged.` 用户可说出目标细节，但系统不得自动把任务卡、研究类型、目标答案或 ID 填入模型上下文。
- C1 明确目标；C2 程度/偏好未精确表达；C3 可能存在不同实质解释；C4 历史/偏好/局部恢复。分类是设计意图，不是强制用户措辞。尤其 C3 的私有卡给出确切意图，是为了让用户能评价；若用户主动说清所有要求，实际请求就可能没有歧义，不能删题或强迫重说。
- **C2 需要按属性适配**：rate/scale 是幅度，length 是内容增减；tone/voice 是定性风格/音色偏好，不存在已支持的连续‘微调强度’。后二者为该类别的适配建议，不宣称五方向是严格同构的全因子设计。如果要求 C2 必须是连续小幅变化，就不能同时声称现有 tone/voice 的这六题满足它。
- 候选竞争解释只供研究者检查情境自然性，不代表 agent 一定出现该候选，也不把‘S 应该问’写成答案。实际表达和条件行为如实记录。
- 用户问卷是结果评价依据；目标范围、内容结构和保持字段用于帮助用户判断，不建立本轮不需要的客观音频正确率。

## 公共基线、资源与呈现

对话默认：rate=1.00（当前模型/声音的默认速度），length=Balanced，tone=Professional，voice=Voice A。外观默认：Liang、蓝色西装、眼镜、scale=1.00。每题从表中起点重置并只覆盖列出的字段，不串用前题状态。所有分支从同一个起点复制，分支内部后续修改分别保存。

除目标字段外保持其他所有字段；对话任务保持全部外观，外观任务保持全部对话设置。表中明确的保留要求覆盖默认说明。相对语速运算以该请求对应的初始已提交值为基准；默认参照和当前参照分开。1.08 等精度需在实现中支持或在正式定稿前调整题目，不能静默取整。

内容档位草案：Brief=关键答案/建议，不附理由或例子；Balanced=关键点＋简短理由，不展开例子；Detailed=关键点＋较充分解释＋相关例子/必要步骤。不以固定句数、字数或更长音频判档位；不靠重复充长。

风格草案：Professional=直接、克制、专业；Friendly=温暖、易接近、像友好交谈；Encouraging=支持尝试和进步、鼓励继续。三者不是强度顺序，也不是人格/能力等级。

**声音依赖（未实现的占位契约）**：Voice A=相对清亮/明快，Voice B=相对温暖/柔和，Voice C=相对低沉/饱满。当前 A/B/C 只是界面标签，不能声称真实模型已有这些音色。必须选出实际可用且可辨的三个声音，或据真实声线改写描述后，这些题才能使用。保持同语言与 rate 参数；不把切换 voice 当作可连续调音高。语气/声音差异可能有重叠，题目不能预设客观纯音色隔离。

外观依赖：颜色/配饰/0.05 步进比例来自现有能力；sport/身份等在扩展 profile 中，研究配置尚待接入。第一版这十二题保持 Liang，不额外加入身份切换或未支持的材质明度功能。

公开历史必须向用户和三个分支一致展示，是本题提供的示例历史，不伪称用户刚才真实操作。语音历史可重听，外观历史用同视角图；本文未生成这些配套音频/截图。私人目标样例与公开历史分开，不能把目标音频/图像附件自动传给 agent 泄露答案。

## 共同输出检查材料（给用户看/听，不作研究者音频测量）

- R/V：固定同句用于速率与声音对比，例如 `The next section explains the main idea and gives one example.` 相同文字及合成条件在同题三策略保持一致。
- L/T：采用真实回答，不能用固定句代替回复构成或措辞风格。三个主题按任务末位 1/2/3 对应：`How can I make a useful study plan for next week?` / `How can I check whether I understand a new concept?` / `What should I do after getting a practice question wrong?` 同题三分支使用同一提示；参与者无需重复口述三次。提示示例可在定稿时调整，但不能为某策略单独换题。
- A：呈现实际外观，角度/光照/距离一致，可自由切换对照；目标大小图卡按同相机制作。
- 本文没有自动加入固定三回合后续对话。新结构是否测保持、需要几个回合，尚未决定；没有经历后续交流时不提供‘后续没有保持’原因选项。

## 60 道候选任务

每题一行；“目标提示/预期”是给研究者和参与者理解目标的材料，不是客观评分程序。英文目标卡中已说明具体意图，不能把它作为固定口述脚本。

### Speech rate：语速

| ID | 情境 | 公共起点／上下文 | 英文目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- | --- |
| R1-1 | C1 | rate=1.20 | Change the speaking speed to 90% of the model’s default speed. | 0.90× 默认 |
| R1-2 | C1 | rate=1.20 | Reduce the current speaking speed by 10%. | 1.20 × 0.90 = 1.08× 默认 |
| R1-3 | C1 | rate=0.85 | Return to the model’s default speaking speed. | 1.00× 默认 |
| R2-1 | C2 | rate=1.00 | Make the tutor speak a little more slowly. Your target is between 0.90 and 0.95 of the default speed. | 0.90–0.95× |
| R2-2 | C2 | rate=0.85 | Make the tutor speak a little faster, aiming for 0.90 to 0.95 of the default speed. | 0.90–0.95× |
| R2-3 | C2 | rate=1.20 | Reduce the fast pace slightly while keeping it above the default speed. Aim for 1.05 to 1.10. | 1.05–1.10× |
| R3-1 | C3 | rate=1.00 | You want the delivery to feel calmer by slowing the pace to 0.85–0.90, without changing the tone or voice. | rate=0.85–0.90；竞争解释可能是 Friendly/Voice B |
| R3-2 | C3 | rate=1.15; length=Detailed | You want the detailed explanation to be easier to follow by slowing the pace to 0.95–1.00. Keep all its detail. | rate=0.95–1.00；竞争解释可能是减少解释 |
| R3-3 | C3 | rate=0.90 | You want to move through the material more briskly by increasing the pace to 1.05–1.10. Keep the reply structure unchanged. | rate=1.05–1.10；竞争解释可能是 Brief |
| R4-1 | C4 | 公开语速历史 0.90 → 当前 1.10；仅一个先前值 | Restore the previous speaking pace, leaving the other settings as they are now. | 0.90×；唯一引用 |
| R4-2 | C4 | 公开语速历史 0.80 → 1.20 → 当前 1.00 | Restore the faster pace used in the middle history entry. Keep the other settings unchanged. | 1.20×；多历史目标 |
| R4-3 | C4 | rate=1.10；公开软偏好 “I usually prefer a pace of 1.10.” | For this task, use 0.90 of the default speed, even though your earlier preference was 1.10. | 0.90×；明确覆盖旧软偏好 |

### Reply length：回答内容构成

| ID | 情境 | 公共起点／上下文 | 英文目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- | --- |
| L1-1 | C1 | length=Balanced | Give only the key answer or recommendation, without explaining the reason or adding an example. | Brief：关键点 |
| L1-2 | C1 | length=Brief | Give the key answer and a short reason for it, without adding a worked example. | Balanced：关键点＋简短理由 |
| L1-3 | C1 | length=Balanced | Give the key answer, explain why it makes sense, and add one relevant concrete example. | Detailed：关键点＋解释＋相关例子 |
| L2-1 | C2 | length=Detailed | Make the answer a little less detailed: keep the key point and a short reason, but remove the example. | Balanced；删去例子保留理由 |
| L2-2 | C2 | length=Brief | Add a little explanation to the key answer so you know why it is useful, without adding an example. | Balanced；补理由 |
| L2-3 | C2 | length=Balanced | Trim the response down to its key point for a quick check; you do not need the supporting reason this time. | Brief；删理由保留关键点 |
| L3-1 | C3 | length=Detailed | You feel overloaded and want a less overwhelming answer: keep only its key point, rather than changing the speaking speed. | Brief；竞争解释可能是减慢语速 |
| L3-2 | C3 | length=Brief | You need more support to understand the material: add an explanation and an example, rather than only receiving more encouraging wording. | Detailed；竞争解释可能是 Encouraging；实际 tone 保持当前 |
| L3-3 | C3 | length=Detailed | You want to get through the material more efficiently. Keep the key point and a short reason, but remove the example; do not speed up the voice. | Balanced；竞争解释可能是提高语速 |
| L4-1 | C4 | 公开结构历史 Brief → 当前 Detailed | Restore the earlier answer format that gave only the key point. | Brief；唯一历史 |
| L4-2 | C4 | 公开结构历史 Balanced → Detailed → 当前 Brief；配各自回答例子 | Restore the middle answer format, which included an explanation and a concrete example. | Detailed；多历史目标 |
| L4-3 | C4 | 公开旧状态 length=Balanced,tone=Professional；当前 length=Detailed,tone=Friendly | Restore the earlier key-point-plus-reason format, while keeping the friendly tone you now have. | Balanced；保留 Friendly，非整套恢复 |

### Tone：语气风格

| ID | 情境 | 公共起点／上下文 | 英文目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- | --- |
| T1-1 | C1 | tone=Professional | Use a Friendly tone for the tutor’s responses. | Friendly |
| T1-2 | C1 | tone=Friendly | Use an Encouraging tone for the tutor’s responses. | Encouraging |
| T1-3 | C1 | tone=Encouraging | Use a Professional tone for the tutor’s responses. | Professional |
| T2-1 | C2 | tone=Professional | Make the wording feel warmer and less formal, like a friendly tutor talking with you, without adding motivational praise. | Friendly；定性风格偏好，不是强度 |
| T2-2 | C2 | tone=Friendly | Make the wording more neutral and matter-of-fact, while keeping the same amount of information. | Professional；定性风格偏好 |
| T2-3 | C2 | tone=Friendly | After a practice mistake, you want wording that supports another attempt and reinforces that progress is possible. | Encouraging；定性风格偏好 |
| T3-1 | C3 | tone=Professional; rate=1.10 | Make the interaction feel less intimidating by using friendly wording. Keep the current pace and voice. | Friendly；竞争解释可能是语速/声线 |
| T3-2 | C3 | tone=Professional; length=Brief | You want to feel more motivated to continue: use supportive encouragement, without giving a longer explanation. | Encouraging；竞争解释可能是增加说明 |
| T3-3 | C3 | tone=Friendly | You want a more serious study atmosphere through professional wording, without switching to a lower voice. | Professional；竞争解释可能是 Voice C |
| T4-1 | C4 | 公开语气历史 Friendly → 当前 Professional；配实际表达例子 | Restore the friendly style used in the previous response. | Friendly；唯一历史 |
| T4-2 | C4 | 公开语气历史 Encouraging → Friendly → 当前 Professional；配例子 | Restore the supportive style used in the first history entry. | Encouraging；多历史目标 |
| T4-3 | C4 | tone=Professional; voice=Voice B；公开软偏好 “I usually prefer professional wording.” | For this task, use an Encouraging tone instead of your earlier preference for professional wording. Keep Voice B. | Encouraging；明确覆盖软偏好，保留 Voice B |

### Voice：声音选择

| ID | 情境 | 公共起点／上下文 | 英文目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- | --- |
| V1-1 | C1 | voice=Voice A | Switch to Voice B, which you heard during familiarisation. | Voice B |
| V1-2 | C1 | voice=Voice B | Switch to Voice C, which you heard during familiarisation. | Voice C |
| V1-3 | C1 | voice=Voice C | Switch to Voice A, which you heard during familiarisation. | Voice A |
| V2-1 | C2 | voice=Voice A | Choose the warmer, gentler voice represented by target sample B. Keep the speaking rate and wording style. | Voice B；目标音色须真实可辨 |
| V2-2 | C2 | voice=Voice A | Choose the lower, fuller-sounding voice represented by target sample C. Keep the other settings. | Voice C；不要求连续调音高 |
| V2-3 | C2 | voice=Voice C | Choose the brighter, lighter-sounding voice represented by target sample A. Keep the other settings. | Voice A；定性音色偏好 |
| V3-1 | C3 | voice=Voice A; rate=1.10 | You want the delivery to feel calmer by changing to target voice B, not by slowing down or changing the wording style. | Voice B；竞争解释可能是 rate/tone |
| V3-2 | C3 | voice=Voice B | You want the tutor to sound livelier by switching to target voice A. Keep the pace and tone settings unchanged. | Voice A；竞争解释可能是提高语速/Encouraging |
| V3-3 | C3 | voice=Voice A; tone=Friendly | You want a more authoritative-sounding voice like target sample C, while keeping the friendly wording. | Voice C；竞争解释可能是 Professional |
| V4-1 | C4 | 公开声音历史 Voice B → 当前 Voice A；可重听 | Restore the voice used immediately before the current one. | Voice B；唯一历史 |
| V4-2 | C4 | 公开声音历史 Voice B → Voice C → 当前 Voice A；可重听 | Restore the voice from the middle history entry. | Voice C；多历史目标 |
| V4-3 | C4 | 公开旧状态 voice=B,rate=0.90,tone=Professional；当前 voice=A,rate=1.15,tone=Friendly | Restore the earlier Voice B, but keep the current faster pace and friendly tone. | Voice B；保留 rate=1.15、Friendly |

### Appearance：外观

| ID | 情境 | 公共起点／上下文 | 英文目标卡（自由表达，不照读） | 目标提示／预期 |
| --- | --- | --- | --- | --- |
| A1-1 | C1 | 外观基线 | Change the jacket colour to green. Keep the glasses, outfit type and size unchanged. | green；其余外观不变 |
| A1-2 | C1 | 外观基线 | Replace the glasses with a hat. Keep the colour, outfit and size unchanged. | hat；去除 glasses，其余不变 |
| A1-3 | C1 | outfit=suit; colour=purple; accessory=glasses; scale=0.95 | Change to sportswear while keeping the purple colour, glasses and current size. | sport；purple/glasses/0.95 保留 |
| A2-1 | C2 | scale=1.00 | Make the tutor slightly larger. Either target size shown, 1.05 or 1.10, is acceptable; keep the rest unchanged. | scale∈{1.05,1.10} |
| A2-2 | C2 | scale=1.10 | Make the tutor slightly smaller. Either target size shown, 1.00 or 1.05, is acceptable; keep the rest unchanged. | scale∈{1.00,1.05} |
| A2-3 | C2 | scale=0.85 | The tutor looks too small. Increase it modestly toward target size 0.90 or 0.95, without returning all the way to 1.00. | scale∈{0.90,0.95} |
| A3-1 | C3 | 外观基线 | You want a more casual look through sportswear. Keep the glasses, colour and size unchanged. | sport；竞争解释可能是去配饰 |
| A3-2 | C3 | colour=orange; accessory=hat | You want a more understated look through a grey outfit colour. Keep the hat, outfit type and size. | gray；竞争解释可能是去帽子 |
| A3-3 | C3 | 外观基线 | You want the tutor to stand out more through a yellow outfit colour, without making it larger or changing the accessories. | yellow；竞争解释可能是放大比例 |
| A4-1 | C4 | 公开颜色历史 green → 当前 blue；其余外观相同 | Restore the jacket colour used immediately before the current blue. Keep everything else as it is now. | green；唯一历史 |
| A4-2 | C4 | 公开颜色历史 orange → gray → 当前 blue；配图 | Restore the jacket colour from the first history entry. Keep the other appearance settings unchanged. | orange；多历史目标 |
| A4-3 | C4 | 公开旧状态 sport/blue/glasses/1.00；当前 suit/purple/hat/1.05 | Restore the earlier sportswear, while keeping the current purple colour, hat and size. | sport；保留 purple/hat/1.05 |

## 后续定稿事项

本稿已给出六十个不同目标/上下文，不再要求三套策略变体。需要用户确认具体任务是否贴合项目；声音集合、目标图卡和公开历史样例尚需实现/制作。语速容许范围、tone 风格描述和自然歧义只属于设计候选，不宣称已被用户理解或实机验证。

在用户已定的完整规模下继续设计，不在本轮缩减任务量。先确认五方向的具体任务及 C2 适配，再完成参与者可见英文卡、研究者重置配置和问卷绑定；问卷/日志可独立用模拟数据提前验证，真人预实验留实现后讨论。
