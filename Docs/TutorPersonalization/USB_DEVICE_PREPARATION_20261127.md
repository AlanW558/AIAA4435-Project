# 头显接入前准备验收

日期：2026-11-27。**新版构建入口、USB 后端配置、设备数据工具及两套测试 APK 已完成；随后已连接 PICO 4 Ultra，并成功安装自由测试版与研究版。** 本轮没有启动头显应用；头显运行及数据取回仍待验收。研究模式保持 `engineering`，本轮没有新增云端模型／语音调用。

## 交付的 APK

本机目录：`Builds/Tutor/usb-20261127-03/`（Git 忽略）。

| 文件 | 场景 | 包名 | 实际 APK 大小 | 结果 |
| --- | --- | --- | --- | --- |
| `TutorStudyUSB.apk` | TutorComparisonVR | com.iai.aiaa4435.project | 130.38 MiB | 构建成功，15 项 APK 检查通过 |
| `TutorFreeUSB.apk` | TutorFreeTestVR | com.iai.aiaa4435.tutor.free | 130.37 MiB | 构建成功，15 项 APK 检查通过 |

版本均为 `0.4.0`／versionCode `40`；ARM64、IL2CPP、Vulkan；minSdk 29／targetSdk 34。独立包名使两版能够并存，研究包保留原项目标识。两版均已通过 `adb install -r` 安装；研究包从设备原有 `0.1`／versionCode `1` 升级成功，没有卸载或清空应用数据。

检查直接读取实际 APK：包名／版本、SDK、ABI、录音与联网权限、显式 HTTP、非 Development、PICO 元数据、Launcher、IL2CPP 文件、ZIP 完整性、禁止的私有文件名及 APK 签名。两包 SHA-256 在各自 `*-inspection.json` 中；与 Unity 构建报告一致。对两份 APK 解压流中的已配置密钥作 UTF-8／UTF-16LE 精确匹配，均没有发现匹配；该扫描不声称能检测任意混淆或编码形式。

`*-build.json` 的 `bytes` 是 Unity BuildReport 总大小，可能包括额外构建产物；实际 APK 字节数以 `*-inspection.json` 为准。

## 配置与工具

- 新增 `Assets/Editor/TutorDeviceBuild.cs`：使用已有 VR 场景，检查模式、endpoint 与研究资源，不重新生成场景。批处理使用 `Tools/TutorBuild/build_usb.py`，构建完成后保留研究版包名和默认构建场景。
- 当前 PICO SDK 明确禁止 Unity 2022＋Vulkan 启用 Development Build；同时当前 Linear／MSAA4 设置也不适合直接切换 OpenGLES3。因此保留 Vulkan，构建非 Development 的 USB 工程包，显式允许 HTTP。
- 新增 `TutorUsbAndroidManifest.cs`：仅对两套匹配场景／包名的 USB 构建写入 Android `usesCleartextTraffic=true`。已通过最终合并清单验证。
- 场景 endpoint 为 `http://127.0.0.1:8765`；接入后通过 adb reverse 访问电脑后端。
- `Tools/TutorDevice/start_usb_backend.sh` 已在本机启动并通过 `/health`、`/speech/status` 检查。后端读取原有私有配置，数据隔离到 `StudyData/device-usb/backend/`；服务启动与健康检查没有调用付费模型。
- 设备 Python 工具包含 `status`、只读 `info`、`connect`、`install`、`pull-journal`、`export`。安装只使用 `adb install -r`，没有自动卸载、降级或清数据后备操作。
- 取回时要求研究者明确停止应用或确认已经停止；两次保留完整 journal 副本并比较文件集合、大小和 SHA-256。缺目录、权限不足、空日志、临时文件或副本变化均明确失败，不生成假的完整记录。
- 联合导出复用现有数据契约和回执核对，保留 `complete / partial / unreconciled`，不重放模型或替参与者提交反馈。

工具测试：设备工具 23 项、APK 检查工具 10 项通过。设备测试使用模拟 ADB；导出测试另使用临时真实 SQLite／journal。实际 ADB 枚举成功，结果为空，明确 `ready=false`。编辑器已恢复到 TutorComparisonDesktop，退出 Play，场景无未保存修改；临时 IL2CPP 参数已恢复。

## 已复核的构建警告

自由版首次完整编译有 121 条警告，其中 109 条 C# 警告；研究版复用编译结果后剩 12 条非 C# 警告。两版构建错误均为 0。不能把成功构建描述成零警告。

- 空 PICO Platform App ID：项目没有调用平台初始化／权益服务，启动权益检查关闭；SDK 只发警告并跳过平台 ID 写入。当前本地 XR 构建不因此中止，设备启动仍需测试。
- SDK Resources 的基础 `leftHand/rightHand` prefab 存在旧脚本引用；不是本项目场景缺失组件。实际在 Unity 打开两套 VR 场景并遍历组件：缺失组件均为 0，依赖中没有这些 ControllerWithHand／HandPose 资源。
- SDK Wireframe／HPE 手部 shader 警告，以及不支持 Android 的 Windows 插件导入警告已保留在构建报告中；未修改第三方 SDK。
- **五个 SDK 原生库有 16 KB 页对齐警告。** 连接后先运行 `info` 获取 Android SDK、ABI 与 `getconf PAGE_SIZE`。SDK＜29、无 ARM64、16 KB 页或未知关键字段不会被工具标为基础条件满足。遇到 16 KB 设备需要重新评估 SDK／原生库并重打包；APK 静态检查通过不等于适用于所有 Android 设备。

## 构建过程中的处理

首次批处理发现启动时没有可恢复的活动场景，已修正空场景恢复逻辑。随后一次构建因磁盘满而停止。只清理了可再生的项目 Bee／Burst 缓存和 Unity 包下载缓存，保留源码、资源、已安装 PackageCache、SDK、研究数据和原有 APK。编译默认并行度降为 2，随后两包构建成功。当前空间仍较紧张，后续大规模重打包前需再次检查可用空间。

每次使用新输出目录；失败日志和证据保留。成功产物在 `usb-20261127-03/`，不要误用前两次目录。

## 接入后的顺序

### 本次安装结果

- 设备：PICO 4 Ultra（型号属性 A9210），Android 14／SDK 34，支持 ARM64，`PAGE_SIZE=4096`；满足本次 APK 的静态基础条件。
- `AIAA4435 Tutor Free` 与 `AIAA4435 Tutor Study` 均已安装，并通过设备端包信息核实版本为 `0.4.0`／`40`。原有 `com.iai.aiaa4435.appearance` 外观实验应用仍保留。
- 已确认 `adb reverse tcp:8765 tcp:8765`；电脑后端 `/health` 正常、`/speech/status` 显示已配置且音频可用。此结果不代替应用实际联网验收。
- 当前 USB 方案仍需电脑运行后端并保持 USB 连接。模型密钥与 Python 后端保留在电脑；APK 已包含对应 VR 场景、资源、交互实现及任务／问卷配置。USB 重连后需重新检查 `connect`。
- 安装前后后端数据库的 participants、runs、receipts、events 均为 0；本次未启动应用、未创建实验运行、未进行付费模型调用。
- 本机安装证据：`StudyData/device-usb/deployments/20261127-01/`，包含 APK 校验值、设备信息、安装结果、版本核对及连接检查。该目录不进入 Git。

### 后续设备运行验收

1. 开启 PICO 开发者模式／USB 调试，通过数据线连接并接受电脑授权。
2. `status` 查序列号，`info` 核对设备兼容性，再 `connect` 建立 USB reverse。
3. 安装明确的测试 APK。先验证自由测试的界面、射线、拖动、录音、转写、播放和模式切换，再验证研究版任务、问卷、暂停／恢复。
4. 保存并停止一次工程会话，实际取出头显 journal，与本次后端数据库导出对账。只有完成这一步才算设备端保存／取回通过。

具体命令见 [构建与后端说明](../../Tools/TutorBuild/README.md)及[设备与导出说明](../../Tools/TutorDevice/README.md)。真实语音、头显渲染／交互、联网、恢复、文件取回及持续性能仍是接入后的验收项目。

本地证据：`StudyData/validation/tutor-usb-preparation-20261127/summary.json`、`scene-warning-audit.json`、`apk-credential-scan.json`、`backend-readiness.json`、工具测试日志、源码指纹和缓存处理记录；最终 APK 与完整构建报告在 `Builds/Tutor/usb-20261127-03/`。
