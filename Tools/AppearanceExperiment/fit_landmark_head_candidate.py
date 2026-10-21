#!/usr/bin/env python3
"""Final isolated landmark fit, shared head prototype and outfit neck atlases."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inspect_uniform_head_candidate as uniform
import refine_cranium_candidate as cranium
import repair_neck_candidate as repair

ROOT = Path(__file__).resolve().parents[2]
SUIT_NECK_AXIS = np.array([-.0031917989253997803, .01932954043149948])


def smoothstep(value):
    value = np.clip(value, 0, 1)
    return value*value*(3-2*value)


def fit_face_and_posterior(points, landmarks, neck_axis_xy, target_eye_z=1.725):
    """C1 face-height adjustment plus a separate posterior-depth correction."""
    points = np.asarray(points, dtype=np.float64)
    chin = float(landmarks["chin_contour"]["position_xyz_m"][2])
    eye = float(np.mean([landmarks[name]["position_xyz_m"][2]
                         for name in ("left_pupil", "right_pupil")]))
    crown = float(points[:, 2].max())
    multiplier = (target_eye_z-chin)/(eye-chin)
    delta = target_eye_z-eye
    ears = np.array([landmarks[name]["position_xyz_m"] for name in ("left_ear", "right_ear")])
    axis = np.asarray(neck_axis_xy)

    def vertical_delta(z):
        z = np.asarray(z, dtype=np.float64)
        distance = np.maximum(z-chin, 0)
        lower = (multiplier-1)*distance*smoothstep(distance/.015)
        t = np.clip((z-eye)/(crown-eye), 0, 1)
        # Cubic Hermite displacement matches the lower-face derivative at the
        # eye anchor and returns to zero displacement and slope at the crown.
        upper = ((2*t**3-3*t**2+1)*delta
                 + (t**3-2*t**2+t)*(crown-eye)*(multiplier-1))
        return np.where(z <= chin, 0, np.where(z < eye, lower,
                                              np.where(z < crown, upper, 0)))

    def ear_guard(values):
        guard = np.ones(len(values), dtype=np.float64)
        for center in ears:
            radius = np.linalg.norm((values-center)/np.array([.023, .030, .037]), axis=1)
            guard *= smoothstep((radius-1)/.45)
        return guard

    def face_weight(values):
        front = 1-smoothstep((values[:, 1]-(axis[1]-.035))/.030)
        side = 1-smoothstep((np.abs(values[:, 0]-axis[0])-.070)/.020)
        return front*side*ear_guard(values)

    def apply_face(values):
        output = np.asarray(values, dtype=np.float64).copy()
        output[:, 2] += vertical_delta(output[:, 2])*face_weight(output)
        return output

    face = apply_face(points)
    nose_band = ((np.abs(face[:, 0]-axis[0]) < .025)
                 & (face[:, 2] > chin+.045) & (face[:, 2] < target_eye_z+.002))
    nose_candidates = face[nose_band]
    nose_tip = nose_candidates[np.argmin(nose_candidates[:, 1])]
    before_depth = float(face[:, 1].max()-nose_tip[1])
    target_depth = .235
    fixed_y = float(ears[:, 1].max()+.025)
    back_max = float(face[:, 1].max())

    def posterior_weight(values):
        depth = smoothstep((values[:, 1]-fixed_y)/max(back_max-fixed_y, .001))
        height = smoothstep((values[:, 2]-chin)/.025)
        return depth*height*ear_guard(values)

    back_weight = posterior_weight(face)
    # Solve a single scalar displacement against the actual nose/back extrema.
    # The target depth is a modeling inference: no approved side photo exists.
    low, high = 0., .065
    for _ in range(32):
        amplitude = (low+high)/2
        depth = float(np.max(face[:, 1]-amplitude*back_weight)-nose_tip[1])
        if depth > target_depth:
            low = amplitude
        else:
            high = amplitude
    amplitude = high if before_depth > target_depth else 0.
    assert amplitude < .0649, "Requested depth needs a larger posterior change than this candidate permits"

    def apply_all(values):
        output = apply_face(values)
        output[:, 1] -= amplitude*posterior_weight(output)
        return output

    result = apply_all(points)
    fitted_landmarks = {}
    for name, landmark in landmarks.items():
        point = apply_all(np.asarray([landmark["position_xyz_m"]]))[0]
        fitted_landmarks[name] = {"position_xyz_m": point.tolist()}
    neck = points[:, 2] <= chin
    assert np.array_equal(points[neck], result[neck]), "Landmark fit changed the neck below the chin"
    for name in ("left_ear", "right_ear", "chin_contour"):
        assert np.allclose(fitted_landmarks[name]["position_xyz_m"],
                           landmarks[name]["position_xyz_m"], atol=1e-12), name
    before_nose = np.array(landmarks["nose_tip"]["position_xyz_m"])
    before_lip = np.array(landmarks["lip_center"]["position_xyz_m"])
    after_nose = np.array(fitted_landmarks["nose_tip"]["position_xyz_m"])
    after_lip = np.array(fitted_landmarks["lip_center"]["position_xyz_m"])
    nose_lip_scale = float((after_nose[2]-after_lip[2])/(before_nose[2]-before_lip[2]))
    assert abs(nose_lip_scale-multiplier) < 1e-5, "Nose/lip relative vertical ratio was changed"
    samples = np.linspace(chin-.01, crown+.01, 2001)
    mapped = samples+vertical_delta(samples)
    assert np.all(np.diff(mapped) > 0), "Vertical fit folds over"
    derivative_checks = {}
    epsilon = 1e-6
    for name, z in (("chin", chin), ("eyes", eye), ("crown", crown)):
        left = float(1+(vertical_delta(z)-vertical_delta(z-epsilon))/epsilon)
        right = float(1+(vertical_delta(z+epsilon)-vertical_delta(z))/epsilon)
        assert abs(left-right) < .001
        derivative_checks[name] = {"left": left, "right": right}
    report = {
        "fixed_chin_z_m": chin, "original_eye_z_m": eye, "target_eye_z_m": target_eye_z,
        "linear_lower_face_vertical_multiplier": multiplier,
        "nose_to_lip_vertical_multiplier_measured": nose_lip_scale,
        "lower_chin_transition_m": .015, "c1_derivatives": derivative_checks,
        "neck_below_chin_unchanged": True,
        "neck_before_after_sha256": hashlib.sha256(points[neck].tobytes()).hexdigest(),
        "ear_centers_unchanged": True,
        "posterior_inference": "No approved side reference; 0.235m nose-to-occiput target is a modeling inference.",
        "nose_tip_geometry_xyz_m": nose_tip.tolist(),
        "nose_to_back_depth_before_m": before_depth,
        "nose_to_back_depth_after_m": float(result[:, 1].max()-nose_tip[1]),
        "posterior_max_displacement_m": amplitude,
        "posterior_fixed_y_plane_m": fixed_y,
        "posterior_height_start_z_m": chin,
        "posterior_height_full_z_m": chin+.025,
        "front_face_depth_unchanged": True,
    }
    return result, fitted_landmarks, report


def prepare_reference_head(head, neck_axis_xy=SUIT_NECK_AXIS):
    """Complete reusable transform for the original head normalized to .315m.

    Inputs are the unchanged liang-head/textured.glb mesh loaded through the
    assembler's load_mesh(height=.315), with its existing UV/material. It
    cleans genuine floaters, poses the head, corrects the high hair mass, and
    fits facial landmarks. Call once for a shared prototype, then copy it for
    outfit-specific collar cuts. No existing body/neck vertex is required here.
    """
    base = repair._load_base()
    cleanup = uniform.retain_connected_head(head)
    native = base.coordinates(head)
    assert abs(float(np.ptp(native[:, 2]))-.315) < 1e-5
    axis = np.asarray(neck_axis_xy, dtype=np.float64)
    low_neck = native[(native[:, 2] > .025) & (native[:, 2] < .045)]
    source_axis = (low_neck[:, :2].min(axis=0)+low_neck[:, :2].max(axis=0))/2
    pivot = np.r_[source_axis, .035]
    angle = math.radians(-15)
    rotation = np.array([[1., 0., 0.], [0., math.cos(angle), -math.sin(angle)],
                         [0., math.sin(angle), math.cos(angle)]])
    rotated = (native-pivot) @ rotation.T
    pitch_scale = .315/np.ptp(rotated[:, 2])
    rotated *= pitch_scale
    neck_pivot = np.r_[axis, 1.85-rotated[:, 2].max()]
    baseline = rotated+neck_pivot
    base.put_coordinates(head, baseline)
    camera = cranium.face_camera()
    landmarks = cranium.source_landmarks(head, camera, extra_pixels={
        "nose_tip": (503, 649), "lip_center": (505, 701),
        "left_ear": (310, 620), "right_ear": (704, 620),
        "left_cheek": (363, 637), "right_cheek": (650, 637),
    })
    brow_z = max(landmarks[name]["position_xyz_m"][2]
                 for name in ("left_eyebrow", "right_eyebrow"))
    sculpted, sculpt_report = cranium.refine_upper_cranium(baseline, axis, brow_z)
    scale = 1.12
    scaled = (sculpted-neck_pivot)*scale+neck_pivot
    vertical_translation = 1.85-scaled[:, 2].max()
    cranium_points = scaled+np.array([0, 0, vertical_translation])

    def transform_mark(point):
        point = np.asarray(point, dtype=np.float64).copy()
        start = sculpt_report["upper_cranium_start_z_m"]
        level = smoothstep((point[2]-start)/(1.85-start))
        back = smoothstep((point[1]-(axis[1]+.045))/.085)
        point[2] -= .035*level
        point[0] = axis[0]+(point[0]-axis[0])*(1-.045*level)
        point[1] -= .012*back*level
        point = (point-neck_pivot)*scale+neck_pivot
        point[2] += vertical_translation
        return point

    cranium_landmarks = {
        name: {"position_xyz_m": transform_mark(landmark["position_xyz_m"]).tolist()}
        for name, landmark in landmarks.items()
    }
    cranium_landmarks["crown"]["position_xyz_m"] = cranium_points[np.argmax(cranium_points[:, 2])].tolist()
    fitted, final_landmarks, fit_report = fit_face_and_posterior(cranium_points, cranium_landmarks, axis)
    base.put_coordinates(head, fitted)
    for landmark in final_landmarks.values():
        landmark["image_pixel_xy"] = cranium.project_pixel(camera, landmark["position_xyz_m"])
    bpy.data.objects.remove(camera, do_unlink=True)
    eye_z = float(np.mean([final_landmarks[name]["position_xyz_m"][2]
                          for name in ("left_pupil", "right_pupil")]))
    chin_z = float(final_landmarks["chin_contour"]["position_xyz_m"][2])
    crown_z = float(fitted[:, 2].max())
    report = {
        "input": "load_mesh(liang-head/textured.glb, height=.315)",
        "geometry_cleanup": cleanup, "source_low_neck_axis_xy_m": source_axis.tolist(),
        "source_pivot_xyz_m": pivot.tolist(), "pitch_degrees": -15,
        "post_pitch_uniform_scale": float(pitch_scale), "shared_neck_axis_xy_m": axis.tolist(),
        "posed_neck_pivot_xyz_m": neck_pivot.tolist(),
        "upper_cranium_correction": sculpt_report,
        "post_cranium_uniform_scale": scale,
        "post_cranium_vertical_translation_m": float(vertical_translation),
        "baseline_ray_cast_landmarks": landmarks,
        "pre_landmark_fit_points": cranium_landmarks,
        "landmark_fit": fit_report, "final_landmarks": final_landmarks,
        "prototype_coordinates_sha256": hashlib.sha256(base.coordinates(head).tobytes()).hexdigest(),
        "final_head_height_m": crown_z-chin_z,
        "final_head_height_over_body": (crown_z-chin_z)/1.85,
        "final_crown_to_eye_fraction": (crown_z-eye_z)/(crown_z-chin_z),
        "final_eye_to_chin_m": eye_z-chin_z,
        "final_eye_z_m": eye_z, "final_chin_z_m": chin_z, "final_crown_z_m": crown_z,
        "final_prototype_bounds": [fitted.min(axis=0).tolist(), fitted.max(axis=0).tolist()],
        "source_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outfit", choices=("suit", "sport", "none"), default="suit")
    parser.add_argument("--out", type=Path)
    arguments = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None
    args = parser.parse_args(arguments)
    out = (args.out or ROOT / ("StudyData/avatar-v3/neck-candidate/final-landmark-"+args.outfit)).resolve()
    assert "neck-candidate" in out.parts
    out.mkdir(parents=True, exist_ok=True)
    textures = out / "Textures"
    textures.mkdir(exist_ok=True)
    base = repair._load_base()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generated = ROOT / "StudyData/avatar-v3/generated"
    head = base.load_mesh(generated / "liang-head/textured.glb", "Shared fitted head prototype", .315)
    head_report = prepare_reference_head(head)
    base.bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
    projection_mesh = head.data.copy()
    source, material = {
        "suit": ("liang", "Tint_LiangSuit_Reference"),
        "sport": ("liang-sport", "Tint_LiangSport_Reference"),
        "none": ("liang-bare", "Tint_LiangBare_Reference"),
    }[args.outfit]
    body = base.load_mesh(generated / source / "textured.glb", "Body_"+args.outfit, 1.85)
    neck_reference_mesh = body.data.copy() if args.outfit == "none" else None
    base.bind_texture(body, material, textures, False, "blue-cloth")
    base.remove_old_head(body)
    bare_boundary = (repair.smooth_bare_neck_boundary(body, SUIT_NECK_AXIS, reference_head=head)
                     if args.outfit == "none" else None)
    collar_boundary = (base.smooth_collar_boundary(body)
                       if args.outfit != "none" else None)
    fitted_copy = head.copy()
    fitted_copy.data = head.data.copy()
    bpy.context.collection.objects.link(fitted_copy)
    cut = repair.cut_head_above_collar(
        fitted_copy, body, 1.55, neck_axis_xy=SUIT_NECK_AXIS,
        anatomical_nape_height=1.665, anatomical_front_height=1.59,
    )
    bridge = repair.connect_neck(body, fitted_copy, 7, projection_mesh,
                                 transition_texture_dir=textures,
                                 neck_material_name="Fixed_LiangNeck_"+args.outfit,
                                 extend_neck_skin=True, match_upper_tangent=True,
                                 neck_reference_mesh=neck_reference_mesh,
                                 neck_axis_xy=SUIT_NECK_AXIS)
    bpy.data.objects.remove(fitted_copy, do_unlink=True)
    root = base.empty("LiangFittedCandidate")
    base.keep_world_parent(body, base.empty("Outfit_"+args.outfit, root))
    eye_z = head_report["final_eye_z_m"]
    points = base.coordinates(head)
    cheek = points[(np.abs(points[:, 2]-eye_z) < .010) &
                   (np.abs(points[:, 0]-SUIT_NECK_AXIS[0]) > .025) &
                   (np.abs(points[:, 0]-SUIT_NECK_AXIS[0]) < .075)]
    eye_y = float(np.quantile(cheek[:, 1], .04))-.003
    base.glasses(base.empty("Accessory_glasses", root),
                 (float(SUIT_NECK_AXIS[0]), eye_y, eye_z),
                 width=.145*1.12, lens_height=.035, temple_spread=.015, head_surface=head)
    bpy.data.objects.remove(head, do_unlink=True)
    for name, landmark in head_report["final_landmarks"].items():
        marker = base.empty("Landmark_"+name)
        marker.location = landmark["position_xyz_m"]
        marker.empty_display_type, marker.empty_display_size = "SPHERE", .002
        marker.show_name, marker.hide_render = True, True
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (root, *root.children_recursive):
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "Liang-fitted.glb"),
                              export_format="GLB", use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(
        filepath=str(out / "Liang-fitted.fbx"), use_selection=True,
        object_types={"EMPTY", "MESH"}, axis_forward="-Z", axis_up="Y",
        add_leaf_bones=False, bake_anim=False, apply_unit_scale=True,
        mesh_smooth_type="FACE", path_mode="RELATIVE",
    )
    report = {"outfit": args.outfit, "head": head_report, "cut": cut, "bridge": bridge,
              "bare_boundary_repair": bare_boundary,
              "collar_boundary_repair": collar_boundary,
              "bpy_version": bpy.app.version_string,
              "source_head_sha256": hashlib.sha256((generated / "liang-head/textured.glb").read_bytes()).hexdigest(),
              "source_body_sha256": hashlib.sha256((generated / source / "textured.glb").read_bytes()).hexdigest()}
    (out / "head-fit-and-assembly.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report), flush=True)
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
