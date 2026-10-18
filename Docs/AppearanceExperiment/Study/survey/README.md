# 外形实验问卷：供本次招募的 22 位参与者使用

中文文案版本 `appearance-survey-v0.1-zh-CN.2`，2026-10-18，待两位预实验参与者试填后冻结。三份问卷的题目、选项、说明和本地页面提示均为中文，按 humanizer 技能完成文案复核。本目录包括可填写的本地问卷、结构化规格和问卷星导入稿。

问卷星三份草稿已保存（7／8／7题），最后一次成功核验均未发布、0答卷，且三份均未启用设备、IP、账号限答及续答回填，供22人共用一台设备。网页说明仍为中文 v1；本地 v2 的三段说明因最后浏览器连接失败尚未同步。实际编辑链接、已核验设置和剩余限制见 [Browser Use 制作与验收记录](browser_use_creation_status.md)。

数据结构仍使用 `appearance-survey-v0.1`。题目 ID、选项编码、评分方向和显示条件保持原样，导出时另存 `language=zh-CN` 和 `content_revision`，用于区分中文文案。现有导入器兼容这些新增字段，原始回答记录会保留它们；分析前须核对版本，不能直接混合不同语言的回答。

2026-10-18，用户确认另有 22 位真实参与者可安排，仍按 2 位预实验、20 位正式实验准备。旧问卷的 22 份记录中有 19 份模拟回答，另外 3 份来源尚未核实；不能将这 22 份记录计为真人样本或据此推断两批人员相同。旧回答只有在逐条核实真实来源、取得本人关联同意并核对已有匿名编号后，才与本次记录关联。

## 已制作的材料

| 文件 | 用途 |
|---|---|
| [questionnaire.html](questionnaire.html) | 无外部依赖的浏览器问卷。三个表单可切换，保存按钮下载当前回答 JSON；默认不上传、不自动缓存。|
| [questionnaires.json](questionnaires.json) | 所有题目、稳定字段名、选项编码和条件显示的唯一内容规格。|
| [wjx_pre_import.txt](wjx_pre_import.txt) | 开始前：同意参加、VR 经历、接触本原型经历、旧问卷关联许可及可选代码。|
| [wjx_block_import.txt](wjx_block_import.txt) | 每轮结束后重复使用：打断、控制、努力、满意度四项及可选评论。|
| [wjx_exit_import.txt](wjx_exit_import.txt) | 结束时：偏好的轮次、理由及具体正反例。所有实质题均可跳过。|
| [researcher_guide.md](researcher_guide.md) | 中文主持说明、关联旧问卷规则、问卷星制作设置、负担与分析边界。|
| [import_responses.py](import_responses.py) | 校验本地下载的回答，输出与现有分析字段一致的分轮评分 CSV 和缺失说明；不生成测试参与者。|
| [humanizer_review.md](humanizer_review.md) | 中文文案复核、语义保留和版本记录。|
| [validate_artifacts.py](validate_artifacts.py) | 检查题目、评分、路由、参与者编号、前端依赖与脚本语法。|

本地打开 `questionnaire.html` 即可填写。研究者先根据实验日志配置 URL：

```text
questionnaire.html?form=pre&participant=P001&session=AP-P001-20261018-01
questionnaire.html?form=block&participant=P001&session=AP-P001-20261018-01&block=1
questionnaire.html?form=exit&participant=P001&session=AP-P001-20261018-01
```

上面的编号和日期仅为 URL 格式示例，没有对应真实回答。实际 `session` 必须与 Unity marker 中稳定的 `study_session_id` 一致；它跨越四轮，区别于每个条件各自的后端 `session_id`；可以改成系统生成的编号。表单不展示 E/A/N/S，也不从问卷平台收集研究条件。研究者在分析时依据冻结的分配表关联。

本地问卷的回答保存在浏览器默认下载位置，下载后还需确认研究者已收到文件。每次下载后现场核对文件，将实际回答放到专门的数据目录并备份；勿提交到公开 GitHub。没有中心化提交服务，不能把本文件当作已经发布到问卷星的在线链接。刷新或关闭页面会丢弃未下载的答案。重复下载会产生新文件，导入器遇到同一 session/form/block 的多份回答会停止，要求研究者明确选择最终修订版；不能当成新回答。

运行 `python3 Docs/AppearanceExperiment/Study/survey/build_forms.py` 重建规格、导入文本及 HTML。确认冻结后不要在采集中重新生成或修改题目。
