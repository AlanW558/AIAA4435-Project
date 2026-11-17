# 阶段二第 6 步：本地组合验收

日期：2026-11-07。结论：**当前 Reply length 四策略比较框架的本地组合验收完成；发现的初始设置接口问题已修复并回归通过。** 真实调用不是一次无中断自动全通过：首题完成后，第二题创建因设置契约不一致被拒绝；保留失败证据，在同一受限服务上以完整设置继续完成第二题，再用修复后的后端验证部分设置接口。没有进行头显测试或正式参与者收集。

## 验证结果

| 层面 | 本次结果 | 范围 |
| --- | --- | --- |
| 完整后端 | **233 项通过** | 原 230 项＋部分基线创建/新题回归 2 项＋并发付费调用硬上限 1 项；HTTP 测试也覆盖部分设置 |
| Unity 完整 fixture | **93 项检查通过** | 修复后重跑，包括丢失 create/start/answer/submit/next 回复、暂停、评价版本、新题隔离；新题显式只传 Detailed 设置 |
| 新增桌面故障验收 | **10 项行为断言通过** | 错误格式成功响应、旧快照、组件中断和重复操作抑制；无模型费用 |
| Unity＋真实模型 | **10/10 次 provider 尝试成功** | 两题共享解释、实际澄清、统一展示、实际英文回答、单分支修复与历史隔离 |
| 真实运行日志核验 | 两题全部所列审计不变量通过 | 每题一次初始解释、同一 shared_id、一次首次展示、提交版本一致、调用记录不重复计数 |
| 实际头显 | 未执行 | 按计划等全部本地实现完成后统一验证 |

Unity 的 93 项包含等待断言，不代表 93 个研究情境。真实首题自动脚本有 16 项断言通过后中断；第二题由工程工具触发相同 Unity 客户端方法继续，另留 7 条通过记录。两段证据与审计共同支持本次工程结论，不把原始 FAIL 改写成完整自动 PASS。

## 真实模型与调用量

沿用项目已存在、被 Git 忽略的本地 `.env`：请求模型 `deepseek-v4-flash`，返回模型 `deepseek-flash`。服务硬上限 14 次尝试，实际 10 次；没有自动重试或备用密钥切换，检查结束后服务已停止。

只汇总规范 provider_finished 记录：输入 8,568 tokens，输出 970 tokens，合计 **9,538 tokens**。这是 provider 返回的 usage，不据此猜测实际扣费金额。共享解释或分支检查点中引用的调用记录不重复计数。

| 题次 | 解释调用 | N 判断 | 回答生成 | 说明 |
| --- | --- | --- | --- | --- |
| 第一题：明确修改＋知识问题 | 3 | 1 | 2 | 1 次共同初始解释＋A 的自然语言澄清解释＋E 的后续问题解释；其余初始分支复用同一生成 |
| 第二题：两种竞争结构＋知识问题 | 1 | 1 | 2 | 共同解释一次；各澄清以已有选项回答；Brief 和 Detailed 分别生成 |

第一题 5 次生成引用中 3 次复用；第二题 4 次引用中 2 次复用。模型实际生成上下文相同时复用，避免策略结果仅因随机措辞不同；不同结构/对话上下文不会强制复用。

## 实际流程与观察

第一题从 Balanced 起步，要求之后仅关键答案并询问 active recall。E/S 先完成，A 发起澄清，所有结果仍隐藏。暂停/恢复后，通过未来 STT 共用入口发送自然语言确认，再统一开放。四分支均保存 Brief 回答。随后只在 E 用控件改为 Detailed 并追问作用；E 对话增加至两条，S 保持原 Brief 和一条对话，首次 reveal_id 不变。

第一题使用全部 Unable to judge 的**合成工程评价**验证提交接口，不是参与者评分，也不作为研究结果。提交绑定当前结果后进入新题。

第二题以独立 Detailed 基线开始，要求更容易理解，但明确在“仅关键点”与“更完整解释和例子”之间尚未决定。真实 N 与 A/S 都发起澄清。E 虽先完成，仍不公开；A 选 Brief 后继续隐藏；S 选 Detailed 后仍等待 N；N 选 Brief 后统一开放。最终 E/A/N 为 Brief，S 为 Detailed。结束该题直接退出为 aborted，不伪造问卷提交。

已查看实际英文回答和截图：Detailed 有独立理由、例子/操作步骤，Brief 显著较短。但 Brief 的定义仍可能包含说明性短语，例如 active recall 回答包含一个简短举例，spaced repetition 定义也带用途说明。因此当前结构控制不能保证“关键答案”与“补充解释”的语义边界完全准确，也不能自动宣称参与者目标已达标；正式研究仍由参与者问卷评价。

## 发现与修复

**问题：比较创建接口的部分设置与文档不一致。** 文档示例和下一题调用允许 `settings: {reply_length: detailed}`，但服务把它直接传入需要完整设置的 TutorState，返回 `A complete tutor state requires every setting.`。此前完整 fixture 只覆盖省略 settings 或公开历史，遗漏了此路径。

修复：比较任务创建时，先校验提供的部分设置，再覆盖到一份新的 DEFAULT_SETTINGS，最后由 TutorState 校验完整组合。不从旧题继承状态，不改变原单会话接口的完整设置契约，也不自动修补不兼容的 avatar/outfit 组合。

新增测试覆盖：部分创建、部分新题基线、未指定字段使用默认值、空历史、未知字段/非法值/null/不兼容外观仍拒绝；HTTP 和 Unity 也验证只传 Detailed 能正常进入新题。新增并发预算测试证明 24 个并发请求最多放行 14 个 stub 调用。

为避免重跑首题浪费额度，真实服务保持原进程与 14 次总上限，第二题使用明确的完整设置继续。这个进程没有热更新代码；**部分设置修复的证据来自新进程中的免费后端/HTTP/Unity 回归**，不把后续真实调用冒充对新代码的热更新验证。

## 日志核验与证据位置

真实运行目录：

`StudyData/macos/tutor-comparison-acceptance/live/20261107T142047570710Z/`

- `checks.txt`：保留最初的失败与之前 16 条通过记录。
- `continuation-checks.txt`、`continuation-final.json`：同一服务的第二题继续验证及最终退出状态。
- `clear-first.json`、`clear-repaired.json`、`ambiguity-hidden.json`、`ambiguity-final.json`：Unity 实际读取的状态。
- `01-clear-hidden.png` 至 `05-ambiguity-revealed.png`：实际面板截图，右上角为 LIVE；长回答截图显示可滚动内容的一部分。
- `server.json`：调用、用量和请求去重元数据；不含密钥。
- `logs/comparisons/debug/*.jsonl`：服务端完整规范记录。
- `audit.json`：独立读取日志后的核验结果，明确保留 original_check_report 的 FAIL。

新增故障运行目录：

`StudyData/macos/tutor-comparison-acceptance/fixture/20261107T141843914960Z/`

修复后的完整 fixture 结果仍在 `StudyData/macos/tutor-comparison-unity/checks.txt`，本轮为 PASS: 93 checks。

核验内容：四份 gate 指向唯一共同解释；首次展示前各分支最新检查点没有待答问题或待生成作业；首次结果与已提交设置/历史/回答一致；第一题提交保存的 first_reveal 未变化，反馈版本与最终分支版本一致；provider_started/finished 唯一配对，真实尝试计数与服务报告相同。这个审计验证工程一致性，不验证模型解释准确率或策略优劣。

## 复现

新脚本仅用于 localhost 验收，故障入口没有加入生产 server.py。每次运行创建新的时间戳目录，不覆盖本轮原始证据。

免费故障检查：

```bash
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_comparison_acceptance_server.py
```

Unity 打开 Desktop Comparison，进入 Play mode，保持未连接，选择 `AIAA4435 > Tutor > Comparison > Run Fault Acceptance (Play mode)`。

真实模型检查（最多 14 次，会消耗已有配置账户额度）：先停掉占用 8769 的 fixture，退出 Play mode，然后：

```bash
set -a
source .env
set +a
unset DEEPSEEK_FALLBACK_API_KEY
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_comparison_acceptance_server.py --live
```

再进入 Play mode，选择 `Run Live Acceptance (Play mode)`。当前修复后的服务支持脚本中的部分初始设置；模型输出不确定，重跑不保证相同决策或调用数。脚本遇到失败即停，不追加付费重试。

日志检查不调用模型：

```bash
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/validate_comparison_acceptance.py StudyData/macos/tutor-comparison-acceptance/live/20261107T142047570710Z
```

## 后续范围

阶段二框架可作为下一阶段开发基础。下一阶段统一接入 Tone、Speech rate、Voice 与现有外观能力，随后连接 STT/TTS/试听、完整任务问卷与导出，再做全流程本地验证和 VR 实机。

当前仍没有正式问卷页面、60 题五轮调度及偏好关卡、真实语音或头显操作证据；本轮也没有验证不同用户措辞的广泛覆盖。尚不能开始最终 user study。
