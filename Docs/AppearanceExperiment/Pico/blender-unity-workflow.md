# Blender → Unity avatar workflow

Updated: 2026-10-21.

## Available desktop software

- Host: `desktop-ubuntu-ts`.
- Blender executable: `/home/enjixiong/blender-5.2.1-linux-x64/blender`.
- Verified version: **Blender 5.2.1 LTS**, build `9e2066aef7ef`.
- Unity executable: `/home/enjixiong/Unity/Hub/Editor/2022.3.62f3c1/Editor/Unity`.
- Project: `/home/enjixiong/academics/AIAA4435/AIAA4435-Project`.
- Existing script environment: `Builds/AvatarTools/venv/bin/python`, with `bpy 4.5.3`.

The installed Blender executable has run the modelling/rendering scripts and
the production `assemble_reference_avatars.py` export. The native application
can use the existing mesh operations without an MCP bridge.

Blender `--python` does not automatically add this project's script directory
to Python's module search path. Add that directory explicitly when importing
sibling scripts. Use `--python-exit-code 1` so a Python exception causes a
failed command instead of Blender's otherwise successful application exit.
Find shader nodes by their Blender node type, not an English display name:
this desktop's Chinese UI can localize the default Principled BSDF node name.

## Fixed visual target

The three approved images remain under `StudyData/avatar-v3/references/`:

- `liang-reference-v1.png`: muscular human in a blue suit.
- `liang-sport-reference-v1.png`: the same character in sportswear.
- `liang-bare-reference-v1.png`: the same character with bare torso.

These are design references, not screenshots of a completed 3D model.
`liang-head-no-glasses-v1.png` supplies additional face detail. DeepSeek does
not design or generate the default avatar.

Keep source GLBs and textures unchanged. Create isolated candidates under
`StudyData/avatar-v3/neck-candidate/` until their front, side, close-up, and
Unity views have been inspected. Current rejected and diagnostic candidates
are retained for comparison, not labelled as final assets.

## Editable Blender workbench

`Tools/AppearanceExperiment/prepare_blender_avatar_review.py` builds a
separate review workspace from a candidate:

```bash
/home/enjixiong/blender-5.2.1-linux-x64/blender \
  --background --python-exit-code 1 \
  --python Tools/AppearanceExperiment/prepare_blender_avatar_review.py \
  -- --source StudyData/avatar-v3/neck-candidate/CANDIDATE/candidate.blend
```

The output directory is `StudyData/avatar-v3/blender-workbench/`:

- `Liang-review.blend`: editable mesh, packed textures and approved references.
- `Liang-review.fbx`: only the model hierarchy; no reference planes or lights.
- `workbench.json`: version, source hashes, exported objects and triangle count.

The image references are viewport-only helper objects. Named cameras expose
front, face, three-quarter, and side views. The `.blend` is the authoring and
review file; the exported FBX is the interchange file for Unity.

To open the complete production assembly, pass
`--source StudyData/avatar-v3/unity-blender-staging/AvatarDemo/assembled.blend --root Liang`.
This preserves all three outfits and the second character in the editable
file. The initial visible state is the blue suit with glasses. Other outfits,
the optional cap, and Nailong remain hidden; show one outfit at a time when
editing. The FBX includes all variants of Liang, while reference objects,
lights, cameras and Nailong are excluded from that export.

## Interchange and checks

1. Correct head shape, head/body size, posture and collar alignment in Blender.
   Check real eye and chin landmarks rather than treating a mesh bounding box
   or glasses-frame centre as a facial landmark.
2. Keep the neck connected and check open edges, degenerate bridge faces,
   local foldovers, normals, UV continuity and the skin-colour transition.
   A closed, non-degenerate mesh can still fold inward at the collar. Inspect
   the bare torso from the side as well as the front. Use the original body's
   neck surface to constrain the bridge width; the wider hair boundary is not
   a suitable neck-width target.
3. Export metres with `axis_forward="-Z"`, `axis_up="Y"`, applied unit scale,
   no leaf bones and no animation bake. Production assets preserve the
   `Outfit_*` and `Accessory_*` hierarchy used by the runtime.
4. Import the candidate into Unity and inspect actual material rendering.
   A neutral, explicitly recorded ambient probe is needed in the isolated
   preview scene to avoid mistaking a missing lighting environment for dark
   skin or a geometric hole.
5. Verify clothes, colour masks, scale, whole-avatar replacement and undo.
   Only then build the desktop/PICO demonstration and record English subtitles.

The expanded Unity review includes seven appearance states and nine detail
views. Bare-torso three-quarter and side close-ups specifically expose neck
silhouette and collar defects that a dressed front view can conceal. Retain
failed visual-review folders alongside the later accepted engineering checks.

The current reconstructions are static meshes. No humanoid rig, facial
animation, full-body tracking or PICO frame-rate validation is implied.

## Current reviewed outputs

- `StudyData/avatar-v3/blender-workbench/Liang-review.blend`: packed, editable
  Blender 5.2.1 workbench, also opened on the desktop.
- `StudyData/avatar-v3/blender-workbench/blender-window.png`: actual desktop
  Blender window with the references beside the model.
- `StudyData/avatar-v3/unity-blender-reviewed-checks/index.html`: offline
  reference/Unity comparison, with all 16 actual render views.
- `StudyData/avatar-v3/production-resource-install.json`: the 14 published FBX
  and texture hashes, verified in both local and desktop checkouts.

Current geometry is `blender-landmark-neck-fit-v3`; texture cleanup is
`blender-bare-skin-cleanup-v2`. The final texture cleanup samples the original
body's opposite side and nearby clean skin within a measured torso region.
It corrects source-texture blue/purple contamination while preserving mesh
coordinates, UVs, the source GLB and other outfits. The earlier incomplete
cleanup remains documented in the failed review folders.

These checks establish working assets and the intended edits. They do not
establish that the user has accepted the likeness. Hair, collar textures and
small neck/skin shading transitions remain less detailed than the 2D targets.

## Tools suggested in the linked conversation

The linked conversation was read and the upstream repositories inspected:

- [MCP for Blender](https://github.com/ahujasid/mcp-for-blender) provides an
  external control bridge for Blender.
- [Unity MCP](https://github.com/CoplayDev/unity-mcp) provides editor tools and
  an orchestration skill.
- [Meshy 3D Agent](https://github.com/meshy-dev/meshy-3d-agent) supplies a
  separate model-generation CLI/skill workflow.

These are optional workflow tools. No new MCP server, account login, cloud
generation job or paid generation has been started for this revision.
Existing direct Blender scripts and Unity editor checks already provide the
modelling/export/import path needed for this correction.
