# 属性偏好、总体偏好与跨模块导航

> **2026-11-28 当前修订：** 新偏好采用 `strategy-preference-v2`：E/A/N/S 可多选 1–4 项，或互斥选择 No preference。新界面去掉 Unable to compare 和其它旧特殊类别，A0–A4 的 Unable to judge 不变。正式运行在 manifest 固定偏好版本；无该字段的历史运行仍为 v1，恢复/导出保留原记录。下文为 2026-11-11 实现验收历史，不代表当前题量或新偏好选项；当前规则见[属性级问卷修订](Study/ATTRIBUTE_LEVEL_FEEDBACK_AMENDMENT.md)。

> 后续实现（2026-11-11）：32 题预演材料与固定准备流程已接入，见 [研究任务材料](STUDY_TASK_MATERIALS.md)；下文原有“32 题未接入”表示本文件所记录阶段的历史状态。正式采集仍未开放。
日期：2026-11-11。状态：本地实现、后端测试、Unity 模拟 HTTP/STT 联调和截图核对完成；正式 32 题及自然情境入口尚未接入。

## 参与者流程

在既有左前方不透明实验面板中，每个属性最后一道任务的四策略问卷提交后，显示该属性的策略偏好页。没有额外独立面板，不改变纸色样式或坐姿布局。

1. 阅读当前属性偏好问题；选一个策略或 2–3 个并列偏好。
2. 也可选择 No clear preference / I would not want to use any of them / Unable to compare，与策略集合互斥。四者无差别时用 No clear preference，不默认选 S、不从评分推算偏好。
3. 可选口述理由：Record reason → 检查转录 → Use text。没有理由也能提交；未确认转录不可悄悄保存。
4. 点击 Submit preference，收到保存确认后才解锁 Continue to 下一属性。可先休息，隐藏面板或暂停均保留本次运行内的草稿；退出不需要先答偏好。
5. 新属性加载独立任务说明、起点、历史和准备状态，不继承上一属性的结果或偏好草稿。
6. 第四属性偏好保存后，显示一次四属性比较的总体偏好，答案重新从空白开始。
7. 总体偏好保存后停在比较结束、等待自然情境的页面。没有第五个属性比较轮或自然情境策略偏好；此步不自动启动尚未实现的自然情境模块。

总体偏好题明确限定 speech-rate / reply-length / tone / voice tasks，在自然情境之前收集。没有预填答案，不要求与此前四个属性偏好一致。

## 本步练习材料与正式研究的区别

`PracticeTaskSequence.json` 现有四个属性模块，各两道练习，共八题，顺序为 Reply length → Speech rate → Tone → Voice。保留原来的两道 Reply length 练习，再补齐其他属性，用于演练导航和偏好流程。

这是 **practice/debug 工程清单**，不是正式八题研究，也没有改变已选定的四属性×四情境×两题＝32 题设计。所有画面与模拟日志仍标为练习/工程数据。正式模块顺序未据此冻结。

客户端与后端的比较序列只接受四属性，不接受 `natural_scenario` 作为四分支比较模块。自然情境将有独立 S 会话入口，不通过新增第五个比较模块实现。

## 服务端约束与数据

- 创建第一个任务时，登记 `attribute-sequence-v1`：purpose=practice，模块方向、任务代码及情境。传输白名单不含任务标题、私有目标或 instructions。
- 后端校验创建的首题和每次 next 均与登记顺序一致；无法跳到别的题、漏过属性偏好或跨到自然情境。
- 属性偏好只在该属性全部已提交任务之后开放；总体偏好必须在四个属性及四份属性偏好之后。仅含部分属性的练习不会被当作完整四属性总体比较。
- 偏好使用 `strategy-preference-v1`，保存 scope、domain（总体为空）、答案、可选确认文本、提交 ID、系列 ID、时间，以及对应任务 ID／任务提交 ID／实际比较条件。
- 每个作用范围只接受一次正式提交。原请求 ID 重放返回相同结果；不同请求不能覆盖已提交偏好。偏好保存后题目状态保持已提交，不重新开放模型对话或修改已评结果。
- 偏好使用独立 preference_revision；暂停、恢复、退出和保存均校验它。实际任务结果版本不因偏好变化而改写。
- 写审计记录成功后才确认偏好；审计失败不放行下一模块。未知网络结果可用现有 Retry 恢复，前端不乐观增加模块序号。

在 `/tutor/comparisons/{task_id}/` 下新增：

| 操作 | 内容 |
| --- | --- |
| preference | 当前 scope、expected_revision、expected_preference_revision、answers、request_id |
| preference_pause / preference_resume / preference_exit | 对应任务及偏好版本、request_id；不伪造答案 |
| preference-transcribe | 当前偏好 scope 作为 condition、偏好版本作为 expected_revision、瞬时 WAV、request_id；不调用 tutor 请求接口 |

`strategy_preference_submitted` 作为独立 evidence 事件进入原有导出流程，保留答案集合，不自动拆成多个人数。偏好原因不进入 tutor 历史、模型输入或系统设置；原始音频不落盘。STT 在当前偏好范围、版本、暂停/退出状态改变后拒绝迟到结果。

## 本地验证

- **426 项后端测试通过**；新增十项覆盖并列/互斥选项、确认备注、仅元数据序列、提交时点、顺序与漏题拦截、总体范围、部分练习、重复提交、审计失败、暂停退出、STT 隔离及导出。
- **399 项 Unity 检查通过**：完整走完八题、四次属性偏好和一次总体偏好，验证空白初始状态、并列及特殊选项、隐藏/暂停草稿保留、口述确认、模块切换、总体不继承答案、显示文本高度和最终交接页。
- 故意丢失三次成功响应：首次属性偏好保存、首次跨模块 next、总体偏好保存。三次均按原请求恢复，无重复任务或偏好。Console 的三条 Curl error 52 对应故障注入，不是正常联网失败，也不写成测试期间零错误日志。
- 审计复核：八个不同任务、八次任务提交、四份属性偏好和一份总体偏好；每份属性偏好关联两题，总体关联八题；导出恰好五行 preference evidence。理由文本仅在偏好中，不出现在策略对话/最终结果中。
- 评分及偏好页面截图为模拟作答。检查了题干完整性、选择高亮及选项间隔；提交前的完成提示另改为 Submit preference first，避免在总体偏好尚未提交时暗示已结束。
- 新增云调用 0，真实麦克风录音 0，未做头显测试。

证据目录：`StudyData/validation/preferences-20261111/`。包含 summary.json、backend-tests.txt、unity-checks.txt、八份任务审计、preferences-export.jsonl 及三个界面截图。截图中的答案不属于真实参与者研究数据。

重跑：启动 `Backend/tests/unity_preferences_fixture_server.py`（localhost:8777），在新的桌面比较 Play 会话中执行 `AIAA4435 > Tutor > Comparison > Run Preference Checks (Play mode)`。每次重启模拟服务以重置三次故障注入；检查后停止 Play 与服务。

## 下一步与边界

下一步装载正式 32 题：指定起点、公开历史/软偏好素材、音色目标绑定、正式任务准备限制和逐题呈现核对。之后接 Selective 自然情境与其独立问卷、正式参与者会话和完整恢复机制，再进行真实语音及头显验收。

当前偏好与任务日志已写盘，但后端运行状态和未提交草稿仍主要驻留内存；不据此声称能够在应用/后端重启后恢复整场实验。正式采集仍未开放。
