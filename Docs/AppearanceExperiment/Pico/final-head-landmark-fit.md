# Final isolated head landmark fit

The selected isolated candidates are `StudyData/avatar-v3/neck-candidate/final-neck-{suit,sport}` and `StudyData/avatar-v3/neck-candidate/bare-neck-contour-fixed` for the bare outfit. Each directory contains `Liang-fitted.fbx`, `Liang-fitted.glb`, `candidate.blend`, `Textures/`, four actual Blender renders (`front`, `face`, `side`, `side-face`) and `head-fit-and-assembly.json`. The previous `final-neck-none` is rejected: its straight rear/side bridge produced visible triangular skin wings in Unity. The intermediate `bare-neck-contour` corrected the silhouette but exposed a folded triangle near the rear shoulder. Earlier files remain as diagnostic evidence. This task did not modify `Assets`, the production assembler or Unity staging.

The final geometry helpers are locked. The parent task accepted the suit front and corrected side silhouette for production integration. This is not a claim of photographic likeness or final Unity acceptance.

## Reusable transform

`Tools/AppearanceExperiment/fit_landmark_head_candidate.py:150`, `prepare_reference_head(head, neck_axis_xy=SUIT_NECK_AXIS)`, is the complete entry point. It expects the unchanged `generated/liang-head/textured.glb` imported by `load_mesh(..., height=.315)`. It retains loop UVs while welding duplicated positions and removing genuinely disconnected fragments, then applies:

1. A rigid −15° X rotation about the low neck, uniform normalization and placement on the suit collar axis.
2. The selected smooth upper-cranium reduction and uniform 1.12 scaling, with crown fixed at 1.85 m.
3. A C1 front-face height fit: eye-to-chin increases by 1.098839, with the chin and all geometry below it unchanged. Nose-to-lip vertical spacing uses the same multiplier. The deformation blends to zero on the lateral face and protected ear regions.
4. A separate C1 posterior depth correction, preserving front-face depth and the ear centers. The nose-to-occiput target of 0.235 m is a modeling inference; no approved side reference exists. Posterior height influence starts at the chin and reaches full strength 25 mm above it, avoiding the previously visible rear hair ledge.

The helper uses the sibling `inspect_uniform_head_candidate`, `refine_cranium_candidate` and `repair_neck_candidate` modules. Do not apply the rejected segmented Z warp before or after this function.

```python
from fit_landmark_head_candidate import prepare_reference_head, SUIT_NECK_AXIS
from repair_neck_candidate import cut_head_above_collar, connect_neck, smooth_bare_neck_boundary

head = load_mesh(generated / "liang-head/textured.glb", "Head prototype", .315)
head_report = prepare_reference_head(head, SUIT_NECK_AXIS)
bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
projection_mesh = head.data.copy()

# Preserve the full original bare neck before deleting the old head.
neck_reference_mesh = body.data.copy() if outfit == "none" else None
remove_old_head(body)
# Continue with a fresh head prototype copy for each outfit.
if outfit == "none":
    smooth_bare_neck_boundary(body, SUIT_NECK_AXIS, reference_head=head)
else:
    smooth_collar_boundary(body)  # Parent assembler, maximum displacement 2.5 mm.
cut_head_above_collar(
    head_copy, body, 1.55, neck_axis_xy=SUIT_NECK_AXIS,
    anatomical_nape_height=1.665, anatomical_front_height=1.59,
)
connect_neck(
    body, head_copy, intermediate_rings=7, projection_mesh=projection_mesh,
    transition_texture_dir=textures,
    neck_material_name=f"Fixed_LiangNeck_{outfit}",
    extend_neck_skin=True, match_upper_tangent=True,
    neck_reference_mesh=neck_reference_mesh, neck_axis_xy=SUIT_NECK_AXIS,
)
```

All outfits use the same global collar axis `(-0.0031917989253997803, 0.01932954043149948)`. Their cuts follow their own collar boundaries. The atlas materials are `Fixed_LiangNeck_<outfit>` and files are `Fixed_LiangNeck_<outfit>_Albedo.png`.

The anatomical cut removes the source's long nape hair independently of clothing. Its front height of 1.59 m remains approximately 21 mm below the chin. The posterior bridge extends only valid body-skin samples; the final 4 mm below the original hairline blend to the unchanged source head texture. This avoids projecting the removed long hair back onto the new neck.

The front bridge uses a Hermite curve whose upper derivative follows the surviving head's actual neck surface. The bare body additionally receives local boundary smoothing and a ray-cast alignment to the uncut head's neck surface. The anterior correction affects the neck boundary and two adjacent body rings, with maximum displacement 21.31 mm including 11.37 mm of additional retraction.

Only the bare bridge also matches the upper tangent around the sides/back and uses a radial ray to the original complete bare body's neck surface. A `sin²(πt)` profile confines the inset to the bridge interior and makes it vanish at both attachment boundaries; a smooth angular mask excludes the front. In the selected candidate it retracts 557 free bridge vertices by at most 26.79 mm. The neck now descends beneath the head before widening into the trapezius.

The original posterior body cut contained small backwards angular notches. Connecting one of these to the sparse first bridge ring produced an almost 180° fold and a visible black slit despite having no open edges. `smooth_bare_neck_boundary` now regularizes only local posterior notch neighborhoods, preserving topological order. Its additional displacement is capped at 6 mm and fades to the next two body rings at 0.45/0.15. The independent before/after check finds 117 original body vertices moved by more than 0.1 µm; body topology and UVs remain unchanged. Suit/sport never call this helper and receive no new contour correction.

## Measurements and verification

| Measurement | Uniform + pitch | Selected cranium correction | Final fit |
|---|---:|---:|---:|
| Crown-to-chin height | 0.24830 m | 0.23890 m | 0.23890 m |
| Crown-to-eye fraction of head height | 62.73% | 56.61% | 52.32% |
| Eye-to-chin height | 0.09255 m | 0.10366 m | 0.11390 m |

Final mean pupil height is 1.724998 m, chin is 1.611099 m and crown is 1.850000 m. Head height is 12.91% of the 1.85 m body, close to the independent approximately 13.1% reference estimate. The head's full hair bounding width remains 0.23897 m; ear-center span is 0.19134 m. The last fit did not reduce width. The facial and reference landmarks are manual estimates projected onto the actual mesh and UV texture, not anatomical ground truth.

The posterior correction reduces measured nose-to-back depth from 0.27749 to 0.23500 m; maximum backward-surface displacement is 0.04249 m. The large hair mass and low eye placement are visibly reduced compared with the uniform-pitch candidate. The approved front references support the vertical proportion correction; they do not validate the inferred rear shape.

`StudyData/avatar-v3/neck-candidate/final-neck-validation.json` records the preceding three-outfit GLB/FBX checks using Blender Python 4.5.3 LTS. The bare-only replacement is checked by `bare-neck-contour-fixed-validation.json` and its `bounded-change-and-fold-check.json`:

- All three uncut global head prototypes have SHA256 `cd5620ad552acca80aeee44e127ea3d5c8e3263363ca885333a72eb713747695`.
- The preceding transform script SHA256 is `d884b8286b53b7f60acbff77afc6886204e3ceabbdad69b962d3978306e6f655`; the replacement report records each candidate's actual script hash separately. The head prototype hash is unchanged.
- Each FBX reimports at approximately 0–1.85 m, with its outfit and glasses groups intact.
- The suit/sport/none atlases respectively cover 2799/2781/2818 bridge triangles. All bridge boundary-edge and degenerate-face counts are zero.
- The embedded GLB atlas bytes match the source PNG exactly. FBX reimport resolves the same sRGB PNG, with UVs and texture connections present.
- Atlas PNG save/reload has zero 8-bit RGB error; original body/head geometry, UVs and material assignments are unchanged by the atlas baking step.
- All three saved source meshes have `has_custom_normals=False`; stale imported custom split normals are not retained at the neck seam.

The earlier suit's horizontal shadow band was geometrical: the emission-only diagnostic had approximately 1.3/255 mean RGB mismatch at the seam, while the median adjacent face-normal angle was approximately 71°. Raising the front cut and matching the neck tangent reduced the measured angles:

| Outfit | Median | 95th percentile | Maximum |
|---|---:|---:|---:|
| Suit | 8.18° | 21.94° | 33.16° |
| Sport | 8.54° | 16.30° | 21.96° |
| None | 5.60° | 13.11° | 16.17° |

The diagnostic image and per-edge RGB/normal records are in `neck-candidate/suit-shading-diagnostic/`. This distinguishes texture continuity from geometric smoothness instead of treating zero open edges as sufficient visual evidence.

The bare-only replacement has zero nonadjacent bridge-versus-model triangle intersections in the BVH and strict edge/triangle check. It still has a few sharp local creases: posterior lower-fan edges above 150° decrease from eight to one, and the maximum decreases from 179.68° to 158.30°. Across the full lower fan, seven edges remain above 150°. These are reported explicitly rather than described as a globally smooth or fold-free mesh. The demonstrated rear-shoulder black slit disappears in the actual side render. The 72,699 head/hair faces above 1.68 m retain exactly the same position/UV hash; the shared complete pre-cut head prototype hash also remains unchanged.

The head geometry and neck positions are identical across outfits before collar-specific cutting. No Unity process or new generation model was launched by this candidate task.

## Reproduction and remaining limits

From the remote project root:

```bash
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/fit_landmark_head_candidate.py --outfit suit --out StudyData/avatar-v3/neck-candidate/final-neck-suit
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/fit_landmark_head_candidate.py --outfit sport --out StudyData/avatar-v3/neck-candidate/final-neck-sport
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/fit_landmark_head_candidate.py --outfit none --out StudyData/avatar-v3/neck-candidate/bare-neck-contour-fixed
Builds/AvatarTools/venv/bin/python Builds/AvatarTools3D/validate_bare_neck_contour.py
Builds/AvatarTools/venv/bin/python Builds/AvatarTools3D/validate_final_landmark_candidate.py --none-dir StudyData/avatar-v3/neck-candidate/bare-neck-contour-fixed
```

Execution logs are `Builds/AvatarTools3D/logs/final-neck-{suit,sport,none,validation}.log`. The saved native `.blend` files include diagnostic landmark empties and the review camera; these empties are excluded from the FBX/GLB exports.

The source reconstruction still has thick hair strands and soft body textures. Very close suit/sport views reveal residual collar texture jaggedness. The nape hairline is rather straight and its color depends on the different source body's skin. The bare outfit retains a small approximately 1–2 mm anterior cut-edge tooth near pixel `(445, 900)` in `bare-neck-contour-fixed/side-face.png`. The triangular neck wings and demonstrated rear black slit are removed; this is not a claim that every tiny crease is eliminated. The parent task accepted the corrected candidate silhouette and will inspect the native Blender 5.2 production export in Unity.
