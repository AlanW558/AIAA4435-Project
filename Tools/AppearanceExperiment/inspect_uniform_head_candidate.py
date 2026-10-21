#!/usr/bin/env python3
"""Render a separate suit candidate with native, uniformly scaled head shape."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import bpy
import bmesh
import numpy as np

import repair_neck_candidate as repair

ROOT = Path(__file__).resolve().parents[2]


def retain_connected_head(obj):
    """Weld geometry while preserving per-loop UVs, then remove real floaters."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    unseen, components = set(bm.verts), []
    while unseen:
        first = unseen.pop()
        group, pending = {first}, [first]
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in unseen:
                    unseen.remove(other)
                    group.add(other)
                    pending.append(other)
        components.append(group)
    keep = max(components, key=len)
    remove = [vertex for vertex in bm.verts if vertex not in keep]
    report = {"connected_components": len(components), "removed_floating_vertices": len(remove),
              "retained_vertices": len(keep), "loop_uv_preserved": bm.loops.layers.uv.active is not None}
    bmesh.ops.delete(bm, geom=remove, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "StudyData/avatar-v3/neck-candidate/uniform-head-suit")
    parser.add_argument("--head-height", type=float, default=.315)
    parser.add_argument("--head-top", type=float, default=1.85)
    parser.add_argument("--eye-z", type=float)
    parser.add_argument("--pitch-degrees", type=float, default=0)
    args = parser.parse_args()
    out = args.out.resolve()
    assert "neck-candidate" in out.parts
    out.mkdir(parents=True, exist_ok=True)
    textures = out / "Textures"
    textures.mkdir(exist_ok=True)
    base = repair._load_base()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generated = ROOT / "StudyData/avatar-v3/generated"
    head = base.load_mesh(generated / "liang-head/textured.glb", "Uniform head prototype",
                          args.head_height)
    cleanup = retain_connected_head(head)
    native = base.coordinates(head)
    # This is the actual low neck, below the native chin around z=.052.
    low_neck = native[(native[:, 2] > .025) & (native[:, 2] < .045)]
    source_axis = (low_neck[:, :2].min(axis=0) + low_neck[:, :2].max(axis=0)) / 2
    pivot = np.r_[source_axis, .035]
    angle = math.radians(args.pitch_degrees)
    rotation = np.array([[1., 0., 0.], [0., math.cos(angle), -math.sin(angle)],
                         [0., math.sin(angle), math.cos(angle)]])
    rotated = (native-pivot) @ rotation.T
    uniform_scale = args.head_height / np.ptp(rotated[:, 2])
    rotated *= uniform_scale
    body = base.load_mesh(generated / "liang/textured.glb", "Uniform suit body", 1.85)
    base.bind_texture(body, "Tint_LiangSuit_Reference", textures, False, "blue-cloth")
    base.remove_old_head(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    ring, _ = base.neck_ring(bm)
    collar = np.array([tuple(v.co) for v in ring])
    target_axis = (collar[:, :2].min(axis=0) + collar[:, :2].max(axis=0)) / 2
    bm.free()
    translation = np.r_[target_axis, args.head_top-rotated[:, 2].max()]
    points = rotated + translation
    native_eye_band = native[(np.abs(native[:, 2]-.1375) < .008) &
                             (np.abs(native[:, 0]-source_axis[0]) > .025) &
                             (np.abs(native[:, 0]-source_axis[0]) < .060)]
    eye_anchor = np.array([source_axis[0], np.quantile(native_eye_band[:, 1], .10), .1375])
    eye_anchor = ((eye_anchor-pivot) @ rotation.T) * uniform_scale + translation
    eye_z = args.eye_z if args.eye_z is not None else float(eye_anchor[2])
    cheek_normals = [tuple(face.normal) for face in head.data.polygons
                     if .115 < face.center.z < .145 and face.center.y < -.065
                     and .025 < abs(face.center.x-source_axis[0]) < .060]
    native_normal = np.mean(cheek_normals, axis=0)
    native_normal /= np.linalg.norm(native_normal)
    base.put_coordinates(head, points)
    base.bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
    projection_mesh = head.data.copy()
    fitted = head.copy()
    fitted.data = head.data.copy()
    bpy.context.collection.objects.link(fitted)
    cut = repair.cut_head_above_collar(fitted, body, 1.55, neck_axis_xy=target_axis)
    bridge = repair.connect_neck(body, fitted, 7, projection_mesh)
    bpy.data.objects.remove(fitted, do_unlink=True)
    root = base.empty("UniformHeadCandidate")
    base.keep_world_parent(body, root)
    # The fitting routine derives frame position from the real head surface.
    # Its eye-height input is separately reported; no old fixed 1.739 is used.
    cheek = points[(np.abs(points[:, 2]-eye_z) < .010) &
                   (np.abs(points[:, 0]-target_axis[0]) > .025) &
                   (np.abs(points[:, 0]-target_axis[0]) < .07)]
    eye_y = float(np.quantile(cheek[:, 1], .04)) - .003
    glasses = base.empty("Uniform glasses", root)
    base.glasses(glasses, (float(target_axis[0]), eye_y, eye_z),
                 width=.145, temple_spread=.015, head_surface=head)
    bpy.data.objects.remove(head, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (root, *root.children_recursive):
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "Liang-uniform-head.glb"),
                              export_format="GLB", use_selection=True, export_apply=True)
    report = {
        "native_head_total_height_m": args.head_height,
        "head_geometry_cleanup": cleanup,
        "native_head_xyz_scaled_identically": True,
        "pitch_about_neck_root_degrees": args.pitch_degrees,
        "post_rotation_uniform_scale": float(uniform_scale),
        "rotation_pivot_native": pivot.tolist(),
        "head_translation_xyz_m": translation.tolist(),
        "source_low_neck_band_m": [.025, .045],
        "source_low_neck_axis_xy": source_axis.tolist(),
        "target_collar_axis_xy": target_axis.tolist(),
        "head_bounds_after_translation": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
        "eye_frame_center_z_m": eye_z,
        "eye_height_method": "native eye-band anchor transformed rigidly with head",
        "native_cheek_mean_normal": native_normal.tolist(),
        "transformed_cheek_mean_normal": (rotation @ native_normal).tolist(),
        "cut": cut, "bridge": bridge,
        "source_head_sha256": hashlib.sha256((generated / "liang-head/textured.glb").read_bytes()).hexdigest(),
        "source_body_sha256": hashlib.sha256((generated / "liang/textured.glb").read_bytes()).hexdigest(),
        "note": "Independent geometry comparison; atlas off and no main staging/Assets changes.",
    }
    (out / "diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    repair.render_review(out)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "candidate.blend"))


if __name__ == "__main__":
    main()
