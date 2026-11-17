# 比较任务生命周期与评价绑定接口

日期：2026-11-07；阶段二第 5 步。执行版本 `tutor-comparison-execution-v2`；问卷契约 `task-feedback-q1-q7-v1`。仅 debug，不代表正式研究系统已完成。

本步实现暂停/恢复、逐分支评价草稿、提交时冻结结果、独立新题及交互轨迹。问卷字段按当前四策略整合设计的 Q1–Q7 建立版本化接口；后续题干若修改，须相应变更版本，不能混合旧新数据。本步没有搭建完整问卷页面、60 题自动调度、方向末/总体偏好界面或语音识别。

## 生命周期和响应字段

每次创建仍得到独立 task_id。新增 series_id、sequence_index、previous_task_id、next_task_id 记录已提交任务与后继的关系，不能将它们视为已冻结的五轮任务库。

| lifecycle | 含义 | 可用操作 |
| --- | --- | --- |
| active | 正在处理/比较/填写反馈 | 原比较命令、评价、pause、submit、close |
| paused | 可恢复暂停 | GET、resume、close，以及原请求的幂等重放 |
| submitted | 评价与结果已冻结，底层比较 closed | GET、next，以及原请求的幂等重放 |
| aborted | 主动退出，底层比较 closed | GET 和已收到命令的幂等重放；不能冒充已提交题进入 next |

phase 仍表示比较状态，lifecycle 表示本层状态。不要仅靠 phase 或 End task 推断任务成功。提交后的 Q1 可以是 not_met 或 unable_to_judge。

新增反馈视图 `feedback.E/A/N/S`，每项包含：

- feedback_revision：草稿版本；没有草稿为 0。
- draft：草稿与绑定信息，未答为 null。
- current：草稿对应当前 branch_revision。
- complete：current 且 Q1–Q7 有有效答案。

can_submit 只在 active、四分支已统一开放且均 ready/stopped、四份当前草稿完整时为 true。错误响应和重试响应同样不绕过首次展示限制。

## 暂停、恢复和退出

以下均为 POST，成功返回 202；正文包含 request_id、expected_revision。

| 路径 | 行为 |
| --- | --- |
| `/tutor/comparisons/{task_id}/pause` | 保存当前可见视图，暂停用户操作和首次结果开放 |
| `/tutor/comparisons/{task_id}/resume` | 恢复操作；若后台已准备好则继续统一开放 |
| `/tutor/comparisons/{task_id}/close` | 无需先填问卷，明确退出为 aborted |

已经发出的后台工作可以完成，暂停不会承诺撤回 provider 请求或节省其费用。暂停期间首次结果不开放；若此前已开放，也冻结暂停时可见的分支结果。恢复后才读取最新结果。Unity 隐藏三页内容，显示暂停提示；Resume 和 End task 可用。未回答的问题 ID、已有草稿和过程记录保留，不自动重复提问或重新生成。

elapsed_active_seconds 是服务端“本题创建以来、截至结束、扣除显式暂停”的经过时间；包含等待和操作间隔，**不是认知投入时间或精确阅读时间**。elapsed_paused_seconds 单列暂停时间。活跃状态只在进程内，尚无重启恢复。

## 保存逐分支评价草稿

`POST /tutor/comparisons/{task_id}/branches/{E|A|N|S}/feedback`

```json
{
  "request_id": "feedback-E-001",
  "expected_branch_revision": 6,
  "expected_feedback_revision": 0,
  "answers": {
    "completion": "partly_met",
    "ratings": {
      "q2": 5,
      "q3": 3,
      "q4": 5,
      "q5": 4,
      "q6": 4,
      "q7": "unable_to_judge"
    },
    "reasons": ["target_mismatch"],
    "comment": "The response still included more detail than I wanted.",
    "comment_confirmed": true
  }
}
```

版本号为示例，必须读取当前视图。反馈只接受已展示、已处理完毕的分支。answers **替换该分支整份草稿**，不是局部 patch；支持保存部分回答，未答项继续缺失，不能默认填 4。

| 字段 | 约束 |
| --- | --- |
| completion（Q1） | fully_met / partly_met / not_met / unable_to_judge；不转成等距数值 |
| ratings.q2–q7 | 每项显式整数 1–7，或独立字符串 unable_to_judge；拒绝 null、0、8、浮点、布尔及数字字符串 |
| reasons | 可选且不重复；target_mismatch / unwanted_change / not_maintained / hard_to_verify / interaction_problem / other |
| comment | 最多 4000 字符；非空时必须 comment_confirmed=true，仅保存已确认文字，不接收音频 |

Q2 顺利、Q3 打断、Q4 控制、Q5 努力、Q6 满意、Q7 询问/执行选择的合适程度。不自动反向计分或合成总分。Unable to judge 是有效回答，缺失是尚未回答，两者严格区分。

Q1 为 fully_met 或尚未回答时，隐藏原因会从有效草稿中清除。not_maintained 只有该分支在首次结果之后增加了已完成对话时才保留。取消不适用原因不影响可选评论。未确认文本在写入任何日志之前即被拒绝；已确认评论保存在独立反馈记录中，**不进入 tutor 模型上下文**。

同一结果重看/切页/切换策略不使草稿失效。追加修改、回答或重试只要改变该分支版本，旧草稿保留但 current=false；需要参与者重新评价该分支，其他分支继续有效。即使最终设置碰巧相同，过程已改变也需重新确认。expected_feedback_revision 另行防止同一结果上的旧草稿覆盖新草稿。

## 提交与新题

`POST /tutor/comparisons/{task_id}/submit`，正文为通用 request_id、expected_revision。验证四份当前完整草稿后，先写 task_submitted，再关闭比较并返回 submission_id。记录包含固定 first_reveal、四份当前结果快照、各分支评价及其 branch/state/feedback 版本。失败重试不制造第二份提交；日志写入失败时不提前关闭。退出或技术处理 completed 都不等同于这一步。

`POST /tutor/comparisons/{task_id}/next` 只接受 submitted 的题：

```json
{
  "request_id": "next-001",
  "expected_revision": 24,
  "next_task": {
    "task_code": "L1-2",
    "domain": "reply_length",
    "scenario": "C1",
    "settings": {"reply_length": "balanced"},
    "soft_preferences": [],
    "public_setup": []
  }
}
```

返回旧题安全视图中的 next_task_id，然后 GET 新题。task_code/domain/scenario 必填；其余字段使用创建接口的公开起点规则。**未传的新设置、历史、偏好均使用默认起点，不继承上一题结果**。只有显式 public_setup 才会形成新题的公开历史。

同一已提交题只产生一个后继；原 ID 重试返回同一链接，新 ID 的重复推进返回 already_advanced。若新题已创建但链接日志写入失败，使用同一 next_task 配置重试会复用已创建题，不复制第二份；不要在这种恢复中换成不同的任务配置。

后续正式 Next question 按“保存草稿 → submit → 根据任务调度器 next”串联。现在尚未实现方向偏好/总体偏好关卡，debug next 不能作为跳过它们的正式流程。最后一题可提交后结束，不必为了提交而虚构下一题。

## 交互轨迹和 Unity 接口

新增日志事件：task_paused、task_resumed、strategy_selected、panel_presented、feedback_saved、task_submitted、task_advanced、task_aborted。原分支 checkpoint、first_reveal 和 provider 记录继续保留。区分 command_received（尝试）与具体成功事件，不把收到请求当作完成。

`POST .../branches/{condition}/presentation`：request_id、expected_branch_revision、page（conversation / controls / history）。只接受当前选中分支、匹配版本的报告。记录是否开放、当前状态版本及 reveal_id；原 ID 重试不重复计数。

Unity 在面板可见且选中页/分支/版本改变时排队发送报告；暂停时停止报告，旧版本被拒绝后不会冒充新结果的观看记录。网络或服务端记录故障保留事件并提示 Retry。时间戳是服务端接收时刻；panel_presented 仅表示客户端报告渲染，**不能据此断言参与者读完、理解或听过音频**，也不是完整眼动/精确停留时间。

供后续问卷 UI 调用的客户端接口：

- `PauseOrResume()` / `Close()`：已绑定现有面板按钮。
- `SaveFeedback(answersJson)`：保存当前分支评价；与 SubmitUserUtterance 完全分开。
- `SubmitTask()`：仅 can_submit 为真时提交。
- `AdvanceToTask(taskJson)`：仅 submitted 时推进；识别服务器授权的 next_task_id/series/sequence/previous 关联，旧回包不能替换新题。

后面三项已通过本地联调，但本步不添加可供参与者正式填写的问卷页面或 Next question 按钮，也没有预填测试评分进入真实场景。验收脚本中的评分仅用于 fixture 检查。

## 本次验证和限制

2026-11-07：新增 **25 项后端生命周期/HTTP 测试**通过，完整后端 **230 项通过**；Unity 比较验收扩展为 **93 项检查通过**（含 HTTP 等待断言）。仅使用 localhost fixture，真实/付费模型调用 0。

验证覆盖：缺失/无法判断区分、非法评分、未确认文字不落日志、单分支评价失效、版本冲突与幂等、暂停中后台完成但不展示、已显示结果冻结、无问卷退出、提交/链接日志故障、下一题独立起点、丢失 create/start/answer/submit/next 响应恢复。

本轮实际审计有一次 task_submitted、一次 task_advanced；第二题只暂停后退出为 aborted，没有伪造第二份提交。结果见 `StudyData/macos/tutor-comparison-unity/checks.txt`，暂停截图为同目录 `06-paused.png`，工程日志仍在 comparison-fixture 下。

尚未完成：正式任务库/五轮调度和偏好关卡、完整问卷 UI、STT 确认/删除流程、数据表导出、跨进程恢复、真实模型组合验收与头显验证。下一步为阶段二第 6 步本地组合验收；不以本步接口测试替代正式实验预试。
