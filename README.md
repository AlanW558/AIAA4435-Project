# AIAA4435-Project

通过语音调整 VR tutor 的交流属性与外观，研究 Selective 的澄清与执行策略。当前包含 Unity 场景、DeepSeek 对话后端、Qwen STT/TTS、四策略比较、Selective 连续交流，以及任务、问卷和研究数据保存链路。

更新：2026-11-17。最新实现已完成本机编译、自动联调及部分人工语音/问卷操作验证；最新版本尚未完成 PICO 头显整体验收。研究入口当前创建 `engineering` 运行，不代表正式采集已开放。

## 从这里开始

| 用途 | Unity 菜单（AIAA4435 > Tutor） | 场景（Assets/Project/Scenes/） |
| --- | --- | --- |
| 自由测试，桌面 | Free Testing > Open Desktop | TutorFreeTestDesktop.unity |
| 自由测试，VR | Free Testing > Open VR | TutorFreeTestVR.unity |
| 研究流程，桌面 | Comparison > Open Desktop | TutorComparisonDesktop.unity |
| 研究流程，VR | Comparison > Open VR | TutorComparisonVR.unity |

自由测试可选择 **Four-strategy comparison** 或 **Selective conversation**。比较模式的普通输入、追问及手动控件作用于四策略；四策略按钮只切换查看，澄清回复仅交给提问分支。所有策略完成或明确停止后统一显示该轮结果。研究任务固定模式：四属性比较、自然模拟 Selective。详见[交互模式](Docs/TutorPersonalization/INTERACTION_MODES.md)。

- [项目与研究文档导航](Docs/README.md)：proposal、Formative、第一次外观实验与当前研究。
- [Tutor 当前实现与使用说明](Docs/TutorPersonalization/README.md)：任务、问卷版本、语音、日志、保存/导出、验证边界。
- [最终研究设计](Docs/TutorPersonalization/Study/FINAL_USER_STUDY_DESIGN_4_STRATEGIES.md)：32 道属性任务＋一段 Selective 自然模拟；5／26 题问卷、偏好及可选访谈。
- [数据保存契约](Docs/TutorPersonalization/Study/STUDY_DATA_PERSISTENCE_CONTRACT.md)与[保存/导出实现](Docs/TutorPersonalization/STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md)。

`TutorPersonalizationDesktop/VR` 是早期单会话开发场景；`AppearanceDesktopDemo/AppearanceVR/AppearanceExperiment` 属于第一次外观实验；`CloudConversationRoom` 是原始房间原型。保留它们用于复现，不作为当前完整研究入口。

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
4. 按下方场景表打开最新 Tutor 场景；`CloudConversationRoom` 仅为原始房间演示。
5. 保留仓库中的材质、纹理和烘焙文件；通常不需要重新生成房间或重新烘焙。


### 克隆后的依赖检查

在仓库根目录运行（需要 Python 3.10+）：

```sh
python3 - <<'CHECK'
import json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root / 'Packages/manifest.json').read_text())
for name, location in manifest['dependencies'].items():
    if location.startswith('file:'):
        package = (root / 'Packages' / location[5:] / 'package.json').resolve()
        assert package.is_file(), f'Missing {name}: {package}'
        data = json.loads(package.read_text())
        assert data['name'] == name, f'Wrong package at {package}'
        print(name, data['version'])
CHECK
git lfs fsck
```

PICO 应为 3.4.0，Unity MCP 应为 10.3.0；MCP 源码提交也应与上述固定提交一致。依赖与 LFS 资源核对后再打开 Unity。MCP 是开发依赖，不是语音后端。不要将 SDK、Python 环境或本机私有配置整体复制到仓库。

## 启动后端与桌面测试

后端使用 Python 3.10+ 标准库。以下命令在仓库根目录执行。无密钥的有限规则 mock 可检查接口，但不能验证任意自然语言或真实语音：

```sh
python3 Backend/server.py --mode mock --host 127.0.0.1 --port 8765 --log-dir StudyData/mock
```

真实模式：仅当 `.env` 不存在时复制 `.env.example` 为 `.env`，在本机填写 DeepSeek 与 Qwen 凭据、匹配的 endpoint 和模型。不要覆盖已有配置。当前对话模型配置为 `deepseek-v4-flash`；语音适配器模型为 `qwen-audio-3.0-asr-flash` / `qwen-audio-3.0-tts-plus`，实际可用性取决于所使用服务与凭据权限。

```sh
APPEARANCE_ENV_FILE="$PWD/.env" APPEARANCE_PYTHON=python3 \
  bash Tools/AppearanceExperiment/start_backend.sh --speech-mode qwen --timeout 45
```

先停止同端口旧服务。此脚本默认绑定 `127.0.0.1:8765`，日志/数据库写入 `StudyData/logs/`。脚本还兼容本机 `~/.config/aiaa4435/deepseek-teacher.key` 覆盖配置；若该文件存在，优先使用它，详情见脚本。模型密钥始终留在后端，不写入场景或 APK。

打开自由测试桌面场景，进入 Play → Connect。比较模式确认共同初始设置后，Record → Stop → 复核转写 → Send。Controls 可调四属性并 Play sample；History 查看修改。研究场景用独立纸色面板登记、阅读任务、填写和提交问卷；不要把自由测试记录当正式研究数据。

## VR 场景与构建边界

- 入座后 tutor 位于正前方；控制面板在右侧，任务/问卷面板在左前方。控制面板支持拖动，研究面板可收起为 Show panel 按钮。
- **当前提交的 Build Settings 仍启用旧 `CloudConversationRoom`。** 旧 `AIAA4435 > Build > Build Pico APK` 和 `macos.sh build-pico` 分别针对旧房间/外观场景，不会构建最新 Tutor 研究。
- 构建新版本前退出 Play，选择 Android，在 File > Build Settings 的 Scenes In Build 中加入并只启用目标 `TutorComparisonVR`（研究）或 `TutorFreeTestVR`（自由测试），再 Build。不要将桌面场景作为头显入口，也不要运行会重新生成旧场景的构建脚本。
- 保留已配置的 PICO XR、ARM64/IL2CPP 等项目设置，检查录音权限与网络可达性。头显上的 localhost 指头显本身：USB 开发可使用 `adb reverse tcp:8765 tcp:8765`；无线运行则使用头显可达的后端地址，并显式配置后端监听接口及 Unity endpoint。
- 本轮未生成新版 APK，尚需头显真实录音、播放、射线、拖动、长时流程和设备端恢复验收。早期房间的设备测试不作为新版功能验收。

## 数据与导出

后端：`<log-dir>/study/study.sqlite3`；Unity Editor：`StudyData/macos/study-journal/`；头显：`Application.persistentDataPath/StudyData/journal/`。环境变量可以覆盖本机路径。问卷口述只保留确认后的 STT 文本，不保存参与者录音；对话日志记录输入和模型输出。

```sh
python3 Backend/export_study_data.py \
  --data-dir StudyData/logs/study --run STUDY_RUN_ID \
  --destination StudyData/exports/NEW_EXPORT_DIRECTORY
```

替换运行编号和新的目标目录；批量导出用 `--all` 替代 `--run`。已提交问卷 CSV、未完成记录、对话/审计 JSONL 和清单分别输出；有头显 journal 副本时加 `--local-journal /path/to/copied/journal`。详细步骤见[保存与导出说明](Docs/TutorPersonalization/STUDY_DATA_PERSISTENCE_IMPLEMENTATION.md)。实际日志、数据库、导出包和私有配置不进入 Git。

## 本地检查与协作

```sh
python3 -m unittest discover -s Backend/tests -q
python3 -m unittest discover -s Tools/AppearanceExperiment/tests -q
python3 -m unittest discover -s Docs/AppearanceExperiment/Study/tests -q
```

HTTP 测试需要本机回环端口，不调用付费模型。Unity 编译和桌面检查不替代头显测试。历史阶段文档的测试数字对应当时版本；当前交付检查见 [GitHub 交付记录](Docs/TutorPersonalization/GITHUB_DELIVERY.md)。

- Assets 与 `.meta` 一起提交，保留 GUID；模型、纹理、音视频、字体等依照 `.gitattributes` 使用 LFS。
- 不上传 `.env`、真实参与者资料、`StudyData`、缓存、虚拟环境或 APK。
- 后续功能可在独立分支开发；本次按项目负责人要求直接整合到 main，保留已有历史。
- 旧外观项目资料见 [AppearanceExperiment](Docs/AppearanceExperiment/README.md)，模型来源见 [Art](Art/AppearanceAvatars/README.md)。第三方资源仍遵循其原许可。
