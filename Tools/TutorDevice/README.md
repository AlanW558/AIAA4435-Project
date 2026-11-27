# Tutor 头显 USB 与数据取回

这组 Python 命令用于研究者的本机操作。它不读取 API key，不调用云端模型，不卸载应用、不清空应用数据、不删除头显日志。APK 构建和后端启动见 [Tutor USB 构建说明](../TutorBuild/README.md)。同目录的 `start_usb_backend.sh` 单独启动使用私有配置的真实后端，将本次头显工程数据固定在 `StudyData/device-usb/backend/`。

默认研究包名为 `com.iai.aiaa4435.project`。自由测试包可使用 `com.iai.aiaa4435.tutor.free`；自由测试场景没有正式研究 journal 时，取回命令会明确失败，而不会生成假的空研究导出。

需要 Python 3.10+。ADB 默认查找本机 Unity 路径：

`/Applications/Unity/Hub/Editor/2022.3.62f3c1/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb`

其他机器可以通过命令最前面的 `--adb /path/to/adb` 或环境变量 `TUTOR_ADB` 指定。所有命令在仓库根目录执行。`--serial` 是全局选项，必须放在子命令之前。

## 1. 识别和连接

```sh
python3 Tools/TutorDevice/tutor_device.py status
python3 Tools/TutorDevice/tutor_device.py --serial DEVICE_SERIAL info
python3 Tools/TutorDevice/tutor_device.py --serial DEVICE_SERIAL connect
```

把 `DEVICE_SERIAL` 替换为 status 显示的实际序列号。无设备时 status 明确返回 `ready: false`；未授权设备需要先在头显内接受 USB 调试提示。即便只连接一个设备，后续命令也要求显式序列号。status 只做清单查询，不安装或启动应用。

安装前执行 info：只读查询设备型号、Android 版本／SDK、ABI 列表和 `getconf PAGE_SIZE`，读取失败的字段明确为 `unknown`。当前 APK 要求 SDK ≥29、`arm64-v8a`；本次构建发现 PICO SDK 原生库的 16 KB 页对齐警告，所以页大小为 16384 时不标为可继续，应先升级 SDK／原生库并重新打包。SDK 太低、缺 ARM64、字段未知或其它页大小同样不标为就绪。SDK ≥29、ARM64、4096 页仅满足静态基础条件，不能据此认定头显运行通过。info 不会自动安装；研究者需查看其 compatibility 结果。

connect 确认 `adb reverse tcp:8765 tcp:8765`。已经正确映射时不重复设置；同一设备端口映射到别处时拒绝覆盖。默认场景 endpoint 可保持 `http://127.0.0.1:8765`，电脑后端需监听相同端口。USB reverse 成功不等于应用能联网，还须在头显内实际连接后端。USB 重连后可再次执行 connect。

## 2. 安装明确的 APK

```sh
python3 Tools/TutorDevice/tutor_device.py --serial DEVICE_SERIAL install --apk /absolute/path/to/TutorStudy.apk
```

仅调用 `adb install -r`，记录实际安装包 SHA-256；没有自动卸载、降级或清空数据的后备操作。签名冲突／安装失败会停止并保留旧应用及数据。安装成功后由研究者在头显中启动应用；命令不自动开始实验。

## 3. 取回研究 journal

先在实验中保存当前反馈，并暂停或结束交互，等待同步完成。需要保留未完成运行时也可以取回，之后导出会保留 pending／草稿状态；取回命令不会替参与者提交问卷。

```sh
python3 Tools/TutorDevice/tutor_device.py --serial DEVICE_SERIAL pull-journal \
  --stop-app \
  --out StudyData/device-usb/copies/NEW_COPY_DIRECTORY
```

`--stop-app` 明确授权停止研究包进程，便于复制稳定文件；它不会清除数据。若研究者已经停止应用，则使用 `--app-already-stopped`，命令不会再停止进程。两者必须且只能选择一项。仅在 VR 内暂停但应用进程仍运行，不应声明 `--app-already-stopped`。

默认读取候选路径：

`/sdcard/Android/data/com.iai.aiaa4435.project/files/StudyData/journal`

**这是 Android 常见的 persistentDataPath 映射，实际路径和 ADB 可访问性必须连机确认。** 路径缺失／拒绝访问时命令失败，不假定 `run-as`、root 或文件浏览器权限可用。确认设备上的实际路径后，可用 `--remote-journal /actual/path/StudyData/journal` 覆盖；不同包可用 `--package <package-id>`。

命令把整个目录拉取两次，保留为 `journal/` 和 `verification-journal/`，比较文件集合、大小和 SHA-256。新目录中的 `copy_manifest.json` 保存结果：

- `verified_local_copies`：两次观察到的副本一致；还需后端对账，不能直接算作完整实验数据。
- `incomplete`：拉取失败、两次不同、出现未完成写入、空 journal 或目录结构异常。保留已有副本与错误记录，先检查／恢复应用，再用新的目录重试。

两次拉取一致不是原子文件系统快照。工具不删除任何远端文件，不重用／覆盖旧本地输出目录，也不尝试自动修复 `.tmp` 或损坏记录。对账会继续核验 journal 内部校验和、请求身份与回执。

## 4. 联合导出问卷、对话和本地副本

此步骤不需要连接头显，不发起 API 请求。使用本次头显测试实际连接的电脑后端数据库，不能混用其它本机测试目录。

```sh
python3 Tools/TutorDevice/tutor_device.py export \
  --data-dir StudyData/device-usb/backend/study \
  --run STUDY_RUN_ID \
  --snapshot StudyData/device-usb/copies/NEW_COPY_DIRECTORY \
  --out StudyData/device-usb/exports/NEW_EXPORT_DIRECTORY
```

`--run` 是应用记录的 32 位 `study_run_id`，不是参与者编号。`--snapshot` 指向第 3 步的整个复制目录；`--data-dir` 必须已有 `study.sqlite3`。示例 backend 目录仅是建议的隔离位置，启动后端时要使用对应日志目录。

工具先验证副本没有在取回后改变，再调用现有 `Backend/export_study_data.py` 的版本化导出／回执核对功能。输出包括问卷 CSV、偏好 CSV、对话与事件 JSONL、未完成记录、`local_reconciliation.json`、`export_manifest.json`。

请以 `export_status` 判断结果：

- `complete`：后端运行正常结束且提供的本地副本已核对。
- `partial`：提供副本已核对，但运行没有正常完成；已提交内容与未完成内容仍分别保留。
- `unreconciled`：仍有本地待同步／冲突／未反映草稿等情况；保留证据后检查，不把它解释成采集完成。

## 本机验证与边界

```sh
python3 -m unittest discover -s Tools/TutorDevice/tests -q
```

23 项自动测试使用模拟 ADB subprocess，覆盖无设备／未授权／显式选择、多设备隔离、4 KB／16 KB 页及 SDK／ABI 静态检查、端口冲突、保留数据的安装、取回失败、双副本变化、不覆盖旧输出和导出路径校验。另使用临时真实 SQLite 与 journal，验证现有导出器输出 `partial` 和 `provided_copy_reconciled`。所有测试不连接设备、不调用 API。

2026-11-27：工具单元测试通过；已在 PICO 4 Ultra（Android 14、ARM64、4 KB 页）实际安装自由测试版与研究版 `0.4.0`／`40`，确认 USB reverse 与电脑后端健康状态。安装没有启动应用、卸载旧包或清空数据；研究包原有 `0.1` 已升级，旧外观实验包仍保留。应用联网、设备端实际 journal 路径／存储访问与取回尚待运行验收。安装证据在 `StudyData/device-usb/deployments/20261127-01/`。工程测试数据与取回文件应保存在被 Git 忽略的 `StudyData/` 中。
