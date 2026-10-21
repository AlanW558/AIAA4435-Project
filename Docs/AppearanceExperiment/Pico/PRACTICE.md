# PICO 练习与线下目标卡

正式题目使用冻结材料。下面的练习独立于正式 16 题，用来熟悉说出外形意图、回答追问、撤销、完成和研究者暂停流程；练习成功不等于正式试次成功，debug / pilot 记录不属于正式参与者数据。

## 独立练习

先按 `CONTROLLER.md` 使用已有的合法 debug 或 pilot 会话元数据配置专用应用。保留原有记录，不把练习身份改写成正式参与者身份。练习时不要指定正式 `--task`；使用自由交互。研究者先确认头显连接、中文输入、实际外形与完成按钮正常，再让参与者自行操作。

外形能力域为六种既有颜色、帽子 / 眼镜 / 无配饰，以及 **0.85–1.15、步长 0.05** 的比例。每个自由会话最多共用 **2 次 repair / undo**：初始请求之后再提交修改请求计一次 repair，分字段撤销也占一次，不能把以下练习串在同一个会话内。每次练习结束都点击“完成”，等待全部三次渲染探针与核验结束、状态显示完成，再点击“继续修改”启动新自由会话。

1. **练习一：初始请求与完成（不使用 repair / undo）。** 在新自由会话中首次输入“外衣改成灰色，配饰不要，比例设成 0.85”。核对实际外套、配饰和大小；达到目标后点击“完成”，等待三探针结束，再点击“继续修改”进入下一练习。此组合独立于正式任务卡。
2. **练习二：一次修复、一次分字段撤销（刚好使用 2 次预算）。** 在新的自由会话中首次输入“外衣改成灰色，戴帽子，比例设成 0.85”。确认初始结果后，提交一次修改“把帽子换成眼镜，比例改成 0.90，外衣仍是灰色”（repair 1 次）。结果生效后仅撤销比例（undo 1 次），确认比例回到 0.85，眼镜与灰色外衣保留。不要再撤销配饰或继续提交修改；直接点击“完成”，等待三探针结束，再点击“继续修改”启动新会话。
3. **练习三：独立的意图表达与可能的追问。** 在新自由会话中首次输入“再精神一点”。系统可能追问，也可能直接尝试修改；不保证一定出现澄清。若出现追问，练习选项和补充回答，明确只改变自己想改的字段。若没有追问，如实记录，再另开独立练习，不伪造澄清结果；仍须先完成并等待三探针结束。此练习不要额外演示撤销，任何后续修改仍受同一最多 2 次预算约束。

每条操作后都等待实际设备结果，任何失败先排查，不以重复发送消耗剩余预算。研究者同时让参与者练习舒适站立、指向和输入；需要座位时按现场指引操作。

pilot 必须由参与者界面交互；控制器的脚本输入、回答、撤销、完成和坐下只在 debug 开放。若研究者需要自动诊断，另开 debug 会话，不把操作写入 pilot 或正式会话。分轮问卷、恢复和任务切换先在已有研究流程中单独核对；自由交互练习不声称验证了正式冻结日程。

可用的研究者 debug 诊断示例（将序列号替换为真实值）：

```bash
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command submit --text '外衣改成灰色，配饰不要，比例设成 0.85'
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL status
```

回执接受仅代表开始处理。检查实际 `observed` 和完成状态后再发送下一条命令。

## 从冻结材料生成真实 Avatar 目标卡

输入是现有 `Docs/AppearanceExperiment/Study/materials/tasks_private.json`，不修改该文件。输出默认位于项目 `StudyData/pico/materials`，完全在 APK 资源目录之外。Python 不调用 Unity、不访问设备、不向后端或模型发送目标信息。

第一步，在项目根目录生成本地 Editor job manifest：

```bash
python3 Tools/AppearanceExperiment/generate_pico_task_cards.py prepare
```

它为每题生成起始外形和所有允许的目标组合：16 张卡、20 种可接受目标，共 36 个渲染任务。多个 `allowed_values` 全部展示，保持字段来自该题初始外形。准备阶段只写渲染任务，不生成冒充已渲染的图，也不发布缺图卡片。

第二步，等当前真机调试和构建结束、同项目的其他 Editor 实例关闭后，由研究者运行 Editor 渲染。必须启用图形设备，不能加 `-nographics`。Linux / WSL 图形环境的精确入口：

```bash
"$HOME/Unity/Hub/Editor/2022.3.62f3c1/Editor/Unity" \
  -batchmode -quit \
  -projectPath "$PWD" \
  -executeMethod AppearanceTaskCards.RenderFromCommandLine \
  -appearanceTaskCardManifest "$PWD/StudyData/pico/materials/render-jobs.json" \
  -logFile "$PWD/StudyData/pico/materials/unity-render.log"
```

如实际 Editor 位于其他路径，只替换可执行文件路径；使用 Windows Editor 时，`-projectPath`、manifest 和日志路径均需传 Windows 绝对路径（WSL 可用 `wslpath -w` 转换），其余参数和入口不变。不要对正用于真机调试的同一项目启动第二个批处理实例。无图形桌面时需先配置可用的图形显示会话，由集成流程运行，本工具不自动安装依赖或启动显示服务。

渲染器只在临时 Preview Scene 内调用共享 `AppearanceAvatar.Create()` / `Apply()`，不保存或改写项目场景、构建设置或目标材料。相机固定在 `(0, 1.25, -5)`，朝向 `(0, 1.25, 0)`，固定正交尺寸 `1.45`、输出 `768 × 1024`，对每种比例不重新取景。Avatar 使用同一中性姿态和两盏固定白光；实际颜色、配饰和比例经共享 Avatar 观察值核对后才写 PNG 和回执。

项目的 URP 使用同步 `UniversalRenderPipeline.SingleCameraRequest`；内置管线使用 `Camera.Render()`。这些是实际 Editor 相机输出，属于任务材料，不是头显截图、参与者试次或行为证据。相关 Unity 2022.3 接口见 [Camera.scene](https://docs.unity3d.com/cn/2022.3/ScriptReference/Camera-scene.html) 和 [Camera.SubmitRenderRequest](https://docs.unity3d.com/ja/2022.3/ScriptReference/Camera.SubmitRenderRequest.html)。

第三步，核对渲染日志成功后发布可独立打印的中文卡片：

```bash
python3 Tools/AppearanceExperiment/generate_pico_task_cards.py publish
```

只有当源文件 / Avatar / renderer 哈希、job manifest、全部 PNG、图像尺寸与校验和，以及 Editor 回执里的观察状态一致时才发布。生成：

- `index.html`：研究者索引，显示任务 ID，用于对照冻结分配表，不能展示给参与者。
- `A_T1.html` 等 16 个独立 HTML：内嵌真实 PNG，可离线单张分享 / 打印。正文不显示条件、任务分类、编号或轮次；多个可接受目标并列显示。
- `source-hashes.json`：源文件、共享 Avatar、renderer、manifest、回执、PNG 和 HTML 的哈希来源记录，不是研究数据。
- `images/*.png` 与 `render-receipt.json`：实际相机输出和渲染核对记录。

重新 `prepare` 会清除旧渲染回执、已发布 HTML / 索引和哈希 sidecar，要求重新渲染后才能发布；PNG 可被后续真实渲染覆盖。源文件或 renderer 改变后应重新执行三个步骤；不要继续使用旧版 HTML。发布校验不替代视觉检查：研究者至少核对六种颜色、帽子 / 眼镜 / 无配饰，以及全部大小变化是否清楚、未裁切，打印时统一使用 100% 比例，关闭浏览器打印页眉页脚以免显示带任务 ID 的文件路径。每张卡中所有图像保持相同物理显示尺寸，不能分别拉伸或自动裁切。

正式试验中，研究者按冻结分配表只在线下出示当前单张卡；不要把索引、私有目标 JSON、render jobs、目标图或卡片文字粘贴到模型请求、公共屏幕或 APK 资源里。任务 ID 只用于研究者索引与来源核对，不要求参与者记忆或输入。完成后收起该卡再进入下一题。

## 已验证范围

```bash
python3 -m unittest discover -s Tools/AppearanceExperiment/tests -p 'test_generate_pico_task_cards.py' -v
```

测试使用临时 fixture 图像和模拟回执核对 Python 的完整性与拒绝行为，不会运行 Unity、ADB 或生成实际参与者记录。真实 Editor 编译 / 渲染、PNG 视觉检查、打印可读性及现场出示仍需集成验收。
