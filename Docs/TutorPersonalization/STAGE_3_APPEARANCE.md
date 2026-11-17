# 阶段三第五步：外观接入统一四策略流程

日期：2026-11-08。状态：**第五步完成：309 项后端测试与最终 70 项 Unity 外观检查通过。** 使用本地测试替身验收，不含真实模型效果或 VR 实机结论。

衔接：[第四步语音参数](STAGE_3_SPEECH_SETTINGS.md)、[整体能力与步骤](STAGE_3_CAPABILITY_CONTRACT.md)。下一步是四属性控件、历史操作及状态提示的统一面板接线。

## 1. 执行与兼容规则

- 自然语言执行范围扩展至全部九个字段：四项对话属性，加 avatar_id、outfit、jacket_color、accessory、scale。现有 E/A/N/S 与共同候选不变。
- 复用已有 Liang/Nailong 模型、服装、颜色、配饰及整体比例；没有新建替代模型、材质或场景。
- 单独换服装保持颜色、配饰、比例及对话设置。配饰仍为 none/hat/glasses 单选；Nailong 仅支持 outfit=none。
- 角色替换在候选阶段展开五个外观字段，显式且兼容的保持要求覆盖默认；不重置对话属性。混合请求完整校验后一起提交。
- 外观只支持持久的当前任务/分支作用域，不新增“一次回答期间临时换外观”。非法组合或作用域不部分执行。
- 所有字段支持明确的局部撤销，all 表示最近一次完整修改。局部撤销若会构成非法模型/服装组合则整体拒绝；whole undo 可以恢复此前合法整套外观。撤销不覆盖无关的新设置。
- 分开执行字段与控件字段：`EXECUTABLE_FIELDS` 为全部字段，`CONTROL_FIELDS` 仍只含四项对话属性。后端 settings 不开放独立外观编辑器，与已确认的面板设计一致。

比较执行版本为 `tutor-comparison-execution-v5`。参数/文字/音频边界不变：语音参数已保存，`audio_available=false`，未接入 TTS。

## 2. Unity 外观与历史

现有 TutorComparisonClient.Project 在结果隐藏时只投影 baseline，开放后才投影选中分支。外观 ApplyAppearance 继续只读取该投影，不直接访问隐藏分支。

这意味着 E 提前完成时场景仍保持共同外观；回答 A 后若 S 还在澄清也不提前切换。统一开放后，切换 E/A/N/S 才分别应用其已保存外观。后续修复独立更新当前结果，first_reveal 固定保存。

新增 TutorHistoryPresentation 根据 before/after 中真正变化的字段生成英文记录。外观结果不再被错误显示为 REPLY LENGTH；颜色、服装、配饰、比例和角色都显示前后值，并区分 Applied / Partly undone / Undone / Restored。四项对话属性也使用同一格式。

History 按最新记录在前排列；更新时定位顶部，不再像 Conversation 一样滚到底部。内容未变化的轮询不会重设用户滚动位置。保留三页结构、现有玻璃背景与外观摘要，没有 Appearance 主标签。

两个客户端新增 CanUndoSetting(field)/UndoSetting(field)，受隐藏、忙碌、暂停和可撤销记录约束。现有 Reply length 按钮通过该公共方法执行，外观局部撤销已通过客户端方法及 HTTP 验证；**面板上的按字段撤销选择仍在第六步接线**，不把开发入口当成参与者已具备的按钮。

## 3. 可复现的本地验收

后端完整回归：**309 项通过，其中新增 10 项**。

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python -m unittest discover -s Backend/tests -q
```

新增覆盖定向服装/配饰、角色替换及整体撤销、非法部分撤销、保留约束、局部恢复、非法临时外观、不新增外观控件接口、混合请求取消，以及四分支展示/修复隔离。此前各阶段测试继续通过。

Unity 专用测试服务：

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python Backend/tests/unity_appearance_comparison_fixture_server.py
```

仅监听 127.0.0.1:8770，模型标识 unity-appearance-comparison-fixture。打开已有 TutorComparisonDesktop 场景，在未连接的 Play mode 执行菜单 `AIAA4435/Tutor/Comparison/Run Appearance Checks (Play mode)`。

检查使用真实场景资源，并读取 AppearanceAvatar 的 ObservedAvatar/Outfit/Color/Accessory/Scale，而非只断言服务器参数。流程包括隐藏期逐分支切换、A 完成但 S 仍待回答、统一开放后的不同外观、E 颜色/比例修复、颜色局部撤销、Nailong 替换及整套恢复、对话设置保持与首次快照不变。测试使用固定英文请求，不能代替真实模型对任意自然语言的理解验证。

结果与截图保存在 `StudyData/macos/tutor-appearance-comparison/`：checks.txt、hidden/revealed/final.json、nailong-history.png、restored-history.png。首次外观验收通过 69 项，原 Reply length 比较回归通过 93 项；随后修正历史滚动定位并追加一项检查，最终外观验收 **70 项全部通过**，截图已再次目视核对。最后这一滚动修正后未重跑 93 项旧套件；Conversation 的默认滚动逻辑保持原样，History 的新行为由追加检查覆盖。

最终 Unity 编译成功，Console error 为 0。验收结束后退出 Play mode，并关闭 8770 外观与 8768 原比较测试服务，没有保存运行时场景改动。

未运行头显，也未调用付费模型。正式十二道外观任务仍保持 Liang 身份；Nailong 切换只是已有能力的工程回归，不扩大正式任务库。

关键文件：[后端能力](../../Backend/tutor_capabilities.py)、[后端外观测试](../../Backend/tests/test_tutor_appearance.py)、[固定测试服务](../../Backend/tests/unity_appearance_comparison_fixture_server.py)、[Unity 统一历史](../../Assets/Project/Scripts/Tutor/TutorHistoryPresentation.cs)、[Unity 外观验收](../../Assets/Project/Scripts/Tutor/TutorAppearanceComparisonChecks.cs)。
