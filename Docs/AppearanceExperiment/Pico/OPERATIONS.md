# PICO 启动与恢复

所有本机命令从项目根目录的 WSL 终端运行。当前设备序列号为 `PA9410MGK6200308G`；每次先用 `python3 Tools/AppearanceExperiment/pico.py devices` 核对。研究者界面与目标卡在头显外管理。

## 后端与连接

台式机后端由 `Tools/AppearanceExperiment/start_backend.sh` 启动，仅监听 127.0.0.1:8765。实际日志在 `StudyData/logs`，密钥只在台式机 `~/.config/aiaa4435/`。启动前检查 `/health`，不要同时启动第二个同端口服务。老师密钥优先，只有 HTTP 402 才使用个人备用；401/429/网络错误不会触发备用消费。

在单独终端保持 SSH 转发：

```bash
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:8765:127.0.0.1:8765 desktop-ubuntu-ts
```

本环境使用 Windows adb.exe 和 WSL localhost 转发，同时保持 IPv6 回环中继（另一个终端，仅监听 ::1）：

```bash
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(wslpath -w Tools/AppearanceExperiment/windows_adb_ipv6_relay.ps1)"
```

USB 重新连接会清除设备端 reverse。以下进程仅自动恢复同一设备的端口映射；不会重启应用、重复请求或把失败试次算成成功：

```bash
python3 Tools/AppearanceExperiment/keep_pico_usb.py --serial PA9410MGK6200308G
```

本机健康检查需绕开系统代理：`curl --noproxy '*' http://127.0.0.1:8765/health`。forward 存在仍不等于后端可用；最终以设备 initialized、有效 session_id 和实际操作为准。断线后出现 fault 时保留记录，由研究者重新配置新会话；不要在原试次盲目重发。

## 安装、配置与研究者操作

```bash
python3 Tools/AppearanceExperiment/pico.py --serial PA9410MGK6200308G install --apk Builds/Pico/AppearanceVR.apk
python3 Tools/AppearanceExperiment/pico.py --serial PA9410MGK6200308G configure --session-file /absolute/path/session.json --build-sha256 ACTUAL_APK_SHA256
python3 Tools/AppearanceExperiment/pico.py --serial PA9410MGK6200308G launch
python3 Tools/AppearanceExperiment/pico.py --serial PA9410MGK6200308G status
python3 Tools/AppearanceExperiment/pico.py --serial PA9410MGK6200308G serve --port 8766
```

将占位路径和实际 SHA 替换后执行。配置文件来自问卷关联工具；正式身份只能按冻结日程启动，不允许覆盖条件或任务。浏览器打开 http://127.0.0.1:8766。PICO 每试次结束后由研究者点击“下一试次”；每四项暂停，问卷结束后点击“问卷完成，恢复”。第 16 项完成后停止，不循环。参与者仍只看到修改界面。

详细 CLI、命令回执和导出规则见 `CONTROLLER.md`。目标卡和独立练习见 `PRACTICE.md`。目标卡输出 `StudyData/pico/materials/index.html` 为研究者索引，仅向参与者出示当次单张 HTML；正式任务源文件没有被改写。

## 构建与桌面视频

台式机构建 PICO：`DISPLAY=:1 XAUTHORITY=/run/user/1000/gdm/Xauthority bash Tools/AppearanceExperiment/build_pico.sh`。脚本恢复临时 PlayerSettings，输出 APK、构建报告、实际 SHA 和 Unity 检查报告。若当前桌面显示号改变，先核对 DISPLAY / XAUTHORITY。

桌面演示入口为 `AppearanceDemoSetup.BuildLinux`，生成独立 `AppearanceDesktopDemo` 场景 / Linux player，固定相机只用于录制，同一客户端、角色和后端不变。按实际窗口 ID 调用 `record_desktop_demo.py --help` 所列参数；只接受新建的 S/debug/READY 会话。录制是真实窗口，所有动作等待实际状态与四张截图确认，不生成模拟结果。

当前双形象视频：`Builds/Demos/AppearanceRoom-Avatars-60s-en.mp4`（英文字幕及顶部标题，60 秒 / 1080p / 30 fps）。原始录制、7 个真实事件、4 张状态截图和 8 张字幕关键帧为 `StudyData/avatar-v3/desktop-demo/take-01/`；成片旁的 manifest 记录 28 个来源文件哈希。内容包括换装、颜色、缩放、澄清、整体替换和完整撤销；实际桌面录像，并非 PICO 佩戴画面或正式参与者数据。

旧角色视频 `Builds/Demos/AppearanceRoom-60s-debug.mp4` 和 `StudyData/pico/desktop-demo/take-02/` 已保留，不能把两版资产和证据混用。

## 新双形象 demo 配置

新的参考重建角色通过 `avatar-demo-v1` 启用；默认是蓝西装、眼镜、比例 1.00 的梁文锋风格男性，全替换使用黄色奶龙。西装、运动服、裸上身加短裤可切换。省略 profile 仍进入冻结的 `study-v1`，仅升级 APK 不会把正式实验切换成新 demo。

2026-10-21 最新 APK 为 `Builds/Pico/AppearanceVR.apk`，版本 0.3.0（30），实际 SHA-256 为 `74305dce9b618bf9dec37f9539bc95d9fa26ccc484f0d05ee1b8649f8c553bca`。本轮 23 项运行逻辑检查、APK 完整性及签名检查通过；构建保留 11 条现有 SDK 警告，详见 `StudyData/avatar-v3/builds/android/`。安装前再次计算本地 APK 哈希，并使用该次实际值配置；不要将这里的哈希套用到未来重构建的 APK。旧包在 `Builds/Pico/Archive/AppearanceVR-before-avatars-2aeb202f2653.apk`。

模型编辑入口是 `StudyData/avatar-v3/blender-workbench/Liang-review.blend`，实际 Unity 对照为 `StudyData/avatar-v3/unity-blender-reviewed-checks/index.html`；[Blender 与 Unity 工作流](blender-unity-workflow.md) 记录重新导出与检查方式。当前几何修订 `blender-landmark-neck-fit-v3`、贴图修订 `blender-bare-skin-cleanup-v2`，默认参考图保存在工程内。

本次独立演示后端位于台式机 `http://127.0.0.1:8775`。使用新的 debug 身份与会话文件，不指定冻结目标卡；配置时追加：

```bash
python3 Tools/AppearanceExperiment/pico.py --serial ACTUAL_DEVICE_SERIAL configure \
  --session-file /absolute/path/new-debug-session.json \
  --condition S --capability-profile avatar-demo-v1 \
  --backend http://127.0.0.1:8775 --build-sha256 ACTUAL_NEW_APK_SHA256
```

USB 接台式机时，在台式机执行 ADB 和对应的 `adb reverse tcp:8775 tcp:8775`；USB 接本机时，需要将原有 SSH／回环转发链路对应到 8775。每次连接先核对实际序列号、设备授权、后端健康及初始化状态。用户已要求稍后连接 PICO，本次新资源的安装、设备帧率、6DoF 和佩戴视角检查尚未执行。
