# PICO 研究者控制台

此工具只控制专用包 `com.iai.aiaa4435.appearance`，研究者页面不可向参与者展示。它使用 Python 3 标准库；无需安装 Python 依赖。以下命令在 `AIAA4435-Project` 根目录的 WSL shell 执行。先从设备列表取得真实序列号，再替换示例中的 `YOUR_SERIAL`。工具不会自动选择设备。

```bash
python3 Tools/AppearanceExperiment/pico.py devices
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL install --apk /absolute/path/to/Appearance.apk
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL configure --session-file /absolute/path/to/session.json
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL launch
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL status
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL serve --port 8766
```

浏览器打开 [本机研究者控制台](http://127.0.0.1:8766)。它显示从设备读取的会话、条件、进度、当前实际外形、运行消息、暂停、结束和故障状态。后端状态来自运行时消息，不另行猜测健康情况。设备不可用、文件缺失或状态无效时明确报错，页面不会生成示例结果。`Ctrl+C` 关闭服务。

## ADB 与连接

ADB 查找顺序为全局参数 `--adb /path/to/adb`、`APPEARANCE_ADB` 环境变量、项目 `Builds/AndroidTools/platform-tools/adb.exe`（存在时）、PATH 中的 `adb`。参数写在子命令前，例如：

```bash
python3 Tools/AppearanceExperiment/pico.py --adb /path/to/adb.exe --serial YOUR_SERIAL status
```

WSL 使用 Windows `adb.exe` 时，本地安装、推送与拉取路径均通过 `wslpath -w` 转换；该程序不可用时明确失败。所有设备操作使用 `-s YOUR_SERIAL`，使用参数列表、超时与退出码检查。工具不会卸载、清除应用数据、读取凭证或修改其他包。安装使用 `adb install -r`，完成后创建专用包的文件目录，并输出本地 APK SHA-256。安装错误不会回显潜在私有的 ADB 输出。

默认后端为设备端 `http://127.0.0.1:8765`。此工具不自动建立 USB reverse、SSH tunnel 或启动后端；部署流程需先建立这些连接。可通过 `configure --backend http://host:port` 指定现有后端，不允许 URL 凭证。不要在命令行传入密钥。

## 会话配置与身份隔离

输入必须是问卷工具产生的 `appearance-session-v1` 会话元数据文件；问卷回答文档不接受。控制器复用 `launch_session.prepare()` 与 `session_identity` 的参与者、阶段、会话及冻结日程校验。配置仅包含身份、阶段、日程选择标记、后端地址和可选构建校验值；输入里的问卷回答、私有目标或旧配置字段不会复制。

- `debug`：编号为 `DEBUG…` 或 `ENGINEERING…`。
- `pilot`：仅 `PILOT01` / `PILOT02`。
- `formal`：仅冻结分配表中的 `P001`–`P020`，必须有完整 16 项日程。

`--condition E|A|N|S` 与 `--task AUTHORED_TASK_ID` 仅限 debug / pilot。其他情况下默认条件为 `S`，任务为空表示自由交互；正式阶段拒绝任何显式条件或任务覆盖，写入 `assigned: true`、空条件和空任务。可加入 `--build-sha256` 加上安装输出的 64 位 SHA-256，让运行时核对安装包。

配置在完整本地校验通过后，先停止专用应用，清除旧命令、回执和状态，再把新元数据推送到临时文件并通过设备端 `mv` 生效。之前的 `appearance-captures` 保留。配置不会自动启动应用；必须执行 `launch`，并确认 `status` 报告 `ready`，防止沿用上一位参与者的运行实例。启动命令明确指定 `com.unity3d.player.UnityPlayerActivity`，启动请求成功不等于初始化完成。

## 操作与回执

浏览器提供下一试次和问卷完成后的恢复；仅 debug 显示修改请求、当前澄清选项、回答、撤销、完成和坐下操作。debug 输入留空时运行时可提交首个预填任务。CLI 示例：

```bash
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command submit --text '把外套改成蓝色'
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command answer --value CURRENT_OPTION_ID --text '可选的补充回答'
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command undo --value jacket_color
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command finish
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command next
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL command resume
```

`submit`、`answer`、`undo`、`finish`、`sit` 在 CLI 和运行时都仅限 debug，pilot / formal 只能发送 `next` / `resume`。可撤销 `all`、`jacket_color`、`accessory` 或 `scale`。回答的 value 必须出现在当前设备问题的选项中。所有操作仍由运行时按忙碌、验证、试次结束与分轮暂停规则决定是否接受。

每个命令先重新读取设备状态，校验身份和阶段，然后写入随机 UUID 及研究会话 ID。CLI 可加 `--session-id`，必须与刚读取的状态一致；未指定时从该状态取得。浏览器始终把刚显示的会话 ID 一并提交，切换会话后旧页面命令会被拒绝。命令通过临时文件加 `mv` 写入 `appearance-command.json`，用户文本不会拼接到 shell。

默认等待最多约 8 秒读取同一 command_id 的回执；`--wait 0` 只写邮箱，`--wait` 范围 0–30 秒。ADB 自身也有超时。`acknowledgment: accepted` 只说明设备接受命令，`completion` 始终为 `not_confirmed`；后端调用、渲染核验与试次完成需继续查看状态和采集文件。`rejected` 会保留设备的拒绝原因。超时或连接中断意味着结果未知，先查状态，避免直接重发产生第二次操作。仅运行一个操作控制器，避免不同进程覆盖同一个邮箱。

CLI 退出码：`0` 为操作成功或命令已接受；`1` 为校验、ADB 或本地文件错误；命令被拒绝为 `2`；未获命令回执、启动中或状态文件尚不存在为 `3`。浏览器拒绝回执使用 HTTP 409，并明确显示拒绝原因。

## 采集与本机访问

```bash
python3 Tools/AppearanceExperiment/pico.py --serial YOUR_SERIAL collect --output StudyData/pico/unique-session-capture
```

输出必须位于项目 `StudyData/pico` 内，包括符号链接解析后的实际路径。工具拉取设备 `appearance-captures` 子目录，并在成功拉取后保存 `controller-status.json`。使用每会话独立输出目录避免合并证据。采集文件来自真实运行时；控制器不生成参与者数据，也不把数据标记为已通过研究验收。

服务仅绑定 `127.0.0.1`。浏览器修改请求只接受 POST JSON，要求精确匹配的本机 Host / Origin 及页面随机 token，拒绝跨站请求和缺失 Origin，不开放 CORS。页面通过安全的 `textContent` / DOM 节点显示设备文本，并使用 CSP。单进程内 ADB 调用串行，页面轮询不会并发叠加 ADB 操作。不要通过代理或公网暴露此研究者页面。

## 验证边界

```bash
python3 -m unittest discover -s Tools/AppearanceExperiment/tests -p 'test_pico.py' -v
```

测试替换所有 subprocess 调用，不运行真实 ADB。覆盖身份与阶段、正式覆盖拒绝、Windows 路径和参数、命令及选项校验、接受/拒绝/未回执的区分、跨会话防护及本机来源验证。真实 APK 安装、USB / tunnel、运行时回执、佩戴交互与页面视觉需由设备集成流程验收。
