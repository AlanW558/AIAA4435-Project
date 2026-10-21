# Editable appearance avatars

Open [AppearanceAvatars.blend](AppearanceAvatars.blend) in Blender 5.2.1 LTS.
Run `git lfs pull` first: the authoring file, reference images, production FBXs,
textures, CJK font and demonstration video use Git LFS.

The file contains both `Liang` and `Nailong` roots, packed textures, three human
outfits, detachable glasses/caps, design-reference planes and named inspection
cameras. The initial visible state is the human in a blue suit and glasses.
Switch the visibility of `Outfit_suit`, `Outfit_sport` and `Outfit_none` one at a
time. Nailong and the optional cap are initially hidden.

The model is a static appearance-editing prototype. It does not provide facial
animation, full-body tracking or a finished VTuber humanoid rig. Hair, collar
textures and some neck/skin transitions remain less detailed than the reference
images; engineering checks do not establish user acceptance of resemblance.

## Production resources

Unity loads the two committed FBXs from `Assets/Project/Resources/AvatarDemo/`.
Keep their `.meta` files when re-exporting. Export only the chosen root and its
model descendants, excluding reference planes, cameras and lights. The current
interchange uses metres, forward `-Z`, up `Y`, no leaf bones and no baked animation.
Preserve `Outfit_*`, `Accessory_*`, material names and the colour-mask textures:
the runtime uses these names to apply edits without changing skin or fixed parts.

The default human supports suit, sportswear and bare torso with training shorts.
Full replacement uses the yellow Nailong character; undo restores identity,
outfit, colour, accessories and scale together. DeepSeek parses requests at
runtime; it does not generate or redesign these assets.

The production FBXs are ready to import. The packed Blender file allows further
editing without the original reconstruction weights or intermediate GLBs.
`Tools/AppearanceExperiment/assemble_reference_avatars.py` documents the earlier
assembly pipeline, whose original GLB inputs remain local under `StudyData`.
The older MakeHuman builders are historical experiments, not required to build
the current avatars; their downloaded source archives remain local.

## Sources and evidence

The design references in [references/](references/) were generated for this task,
then reconstructed locally with Hunyuan3D-2 and corrected in Blender. They are
reference illustrations, not screenshots of completed models. The human is a
user-requested Liang Wenfeng-inspired character; Nailong is a user-requested
character reference. No official model, personal scan or endorsement is claimed.
Third-party tools, dependencies and character rights are not relicensed here.

- [File hashes and provenance](provenance.json)
- [Actual Unity renders and checks](../../Docs/AppearanceExperiment/Validation/avatar-v3/index.html)
- [Modelling details and known limitations](../../Docs/AppearanceExperiment/Pico/avatar-v3-design.md)
- [Blender/Unity workflow](../../Docs/AppearanceExperiment/Pico/blender-unity-workflow.md)

Geometry: `blender-landmark-neck-fit-v3`.
Texture cleanup: `blender-bare-skin-cleanup-v2`.
