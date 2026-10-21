#!/usr/bin/env python3
"""Compare the previous face proportions with corrected size and a short neck."""
import json
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repair_neck_candidate as repair
from inspect_uniform_head_candidate import retain_connected_head

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = repair._load_base()
    out = ROOT / "StudyData/avatar-v3/neck-candidate/reference-fit-suit"
    out.mkdir(parents=True, exist_ok=True)
    textures = out / "Textures"
    textures.mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generated = ROOT / "StudyData/avatar-v3/generated"
    head = base.load_mesh(generated / "liang-head/textured.glb", "Reference-fit head", .335)
    cleanup = retain_connected_head(head)
    native = base.coordinates(head)
    points = native.copy()
    neck = native[(native[:, 2] > .025) & (native[:, 2] < .045)]
    axis = (neck[:, :2].min(axis=0) + neck[:, :2].max(axis=0)) / 2
    # This is a diagnostic of the earlier face profile, not a new approved asset.
    # Neck vertices below the collar are removed and rebuilt instead of stretched.
    points[:, 0] = (points[:, 0] - axis[0]) * .92 * 1.12
    points[:, 1] = (points[:, 1] - axis[1]) * 1.05 * 1.12
    points[:, 2] = np.interp(points[:, 2], [0, .025, .06, .12, .15, .335],
                             [1.525, 1.56, 1.65, 1.72, 1.745, 1.85])
    points[:, 2] = 1.85 + 1.12 * (points[:, 2] - 1.85)
    body = base.load_mesh(generated / "liang/textured.glb", "Reference-fit suit", 1.85)
    base.bind_texture(body, "Tint_LiangSuit_Reference", textures, False, "blue-cloth")
    base.remove_old_head(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    boundary, _ = base.neck_ring(bm)
    collar = np.array([tuple(v.co) for v in boundary])
    target = (collar[:, :2].min(axis=0) + collar[:, :2].max(axis=0)) / 2
    bm.free()
    points[:, :2] += target
    base.put_coordinates(head, points)
    base.bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
    projection = head.data.copy()
    fitted = head.copy()
    fitted.data = head.data.copy()
    bpy.context.collection.objects.link(fitted)
    cut = repair.cut_head_above_collar(fitted, body, 1.55, neck_axis_xy=target)
    bridge = repair.connect_neck(body, fitted, 7, projection,
                                 transition_texture_dir=textures)
    bpy.data.objects.remove(fitted, do_unlink=True)
    root = base.empty("UniformHeadCandidate")
    base.keep_world_parent(body, root)
    eye_z = 1.7364
    glasses = base.empty("Reference-fit glasses", root)
    base.glasses(glasses, (float(target[0]), -.075, eye_z), width=.157,
                 temple_spread=.015, head_surface=head)
    bpy.data.objects.remove(head, do_unlink=True)
    report = {"status": "diagnostic only; not accepted",
              "head_cleanup": cleanup, "head_uniform_scale_after_profile": 1.12,
              "head_bounds": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
              "eye_z_approximate": eye_z, "cut": cut, "bridge": bridge}
    (out / "diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    repair.render_review(out)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "candidate.blend"))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
