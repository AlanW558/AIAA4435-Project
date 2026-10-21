# 问卷星发布状态

**389439995已发布，正在运行。** 本次仅发布“虚拟角色外形修改研究（全流程）”，保留32题六页内容。用户于2026-10-19明确授权发布，覆盖此前保持草稿的限制。

| 字段 | 实际结果 |
|---|---|
| questionnaire_id | 389439995 |
| publication_status | published（已发布，正在运行） |
| public_url | [https://v.wjx.cn/vm/QZCoEdh.aspx](https://v.wjx.cn/vm/QZCoEdh.aspx) |
| 平台列表时间 | 2026-10-19 20:59（Asia/Singapore，分钟精度） |
| 核验时间 | 2026-10-19T21:02:40+08:00（Asia/Singapore） |
| qr_code_file | [wjx_389439995_qr.png](wjx_389439995_qr.png) |
| 观察到的答卷数 | 0 |
| answers_submitted_by_agent | 0 |

二维码绝对路径：`/home/enjixiong/academics/AIAA4435/AIAA4435-Project/Docs/AppearanceExperiment/Study/survey/wjx_389439995_qr.png`。从问卷星“链接与二维码”页面的1024×1024官方入口下载；平台提供JPEG，保持原像素、尺寸转换为PNG，没有另行生成二维码。原始JPEG保留在[Validation](../../Validation/wjx-389439995-qr-original-20261019.jpg)。平台下载链接中的目标参数与上述公开URL一致。平台未提供秒级发布时间，本记录使用实际核验时间，不推测精确发布时间。

## verification

- 登录状态曾失效；用户在可见原生内置浏览器中自行重新登录后继续。
- 正常界面确认标题及ID389439995后，点击“发布此问卷”。管理列表随后显示“已发布、答卷0”，设计向导显示“此问卷正在运行”。
- 真实填写URL从发布后的“链接与二维码”页面读取，未猜测URL；已新开该公开入口并核验中文首页正常显示，无登录拦截。
- 公开页已加载DOM确认32题、六页，顺序为Q1–Q7、Q8–Q12、Q13–Q17、Q18–Q22、Q23–Q27、Q28–Q32；仅Q1–Q3必答，其余29题选填。文本输入均为空、选项均未选。详见[公开页结构记录](../../Validation/wjx-389439995-public-home-20261019.json)。
- 本次未编辑题目或修改问卷设置，未填写或提交答卷，未推送GitHub。此前逐题核对保留在[台式机完成记录](desktop_completion.md)和[重载审计](../../Validation/wjx-desktop-reload-audit.json)。
- 旧384478976仍已发布、22答卷；参考389455149及389455386仍未发布、0答卷。未修改这些问卷。旧问卷22份总数不代表22份可用真人数据。

## 剩余未验证边界

- 未提交任何测试或正式答卷；同设备连续真实提交未验证。
- 拒绝参加路径的服务端保存行为未验证；此前预览仍出现提交控件，不能承诺拒绝记录零保存。
- 此前预览发现撤回旧问卷关联同意后Q7隐藏但DOM值保留；隐藏字段入库、导出是否排除未验证。分析必须以参加同意及关联许可为准。
- 当前设置界面没有独立的问卷星账号一次限答控件，该项目未独立验证。
- 真实导出列名、数据入库和真实手机扫码流程未验证；本次公开入口在已登录的内置浏览器中打开，未另做登出或外部设备访问测试。

## 截图证据

- before_publication：[查看截图](../../Validation/wjx-389439995-prepublication-20261019.jpg)
- link_and_qr：[查看截图](../../Validation/wjx-389439995-publication-link-20261019.jpg)
- public_home：[查看截图](../../Validation/wjx-389439995-public-home-20261019.jpg)
- published_list：[查看截图](../../Validation/wjx-389439995-published-list-20261019.jpg)
- running_status：[查看截图](../../Validation/wjx-389439995-published-summary-20261019.jpg)

## 历史

2026-10-18：32题六页草稿完成，未发布、0答卷。该日期的截图和完成记录均保留。

2026-10-19：用户明确授权发布，仅389439995转为已发布；公开首页和官方链接、二维码已核验，观察到0答卷。以本记录为当前发布状态，早期“未发布”描述仅为历史。

## 发布后的独立核验

2026年10月19日，在本地使用zxing-cpp 3.1.1分别解码官方PNG与最终PDF第7页中的二维码，两者均得到 `https://v.wjx.cn/vm/QZCoEdh.aspx`，与平台公开链接一致。[解码记录](../../Midterm/qr_decode_verification.json)。这是文件解码验证，未代替真实手机扫码与连续提交测试；没有提交答卷。
