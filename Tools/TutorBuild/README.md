# Tutor USB 测试 APK

当前配置为 Unity 2022.3.62f3c1、PICO SDK 3.4、Vulkan、ARM64／IL2CPP、minSdk 29、targetSdk 34。

本机 SDK 的 `PXR_ProjectValidationRequired.cs` 明确禁止 Unity 2022＋Vulkan 使用 Development Build。因此这里使用**非 Development 的 USB 工程测试包**，显式允许 HTTP。不能把构建的非 Development 标志理解为已通过正式发布／正式采集验收。

## 构建

退出 Play 并保存场景。批处理前关闭普通 Unity 编辑器，再在项目根目录执行：

```sh
python3 Tools/TutorBuild/build_usb.py
```

需要 Python 3.10+。可用 `--out Builds/Tutor/NEW_DIRECTORY` 指定新输出目录，`--unity /absolute/path/to/Unity` 指定同版本编辑器。旧输出和日志不会被覆盖。残留但未被进程持有的 UnityLockfile 不会阻止构建；工具不会删除锁文件。

编辑器也提供 `AIAA4435 > Tutor > Device > Configure Study USB Build` 和 `Build Both USB Test APKs`。当前平台必须是 Android，场景有未保存内容或正在 Play 时会停止操作。构建不调用 Create Scenes，也不重新生成房间、模型或面板。

| APK | 唯一场景 | 包名 | 用途 |
| --- | --- | --- | --- |
| `TutorStudyUSB.apk` | `TutorComparisonVR` | `com.iai.aiaa4435.project` | 32 属性任务＋Selective 自然模拟，engineering 保存链路 |
| `TutorFreeUSB.apk` | `TutorFreeTestVR` | `com.iai.aiaa4435.tutor.free` | 自由切换比较／Selective 模式，不作为正式研究记录 |

两者可同时安装，存储独立。构建结束后项目保留**研究版**设置及新版研究场景入口。两个包都使用版本 `0.4.0`／versionCode `40`，首次升级需确认设备已有应用的签名／版本；安装工具没有卸载或降级后备动作。

每包产生 `*-build.json` 和 `*-inspection.json`，记录场景、配置、大小、时间、SHA-256、构建警告与实际 APK 检查。Unity 编辑器日志在输出目录旁的 `*-editor.log`。APK、日志、构建报告位于忽略的 `Builds/`，不进入 Git。

批处理默认将 Bee 并行度设为 2（可通过 `BEE_BUILD_THREADS` 覆盖）；若原有 IL2CPP 参数没有 `--jobs`，本次构建临时加 `--jobs=2` 并在结束后恢复。此设置降低本机构建峰值负担，不改变 APK 中的运行线程设置。构建需要额外磁盘空间；空间不足时应先检查可再生缓存，保留源码、资源、研究数据和已有发布物。

## 实际 APK 检查

构建脚本自动调用 `inspect_apk.py`；单独检查已有包也可以：

```sh
python3 Tools/TutorBuild/inspect_apk.py \
  --apk Builds/Tutor/NEW_DIRECTORY/TutorStudyUSB.apk \
  --package com.iai.aiaa4435.project \
  --output StudyData/device-usb/NEW_INSPECTION.json
```

检查 merged manifest 的包名、版本、SDK、ARM64、录音／联网权限、明文 HTTP、非 Development、Launcher／PICO 元数据，以及 IL2CPP 文件、ZIP 完整性、APK 签名和禁止的私有文件名。签名检查直接使用 Unity 的 OpenJDK，不依赖系统 Java。默认工具链路径为 Unity Editor 同级 `PlaybackEngines/AndroidPlayer`，单独检查可通过 `--android-player` 覆盖。

## USB 联网与数据

两个场景保持 `http://127.0.0.1:8765`，不自动连接。头显接入后通过 ADB reverse 访问电脑后端。密钥只由电脑后端读取，场景和构建器不读取密钥。

启动隔离的头显工程后端：

```sh
bash Tools/TutorDevice/start_usb_backend.sh
```

默认使用本机 `.env` 和已有 Python 环境，监听 `127.0.0.1:8765`，数据存放 `StudyData/device-usb/backend/`。此目录跨后端重启保持不变，便于恢复同一会话；不同工程测试与原有人工测试数据分开。端口已有服务时先核对其用途，不自动结束现有服务。启动服务本身不调用云模型；参与者交互／语音请求才消耗 API 额度。

设备识别、安装、取回日志和联合导出见 [TutorDevice 操作说明](../TutorDevice/README.md)。无线测试需要另外配置可达 endpoint、后端监听和相应传输设置；不能把 USB reverse 的成功等同于无线可用。

## 自动检查

```sh
python3 -m unittest discover -s Tools/TutorBuild/tests -q
python3 -m unittest discover -s Tools/TutorDevice/tests -q
```

这些检查和 APK 静态检查均不替代头显安装、录音／播放、XR 操作、实际联网、文件取回与性能验收。
