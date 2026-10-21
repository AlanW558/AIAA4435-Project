# Avatar v3: reference-driven 3D reconstruction

The earlier MakeHuman/primitive avatars were rejected for likeness. This attempt
uses the user-selected, imagegen-produced RGBA references in
`StudyData/avatar-v3/references/`. DeepSeek is not involved. Original references
are not sent to a third-party generation service.

## Available character assets

Searches covered Nailong/奶龙, FBX/GLB/VRM/MMD, author repositories, GitHub,
Sketchfab and model marketplaces. No complete character mesh was found with both
a verified reusable license and an anonymous direct download:

- [Sketchfab, 78红米](https://sketchfab.com/3d-models/d7a3f20de4e4486182806c40699d26d4):
  actual 8,334-triangle model; platform sign-in required. No bypass attempted.
- [Aigei full character listing](https://www.aigei.com/item/q_ban_ben_pao.html):
  FBX/glTF advertised, but download and author license were not independently
  verified. Preview images were not treated as models.
- [Cults author bust](https://cults3d.com/en/3d-model/art/grumpy-nailong):
  a print-oriented bust, not a complete real-time character.
- [Nexprint spring toy](https://www.nexprint.com/en/models/C8776070):
  printable articulated toy, with redistribution restrictions.
- [Polycam capture](https://poly.cam/explore/capture/a29084f6-d3bc-4ae5-aa0b-d9315713b228/nailong):
  splat capture, without a verified mesh download/license.
- [Steam workshop MMD](https://steamcommunity.com/sharedfiles/filedetails/?id=3607532934):
  listing attributes the source to Peace Elite; reusable rights were not clear.
- Public GitHub Nailong detection projects contain detector weights/data;
  pet projects contain sprites or 2.5D assets, not a verified full 3D mesh.

## Selected implementation

[Official Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) documents
approximately 6 GB VRAM for shape and 16 GB for shape plus texture. The standard
1.1B shape model was selected over the 0.6B mini to prioritize fidelity.
[TRELLIS.2](https://github.com/microsoft/TRELLIS.2) officially requests at least
24 GB VRAM; [TripoSR](https://github.com/VAST-AI-Research/TripoSR) remains a lower
resource fallback, not the selected generator.

Pinned source: `Tencent-Hunyuan/Hunyuan3D-2`
`f8db63096c8282cb27354314d896feba5ba6ff8a`.
Pinned model: [`tencent/Hunyuan3D-2`](https://huggingface.co/tencent/Hunyuan3D-2)
`9cd649ba6913f7a852e3286bad86bfa9a2d83dcf`.

The official [Tencent Hunyuan3D 2.0 Community License](https://huggingface.co/tencent/Hunyuan3D-2/blob/main/LICENSE)
applies, not MIT/CC0. It excludes the EU, UK and South Korea from its territory,
requires preservation of applicable notices when distributing covered materials,
and contains use restrictions. The project retains the original LICENSE and
NOTICE with downloaded weights. Generated meshes should not be described as an
official licensed Nailong model or as a precise scan of a real person.

## Isolation and storage

Remote work is confined to `Builds/AvatarTools3D` and generated evidence under
`StudyData/avatar-v3`. The venv uses the existing `dl` environment's Python 3.11.6
and PyTorch 2.10.0+cu128 read-only. CUDA extensions use the existing
`/usr/local/cuda-12.8`; no system driver or mathematics environment is changed.

Installed in this venv: diffusers 0.32.2, transformers 4.48.3,
huggingface_hub 0.36.2, accelerate, einops, omegaconf, trimesh, pymeshlab,
pygltflib, xatlas, opencv-python-headless, scikit-image, ninja and pybind11.
Both official rasterizer extensions compiled successfully; shape and texture
imports passed on the RTX 5060 Ti.

The remote filesystem initially had about 13 GB free. After the user explicitly
authorized the main task to remove specified old Qwen/HF caches, that task
verified 117.78 GiB free. No files outside that approval were removed. This
reconstruction's weights remain intact. HF caches are scoped to this task,
and duplicate checkpoint formats are excluded.

| Stage | Selected weight files | Bytes, excluding tiny configs |
| --- | --- | ---: |
| Shape | `hunyuan3d-dit-v2-0/model.fp16.safetensors` | 4,928,151,562 |
| Paint | standard text encoder `.bin`, UNet and VAE `.safetensors` | 5,191,643,677 |
| Delight | text encoder, UNet and VAE `.safetensors` | 4,311,928,326 |

The shape checkpoint already includes its VAE and image conditioner. The separate
VAE checkpoint is not required. Paint plus delight total about 9.50 GB. The
shape binary was archived to the local D: project and its SHA256 verified;
the remote copy was retained after the disk constraint was resolved.

## Execution record

- `logs/install-shape.log`: isolated dependency installation.
- `logs/install-source.log`: editable official source installation.
- `logs/install-renderers.log`: CUDA 12.8 / sm_120 custom rasterizer and CPU mesh
  processor compilation.
- `logs/download-shape.log`: pinned, explicitly selected shape files via `hf`.
- `run_shape.py`: empty-parameter construction and `load_state_dict(assign=True)`
  avoid a second FP32 copy in RAM. Uses original RGBA, official image processing,
  50 diffusion steps, guidance 5.0, seed 20261020, 512 spatial resolution,
  the official default volume decoder and marching cubes.

Each generated model receives a manifest with input hash, versions, parameters,
mesh dimensions/counts, elapsed time and measured GPU allocation. Shape-only
outputs are intermediate evidence; delivery requires textured meshes and actual
multi-view inspection. Run results are appended as stages finish.

### 2026-10-21, first actual shape result

The 4,928,151,562-byte shape checkpoint SHA256 is
`360bc281fc956d4acac0c3d36d5ec0ebf8cdddbf4b8892e894d12419388d479b`,
matching the official file's LFS digest. The task's source, environment, cache and
weights occupy 5.3 GiB on the remote host; the model has only one local copy.

The initial optional `HierarchicalVolumeDecoding` run failed with an empty query
list at r257. The same diffusion configuration works with the official default
`VanillaVolumeDecoder`; no upstream code was modified. The 256-resolution
diagnostic produced a watertight full-body mesh with 73,800 vertices and 147,604
triangles in 43.7 seconds, measured peak allocation 5,341,317,120 bytes.
`shape-diagnostic-256.glb` preserves that intermediate result while 512-resolution
generation proceeds. Logs retain both the failure and the successful fallback.

The exact RGBA input's actual official RGB/alpha preprocessing is saved beside
each model. Transparent RGB glow is alpha-composited onto white by the official
processor, not sent as an opaque background. No rembg was applied.

The script saves finite-checked diffusion latents so surface-decoding adjustments
can reuse the generated shape. The texture script runs the official delight and
multiview stages in separate processes; this changes memory lifetime without
retaining both texture networks in system RAM.

### Five completed 512-resolution shapes

| Output directory | Raw triangles | Notes |
| --- | ---: | --- |
| `generated/liang` | 591,168 | Blue suit, full body |
| `generated/nailong` | 986,432 | Original orientation retained for painting |
| `generated/liang-head` | 1,823,226 | Same face and hair, without glasses |
| `generated/liang-sport` | 601,992 | Blue training shirt and shorts |
| `generated/liang-bare` | 626,016 | Muscular torso and training shorts |

All paths above are under `StudyData/avatar-v3`. The measured shape peak was
6.37 GiB allocated GPU memory. Full generation took approximately 158–159 seconds
per new input; the suit's 512 decode reused its saved diffusion latent.

Raw marching-cubes outputs contain a few duplicate/zero-area triangles. Removing
only these in a copy made the checked suit, sport, Nailong and head meshes
watertight, with zero boundary/non-manifold edges (2, 2, 8 and 26 faces removed,
respectively). No holes were filled and raw high-resolution files remain intact.
Paint inputs retain up to 100,000 triangles; runtime reduction is separate.

### Actual texture compatibility findings

All selected paint/delight weights downloaded and passed the pinned official LFS
SHA256 checks. The standard paint repo's `unet/modules.py` nevertheless hardcodes
the duplicate `.bin` filename. The project wrapper loads the **unchanged official
module class** from that file, constructs empty parameters, assigns the published
`.safetensors` with `strict=True`, and explicitly constructs the official
`HunyuanPaintPipeline` from its components. Every UNet parameter matched.
Neither official source nor downloaded model files were edited.

Generic diffusers model CPU offload also caused mixed devices: the standard paint
pipeline reads its learned prompt parameters before the UNet forward hook.
The wrapper keeps the paint-only network on CUDA. Delight runs in a separate
process, so this fits the 16 GB GPU without retaining both networks together.
Actual paint inference reached approximately 9 GB total device usage.

Five delight runs completed successfully at roughly 3 seconds each and about
2.02 GB allocated GPU memory. Outputs are `delighted.png`, with separate
manifests. The independent head preserves much more face detail than the
full-body conditioning image. Nailong's dark hands/feet from the reference remain
dark. These are present in both the original screenshot and the selected
reference, so they must remain distinct from the golden body and cream belly.

### Five completed textured assets and container verification

All five paint runs completed successfully. `run-paint-cuda.log` ends normally.
They use six 512-pixel conditioning views, 30 multiview diffusion steps, seed 0
and a 2048 × 2048 albedo. Maximum measured paint allocation was 7.31 GiB; the
paint-only network remained on CUDA while delight had already exited.

| Output directory | Triangles | Embedded GLB bytes | Paint seconds |
| --- | ---: | ---: | ---: |
| `generated/liang` | 100,000 | 4,884,608 | 63.0 |
| `generated/nailong` | 100,000 | 4,648,500 | 50.8 |
| `generated/liang-head` | 100,000 | 5,968,676 | 59.4 |
| `generated/liang-sport` | 100,000 | 5,647,364 | 61.2 |
| `generated/liang-bare` | 100,000 | 5,190,756 | 52.0 |

Each directory retains the raw high-resolution `shape.glb` and `shape.ply`,
the cleaned/reduced `paint-input.glb`, `textured.glb`, OBJ/MTL/PNG alternatives,
original preprocessing evidence, and per-stage manifests. These are archived
in both remote and local project folders. No source reference was overwritten.

`Builds/AvatarTools3D/validate_textured_glb.py` inspected the actual binary
containers. All five have valid glTF 2 headers, indexed triangle meshes,
`TEXCOORD_0`, materials, an embedded 2048 × 2048 PNG, and no external buffer
dependencies. Full file hashes and counts are recorded in
`StudyData/avatar-v3/generated/textured-container-validation.json`.

The successful stage commands, run from the remote project root, are:

```bash
Builds/AvatarTools3D/venv/bin/python Builds/AvatarTools3D/run_shape.py --decoder vanilla --resolution 512 --steps 50 --chunks 6000 --seed 20261020 --names liang nailong liang-head
Builds/AvatarTools3D/venv/bin/python Builds/AvatarTools3D/run_shape.py --decoder vanilla --resolution 512 --steps 50 --chunks 6000 --seed 20261020 --names liang-sport liang-bare
Builds/AvatarTools3D/venv/bin/python Builds/AvatarTools3D/run_texture.py delight
Builds/AvatarTools3D/venv/bin/python Builds/AvatarTools3D/run_texture.py paint --max-faces 100000 --texture-size 2048
```

The shape runner reuses a finite-checked saved latent when one exists. The
original failed hierarchy, successful diagnostic and compatibility failures
remain in the logs; these commands describe the successful configuration.

### Visual review status

Actual Blender front/side/back/three-quarter previews were rendered by the
main task. The source suit has a recognizable muscular silhouette, blue jacket,
white shirt and black shoes; the full-body texture has insufficient facial
detail, so the separately generated head is required. Nailong has a complete
round body, cream belly, green eyes, dark hands/three-toed feet and a tail.
The current lit preview is paler than the reference; final body recoloring must
preserve the belly, eyes and dark extremities.

The first `liang-assembled-textured` preview was **not accepted** in the
independent review: its long stretched neck, jagged neck/chest boundary and
open rear collar are visible even in the full-body view. The glasses also
need a near-view check for occlusion/continuity. These findings were sent to
the main task, which owns head/body assembly and runtime materials. Successful
generation and container validation do not mean final visual acceptance.

### Read-only color diagnosis of the first textured assembly

The original GLB's embedded PNG was decoded with Pillow and compared pixel for
pixel against each staging `Textures/*_Albedo.png`. **All five RGB images match
exactly:** maximum absolute difference 0, mean absolute difference 0, and 100%
identical RGB pixels. Blender's save added PNG metadata/compression differences,
so the standalone file hashes differ, but there is no added gamma conversion.
The raw and assembled GLBs also contain byte-identical embedded PNGs.

Blender 4.5.3 reports `sRGB`, 8-bit/non-float and `CHANNEL_PACKED` for the source
images, their in-memory copies and the assembled imports. The observed material
parameters do change:

| Import | Metallic | Roughness |
| --- | ---: | ---: |
| Raw Hunyuan/trimesh GLB | 1.0 | 0.903602 |
| Newly assembled material | 0.0 | 0.55 |

This is a material-response difference, not an albedo-file difference. Its
visual contribution was not separately rendered in this diagnosis; the main
task owns rendering and material tuning. Keep cloth and skin nonmetallic, and
assess roughness/specular/lighting under the actual Unity material. Applying
inverse gamma to the verified unchanged textures would introduce a new error.

For byte-preserving extraction of these verified PNG-packed images, write
`image.packed_file.data` directly to the output PNG and load that file as
`sRGB`, instead of re-encoding through `image.copy().save()`. This makes file
provenance simpler, but does not itself resolve the observed pale shading.
The measurement records are
`generated/texture-color-diagnostic-pixels.json` and
`generated/texture-color-diagnostic-bpy.json`.
