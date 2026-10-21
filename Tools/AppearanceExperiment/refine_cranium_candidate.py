#!/usr/bin/env python3
"""One isolated, measured upper-cranium correction with native face protection."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inspect_uniform_head_candidate as uniform
import repair_neck_candidate as repair

ROOT = Path(__file__).resolve().parents[2]


def face_camera():
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 1024, 1280
    scene.render.resolution_percentage = 100
    data = bpy.data.cameras.new("Landmark measurement camera")
    obj = bpy.data.objects.new("Landmark measurement camera", data)
    bpy.context.collection.objects.link(obj)
    obj.location = (0, -5.55, 1.665)
    obj.rotation_euler = (Vector((0, 0, 1.665))-obj.location).to_track_quat("-Z", "Y").to_euler()
    data.type, data.ortho_scale = "ORTHO", .555
    bpy.context.view_layer.update()
    return obj


def project_pixel(camera, point):
    coordinate = world_to_camera_view(bpy.context.scene, camera, Vector(point))
    return [float(coordinate.x*1024), float((1-coordinate.y)*1280)]


def source_landmarks(head, camera, extra_pixels=None):
    """Ray-pick actual surface/UVs; pupil ROIs are manually located in real PNG."""
    mesh = head.data
    vertices = [vertex.co.copy() for vertex in mesh.vertices]
    triangles = [tuple(face.vertices) for face in mesh.polygons]
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    uv = mesh.uv_layers.active.data
    images = {}
    for index, mat in enumerate(mesh.materials):
        image = next(node.image for node in mat.node_tree.nodes
                     if node.type == "TEX_IMAGE" and node.image)
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        images[index] = (image, pixels.reshape(image.size[1], image.size[0], 4))
    frame = camera.data.view_frame(scene=bpy.context.scene)
    xmin, xmax = min(p.x for p in frame), max(p.x for p in frame)
    ymin, ymax = min(p.y for p in frame), max(p.y for p in frame)
    direction = camera.matrix_world.to_3x3() @ Vector((0, 0, -1))

    def pick(x, y):
        local = Vector((xmin+(x+.5)/1024*(xmax-xmin),
                        ymax-(y+.5)/1280*(ymax-ymin), 0))
        origin = camera.matrix_world @ local
        location, normal, index, distance = tree.ray_cast(origin, direction, 20)
        if location is None:
            return None
        face = mesh.polygons[index]
        a, b, c = [vertices[i] for i in face.vertices]
        texture_uv = [Vector((*uv[i].uv, 0.0)) for i in face.loop_indices]
        texture_point = barycentric_transform(location, a, b, c, *texture_uv).xy
        image, pixels = images[face.material_index]
        ix = int(texture_point.x*image.size[0]) % image.size[0]
        iy = int(texture_point.y*image.size[1]) % image.size[1]
        color = pixels[iy, ix, :3]
        return {
            "image_pixel_xy": [float(x), float(y)], "position_xyz_m": list(location),
            "normal_xyz": list(normal), "source_triangle": index,
            "source_uv": list(texture_point), "source_color_srgb": color.tolist(),
            "source_image": image.name,
            "luminance": float(color @ np.array([.2126, .7152, .0722])),
        }

    results = {}
    # These ROIs come from the inspected 1024x1280 pitch15 face render. Search
    # the embedded albedo, not the specular/glasses pixels in the beauty render.
    for name, bounds in {
        "left_pupil": (422, 440, 573, 582),
        "right_pupil": (565, 581, 568, 579),
    }.items():
        x0, x1, y0, y1 = bounds
        samples = [pick(x, y) for y in range(y0, y1) for x in range(x0, x1)]
        samples = [sample for sample in samples if sample is not None]
        threshold = np.quantile([sample["luminance"] for sample in samples], .15)
        dark = [sample for sample in samples if sample["luminance"] <= threshold]
        center = np.mean([sample["image_pixel_xy"] for sample in dark], axis=0)
        result = pick(*center)
        result["method"] = "darkest 15% albedo centroid within manually verified pupil ROI"
        result["manual_roi_xyxy"] = list(bounds)
        results[name] = result
    manual_pixels = {
        "left_eyebrow": (433, 545),
        "right_eyebrow": (570, 543),
        "central_hairline": (507, 499),
        "chin_surface": (502, 782),
    }
    manual_pixels.update(extra_pixels or {})
    for name, pixel in manual_pixels.items():
        result = pick(*pixel)
        assert result is not None, name
        result["method"] = "manual visible landmark raycast onto actual textured head"
        results[name] = result
    crown = max(vertices, key=lambda point: point.z)
    results["crown"] = {"position_xyz_m": list(crown),
                        "image_pixel_xy": project_pixel(camera, crown),
                        "method": "maximum Z vertex of cleaned connected head"}
    # Silhouette chin endpoint lies a few pixels below its stable surface pick.
    # Its Z is exact for this orthographic camera; depth is inherited from the
    # adjacent chin surface pick and is not claimed as an anatomical landmark.
    chin = results["chin_surface"]["position_xyz_m"].copy()
    chin[2] = 1.665+(640-786)*.555/1280
    results["chin_contour"] = {"position_xyz_m": chin, "image_pixel_xy": [502, 786],
                              "method": "manual silhouette endpoint; orthographic Z, adjacent surface depth"}
    return results


def refine_upper_cranium(points, axis_xy, brow_z, crown_drop=.035):
    """Smooth lattice-like offsets above protected facial/auricular vertices."""
    original = np.asarray(points).copy()
    start_z = float(brow_z + .014)
    crown_z = float(original[:, 2].max())

    def smooth(value):
        value = np.clip(value, 0, 1)
        return value*value*(3-2*value)

    level = smooth((original[:, 2]-start_z)/(crown_z-start_z))
    result = original.copy()
    result[:, 2] -= crown_drop*level
    # The width correction acts only on the high hair mass; lower face/ears
    # receive exactly zero local displacement.
    result[:, 0] = axis_xy[0]+(original[:, 0]-axis_xy[0])*(1-.045*level)
    back = smooth((original[:, 1]-(axis_xy[1]+.045))/.085)
    result[:, 1] -= .012*back*level
    protected = original[:, 2] <= start_z
    displacement = np.linalg.norm(result-original, axis=1)
    assert np.max(displacement[protected]) == 0
    return result, {
        "upper_cranium_start_z_m": start_z,
        "original_crown_z_m": crown_z,
        "crown_down_m": crown_drop, "maximum_upper_lateral_contraction": .045,
        "maximum_posterior_contraction_m": .012,
        "protected_vertex_count": int(protected.sum()),
        "protected_local_max_displacement_m": float(np.max(displacement[protected])),
        "protected_geometry_sha256": hashlib.sha256(original[protected].tobytes()).hexdigest(),
        "maximum_local_displacement_m": float(displacement.max()),
        "local_deformation": "smooth cubic falloff above eyebrows +14mm, zero below",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "StudyData/avatar-v3/neck-candidate/refined-cranium-suit")
    args = parser.parse_args()
    out = args.out.resolve()
    assert "neck-candidate" in out.parts
    out.mkdir(parents=True, exist_ok=True)
    textures = out / "Textures"
    textures.mkdir(exist_ok=True)
    base = repair._load_base()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generated = ROOT / "StudyData/avatar-v3/generated"
    head = base.load_mesh(generated / "liang-head/textured.glb", "Measured cranium source", .315)
    cleanup = uniform.retain_connected_head(head)
    native = base.coordinates(head)
    low_neck = native[(native[:, 2] > .025) & (native[:, 2] < .045)]
    source_axis = (low_neck[:, :2].min(axis=0)+low_neck[:, :2].max(axis=0))/2
    pivot = np.r_[source_axis, .035]
    angle = math.radians(-15)
    rotation = np.array([[1., 0., 0.], [0., math.cos(angle), -math.sin(angle)],
                         [0., math.sin(angle), math.cos(angle)]])
    rotated = (native-pivot) @ rotation.T
    rotated *= .315/np.ptp(rotated[:, 2])
    body = base.load_mesh(generated / "liang/textured.glb", "Refined suit body", 1.85)
    base.bind_texture(body, "Tint_LiangSuit_Reference", textures, False, "blue-cloth")
    base.remove_old_head(body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    ring, _ = base.neck_ring(bm)
    collar = np.array([tuple(vertex.co) for vertex in ring])
    target_axis = (collar[:, :2].min(axis=0)+collar[:, :2].max(axis=0))/2
    bm.free()
    neck_pivot_world = np.r_[target_axis, 1.85-rotated[:, 2].max()]
    original = rotated+neck_pivot_world
    base.put_coordinates(head, original)
    camera = face_camera()
    landmarks = source_landmarks(head, camera)
    brow_z = max(landmarks[name]["position_xyz_m"][2]
                 for name in ("left_eyebrow", "right_eyebrow"))
    local, sculpt_report = refine_upper_cranium(original, target_axis, brow_z)
    overall_scale = 1.12
    scaled = (local-neck_pivot_world)*overall_scale+neck_pivot_world
    vertical_translation = 1.85-scaled[:, 2].max()
    final = scaled+np.array([0, 0, vertical_translation])
    base.put_coordinates(head, final)
    transformed_landmarks = {}
    for name, landmark in landmarks.items():
        point = np.asarray(landmark["position_xyz_m"])
        if name == "crown":
            point = final[np.argmax(final[:, 2])]
        else:
            if name != "central_hairline":
                assert point[2] <= sculpt_report["upper_cranium_start_z_m"], name
            start = sculpt_report["upper_cranium_start_z_m"]
            fraction = np.clip((point[2]-start)/(1.85-start), 0, 1)
            level = fraction*fraction*(3-2*fraction)
            back = np.clip((point[1]-(target_axis[1]+.045))/.085, 0, 1)
            back = back*back*(3-2*back)
            point[2] -= .035*level
            point[0] = target_axis[0]+(point[0]-target_axis[0])*(1-.045*level)
            point[1] -= .012*back*level
            point = (point-neck_pivot_world)*overall_scale+neck_pivot_world
            point[2] += vertical_translation
        transformed_landmarks[name] = {"position_xyz_m": point.tolist(),
                                       "image_pixel_xy": project_pixel(camera, point)}
        marker = base.empty("Landmark_" + name)
        marker.location = point
        marker.empty_display_type, marker.empty_display_size = "SPHERE", .002
        marker.show_name, marker.hide_render = True, True
    eye_z = float(np.mean([transformed_landmarks[name]["position_xyz_m"][2]
                           for name in ("left_pupil", "right_pupil")]))
    base.bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
    projection_mesh = head.data.copy()
    fitted = head.copy()
    fitted.data = head.data.copy()
    bpy.context.collection.objects.link(fitted)
    cut = repair.cut_head_above_collar(fitted, body, 1.55, neck_axis_xy=target_axis)
    bridge = repair.connect_neck(body, fitted, 7, projection_mesh,
                                 transition_texture_dir=textures,
                                 neck_material_name="Fixed_LiangNeck_suit")
    bpy.data.objects.remove(fitted, do_unlink=True)
    root = base.empty("RefinedCraniumCandidate")
    base.keep_world_parent(body, root)
    cheek = final[(np.abs(final[:, 2]-eye_z) < .010) &
                  (np.abs(final[:, 0]-target_axis[0]) > .025) &
                  (np.abs(final[:, 0]-target_axis[0]) < .075)]
    eye_y = float(np.quantile(cheek[:, 1], .04))-.003
    glasses = base.empty("Refined glasses", root)
    base.glasses(glasses, (float(target_axis[0]), eye_y, eye_z),
                 width=.145*overall_scale, lens_height=.035, temple_spread=.015,
                 head_surface=head)
    bpy.data.objects.remove(head, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (root, *root.children_recursive):
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "Liang-refined-cranium.glb"),
                              export_format="GLB", use_selection=True, export_apply=True)
    ratios = {}
    for name, marked in [("pitch15_baseline", landmarks), ("local_cranium_candidate", transformed_landmarks)]:
        top = marked["crown"]["position_xyz_m"][2]
        eye = np.mean([marked[key]["position_xyz_m"][2] for key in ("left_pupil", "right_pupil")])
        chin = marked["chin_contour"]["position_xyz_m"][2]
        ratios[name] = {"head_height_m": float(top-chin), "crown_to_eye_m": float(top-eye),
                         "eye_to_chin_m": float(eye-chin),
                         "crown_to_eye_fraction": float((top-eye)/(top-chin)),
                         "head_height_over_body": float((top-chin)/1.85)}
    report = {
        "head_geometry_cleanup": cleanup, "baseline_surface_landmarks": landmarks,
        "candidate_landmarks": transformed_landmarks, "measured_ratios": ratios,
        "local_cranium_sculpt": sculpt_report, "uniform_scale_after_local_correction": overall_scale,
        "uniform_vertical_translation_after_scale_m": float(vertical_translation),
        "source_neck_pivot_world": neck_pivot_world.tolist(), "eye_frame_center_z_m": eye_z,
        "target_collar_axis_xy": target_axis.tolist(), "cut": cut, "bridge": bridge,
        "reference_eye_fraction": [.50, .53],
        "reference_head_height_over_body": [.131, .132],
        "reference_measurement_file": "StudyData/avatar-v3/proportion-review/reference-measurements.json",
        "note": "One measured compromise; unchanged face shape locally, not a claim of exact reference match.",
    }
    (out / "landmarks-and-diagnostic.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report), flush=True)
    bpy.data.objects.remove(camera, do_unlink=True)
    repair.render_review(out)
    scene = bpy.context.scene
    camera = scene.camera
    camera.location = (5.55, 0, 1.665)
    camera.rotation_euler = (Vector((0, 0, 1.665))-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = .555
    scene.render.filepath = str(out / "side-face.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "candidate.blend"))


if __name__ == "__main__":
    main()
