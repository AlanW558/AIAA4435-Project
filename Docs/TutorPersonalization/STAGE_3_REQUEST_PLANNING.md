# 阶段三第二步：五方向共同解释、候选与策略判断

日期：2026-11-08。状态：**第二步已实现并通过本地后端验证；不代表五方向的实际效果、控件或语音已经接通。**

后续更新：同日已完成[第三步 Tone 组合生成](STAGE_3_TONE_GENERATION.md)，执行字段扩展为 Reply length＋Tone。下文保留第二步完成时的范围与 266 项测试记录。

第四步已完成[Speech rate/Voice 参数接线](STAGE_3_SPEECH_SETTINGS.md)：四项对话属性可执行；合法数值意图超出语速范围/精度时返回有说明的 unresolved，非法模型结构仍报错。下述旧版本的数值错误处理记录不代表最新行为。

依据：[能力与修改规则对照表](STAGE_3_CAPABILITY_CONTRACT.md)。下一步：Tone 与 Reply length 的组合回答生成。

## 1. 本次实现

| 内容 | 结果 |
| --- | --- |
| 公开能力 | 新增 `tutor_capabilities.py`，集中提供五方向字段、取值、默认、外观兼容关系和作用域。Voice A/B/C 保持占位，不编造音色描述 |
| 共同解释 | `tutor-interpretation-v2` 可以规划五方向请求；保留普通问答、混合请求与已有澄清回答的区分 |
| 多属性候选 | 区分“必须同时修改”和“可能是不同属性的解释”；校验遗漏、越权字段、非法组合及保持约束；按完整结果去重并重映射默认 |
| 语速表达式 | 默认/当前基准与乘法/倍率差值由程序计算，基于捕获的公共状态；不静默取整或截断 |
| 外观展开 | 候选阶段展开角色替换的五字段影响，兼容的显式保持覆盖默认；不在提交后隐藏重置 |
| 澄清选项 | 按实际属性显示英文说明、数值基准、作用域和保持要求；保留 Other 与 Cancel；顺序由公共输入确定 |
| 策略判断 | `tutor-gates-v2` 将 R1/R2/R3 扩展到五方向，复用旧外观规则，并加入版本化的语速小幅可逆工程规则 |
| 澄清约束延续 | 原始显式保持字段进入自由回答的结构化上下文；模型漏报时仍保留，违反时拒绝且保留原问题 |
| 运行时边界 | `EXECUTABLE_FIELDS` 暂时仍为 Reply length。未接通效果的请求返回 `UNRESOLVED / EXECUTION_NOT_CONNECTED`，不部分执行、不伪装成功 |

本次未改变场景、面板布局、实际 TTS/STT、声音资源或正式任务问卷。新解释规则只经过测试替身验证，尚未进行新版本真实模型语言效果验证；阶段二真实调用记录属于旧版本，不能代替本次新能力的验证。

## 2. 请求与候选契约

原有六个顶层字段保留：kind、conversation_query、scope、requested_fields、proposal、clarification。新增 required_fields、preserved_fields：

| 字段 | 含义 | 例子 |
| --- | --- | --- |
| requested_fields | 所有合理候选可能修改的字段并集 | “calmer”可能涉及 rate 或 tone |
| required_fields | 每个候选必须包含的并列要求，包括目标等于当前值的字段 | “friendly and brief”必须同时包含 tone、reply_length |
| preserved_fields | 显式保持当前值的字段，与 requested_fields 不重叠 | “change outfit but keep colour”要求保持 jacket_color |

兼容旧 Reply length 响应：省略新增字段时，required_fields 默认等于 requested_fields，preserved_fields 默认为空。新模型提示要求显式输出两者。程序可检查模型声明的约束一致性，但不能仅凭 schema 证明模型正确理解了自然语言，后续仍需真实模型检查。

以下是结构片段；完整响应的 candidates 位于 proposal 内：

```json
{
  "requested_fields": ["speech_rate", "tone"],
  "required_fields": [],
  "preserved_fields": ["voice"],
  "candidates": [
    {"id": "c1", "patch": {"speech_rate": 0.90}, "evidence": "Public request evidence"},
    {"id": "c2", "patch": {"tone": "friendly"}, "evidence": "Public request evidence"}
  ]
}
```

仍为 1–3 个有效候选；相同完整结果合并。不能把明确并列要求拆成互不完整的候选。

### 数值、外观与异常

- 当前速度 1.20 时，`{"basis":"default","operation":"multiply","value":0.9}` → 0.90；`{"basis":"current","operation":"multiply","value":0.9}` → 1.08；`{"basis":"current","operation":"add","value":-0.1}` → 1.10。
- Decimal 计算后验证 0.70–1.30/0.01 范围，不依赖浮点近似取整。直接数值沿用已有状态校验的浮点表示容差。
- 模型应将不支持的范围/精度报告为 supported=false；若仍给非法候选，规范化器抛出 ModelError，控制器按既有失败/重试流程处理，绝不提交近似值。更具体的用户端语速提示属于后续参数接线步骤。
- 局部外观修改不能附带不必要的 avatar_id；真实角色替换先展开默认，再应用合法保持，完整状态一起校验。规范化补丁保留替换所需全部外观字段，防止提交时再次套默认而丢失保持值。
- 下一次回答可在只读层规划四项对话属性；临时外观、按字段混合不同作用域尚不支持。实际一次回答执行仍仅有 Reply length 流程。
- 历史与偏好只来自公共输入，不读取研究者私有目标。公开能力不含 S 阈值，N 不额外获得 S 决策规则。

## 3. Selective 规则顺序

1. 不受支持 → UNRESOLVED。
2. 未解决历史/指代 → 有多个有效可区分候选时 R1 ASK，否则 UNRESOLVED。
3. 可能覆盖真实提供的软偏好且没有明确授权 → R2 ASK。覆盖所有实际修改的字段；不变的保留字段不制造冲突。
4. 仅语速变化：默认变化≤0.05 且候选跨度≤0.05 → SMALL_REVERSIBLE_STEP ACT。其他不同目标的语速候选 → R3 ASK；明确单目标不因幅度大而自动询问。
5. 仅外观变化：保留旧规则的小幅比例、分类差异、字段差异和比例跨度判断。
6. 其他不同完整结果，包括离散 Tone/Voice、Reply length 和跨属性候选 → R3 ASK；没有触发则 ACT。

语速 0.05 是工程起点，不是已验证的感知阈值；R1/R2 优先。未来更改阈值需升级策略版本并重新测试，不从私有任务目标反推候选。

## 4. 与执行链的关系

SharedInitialRequest 继续只解释一次初始请求，并向四策略提供相同只读输入；没有新增按属性分别调用模型的路径。后续自然语言修复使用各分支公开状态。只读计划不更新 participant_view，也不提前暴露新属性、回答、外观或声音。

Tone 回答、rate/voice 参数及统一外观接线属于后续步骤，因此会话与比较服务在应用计划前检查已接通字段。涉及未接通字段的整体请求保留所有原设置，不先修改其中 Reply length。日志保留规划的 gate_decision，另记 execution_not_connected；最终 outcome 为 unresolved。以后实际接通一项再相应放开。

自由文本澄清不能绕过这一边界。违反保持约束时保留原问题和状态，可明确重试、重新回答或取消。尚未执行的混合请求保留学习问题，不生成一个假装采用新设置的回答。首次统一展示、固定首次快照、分支隔离、生命周期和评价版本绑定沿用阶段二。

## 5. 本地验收

仓库根目录运行：

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python -m unittest discover -s Backend/tests -q
```

2026-11-08 最终结果：**266 项后端测试通过，其中新增 33 项，原有 233 项继续通过。** 全部使用本地 fixture/mock，不调用付费模型。

新增覆盖五方向候选、数值计算与状态捕获、精度越界、结果去重、多属性遗漏、保持冲突、外观替换和局部保持、作用域、历史与偏好、策略优先级与阈值、旧外观规则一致性、英文澄清、一次共同解释及隐藏状态、会话/比较执行保护、自由回答保持约束及失败后的原问题保留。

初次沙箱回归中，7 项 HTTP 测试因 localhost 端口权限无法启动；允许临时本机回环端口后，完整回归通过，未跳过这些测试。未启动新的 Unity/头显验收或真实模型验证。

文件：[能力模块](../../Backend/tutor_capabilities.py)、[解释与规范化](../../Backend/tutor_interpretation.py)、[策略](../../Backend/tutor_policy.py)、[执行边界](../../Backend/tutor_session.py)、[新测试](../../Backend/tests/test_tutor_multidomain.py)。旧有只读真实模型验证脚本的“不支持”示例改为音高请求，因为 Voice B 的显式选项已经可规划；该脚本本次未运行。
