#!/usr/bin/env python3
"""Open an isolated avatar candidate in a portable Blender review workspace.

Run with the installed Blender executable, for example:
blender --background --python Tools/AppearanceExperiment/prepare_blender_avatar_review.py \
  -- --source StudyData/avatar-v3/neck-candidate/NAME/candidate.blend

The source is never overwritten. Reference images are viewport-only helpers;
only the model hierarchy is included in the FBX export.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--root", default="UniformHeadCandidate")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "StudyData/avatar-v3/blender-workbench")
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(arguments)
    source, out = args.source.resolve(), args.out.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if out == source.parent:
        raise ValueError("Use a separate workbench directory to preserve the candidate.")
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    root = bpy.data.objects.get(args.root)
    if root is None:
        raise ValueError(f"Missing model hierarchy: {args.root}")
    production = root.name == "Liang"
    if production:
        # The assembler prefixes Liang's names only after writing its FBX so
        # both avatars can coexist in one .blend. Restore useful authoring
        # names while retaining the other character in its own hierarchy.
        other = bpy.data.objects.get("Nailong")
        if other:
            for obj in other.children_recursive:
                obj.name = "Nailong_" + obj.name
            for obj in [other, *other.children_recursive]:
                obj.hide_set(True)
                obj.hide_render = True
        for obj in root.children_recursive:
            if obj.name.startswith("BuiltLiang_"):
                obj.name = obj.name.removeprefix("BuiltLiang_")
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    if not any(obj.type == "LIGHT" for obj in scene.objects):
        scene.world = scene.world or bpy.data.worlds.new("Review world")
        scene.world.use_nodes = True
        background = next(node for node in scene.world.node_tree.nodes
                          if node.type == "BACKGROUND")
        background.inputs["Color"].default_value = (.3, .34, .38, 1)
        background.inputs["Strength"].default_value = .5
        for name, position, energy, size in [
            ("Review key", (-3, -4, 4), 650, 4),
            ("Review fill", (3, -2, 2.5), 350, 3),
            ("Review rim", (0, 3, 3), 450, 3),
        ]:
            data = bpy.data.lights.new(name, "AREA")
            data.energy, data.shape, data.size = energy, "DISK", size
            light = bpy.data.objects.new(name, data)
            scene.collection.objects.link(light)
            light.location = position
            light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = 900, 1200
    scene.render.resolution_percentage = 100
    helpers = bpy.data.collections.new("Approved image references - viewport only")
    scene.collection.children.link(helpers)
    references = []
    for index, (name, filename) in enumerate([
        ("Suit - approved reference", "liang-reference-v1.png"),
        ("Sport - approved reference", "liang-sport-reference-v1.png"),
        ("Bare torso - approved reference", "liang-bare-reference-v1.png"),
    ]):
        path = ROOT / "StudyData/avatar-v3/references" / filename
        image = bpy.data.images.load(str(path), check_existing=True)
        obj = bpy.data.objects.new(name, None)
        helpers.objects.link(obj)
        obj.empty_display_type = "IMAGE"
        obj.data = image
        obj.empty_display_size = 1.90
        obj.rotation_euler = (1.5707963267948966, 0, 0)
        obj.location = (-1.05 - index * 1.40, .30, .95)
        obj.empty_image_depth = "BACK"
        obj.hide_render = True
        references.append({"file": str(path.relative_to(ROOT)),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "object": name})

    # Preserve the original lighting. Add explicitly named, reproducible views.
    cameras = []
    for name, position, target, scale in [
        ("Review - front", (0, -5, 1.02), (0, 0, .925), 2.16),
        ("Review - face", (0, -5, 1.665), (0, 0, 1.665), .555),
        ("Review - three-quarter", (2.8, -5, 1.04), (0, 0, .925), 2.16),
        ("Review - side", (5, 0, 1.02), (0, 0, .925), 2.16),
    ]:
        data = bpy.data.cameras.new(name)
        camera = bpy.data.objects.new(name, data)
        scene.collection.objects.link(camera)
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        data.type, data.ortho_scale = "ORTHO", scale
        data.clip_start, data.clip_end = .01, 100
        cameras.append(camera)
    scene.camera = cameras[0]

    notes = bpy.data.texts.new("READ ME - avatar review")
    notes.write(
        "This is a real mesh review scene, not an approved final avatar.\n"
        "The three approved source images are packed into the viewport-only collection.\n"
        "Use the named Review cameras for front / face / side / three-quarter views.\n"
        "Source geometry, source textures and the original candidate remain unchanged.\n"
        "The FBX contains only the model hierarchy, with metres and Unity Y-up axes.\n"
        "Reference helpers, lights and cameras are excluded from the FBX.\n"
        "Production source: Outfit_suit / Outfit_sport / Outfit_none contain "
        "the same fitted head. Enable just one outfit at a time in the Outliner.\n"
        "The other avatar is retained but hidden when present in the source.\n"
        "Validate materials, proportions and runtime switching again in Unity.\n"
        "This static mesh does not claim a humanoid rig or facial animation.\n"
    )
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.clip_end = 100
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_relationship_lines = False
            space.overlay.show_outline_selected = False
            space.shading.type = "MATERIAL"
            space.shading.use_scene_world = False
            space.shading.use_scene_lights = False
            region = space.region_3d
            region.view_perspective = "ORTHO"
            region.view_rotation = Quaternion((1, 0, 0), 1.5707963267948966)
            region.view_location = (-.48, 0, .94)
            region.view_distance = 3.10
    bpy.ops.object.select_all(action="DESELECT")
    objects = [root, *root.children_recursive]
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = root
    export = out / "Liang-review.fbx"
    bpy.ops.export_scene.fbx(
        filepath=str(export), use_selection=True, object_types={"EMPTY", "MESH"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True,
        add_leaf_bones=False, bake_anim=False, use_mesh_modifiers=True,
        mesh_smooth_type="FACE", path_mode="COPY", embed_textures=True,
    )
    bpy.ops.object.select_all(action="DESELECT")
    for obj in scene.objects:
        if (obj.type in {"CAMERA", "LIGHT"} or obj.name == "Candidate floor"
                or obj.name.startswith("Landmark_")):
            obj.hide_set(True)
    if production:
        for obj in root.children_recursive:
            if obj.name.startswith(("Outfit_", "Accessory_")):
                visible = obj.name in {"Outfit_suit", "Accessory_glasses"}
                for member in [obj, *obj.children_recursive]:
                    member.hide_set(not visible)
                    member.hide_render = not visible
    # A portable editable source: external paths are not needed to view it.
    bpy.ops.file.pack_all()
    scene["review_source"] = str(source)
    scene["review_status"] = "candidate; visual acceptance pending"
    destination = out / "Liang-review.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))
    report = {
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "blender_version": bpy.app.version_string, "references": references,
        "blend": str(destination), "fbx": str(export),
        "fbx_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
        "exported_objects": [obj.name for obj in objects],
        "triangles": sum(sum(len(p.vertices)-2 for p in obj.data.polygons)
                         for obj in objects if obj.type == "MESH"),
        "visible_triangles": sum(sum(len(p.vertices)-2 for p in obj.data.polygons)
                                for obj in objects
                                if obj.type == "MESH" and not obj.hide_get()),
        "default_visible_outfit": "suit",
        "status": "candidate; visual acceptance pending",
    }
    (out / "workbench.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
