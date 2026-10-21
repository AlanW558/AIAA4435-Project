# PICO 开发接续记录

更新：2026-10-21（Asia/Singapore）。已通过 read_thread 继承聊天 `01a14de6-8fab-76b0-8a1d-3f0e36c78316`，并以实际代码、构建、PICO 状态和后端日志核验。

## 已确定的项目方向

- 本周先完成外形定制实验；语音链路放在后续阶段。
- 四条件为 Execute-first、Always-ask、Native-gate、Selective，代号 E/A/N/S。共享 proposer、候选、状态、执行、澄清界面、修复预算与撤销，只改变初始请求的询问决策。
- Selective 按 R1 指代不明、R2 软偏好覆盖不明、R3 候选后果实质差异触发询问；小幅可逆缩放有例外。Native-gate 不等于完整自由规划的原生 agent。
- 角色当前支持六种衣服颜色、帽子/眼镜/无配饰、0.85–1.15 的比例。
- Unity 是纯交互界面：不显示实验类型、参与者编号、策略、任务卡或轮次。研究者配置和问卷在客户端外管理。
- 22 人是原始招募目标，预留 2 个预实验和 20 个正式槽位。2026-10-21 已收到 15 份正式类型问卷，实际情况见下节；预留槽位不代表已完成采集。工程验证不计作参与者数据。
- 用户已在 2026-10-21 明确授权用本地 git/gh 将开发内容作为 GitHub PR 发布；这取代此前暂不推送的偏好。原始回答、凭证和逐人日志保留在本地。
- 全流程中文问卷已发布，32 题、六页，链接为 <https://v.wjx.cn/vm/QZCoEdh.aspx>。中期 PDF 和完整 Markdown 在 `Midterm/`。发布结果以 `Study/survey/publication_status.json` 为准。

## 2026-10-21 问卷结果与研究者确认

- 用户提供问卷星 389439995 的本地 XLSX：15 条记录均选择正式实验及同意参加，16 项评分全部完整，共 240 个评分值。
- 研究者确认参与者实际使用 PICO 头显及新蓝西装／奶龙角色；每人顺序均为 **N→E→A→S**。本次分析按实际顺序映射，冻结的平衡分配表保留为原计划材料。
- 第 29 题是研究者根据纸质回答归纳的表述，不能当逐字引语。其余七个开放题在导出中为空。
- [完整结果和分析](Results/2026-10-21/问卷结果与完整分析.md) 同时报告偏好、逐题人数、配对比较、顺序混杂和缺失信息。旧问卷模拟回答不参与分析。
- 这项确认是研究者提供的现场背景，未连接逐人 APK 指纹、客户端 phase/profile 或试次日志。问卷的“正式”标签不证明客户端运行了冻结的正式日程；当前代码的扩展角色 profile 仍仅允许 debug。不能从问卷反推完成了 240 项任务，也不能把研究者报告写成代理执行的新版本性能验证。
- 以下建模与设备记录保留各自发生时的验证边界；“尚未连接／未执行新 APK 真机验证”描述当时的代理工程操作，不否定研究者后来确认的参与者体验。

## 2026-10-21 双形象开发接续

用户本次要求问卷结果的细致分类和人数示例，以及“梁文锋肌肉蓝西装男性”默认形象、黄色奶龙整体替换。两张原参考图已读取，保存在 `StudyData/avatar-v2/references/`。使用 anatomy 技能的部件拆解和近距离检查方法；模型为参考驱动制作，不是官方模型或本人扫描。

- 问卷解读：[11 类结果、具体题号与人数示例](Midterm/问卷结果解读与人数示例.html)。全文示例明确为模拟教学分布，不是真人数据。
- v2 用户明确指出与原参考图差距很大，**视觉验收未通过，不得作为合格默认形象交付**。MakeHuman 人形和程序化奶龙保留为被否定的工程初稿及回退证据。
- 用户进一步确认以原截图**右侧写实肌肉蓝西装**为准。新版参考由内置 imagegen 按原图生成，保存在 `StudyData/avatar-v3/references/`。台式机已用本地 Hunyuan3D-2 完成五份带贴图三维重建，来源、参数和哈希在 `StudyData/avatar-v3/generated/`。模型设计与实现见 [v3 设计](Pico/avatar-v3-design.md) 和 [重建记录](Pico/avatar-v3-reconstruction.md)。
- v3 人形共用细节头部，包含西装、运动服、裸上身加短裤三个状态；奶龙完整替换。每套衣领独立裁剪并连接颈部，眼镜按脸部实际表面贴合。角色是静态三维外形编辑资产，没有完整身体追踪或表情骨骼。
- **用户否定的旧 v3 头部方案已替换；新结果不代表用户已确认相似度。** 用户指定的三张全身参考 `liang-reference-v1.png`、`liang-sport-reference-v1.png`、`liang-bare-reference-v1.png` 已按附件 SHA 逐一核对。原分段 z 变形与原生重建的颅顶/下脸比例均有问题；本轮使用实际眼、眉、下颏位置修形，头高占身高 12.91%，顶到眼占头高 52.32%。三套服装共用同一头部。
- 用户建议的台式机 Blender 5.2.1 LTS 已实际用于修模、渲染和生产 FBX 导出。颈部按解剖位置裁切并使用曲面切向接合，消除主要前颈硬折；后桥改用皮肤采样，移除延伸到颈根的头发。西装前接缝面夹角中位约 8.18°（此前约 71°），三套桥接零开边/零面积。裸颈按原身体曲面收窄，并局部修复后肩回折黑缝；黄色角色眼镜鼻梁连接和镜片高度也已修正。生产修订为 `blender-landmark-neck-fit-v3`；来源和剩余细节限制见 [v3 设计](Pico/avatar-v3-design.md)，操作与所读工具建议见 [Blender 工作流](Pico/blender-unity-workflow.md)。
- 默认形象由本任务设计和检查。DeepSeek 只承担用户修改意图的解析，不生成造型或资产；不能把外观不符归因于 DeepSeek。
- 新能力以 `avatar-demo-v1` 在 debug 中显式启用，包含形象、服装、颜色、配饰、比例和整体替换撤销。省略 profile 仍进入 `study-v1`，旧角色保留在 `AppearanceLegacyAvatar.cs`。这次 demo 不自动变更冻结实验或目标卡。
- 后端 50 项、工具 54 项测试通过；静态来源/冻结材料 10 项检查通过。Unity 七组初稿网格状态及切回旧角色检查通过；这些仅证明接口，不等于视觉合格。最新 v2 表面检查报告包含实际蒙皮后的身高和足底，不使用导入器的保守剔除包围盒。
- 独立 live 演示服务位于台式机 `127.0.0.1:8775`，日志 `StudyData/avatar-v2/backend/`；旧 8765 服务保留。两者继续使用老师优先、仅 402 才使用个人备用的配置。
- 用户已明确说“先完成开发，稍后连接 PICO”。本次未连接头显，不应把下面旧版本的真机验证写成新角色已通过真机验证。新 APK 完成后的安装和性能/6DoF 验收等待用户连接。

## 2026-10-21 Blender 修模后的交付

- 原生 Blender 5.2.1 LTS 已完成生产导出，最终几何修订 `blender-landmark-neck-fit-v3`、贴图修订 `blender-bare-skin-cleanup-v2`。裸上身局部蓝紫色污染修复了 6,398 个像素，其余贴图区域、UV 和原始重建文件保持不变。
- 可编辑工程为 `StudyData/avatar-v3/blender-workbench/Liang-review.blend`，本机和台式机各有一份，台式机 Blender 已打开该文件。工程包含两个形象、三套人形服装、配饰、打包贴图、三张原参考图和检查相机；默认显示蓝西装及眼镜。旁边的 `Liang-review.fbx` 仅导出人形资产，不包含参考图或检查辅助对象。
- [参考图与实际 Unity 渲染对照](../../StudyData/avatar-v3/unity-blender-reviewed-checks/index.html) 包含 7 个状态和 9 张细节图。`checks.json` 通过了五字段观察值、实际身高、足底和旧实验角色恢复检查；14 个生产资源哈希在检查、录像和构建过程中保持一致。最大可见三角面数为 177,450，不能据此推断 PICO 的实际帧率。
- 新成片为 `Builds/Demos/AppearanceRoom-Avatars-60s-en.mp4`，英文标题及字幕，60 秒、1920×1080、30 fps、1,800 帧，SHA-256 `b0a950b4d20b1672cffd4825145eeea9b1ebe56177c69067199088ed9544646c`。真实桌面录像依次展示换运动服及橙色、放大、颜色澄清、选择蓝色、奶龙整体替换、撤销恢复五字段和完成后的状态探针。7 个真实事件、4 张实际状态截图和 28 个来源文件哈希已核验；证据在 `StudyData/avatar-v3/desktop-demo/take-01/`。这仍是桌面 debug 演示。
- 新 APK 为 `Builds/Pico/AppearanceVR.apk`，包名 `com.iai.aiaa4435.appearance`、版本 0.3.0（30）、arm64、135,238,036 bytes，SHA-256 `74305dce9b618bf9dec37f9539bc95d9fa26ccc484f0d05ee1b8649f8c553bca`。构建成功，0 errors、11 条沿用的 SDK 警告，23 项运行逻辑检查通过；APK ZIP 完整性、包信息及 v2 签名验证通过。三份临时构建设置已恢复。证据在 `StudyData/avatar-v3/builds/android/`。
- Linux player 构建成功并实际运行录制。保留 9 条 warning 和 1 项未使用的 SDK 示例 Wireframe shader 编译诊断；实际角色材质正常，未通过修改 SDK 掩盖日志。证据在 `StudyData/avatar-v3/builds/linux/`。
- 旧视频未覆盖；旧 APK 在两端均归档至 `Builds/Pico/Archive/AppearanceVR-before-avatars-2aeb202f2653.apk`，哈希与旧版真机记录一致。
- 本轮工程检查已通过，**用户尚未确认外观相似度**。头发、衣领、后肩短暗折痕和局部皮肤色调边界仍不及参考图细腻；模型仍为静态外形编辑资产。本轮没有执行新 APK 的 PICO 安装、立体视角、性能或 6DoF 验证。

## 2026-10-21 已授权磁盘清理

用户明确批准删除台式机两个 Qwen 目录及之前列出的全部全局 HF 模型缓存。已删除 `/home/enjixiong/Code/Model/Qwen3.5-9B`、`/home/enjixiong/Code/Model/DLED4020-Qwen3.5-9B` 和 `/home/enjixiong/.cache/huggingface/hub/models--*` 及对应模型锁；复查均不存在。释放 110.23 GiB，删除完成时可用空间为 117.78 GiB。后续重建权重和输出会继续使用空间，不能将这个时间点的值写成永久剩余空间。记录在 `StudyData/maintenance/storage-cleanup-20261021.json`。

## 前一版本已完成的真机验证

- PICO 4 Ultra Enterprise（A9210 / Android 14）已通过本机 Windows ADB 授权连接。专用 `Appearance Room` 已安装，包名 `com.iai.aiaa4435.appearance`，保留原房间应用。
- APK SHA-256：`2aeb202f2653f3d803c7a16ffb0e745e199bc43764015b662a218440f50fea6a`。Android 构建 0 errors；23 项真实 Unity 类检查通过。
- 房间接入共享角色、中文 XR 面板、澄清 / 补充 / 撤销 / 完成、Android 配置、冻结日程推进、实际 APK 指纹、截图和三探针。
- 角色加入面部、衣服和配饰细节，以及呼吸、眨眼、视线和反馈动作；动画不改变实验观察值。
- 四种条件已在真实 PICO 的独立 debug 会话完成，12 次探针与 16 张截图均保存。S 还验证了跨字段修改与局部撤销。证据见 `Pico/progress.md` 和本地 `StudyData/pico/debug-20261020-eans/`。
- 用户确认看到房间 / 角色 / 中文，并反馈可用手柄输入发送。工程脚本验证与用户反馈分别记录，不当作参与者研究结果。
- USB 重连会清除 ADB reverse；现有自动恢复工具只恢复端口，不重放请求。头显 HTTP /health 已实测 200。
- 老师 API 优先；仅在 DeepSeek 402 余额不足时切换私有个人备用。当前真机验证调用全部走 primary。凭证不进入仓库、客户端或日志。
- 用户明确要求由台式机完成录像，并使用英文字幕。60 秒演示使用真实 Unity 桌面窗口和同一套交互，顶部标题和字幕均为英文；不标成头显录像。输出 `Builds/Demos/AppearanceRoom-60s-debug.mp4`。
- 16 张线下目标卡已有 36 张共享 Avatar 实际 Editor 渲染图，带来源哈希；独立练习说明在 `Pico/PRACTICE.md`。私有目标不打入 APK，也不进入模型请求。

## 入口与环境

本机仓库为 `/mnt/d/hkust(gz)/assignments/7th semester/aiaa4435 - interactive ai system/AIAA4435-Project`；台式机为 `/home/enjixiong/academics/AIAA4435/AIAA4435-Project`，SSH 别名 `desktop-ubuntu-ts`。Unity 2022.3.62f3c1，PICO SDK 3.4.0，保持现有依赖。跨机只同步相关文件；公开交付范围见 [PR_DELIVERY.md](Pico/PR_DELIVERY.md)。

操作见 `Pico/OPERATIONS.md`；研究者控制器见 `Pico/CONTROLLER.md`；详细证据见 `Pico/progress.md`。本机浏览器控制台为 http://127.0.0.1:8766，仅研究者使用。

## 验证边界与下一阶段

工程检查证明链路可运行；另有上述 15 份研究者确认的 PICO 体验问卷，但没有逐人任务日志完成情况的核对。下一轮受控研究仍需记录独立 pilot、长时间佩戴舒适度 / 性能 / 6DoF、打印目标卡可读性及正式日程演练。预留 20 个正式槽位和 2 个 pilot 槽位不代表实际招募。服务重启后活动会话不恢复；保留原日志并使用新 debug 会话，不能补写丢失试次。

Android 构建保留现有 SDK 警告。桌面演示构建成功，SDK SpatialAudio 示例 Wireframe shader 在 GLCore 仍有一项编译诊断；示例 shader 未用于演示画面，实际窗口和视频已检查。没有修改外部 SDK 来掩盖该诊断。
