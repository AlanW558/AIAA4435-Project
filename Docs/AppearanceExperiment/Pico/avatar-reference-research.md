# Avatar asset research — 2026-10-20

当前方案：用已下载的 CC0 MakeHuman 人体、肌肉变形、男西装、矩形眼镜和真实面部贴图制作“黑短发、眼镜、宽肩蓝西装”的参考形象；黄色角色按用户参考制作完整三维网格。没有找到可直接取得的官方奶龙模型，也没有找到该“梁文锋肌肉梗图”的免费完整绑定模型。下方分别记录素材核验与已完成的人形制作；Blender 渲染不等同头显运行验证。

素材已放入 `Assets/Project/AvatarModels/Source/MakeHuman/`，下载地址、SHA-256 和分包文件的 CRC 见其中的 `download-manifest.json`。使用方法见同目录 `README.md`。

| 候选 | 核实的实际内容 | 本次判断 |
| --- | --- | --- |
| [MakeHuman 官方资产](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md) | 真实 OBJ、形状 target、163 骨骼定义及 skin weights；官方资产采用 CC0，代码许可另行区分 | 已下载最小人体/肌肉/骨骼集合，选用 |
| [Suits 01](https://static.makehumancommunity.org/assets/assetpacks/suits01.html) | Margaret Toigo 的男西装，OBJ + MHCLO + diffuse/normal/specular；页面与所选文件头均明确 CC0 | 已下载并选用 `toigo_male_suit_3`，已改蓝色、去领带并适配宽肩 |
| [Glasses 01](https://static.makehumancommunity.org/assets/assetpacks/glasses01.html) | 多件真实眼镜网格、材质和人体拟合映射 | 已下载；优先文件头明确 CC0 的 `spamrakuen_sagerfrogs_glasses_02`，缩略图为细长矩形框 |
| [系统资产](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html) / [Hair 01](https://static.makehumancommunity.org/assets/assetpacks/hair01.html) | 亚洲男性皮肤、眼球、眉毛、睫毛、短发；页面列出 CC0 | 按公开 ZIP byte ranges 只取需要的文件，保留全部对应贴图，避免整包约 500 MB 下载 |
| [Sketchfab 奶龙模型 — 78红米](https://sketchfab.com/3d-models/d7a3f20de4e4486182806c40699d26d4) | 公开 API 核实 `isDownloadable=true`、4,192 vertices、8,334 triangles、0 animations；标注 Free Standard | 是实际模型，但[官方下载 API 需要账号认证](https://sketchfab.com/developers/download-api)。本次没有登录或下载，也未验证骨骼和贴图 |
| [Sketchfab AI 奶龙 — snacku_mj](https://sketchfab.com/3d-models/cute-cartoon-dinosaur-e4c59b209c544aa2981cf4a1b9cc7320) | Rodin 生成模型的展示页，200k triangles，未见公开下载按钮 | 仅展示，不当成已取得的资产 |
| [Quaternius Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html) | 作者列明 CC0、Humanoid、FBX/glTF、平均约 13k triangles；免费包与付费 Source 包有区别 | 可作卡通人体备选，没有现成目标西装，未下载 |
| [VRoid 肌肉男素体](https://hub.vroid.com/en/characters/842095439715518118/models/8032096353486220645) | VRM 0.0；作者允许改造和商用，但页面禁止再分发 | 适合个人 VTuber 制作，不能直接假定允许把模型随项目公开分发 |
| [VRoid 免费双排扣西装](https://booth.pm/ja/items/2660665) | 作者发布的 VRoid 衣装纹理/自定义衣装 | 不是独立已绑定的肌肉西装男；需 VRoid 制作与逐项许可检查 |
| [Muscular Man in Suit — Poly Forge](https://www.turbosquid.com/FullPreview/2350110) | 作者销售的已绑定模型，多格式与多角度展示 | 付费候选；未购买，商品图不能当作可用网格 |

用户的黄色参考图具备连续的头颈与梨形身体、浅色腹部、绿色大眼、嘴缝、短手臂和三趾脚。自制时应先对齐侧面轮廓、腹部体积和面部比例，再制作连接连续的主体与附肢、眼口细节和动作骨骼。当前只有单张参考，背面与被遮挡部位属于设计推断；不能称作官方模型或精确复刻。

VTuber 的 VRM 是交付格式之一，并不要求当前 Unity demo 必须使用 VRM。Unity 2022.3 可导入 FBX 的 Humanoid 或 Generic 骨骼；人形先保留规范的 bind pose，再用动作下垂双臂。奶龙可用 Generic 骨骼。参见 [Unity Rig 文档](https://docs.unity3d.com/cn/2022.3/Manual/FBXImporter-Rig.html)。若后续接入 VRM，URP 的 MToon 支持需要区分版本：官方不提供 VRM 0.x 的 URP MToon，VRM 1.0 有对应 shader，不能把下载的 VRM 0.x 直接视为 URP 即插即用。[UniVRM 官方说明](https://vrm.dev/en/api/material/urp/)

本地 image-to-3D 是备选，而不是已经完成的资产路径。[TripoSR](https://github.com/VAST-AI-Research/TripoSR) 的官方说明为默认约 6 GB VRAM、MIT 代码与权重、支持纹理烘焙；[Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) 官方仓库列出 6 GB 形状生成、16 GB 形状加纹理，以及多视角版本。这些是模型需求说明，不是本机测速。即使生成成功，还要检查隐藏面、眼镜、手指、拓扑与骨骼；本次没有下载 AI 权重、安装推理环境或占用 GPU。

## 已完成的人形交付

`Tools/AppearanceExperiment/build_liang_avatar.py` 使用 Blender 4.5.3 将上述 CC0 资产组合为 `Assets/Project/Resources/AvatarDemo/Liang.fbx`。这是参考驱动的东亚男性形象，不是真人扫描或身份精确重建。

实际采用 Suit 3 的西装、裤子、白衬衫与袖口，移除了独立领带网格；使用 `short01` 黑短发、`eyebrow005`、`eyelashes01`、高模棕色眼球、`young_asian_male` 皮肤及 Sagerfrog 02 矩形眼镜框。运动上装从真实人体表面平滑外扩并沿上臂轴裁切；鞋、棒球帽、帽檐和缝线为本次制作的几何。原生骨骼与权重被保留，双臂的自然下垂姿态已烘焙为当前静止姿态。

所有目标形变按同一基础坐标相加。当前系数：亚洲青年男性 1.0、最大肌肉/正常体重 0.85、最大肌肉/最大体重 0.15、胸肌 0.65、背阔肌 0.40、V 形躯干 0.50。完整 helper 顶点只参与服装拟合及关节定位；最终身体表面只取 `body` 面组。

文件包含严格的 `Outfit_suit`、`Outfit_sport`、`Outfit_none`、`Accessory_glasses`、`Accessory_hat` 父对象，以及公共头部和 `head` 骨骼。全部可变色服装共用 `Tint_Liang_Blue`，目标 sRGB 为 `#2358B8`。名字含 `Cutout` 的四种材质（头发、眉毛、睫毛、眼球）需要 alpha clip；棕色眼球贴图含透明角膜区域，忽略 alpha 会遮挡虹膜与眼白。

贴图复制到 `Assets/Project/Resources/AvatarDemo/Textures/`，文件名加 `Liang_` 前缀，图像内容与 Source 中原文件相同。西装使用统一颜色与原有衣褶几何，因此下载的西装原始纹理仍保留在 Source，未作为着色底图。

`StudyData/avatar-v2/liang-preview/` 包含八张已人工查看的 Cycles 渲染、可再次打开的 `Liang-studio.blend`、`build-report.json` 和 `fbx-validation.json`。FBX 回导检查通过：163 根骨骼、24 个蒙皮网格、五张贴图，默认可见高度 1.8500004 m，足底 z 约 −1.4×10⁻⁷ m；三套服装与全部配饰合计 74,498 个三角形。Blender 导入器会把蒙皮网格临时重挂到骨架，但原始 FBX 的 OO 父子连接已另行解析，确认保留上述服装与配饰分组。Unity/PICO 的实际渲染和运行表现由集成步骤另行验证，这里不将 Blender 图像当作头显运行证据。
