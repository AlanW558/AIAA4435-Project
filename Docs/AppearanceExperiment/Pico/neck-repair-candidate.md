# Independent neck bridge candidate

The candidate is implemented in
`Tools/AppearanceExperiment/repair_neck_candidate.py`. It does not edit the main
assembler or `unity-staging/AvatarDemo`. Its outputs are under
`StudyData/avatar-v3/neck-candidate/`.

## Cause established from the real boundaries

The original bridge started both rings at their independent minimum-Y vertex.
The collar's start was `(0.0538, -0.0611, 1.5712)` while the head's was
`(-0.0172, -0.0467, 1.6000)`. These points are at different anatomical angles.
The collar's 3D perimeter was 0.799 m, including its height changes and jagged
edge, versus 0.444 m for the head. Matching normalized 3D arc length therefore
pulled the front skin diagonally around the neck.

The collar spans Z=1.5567–1.6415 m. A horizontal head cut at 1.60 m puts the
upper bridge below the rear collar; raising the whole plane to 1.647 m instead
clips the chin. The bridge also used one texture coordinate for every corner,
which created a large flat color band even after its geometry was smoothed.

## Candidate and actual checks

1. `angular_positions` preserves the existing topological edge order, rotates
   the start to the front, and uses unwrapped anatomical angles. Local backwards
   steps are clamped in the parameter, without reordering the mesh vertices.
2. `cut_head_above_collar` uses a smooth collar-height envelope. It cuts at
   1.603 m in front and about 1.6534 m behind for the suit, preserving the jaw
   while keeping the back bridge above the collar. A reversible Z-coordinate
   warp lets Blender's plane bisector retain face/UV interpolation.
3. `connect_neck` inserts seven smoothed interior rings with 128 samples each.
   Both original boundary loops remain fixed and retain their true edge order.
4. The bridge UVs project onto the unchanged, **uncut** detailed head. Faces
   spanning distant atlas islands use a local center sample to avoid sampling
   unrelated atlas regions.

The inspected suit result is:
`neck-candidate/collar-following/{face,front,side}.png`.
It has 2,198 bridge triangles, zero bridge boundary edges and zero degenerate
bridge faces. The rendered jaw is intact, the neck is continuous, and the
diagonal scarf-like fold is gone.

Close views still show some projected texture patches and a color/texture seam
where the generated head meets the original chest. This candidate addresses
the geometry failure; it does not claim a seamless close-up scan. Its glasses
are the old reference version; the main task has a separate fit correction.

## Minimal integration

Keep the transformed detailed head **uncut** as the common source. Remove the
old global `cut_at(head, 1.60, keep_below=False)` call. After `remove_old_head`
for each body variant, make a temporary copy and call:

```python
from repair_neck_candidate import cut_head_above_collar
from repair_neck_candidate import connect_neck as connect_candidate_neck

variant_head = head.copy()
variant_head.data = head.data.copy()
bpy.context.collection.objects.link(variant_head)
cut_head_above_collar(variant_head, body, minimum_height=1.603)
report = connect_candidate_neck(
    body, variant_head, intermediate_rings=7, projection_mesh=head.data
)
bpy.data.objects.remove(variant_head, do_unlink=True)
```

The source head must already use the `Fixed_Liang_DetailedHead` material, as in
the main assembler. Its uncut mesh remains available for glasses fitting and
for each subsequent clothing variant. These helpers return measured geometry
diagnostics; they assert that new bridge faces have no open edge or zero area.

To reproduce the independent suit render in the remote project:

```bash
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/repair_neck_candidate.py --out StudyData/avatar-v3/neck-candidate/collar-following --cut-height 1.603 --rings 7 --project-uv --collar-following-cut
```

The diagnostic-only run on all three outfit sources is recorded separately in
`neck-candidate/all-outfits-validation.json`. Rendering uses Blender 4.5.3,
Cycles CPU, 24 samples. No GPU inference, model download or Unity process is
started by this candidate.
