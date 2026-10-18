# AIAA4435-Project

Interactive AI 课程项目：Pico 4 Ultra 上的云海会谈室原型。研究方向是对话中的选择性澄清与执行（Selective），目前先完成 VR 场景和交互框架。

## 外形实验开发入口

新增 Unity + DeepSeek 四策略外形实验、局部撤销、实验日志和22人研究材料。台式机运行与验证边界见 [外形实验说明](Docs/AppearanceExperiment/README.md)。这版增加独立桌面场景；下面保留原 Pico 会谈室说明。

## 原 Pico 会谈室状态

- 大型会谈室、高清浅木纹材质、深灰天花板、云海落地窗和暖色午后烘焙光照。
- 座椅靠近提示、入座/离座、淡入淡出过渡。
- 右前方半透明暖白弧形面板：仅入座后显示，距坐姿视点约 0.75 m。
- 四项演示设置：语速、回复长度、语气、声音；包含页面切换与滑块交互。
- 四项设置尚未连接真实 LLM、STT、TTS；导师角色模型尚待加入。
- 2026-10-16 已成功构建、安装到 Pico 4 Ultra。用户已确认当前所有交互功能没有问题。短时运行日志采样为 90 FPS，不代表完整持续负载测试。

## 开发环境

| 组件 | 版本 |
| --- | --- |
| Unity Editor | **2022.3.62f3c1**（中国版修订） |
| 渲染管线 | URP 14.0.12 |
| PICO Unity Integration SDK | 3.4.0，当前本地发布包目录后缀 20260226 |
| XR Interaction Toolkit | 3.0.8 |
| Input System | 1.14.0 |
| Unity MCP | 10.3.0，固定源码提交 `aa5fc638d623f56178d50329d9ad8c541a57fe66` |
| Android | ARM64 / IL2CPP / Vulkan / PICO Multiview；minSdk 29、targetSdk 34 |

通过 Unity Hub 安装相同 Editor 和 Android Build Support（含 SDK、NDK、OpenJDK）。不要直接用其他 Unity 版本升级主项目。

## 首次获取项目

先安装 Git 和 [Git LFS](https://git-lfs.com/)，再执行：

```sh
git lfs install
git clone https://github.com/AlanW558/AIAA4435-Project.git
cd AIAA4435-Project
git lfs pull
```

必须使用 Git LFS 下载真实资源。仅下载 GitHub 的 ZIP 或缺少 LFS 的克隆可能得到指针文件，导致贴图、天空或烘焙资源无法导入。

### 打开 Unity 前准备两个外部依赖

为了保持已验证的本地配置，`Packages/manifest.json` 仍采用原有相对路径。Unity 将 `file:` 路径相对于 `Packages` 目录解析。请按以下结构放置文件；项目文件夹名称可以不同：

```text
工作目录/
├── AIAA4435-Project/                    # 本仓库
│   ├── Assets/
│   ├── Packages/
│   └── ProjectSettings/
├── PICO Unity Integration SDK-3.4.0-20260226/
│   ├── package.json                    # 应显示版本 3.4.0
│   ├── Runtime/
│   └── ...
└── Tools/
    └── unity-mcp/
        └── MCPForUnity/
            ├── package.json
            └── ...
```

1. 从 [PICO 官方资源页](https://developer.picoxr.com/resources/?platform=unity) 获取 **PICO Unity Integration SDK 3.4.0**，解压至上图目录。避免多套一层文件夹，确认 `package.json` 就在该目录根部。当前 SDK 随包许可限制复制发布，因此仓库不包含其源码和二进制；获取和使用遵循官方许可。另见 [官方导入说明](https://developer.picoxr.com/document/unity/import-the-sdk/)。
2. 在本仓库根目录执行以下命令，准备固定版本的 Unity MCP（已有目录时先检查，不要覆盖正在使用的副本）：

```sh
git clone https://github.com/CoplayDev/unity-mcp.git ../Tools/unity-mcp
git -C ../Tools/unity-mcp checkout aa5fc638d623f56178d50329d9ad8c541a57fe66
```

MCP 是开发辅助工具；运行头显中的 APK 不需要连接 MCP 服务。当前项目清单包含它，因此首次打开仍需准备该包。

3. Unity Hub → Add project from disk，选择本仓库根目录，等待依赖解析和资源导入。
4. 打开 `Assets/Project/Scenes/CloudConversationRoom.unity`。
5. 保留仓库中的材质、纹理和烘焙文件；通常不需要重新生成房间或重新烘焙。

## 操作与构建

- 左摇杆移动，右摇杆分段转向。
- 靠近并看向用户座椅，A / X 入座，B / Y 离座。
- 入座后向右转头查看面板，扳机点击或按住拖动滑块。
- Editor 中可使用 Enter / Backspace 测试入座和离座。
- 切换到 Android 后，退出 Play 模式，使用菜单 **AIAA4435 > Build > Build Pico APK**。
- 输出 `Builds/Pico/AIAA4435Project.apk`；构建详情见 `Tools/PICO_BUILD_AND_RUN.txt`。
- APK 和设备日志属于本地构建产物，未提交至源码仓库。

## 协作约定

- 每人使用自己的本地克隆；开始工作前保存修改并获取最新版本。
- 在功能分支开发，通过 Pull Request 合并；主场景尽量由一人集成。
- 导师模型、语音和 LLM 模块可使用独立 Prefab 或测试场景开发。
- `Assets` 下的资源及 `.meta` 文件必须一起提交。移动资源优先在 Unity 中完成。
- 高清贴图与部分大型资源使用 Git LFS；不要将所有 `.asset` 文件一律当二进制，以便普通配置仍可比较。
- `Library`、`Temp`、`Logs`、`UserSettings`、`Builds` 和 `SetupBackups` 不进入版本控制。
- 不要提交 API Key、访问令牌或 Android 签名密钥；后续接入服务时另行管理凭据。

## 文件索引

- `Assets/Project/`：场景、运行时脚本、模型、材质、高清纹理和烘焙数据。
- `Assets/Editor/`：房间、座椅、面板配置工具及 Pico 构建入口。
- `Packages/`、`ProjectSettings/`：依赖和项目配置。
- `Captures/`：开发阶段场景截图，可能包含历史版本。
- `Tools/`：场景、光照、座椅、面板和部署说明。

木纹来源与 CC0 说明保留在 `Assets/Project/Textures/Room/PolyHaven/SOURCE.txt`。第三方组件遵循各自许可；本仓库未替这些组件授予新的许可。
