# 外形实验问卷

当前填写入口为 [六页合并问卷](questionnaire_unified.html)，文案版本 `appearance-survey-v0.1-zh-CN.4-unified`，2026-10-18。顺序为开始前、四轮体验后的反馈、最后回顾。编号与实验类型只填一次，最后下载一个包含整份回答的文件。中文文案按 humanizer 复核，待预实验试填后冻结。

本地问卷已把手填实验编号改为“调试／预实验／正式实验”选项，唯一关联编号自动生成。新建一人后，整份问卷和四轮沿用相同编号；换人点击“换下一位”，清空上一人的编号、答案和轮次。研究者可以在折叠的“关联记录”中下载或读取配置，供客户端和问卷共用。

问卷星开始前草稿389439995已保存第三版实验类型选项，仍为7题；全流程32题版尚未写入网页。Browser Use 因额度不足拒绝启动合并任务。用户选择先完成本地，再由台式机 Codex Desktop 新聊天接手。其余两个草稿保持未发布参考稿，旧问卷384478976保持原样。详见 [线上状态](browser_use_creation_status.md) 和 [台式机交接要求](desktop_handoff.md)。

合并文件使用 `appearance-survey-bundle-v1`，其中六页记录仍使用 `appearance-survey-v0.1`。题目 ID、选项编码、评分方向和显示条件保持原样，导出时另存 `language=zh-CN` 和 `content_revision`，用于区分中文文案。现有导入器兼容这些新增字段，原始回答记录会保留它们；分析前须核对版本，不能直接混合不同语言的回答。

2026-10-18，用户更新招募情况：实际到场可能少于原目标22人，人数尚未确定。保留2个预实验、20个正式槽位作为准备容量，按实际开始、完成和退出人数记录，不补造回答，也不将调试或预实验计入正式结果。旧问卷22份记录中的19份为模拟回答，另3份来源未核实；只在核实来源、本人同意和已有编号一致时关联旧记录。

## 已制作的材料

| 文件 | 用途 |
|---|---|
| [questionnaire_unified.html](questionnaire_unified.html) | 推荐的六页连续填写入口；最后一次下载，支持前后翻页和换人清空，不上传、不自动缓存。|
| [questionnaire_unified.json](questionnaire_unified.json) | 六页32题、显示条件及选填规则。|
| [unified_field_map.csv](unified_field_map.csv) | 问卷星题号与原有数据字段的对应。|
| [wjx_unified_import.txt](wjx_unified_import.txt) | 问卷星全流程导入稿，另按交接说明配置分页和逻辑。|
| [questionnaire.html](questionnaire.html) | 保留的旧分表工具，分别下载pre、block、exit；不作为本次统一入口。|
| [questionnaires.json](questionnaires.json) | 所有题目、稳定字段名、选项编码和条件显示的唯一内容规格。|
| [wjx_pre_import.txt](wjx_pre_import.txt) | 开始前：同意参加、VR 经历、接触本原型经历、旧问卷关联许可及可选代码。|
| [wjx_block_import.txt](wjx_block_import.txt) | 每轮结束后重复使用：打断、控制、努力、满意度四项及可选评论。|
| [wjx_exit_import.txt](wjx_exit_import.txt) | 结束时：偏好的轮次、理由及具体正反例。所有实质题均可跳过。|
| [researcher_guide.md](researcher_guide.md) | 中文主持说明、关联旧问卷规则、问卷星制作设置、负担与分析边界。|
| [import_responses.py](import_responses.py) | 校验本地下载的回答，输出与现有分析字段一致的分轮评分 CSV 和缺失说明；不生成测试参与者。|
| [humanizer_review.md](humanizer_review.md) | 中文文案复核、语义保留和版本记录。|
| [validate_artifacts.py](validate_artifacts.py) | 检查题目、评分、路由、参与者编号、前端依赖与脚本语法。|

本地打开 `questionnaire_unified.html` 即可填写。选择实验类型并填写研究者分配的参与者编号，关联编号自动生成；不需要参与者手输长编号。空白类型不预选，编号与阶段不匹配时会提示。现有正式槽位为P001至P020，预实验为PILOT01、PILOT02，调试使用DEBUG开头编号；槽位不是最低样本量。

研究者在“关联记录”中下载不含答案的配置文件，保存在私有数据目录。取得本次参与同意后，将同一文件交给启动器：

```bash
python3 Tools/AppearanceExperiment/launch_session.py --session-file /path/to/session.json
```

正式模式自动读取冻结分配；调试／预实验可另指定 `--condition`，默认S。Unity界面不展示编号、阶段、策略、目标卡或轮次。任务材料另行提供，研究者按F8推进正式任务，每四项暂停填问卷。

在合并问卷内使用“上一页／下一页”，回答会保留到最终下载。刷新或关闭会丢失尚未下载的回答；关联配置只恢复编号，不能恢复回答。研究者在每轮结束后提醒参与者回到对应页，全部完成后下载并确认收到文件，再点击“换下一位，清空全部”。旧分表入口仍可使用，但不能把同一次实验的分表文件和合并文件重复导入。问卷星不自动读取本地关联配置，研究者需按参与者编号和阶段核对日志。

导入器默认仅导入 `formal`。需要调试或预实验时显式传 `--phase debug` 或 `--phase pilot`，输出到独立目录；其他阶段排除数量会记录。关联配置文件不会被误认为回答。一个合并文件会校验为一名参与者、六页记录和四条分轮评分；页数不计为参与人数。少于20名正式参与者不阻止导入，报告列出实际人数、已有轮次和缺失。

本地问卷的回答保存在浏览器默认下载位置，下载后还需确认研究者已收到文件。每次下载后现场核对文件，将实际回答放到专门的数据目录并备份；勿提交到公开 GitHub。没有中心化提交服务，不能把本文件当作已经发布到问卷星的在线链接。刷新或关闭页面会丢弃未下载的答案。重复下载会产生新文件，导入器遇到同一 session/form/block 的多份回答会停止，要求研究者明确选择最终修订版；不能当成新回答。

运行 `python3 Docs/AppearanceExperiment/Study/survey/build_forms.py` 重建规格、导入文本及 HTML。确认冻结后不要在采集中重新生成或修改题目。
