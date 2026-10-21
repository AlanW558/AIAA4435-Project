#!/usr/bin/env python3
"""Build the licensed, reference-inspired Liang demo with Blender's Python.

Run with Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/build_liang_avatar.py
The CC0 source files and provenance are in Assets/Project/AvatarModels/Source/MakeHuman.
Coordinates, UVs, fitting, and skinning are read from the source assets rather than
replacing the person with geometric primitives. No MakeHuman program code is used.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Assets/Project/AvatarModels/Source/MakeHuman"
OUTPUT = ROOT / "Assets/Project/Resources/AvatarDemo"
EVIDENCE = ROOT / "StudyData/avatar-v2/liang-preview"
TEXTURES = OUTPUT / "Textures"
BLUE = "#2358B8"
RECIPE = {
    "asian-male-young.target": 1.0,
    "universal-male-young-maxmuscle-averageweight.target": 0.85,
    "universal-male-young-maxmuscle-maxweight.target": 0.15,
    "torso-muscle-pectoral-incr.target": 0.65,
    "torso-muscle-dorsi-incr.target": 0.40,
    "torso-vshape-incr.target": 0.50,
}


def read_obj(path):
    vertices, texcoords, faces, face_uv, groups = [], [], [], [], []
    group = ""
    for line in path.read_text().splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "v":
            vertices.append([float(v) for v in tokens[1:4]])
        elif tokens[0] == "vt":
            texcoords.append([float(v) for v in tokens[1:3]])
        elif tokens[0] == "g":
            group = " ".join(tokens[1:])
        elif tokens[0] == "f":
            ids = [v.split("/") for v in tokens[1:]]
            faces.append([int(v[0]) - 1 for v in ids])
            face_uv.append([int(v[1]) - 1 if len(v) > 1 and v[1] else 0 for v in ids])
            groups.append(group)
    return {
        "v": np.asarray(vertices, dtype=float),
        "uv": np.asarray(texcoords or [[0, 0]], dtype=float),
        "f": faces, "fu": face_uv, "groups": groups,
    }


def components(obj):
    parents = list(range(len(obj["v"])))

    def root(i):
        while i != parents[i]:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for face in obj["f"]:
        for vertex in face:
            parents[root(vertex)] = root(face[0])
    groups = {}
    for i in range(len(parents)):
        groups.setdefault(root(i), []).append(i)
    labels = np.zeros(len(parents), dtype=int)
    for ids in groups.values():
        labels[ids] = min(ids)
    return labels, {min(ids): ids for ids in groups.values()}


def clip_surface(source, coords, weights, face_ids, planes):
    """Clip a garment at exact planes while interpolating its UVs and skin weights."""
    vertices, out_weights, texcoords, faces, face_uv, lookup = [], [], [], [], [], {}
    for fi in face_ids:
        polygon = [(coords[i].copy(), weights[i].copy(), source["uv"][uv].copy())
                   for i, uv in zip(source["f"][fi], source["fu"][fi])]
        for plane in planes:
            distance = plane if callable(plane) else lambda co: plane[1] * co[plane[0]] - plane[2]
            output = []
            for i, current in enumerate(polygon):
                previous = polygon[i - 1]
                a, b = distance(previous[0]), distance(current[0])
                if (a <= 0) != (b <= 0):
                    t = a / (a - b)
                    output.append(tuple(x + t * (y - x) for x, y in zip(previous, current)))
                if b <= 0:
                    output.append(current)
            polygon = output
            if len(polygon) < 3:
                break
        if len(polygon) < 3:
            continue
        face, uv_face = [], []
        for co, weight, uv in polygon:
            key = tuple(np.round(co, 7))
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append(co)
                out_weights.append(weight)
            face.append(lookup[key])
            uv_face.append(len(texcoords))
            texcoords.append(uv)
        if len(set(face)) >= 3:
            faces.append(face)
            face_uv.append(uv_face)
    result = {"v": np.asarray(vertices), "f": faces, "uv": np.asarray(texcoords), "fu": face_uv}
    return result, np.asarray(out_weights)


def fit_asset(path, body, body_weights):
    """MHCLO barycentric fit; offsets scale with the morphed helper geometry."""
    scales = np.ones(3)
    rows, removed = [], set()
    in_verts = in_delete = False
    obj_name = None
    for line in path.read_text().splitlines():
        token = line.split()
        if not token or token[0].startswith("#"):
            continue
        key = token[0]
        if key == "obj_file":
            obj_name = " ".join(token[1:])
        elif key in ("x_scale", "y_scale", "z_scale"):
            axis = "xyz".index(key[0])
            i, j = int(token[1]), int(token[2])
            scales[axis] = abs(body[i, axis] - body[j, axis]) / float(token[3])
        elif key == "verts":
            in_verts, in_delete = True, False
        elif key == "delete_verts":
            in_verts, in_delete = False, True
        elif in_delete:
            i = 0
            while i < len(token):
                if i + 2 < len(token) and token[i + 1] == "-":
                    removed.update(range(int(token[i]), int(token[i + 2]) + 1))
                    i += 3
                else:
                    removed.add(int(token[i]))
                    i += 1
        elif in_verts:
            if len(token) == 1:
                rows.append(([int(token[0])] * 3, [1, 0, 0], [0, 0, 0]))
            elif len(token) >= 9:
                rows.append((list(map(int, token[:3])), list(map(float, token[3:6])),
                             list(map(float, token[6:9]))))
            else:
                raise ValueError(f"Unrecognized fitting row in {path}: {line}")
    obj = read_obj(path.parent / obj_name)
    if len(rows) != len(obj["v"]):
        raise ValueError(f"{path}: {len(rows)} mappings for {len(obj['v'])} vertices")
    ids = np.asarray([row[0] for row in rows])
    bary = np.asarray([row[1] for row in rows])
    offsets = np.asarray([row[2] for row in rows])
    obj["v"] = np.einsum("ij,ijk->ik", bary, body[ids]) + offsets * scales
    # Negative coordinates are valid extrapolation. Skin influences, in contrast,
    # must remain nonnegative for Blender and Unity.
    weights = np.einsum("ij,ijk->ik", np.maximum(bary, 0), body_weights[ids])
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    return obj, weights, removed


def srgb(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]


def material(name, color="#FFFFFF", texture=None, roughness=.55, metallic=0, cutout=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    color = (*srgb(color), 1)
    mat.diffuse_color = color
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in shader.inputs:
        shader.inputs["Specular IOR Level"].default_value = .28
    if texture:
        dst = TEXTURES / ("Liang_" + texture.name)
        shutil.copy2(texture, dst)
        image = bpy.data.images.load(str(dst), check_existing=True)
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
        if cutout:
            # Hard threshold previews the same cutout treatment the runtime uses.
            threshold = mat.node_tree.nodes.new("ShaderNodeMath")
            threshold.operation = "GREATER_THAN"
            threshold.inputs[1].default_value = .42
            mat.node_tree.links.new(tex.outputs["Alpha"], threshold.inputs[0])
            mat.node_tree.links.new(threshold.outputs[0], shader.inputs["Alpha"])
            mat.surface_render_method = "DITHERED"
            mat.use_transparency_overlap = False
            mat["alphaClip"] = True
            mat["cutoff"] = .42
    return mat


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


def to_world(vertices):
    result = np.asarray(vertices)[:, [0, 2, 1]].copy()
    result[:, 1] *= -1
    result[:, 2] -= FLOOR_NATIVE
    return result * SCALE


def mesh_object(name, source, coords, weights, parent, mats, selected_faces=None,
                material_indices=None, world=False, rigid_bone=None):
    if selected_faces is None:
        selected_faces = list(range(len(source["f"])))
    ids = sorted({v for fi in selected_faces for v in source["f"][fi]})
    reindex = {v: i for i, v in enumerate(ids)}
    faces = [[reindex[v] for v in source["f"][fi]] for fi in selected_faces]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    xyz = coords[ids] if world else to_world(coords[ids])
    mesh.from_pydata(xyz.tolist(), [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    for mat in mats:
        mesh.materials.append(mat)
    layer = mesh.uv_layers.new(name="UVMap")
    for pi, fi in enumerate(selected_faces):
        polygon = mesh.polygons[pi]
        polygon.use_smooth = True
        if material_indices is not None:
            polygon.material_index = int(material_indices[fi])
        for loop, uv_idx in zip(polygon.loop_indices, source["fu"][fi]):
            layer.data[loop].uv = source["uv"][uv_idx]
    if rigid_bone:
        group = obj.vertex_groups.new(name=rigid_bone)
        group.add(list(range(len(ids))), 1, "REPLACE")
    elif weights is not None:
        compact = weights[ids]
        for bi, bone in enumerate(BONE_NAMES):
            selected = np.flatnonzero(compact[:, bi] > .0001)
            if len(selected):
                group = obj.vertex_groups.new(name=bone)
                for i in selected:
                    group.add([int(i)], float(compact[i, bi]), "REPLACE")
    if weights is not None or rigid_bone:
        modifier = obj.modifiers.new("Skin", "ARMATURE")
        modifier.object = ARMATURE
        modifier.use_deform_preserve_volume = True
    return obj


def simple_mesh(name, verts, faces, parent, mat, bone=None, smooth=True):
    source = {"v": np.asarray(verts), "f": faces, "uv": np.zeros((1, 2)),
              "fu": [[0] * len(f) for f in faces]}
    obj = mesh_object(name, source, source["v"], None, parent, [mat],
                      world=True, rigid_bone=bone)
    for p in obj.data.polygons:
        p.use_smooth = smooth
    return obj


def make_armature(body):
    skel = json.loads((SOURCE / "rigs/default.mhskel").read_text())
    arm = bpy.data.armatures.new("Liang_Skeleton")
    obj = bpy.data.objects.new("Liang_Rig", arm)
    bpy.context.collection.objects.link(obj)
    obj.parent = ROOT_OBJECT
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    joints = {key: to_world(np.mean(body[indices], axis=0)[None])[0]
              for key, indices in skel["joints"].items()}
    for name, data in skel["bones"].items():
        bone = arm.edit_bones.new(name)
        bone.head, bone.tail = joints[data["head"]], joints[data["tail"]]
        if (bone.tail - bone.head).length < 1e-6:
            bone.tail.z += .001
        plane = skel["planes"].get(data.get("rotation_plane"))
        if plane:
            a, b, c = (Vector(joints[key]) for key in plane)
            normal = (b - a).cross(c - a)
            if normal.length > 1e-8:
                bone.align_roll(normal.normalized())
    for name, data in skel["bones"].items():
        if data.get("parent") and data["parent"] in arm.edit_bones:
            arm.edit_bones[name].parent = arm.edit_bones[data["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)
    obj.show_in_front = True
    return obj, list(skel["bones"])


def create_shoes(parent, prefix):
    # A continuous leather upper and layered sole, with a rounded toe. Bounds
    # derive from the target feet rather than isolated sphere/cube components.
    for sign, side in ((1, "L"), (-1, "R")):
        surface = BODY[BODY_IDS]
        foot = surface[(surface[:, 1] < -7.0) & (surface[:, 0] * sign > .5)]
        pts = to_world(foot)
        x = float((pts[:, 0].max() + pts[:, 0].min()) / 2)
        back, front = float(pts[:, 1].max() + .007), float(pts[:, 1].min() - .012)
        cy = (back + front) / 2
        half_len = (back - front) / 2
        half_width = float((pts[:, 0].max() - pts[:, 0].min()) / 2 + .008)
        verts, faces = [], []
        rings = [(0.012, 1.02), (.034, 1.02), (.051, 1), (.095, .89), (.128, .68)]
        count = 48
        for z, shrink in rings:
            for i in range(count):
                angle = 2 * math.pi * i / count
                c, s = math.cos(angle), math.sin(angle)
                xx = math.copysign(abs(c) ** .77, c)
                yy = math.copysign(abs(s) ** .8, s)
                # The ankle end is narrower than the toe.
                width = half_width * (1 - .13 * max(yy, 0))
                top_shape = 1 if z < .051 else .65 + .35 * (yy + 1) / 2
                verts.append((x + width * xx * shrink, cy + half_len * yy * shrink, z * top_shape))
        for row in range(len(rings) - 1):
            for j in range(count):
                faces.append([row * count + j, row * count + (j + 1) % count,
                              (row + 1) * count + (j + 1) % count, (row + 1) * count + j])
        faces += [list(reversed(range(count))), list(range((len(rings)-1)*count, len(rings)*count))]
        shoe = simple_mesh(prefix + "_Shoe_" + side, verts, faces, parent, LEATHER, "foot." + side)
        shoe.data.materials.append(SOLE)
        for p in shoe.data.polygons[:count]:
            p.material_index = 1


def create_cap():
    top = to_world(np.array([[0, float(BODY[:, 1].max()), .1]]))[0, 2]
    center_y = -.055
    verts, faces = [], []
    segments, rings = 48, 10
    for row in range(rings + 1):
        theta = (row / rings) * math.pi / 2
        radius = math.cos(theta)
        for i in range(segments):
            phi = i / segments * 2 * math.pi
            verts.append((.112 * radius * math.cos(phi), center_y + .147 * radius * math.sin(phi),
                          top - .082 + .118 * math.sin(theta)))
    for row in range(rings):
        for i in range(segments):
            faces.append([row * segments + i, row * segments + (i+1) % segments,
                          (row+1) * segments + (i+1) % segments, (row+1) * segments + i])
    simple_mesh("Cap_Crown", verts, faces, HAT, TINT, "head")
    verts, faces = [], []
    n = 32
    for radial in (0, 1):
        for i in range(n+1):
            a = -math.pi * .45 + math.pi * .9 * i/n
            x = math.sin(a) * (.099 + .025 * radial)
            y = center_y - math.cos(a) * (.128 + .095 * radial)
            z = top - .080 - .012 * radial + .006 * (x/.124)**2
            verts.append((x, y, z))
    for i in range(n):
        faces.append([i, i+1, n+2+i, n+1+i])
    bill = simple_mesh("Cap_Visor", verts, faces, HAT, TINT, "head")
    solid = bill.modifiers.new("Visor edge", "SOLIDIFY")
    solid.thickness = .004
    # Small top button and seam lines keep the cap legible at normal VR scale.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=.009,
                                       location=(0, center_y, top+.036))
    button = bpy.context.object
    button.name, button.parent = "Cap_Button", HAT
    button.scale.z = .45
    button.data.materials.append(TINT)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    group = button.vertex_groups.new(name="head")
    group.add(list(range(len(button.data.vertices))), 1, "REPLACE")
    modifier = button.modifiers.new("Skin", "ARMATURE")
    modifier.object = ARMATURE
    thread = material("Fixed_Cap_Stitching", "#7A8EA4", roughness=.88)
    paths = []
    for phi in np.linspace(0, 2*math.pi, 6, endpoint=False):
        path = []
        for theta in np.linspace(.015, math.pi/2-.055, 28):
            radius = math.cos(theta)
            path.append((.1126*radius*math.cos(phi), center_y+.1476*radius*math.sin(phi),
                         top-.082+.1186*math.sin(theta)))
        paths.append(path)
    for inset in (.90, .96):
        path = []
        for a in np.linspace(-math.pi*.42, math.pi*.42, 40):
            x = math.sin(a)*(.099+.025*inset)
            path.append((x, center_y-math.cos(a)*(.128+.095*inset),
                         top-.080-.012*inset+.006*(x/.124)**2+.0007))
        paths.append(path)
    curve = bpy.data.curves.new("Cap_Seams_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth, curve.bevel_resolution = .00055, 1
    for path in paths:
        spline = curve.splines.new("POLY")
        spline.points.add(len(path)-1)
        for point, co in zip(spline.points, path):
            point.co = (*co, 1)
    obj = bpy.data.objects.new("Cap_Stitching", curve)
    bpy.context.collection.objects.link(obj)
    obj.parent = HAT
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.data.materials.append(thread)
    group = obj.vertex_groups.new(name="head")
    group.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
    modifier = obj.modifiers.new("Skin", "ARMATURE")
    modifier.object = ARMATURE


def pose_and_bake():
    bpy.context.view_layer.update()
    for side, sign in (("L", 1), ("R", -1)):
        bone = ARMATURE.pose.bones["upperarm01." + side]
        rotation = Matrix.Rotation(math.radians(34) * sign, 4, "Y")
        pivot = bone.head.copy()
        bone.matrix = Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ bone.matrix
        bpy.context.view_layer.update()
        forearm = ARMATURE.pose.bones["lowerarm01." + side]
        # Align the whole forearm with a relaxed, nearly vertical direction.
        start = forearm.head.copy()
        end = ARMATURE.pose.bones["wrist." + side].head.copy() if "wrist."+side in ARMATURE.pose.bones else ARMATURE.pose.bones["hand."+side].head.copy()
        current = (end - start).normalized()
        desired = Vector((sign * .06, -.10, -1)).normalized()
        rotation = current.rotation_difference(desired).to_matrix().to_4x4()
        forearm.matrix = Matrix.Translation(start) @ rotation @ Matrix.Translation(-start) @ forearm.matrix
        bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not any(m.type == "ARMATURE" for m in obj.modifiers):
            continue
        # Temporarily omit non-skin modifiers to retain the original topology.
        extras = [m for m in obj.modifiers if m.type != "ARMATURE"]
        for m in extras:
            m.show_viewport = False
        depsgraph.update()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        coords = [v.co.copy() for v in mesh.vertices]
        evaluated.to_mesh_clear()
        for v, co in zip(obj.data.vertices, coords):
            v.co = co
        for m in extras:
            m.show_viewport = True
    bpy.ops.object.select_all(action="DESELECT")
    ARMATURE.select_set(True)
    bpy.context.view_layer.objects.active = ARMATURE
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    ARMATURE.select_set(False)
    bpy.context.view_layer.update()


def set_visible(outfit="suit", accessory="glasses"):
    for name, parent in OUTFITS.items():
        for obj in parent.children_recursive:
            obj.hide_render = name != outfit
    for name, parent in (("glasses", GLASSES), ("hat", HAT)):
        for obj in parent.children_recursive:
            obj.hide_render = name != accessory


def point_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_area(name, location, power, size, color):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size, data.color = power, "DISK", size, color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    point_at(obj, (0, 0, 1))
    return obj


def setup_studio():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.device = "CPU"
    scene.render.resolution_x = 850
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.world.color = (.15, .15, .15)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.file_format = "PNG"
    add_area("Key", (3, -4, 4.5), 380, 2.5, (1, .94, .86))
    add_area("Fill", (-3, -2, 2.7), 130, 3, (.85, .92, 1))
    add_area("Rim", (1, 2, 3.5), 220, 3, (1, 1, 1))
    bpy.ops.mesh.primitive_plane_add(size=200)
    ground = bpy.context.object
    ground.name = "Studio_Floor"
    ground.location.z = -.005
    ground.data.materials.append(material("StudioFloor", "#C8CDD4", roughness=.9))
    camera_data = bpy.data.cameras.new("Evidence_Camera")
    camera = bpy.data.objects.new("Evidence_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.12
    scene.camera = camera
    return camera


def render_evidence(camera, quick=False):
    scene = bpy.context.scene
    views = [
        ("01_suit_front", "suit", "glasses", (0, -5, 1.25), (0, 0, .96), 2.08),
        ("02_suit_threequarter", "suit", "glasses", (2.5, -5, 1.5), (0, 0, .99), 2.13),
        ("03_suit_side", "suit", "glasses", (5, -.1, 1.25), (0, 0, .96), 2.1),
        ("04_face", "suit", "glasses", (.50, -5, 1.72), (0, -.01, 1.64), .65),
        ("05_sport", "sport", "hat", (1.5, -5, 1.4), (0, 0, .98), 2.1),
        ("06_muscle", "none", "glasses", (1.2, -5, 1.4), (0, 0, .98), 2.1),
    ]
    if quick:
        views = [views[0], views[3], views[-1]]
        scene.render.resolution_percentage = 70
        scene.cycles.samples = 16
    for name, outfit, accessory, location, target, scale in views:
        set_visible(outfit, accessory)
        camera.location = location
        camera.data.ortho_scale = scale
        point_at(camera, target)
        scene.render.filepath = str(EVIDENCE / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    set_visible()


def build(args):
    global ROOT_OBJECT, ARMATURE, BONE_NAMES, BODY, BODY_IDS, SCALE, FLOOR_NATIVE
    global OUTFITS, GLASSES, HAT, TINT, LEATHER, SOLE
    OUTPUT.mkdir(parents=True, exist_ok=True)
    TEXTURES.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    base = read_obj(SOURCE / "base.obj")
    BODY = base["v"].copy()
    for filename, strength in RECIPE.items():
        target = np.loadtxt(SOURCE / "targets" / filename, comments="#")
        BODY[target[:, 0].astype(int)] += target[:, 1:4] * strength
    body_faces = [i for i, g in enumerate(base["groups"]) if g == "body"]
    ids = np.unique([v for fi in body_faces for v in base["f"][fi]])
    BODY_IDS = ids
    FLOOR_NATIVE = float(BODY[ids, 1].min())
    SCALE = 1.83 / float(np.ptp(BODY[ids, 1]))
    ROOT_OBJECT = empty("Liang")
    ARMATURE, BONE_NAMES = make_armature(BODY)
    source_weights = json.loads((SOURCE / "rigs/default_weights.mhw").read_text())["weights"]
    weights = np.zeros((len(BODY), len(BONE_NAMES)), dtype=float)
    for bi, bone in enumerate(BONE_NAMES):
        pairs = np.array(source_weights.get(bone, []))
        if len(pairs):
            weights[pairs[:, 0].astype(int), bi] = pairs[:, 1]
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    OUTFITS = {key: empty("Outfit_" + key, ROOT_OBJECT) for key in ("suit", "sport", "none")}
    GLASSES, HAT = empty("Accessory_glasses", ROOT_OBJECT), empty("Accessory_hat", ROOT_OBJECT)
    common = empty("Common_Head", ROOT_OBJECT)
    TINT = material("Tint_Liang_Blue", BLUE, roughness=.68)
    white = material("Fixed_Cotton_White", "#F4F4F0", roughness=.76)
    LEATHER = material("Fixed_Leather_Black", "#15191F", roughness=.32)
    SOLE = material("Fixed_Sole_Charcoal", "#252830", roughness=.85)
    metal = material("Fixed_Glasses_Graphite", "#26252A", roughness=.26, metallic=.35)
    skin = material("Fixed_Skin_Asian", texture=SOURCE / "skins/young_asian_male/young_lightskinned_male_diffuse3.png", roughness=.5)
    eyes = material("Cutout_Eyes_Brown", texture=SOURCE / "eyes/materials/brown_eye.png", roughness=.23, cutout=True)
    hair = material("Cutout_Hair_Black", texture=SOURCE / "hair/short01/short01_diffuse.png", roughness=.76, cutout=True)
    brows = material("Cutout_Eyebrows_Black", texture=SOURCE / "eyebrows/eyebrow005/eyebrow005.png", roughness=.85, cutout=True)
    lashes = material("Cutout_Eyelashes_Black", texture=SOURCE / "eyelashes/eyelashes01/eyelashes01.png", roughness=.8, cutout=True)
    centers = np.array([BODY[f].mean(axis=0) for f in base["f"]])
    head_faces = [fi for fi in body_faces if centers[fi, 1] > 5.65]
    mesh_object("Face_Neck_Ears", base, BODY, weights, common, [skin], head_faces)
    for name, relative, mat in [
        ("Eyes_Brown", "eyes/high-poly/high-poly.mhclo", eyes),
        ("Hair_Short_Black", "hair/short01/short01.mhclo", hair),
        ("Eyebrows", "eyebrows/eyebrow005/eyebrow005.mhclo", brows),
        ("Eyelashes", "eyelashes/eyelashes01/eyelashes01.mhclo", lashes),
    ]:
        obj, _, _ = fit_asset(SOURCE / relative, BODY, weights)
        mesh_object(name, obj, obj["v"], None, common, [mat], rigid_bone="head")
    glasses, _, _ = fit_asset(SOURCE / "clothes/spamrakuen_sagerfrogs_glasses_02/spamrakuen_sagerfrogs_glasses_02.mhclo", BODY, weights)
    labels, _ = components(glasses)
    frame_faces = [fi for fi, face in enumerate(glasses["f"]) if labels[face[0]] not in (0, 40)]
    mesh_object("Glasses_Rectangular_Frames", glasses, glasses["v"], None, GLASSES, [metal], frame_faces, rigid_bone="head")
    suit, suit_weights, covered = fit_asset(SOURCE / "clothes/toigo_male_suit_3/toigo_male_suit_3.mhclo", BODY, weights)
    labels, groups = components(suit)
    assignments = []
    suit_faces, pants_faces = [], []
    for fi, face in enumerate(suit["f"]):
        component = labels[face[0]]
        size = len(groups[component])
        assignments.append(1 if size in (766, 96) else 2 if size == 65 else 0)
        if size != 675:  # Remove the red necktie, keeping the white shirt.
            suit_faces.append(fi)
        if size == 2053:
            pants_faces.append(fi)
    mesh_object("Suit_Tailored_Jacket_Shirt_Trousers", suit, suit["v"], suit_weights,
                OUTFITS["suit"], [TINT, white, LEATHER], suit_faces, assignments)
    visible_skin = [fi for fi in body_faces if centers[fi, 1] <= 5.65
                    and centers[fi, 1] > -7.1 and not all(v in covered for v in base["f"][fi])]
    mesh_object("Suit_Visible_Skin", base, BODY, weights, OUTFITS["suit"], [skin], visible_skin)
    create_shoes(OUTFITS["suit"], "Formal")

    # Build the sports fabric from the body surface with its own smoothed,
    # outward offset. Matching skin weights prevents the sleeve from crossing
    # the upper arm when the A-pose is relaxed.
    top = BODY.copy()
    neighbors = {}
    for fi in body_faces:
        face = base["f"][fi]
        for a, b in zip(face, face[1:] + face[:1]):
            neighbors.setdefault(a, set()).add(b)
            neighbors.setdefault(b, set()).add(a)
    for _ in range(4):
        smooth = top.copy()
        for i, adjacent in neighbors.items():
            smooth[i] = top[i] * .6 + top[list(adjacent)].mean(axis=0) * .4
        top = smooth
    normals = np.zeros_like(top)
    for fi in body_faces:
        face = base["f"][fi]
        normal = np.cross(top[face[1]] - top[face[0]], top[face[2]] - top[face[0]])
        for i in face:
            normals[i] += normal
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-8)
    top += normals * .085
    sleeve_cut = lambda co: min(abs(co[0]) - 2.05, .66*abs(co[0]) - .75*co[1] + .8145)
    top_mesh, top_weights = clip_surface(base, top, weights, body_faces,
                                        [(1, -1, -.75), (1, 1, 5.70), sleeve_cut])
    mesh_object("Sport_Training_Top", top_mesh, top_mesh["v"], top_weights, OUTFITS["sport"], [TINT])
    # Narrow sewn edging at the neckline and sleeves, following the actual cut
    # boundary, not a second intersecting shirt shell.
    edges = {}
    for face in top_mesh["f"]:
        for a, b in zip(face, face[1:] + face[:1]):
            key = tuple(sorted((a, b)))
            edges[key] = edges.get(key, 0) + 1
    trim_v, trim_f, trim_w = [], [], []
    for (a, b), count in edges.items():
        if count != 1:
            continue
        pa, pb = top_mesh["v"][[a, b]]
        shift = np.zeros(3)
        if min(pa[1], pb[1]) > 5.69:
            shift[1] = -.045
        elif abs(sleeve_cut(pa)) < .001 and abs(sleeve_cut(pb)) < .001:
            shift[0], shift[1] = -.033 * np.sign(pa[0]), .0375
        else:
            continue
        start = len(trim_v)
        trim_v.extend((pa, pb, pb + shift, pa + shift))
        trim_w.extend((top_weights[a], top_weights[b], top_weights[b], top_weights[a]))
        trim_f.append(list(range(start, start + 4)))
    trim_source = {"v": np.asarray(trim_v), "f": trim_f, "uv": np.zeros((1, 2)),
                   "fu": [[0]*4 for _ in trim_f]}
    # A sub-millimeter expansion prevents coincident surface flicker.
    trim_source["v"][:, 0] *= 1.001
    trim_source["v"][:, 2] *= 1.003
    mesh_object("Sport_White_Edging", trim_source, trim_source["v"], np.asarray(trim_w),
                OUTFITS["sport"], [white])
    mesh_object("Sport_Training_Trousers", suit, suit["v"], suit_weights, OUTFITS["sport"], [TINT], pants_faces)
    sport_skin = [fi for fi in body_faces if centers[fi, 1] <= 5.65
                  and centers[fi, 1] > -7.1 and abs(centers[fi, 0]) > 2.45]
    mesh_object("Sport_Arms_Hands", base, BODY, weights, OUTFITS["sport"], [skin], sport_skin)
    create_shoes(OUTFITS["sport"], "Training")

    pants_center = np.array([suit["v"][f].mean(axis=0) for f in suit["f"]])
    shorts_faces = [fi for fi in pants_faces if pants_center[fi, 1] > -2.25]
    shorts_coords = suit["v"].copy()
    edges = {}
    for fi in shorts_faces:
        face = suit["f"][fi]
        for a, b in zip(face, face[1:] + face[:1]):
            edge = tuple(sorted((a, b)))
            edges[edge] = edges.get(edge, 0) + 1
    for edge, count in edges.items():
        if count == 1 and shorts_coords[list(edge), 1].mean() < -1.2:
            shorts_coords[list(edge), 1] = -2.25
    mesh_object("Training_Shorts", suit, shorts_coords, suit_weights, OUTFITS["none"], [TINT], shorts_faces)
    exposed = [fi for fi in body_faces if centers[fi, 1] <= 5.65 and centers[fi, 1] > -7.6
               and (centers[fi, 1] > .50 or centers[fi, 1] < -2.17 or abs(centers[fi, 0]) > 3.0)]
    mesh_object("Muscular_Torso_Arms_Legs", base, BODY, weights, OUTFITS["none"], [skin], exposed)
    create_shoes(OUTFITS["none"], "Gym")
    create_cap()
    pose_and_bake()

    # Normalize the default rendered silhouette including hair and footwear.
    avatar_meshes = [o for o in ROOT_OBJECT.children_recursive if o.type == "MESH"]
    main = [o for o in avatar_meshes if o.parent not in (HAT, OUTFITS["sport"], OUTFITS["none"])]
    zmin = min(v.co.z for o in main for v in o.data.vertices)
    zmax = max(v.co.z for o in main for v in o.data.vertices)
    factor = 1.85 / (zmax-zmin)
    for obj in avatar_meshes:
        for v in obj.data.vertices:
            v.co.z -= zmin
            v.co *= factor
    bpy.context.view_layer.objects.active = ARMATURE
    ARMATURE.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in ARMATURE.data.edit_bones:
        for name in ("head", "tail"):
            point = getattr(bone, name).copy()
            point.z -= zmin
            setattr(bone, name, point * factor)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    ROOT_OBJECT["reference"] = "Reference-inspired muscular East Asian man; not a scan or identity reconstruction."
    ROOT_OBJECT["height_m"] = 1.85
    ROOT_OBJECT["source_assets"] = "MakeHuman Community graphical assets CC0; see Source/MakeHuman."
    for obj in [ROOT_OBJECT, *ROOT_OBJECT.children_recursive]:
        obj.hide_render = False
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = ROOT_OBJECT
    bpy.ops.export_scene.fbx(
        filepath=str(OUTPUT / "Liang.fbx"), use_selection=True, object_types={"EMPTY", "MESH", "ARMATURE"},
        axis_forward="-Z", axis_up="Y", add_leaf_bones=False, bake_anim=False,
        apply_unit_scale=True, use_mesh_modifiers=True, mesh_smooth_type="FACE",
        path_mode="RELATIVE", use_custom_props=True,
    )
    report = {
        "source": "MakeHuman Community CC0 graphical assets",
        "height_m": 1.85, "recipe": RECIPE, "tint_srgb": BLUE,
        "objects": [{"name": o.name, "vertices": len(o.data.vertices),
                     "polygons": len(o.data.polygons),
                     "materials": [m.name for m in o.data.materials]} for o in avatar_meshes],
        "bones": len(BONE_NAMES), "body_helper_faces_rendered": 0,
        "hierarchy": [o.name for o in ROOT_OBJECT.children],
        "triangle_count_all_outfits": sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in avatar_meshes),
    }
    (EVIDENCE / "build-report.json").write_text(json.dumps(report, indent=2))
    camera = setup_studio()
    set_visible()
    bpy.ops.wm.save_as_mainfile(filepath=str(EVIDENCE / "Liang-studio.blend"))
    if not args.no_render:
        render_evidence(camera, args.quick)
    print(json.dumps({"fbx": str(OUTPUT/"Liang.fbx"), "evidence": str(EVIDENCE),
                      "triangles_all_outfits": report["triangle_count_all_outfits"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Three smaller review renders.")
    parser.add_argument("--no-render", action="store_true")
    build(parser.parse_args())
