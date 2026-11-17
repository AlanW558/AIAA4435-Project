# Mac 本地开发入口

> 本文记录 2026-11-05 外观系统恢复阶段；`editor` / `build-pico` 仍打开/构建旧外观场景。当前 Tutor、语音与研究功能已实现，最新入口和跨电脑启动步骤见[根 README](../../README.md)及[Tutor 导航](../../Docs/TutorPersonalization/README.md)。不要把下文“尚未接入”当作当前工程状态。

本地工程基于 appearance 分支提交 `2631dded81fd02e59f45a131fe77dcea698a5670`，后续分支为 `codex/tutor-personalization`。原始 `main` 和 CloudConversationRoom 场景保留。

## 环境

- Unity：2022.3.62f3c1，默认 `/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity`。
- 已有 Android Build Support、SDK、NDK、OpenJDK，以及工程相对路径下的 PICO SDK 3.4.0 / Unity MCP 10.3.0。
- Python：`Tools/AppearanceExperiment/.runtime/macos` 虚拟环境，使用 Python 3.12.14；后端只依赖标准库。
- `.runtime`、`StudyData`、`.env` 均被 Git 忽略。Python 环境依赖创建它的解释器；若 Codex runtime 路径移除，可设置 `APPEARANCE_PYTHON` 指向独立 Python 3.10+，或重新建立虚拟环境。

所有命令在工程根目录运行：

```bash
cd '/Users/alanwong/Desktop/IAI/Unity/AIAA4435 Project'
bash Tools/AppearanceExperiment/macos.sh setup
bash Tools/AppearanceExperiment/macos.sh check
```

`check` 运行后端、设备工具、研究导出测试和源码审计。HTTP 测试需要本机回环端口权限，不调用真实模型。

## 后端

不使用密钥的开发模式（终端保持开启，Ctrl+C 停止）：

```bash
bash Tools/AppearanceExperiment/macos.sh mock
```

mock 是有限规则测试替身，不是 DeepSeek，不用于用户研究，也不保证理解任意自然语言。

真实模式：在本机编辑根目录 `.env`，填入课程密钥与课程指定的模型名称；不要将文件提交或复制到聊天。`.env.example` 只含空值模板。根目录 `.env` 存在时优先使用它，也可以用 `APPEARANCE_ENV_FILE` 指定其他私有文件。

```bash
bash Tools/AppearanceExperiment/macos.sh live
```

先停止同端口的 mock 服务再启动 live。用 `/health` 的 `mode` 确认实际模式。默认监听 `127.0.0.1:8765`，可设置 `APPEARANCE_PORT`。没有密钥或有效模型名称时，live 不会自动降级为 mock。

## Unity 演示

先关闭该工程已有 Editor，确保没有未保存编辑，再从另一终端启动：

```bash
bash Tools/AppearanceExperiment/macos.sh editor
```

打开已有 `AppearanceDesktopDemo` 房间场景，然后手动点击 Play。启动环境默认使用 S、debug、`avatar-demo-v1`（双角色），不是正式研究配置。新环境变量只有通过此入口启动的 Editor 才会收到；从 Hub 打开的旧进程不会自动更新。

默认连接本机 8765 后端。若使用远程后端，设置 `APPEARANCE_BACKEND_URL`。使用 `APPEARANCE_CAPABILITY_PROFILE=study-v1` 可检查旧实验角色。

在关闭 Editor 后运行导入和组件验证：

```bash
bash Tools/AppearanceExperiment/macos.sh verify-unity
```

该命令检查 Unity 编译、双模型、字体、着色器加载及角色状态应用，并运行已有运行时逻辑检查。报告位于 `StudyData/macos/` 和 `Builds/Pico/runtime-checks.json`；它不等于实际佩戴、视觉质量或真实 API 验收。

## PICO

```bash
bash Tools/AppearanceExperiment/macos.sh build-pico
```

使用已有构建脚本及 Mac Unity 路径，输出 `Builds/Pico/AppearanceVR.apk`。构建流程会重新生成 AppearanceVR 场景；有自定义场景修改时先保存到独立场景。脚本恢复其记录的临时项目设置。

设备连接仍需实际 PICO、设备授权、匹配构建的 debug 会话配置及 ADB reverse。Mac 的 ADB 位于 Editor 同级的 `PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb`。不要直接照搬旧 Windows/WSL 的中继命令或旧设备序列号。头显的 localhost 不是 Mac；使用本机后端时应配置对应端口的 `adb reverse`。

## 原有与新增场景

- CloudConversationRoom：原房间和四项演示设置面板。
- AppearanceVR：外观交互 XR 面板和角色。
- AppearanceDesktopDemo：固定相机桌面房间演示。
- AppearanceExperiment：旧独立实验场景。

四项导师设置、普通导师对话、STT/TTS 尚未在本轮新增。当前工作用于恢复已有外观系统并建立 Mac 开发起点。

## 2026-11-05 本机验证结果

- 138 个 LFS 工作文件均与提交的 SHA-256 一致，git lfs fsck 通过。
- 后端 50 项、设备工具 54 项、研究导出 11 项测试通过；源码审计 10 项通过。
- Unity 2022.3.62f3c1 批处理成功退出，23 项运行时检查通过；双角色、字体、材质加载和状态应用通过。
- 本机 live 后端使用仓库原配置 deepseek-v4-flash：一次真实 Selective 请求完成绿色西装修改、保留其他属性和单字段撤销。记录在 StudyData/macos/live-backend-check.json。
- 本轮未构建新的 APK，未进行头显佩戴或桌面视觉验收。临时验证服务已停止；使用时按上面的步骤启动。
