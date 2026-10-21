#!/usr/bin/env python3
"""Render actual reconstructed geometry from multiple views before Unity import."""
import argparse
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Matrix, Vector


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def bounds(objects):
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    return Vector(tuple(min(p[i] for p in points) for i in range(3))), Vector(
        tuple(max(p[i] for p in points) for i in range(3)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--height", type=float, default=1.85)
    parser.add_argument("--face", action="store_true", help="Also render the upper head of a full body.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if args.mesh.suffix.lower() == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(args.mesh.resolve()))
    elif args.mesh.suffix.lower() == ".obj":
        bpy.ops.wm.obj_import(filepath=str(args.mesh.resolve()))
    else:
        raise ValueError("Provide an actual GLB or OBJ reconstruction.")
    models = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not models:
        raise ValueError("No mesh geometry.")
    # Bake the imported basis into the real vertices before normalizing meters.
    transforms = {obj: obj.matrix_world.copy() for obj in models}
    for obj in models:
        obj.data = obj.data.copy()
        obj.data.transform(transforms[obj])
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
    low, high = bounds(models)
    factor = args.height / (high.z - low.z)
    offset = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for obj in models:
        for vertex in obj.data.vertices:
            vertex.co = (vertex.co - offset) * factor
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.update()
    bpy.context.view_layer.update()
    low, high = bounds(models)
    images = [img for img in bpy.data.images if img.type == "IMAGE" and img.size[0] > 0]
    if not images:
        clay = bpy.data.materials.new("Untextured geometry review")
        clay.use_nodes = True
        clay.diffuse_color = (.22, .24, .27, 1)
        surface = clay.node_tree.nodes.get("Principled BSDF")
        surface.inputs["Base Color"].default_value = clay.diffuse_color
        surface.inputs["Roughness"].default_value = .7
        for obj in models:
            obj.data.materials.clear()
            obj.data.materials.append(clay)
    report = {
        "source": str(args.mesh.resolve()), "sha256": hashlib.sha256(args.mesh.read_bytes()).hexdigest(),
        "kind": "actual 3D geometry review, not a concept image",
        "mesh_objects": len(models),
        "triangles": sum(len(p.vertices) - 2 for obj in models for p in obj.data.polygons),
        "normalized_bounds_m": [list(low), list(high)],
        "textures": [{"name": img.name, "size": list(img.size)} for img in images],
        "bpy_version": bpy.app.version_string,
    }
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1024, 1280
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (.24, .24, .24)
    scene.render.image_settings.file_format = "PNG"
    h = args.height
    for name, location, energy, color in [
        ("Key", (1.5*h, -2*h, 2.5*h), 250*h*h, (1, .97, .93)),
        ("Fill", (-1.5*h, -1.5*h, 1.5*h), 130*h*h, (.93, .97, 1)),
        ("Rim", (.8*h, 1.8*h, 2*h), 160*h*h, (1, 1, 1)),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.shape, data.size, data.color = energy, "DISK", 1.8*h, color
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        aim(obj, (0, 0, .5*h))
    bpy.ops.mesh.primitive_plane_add(size=100*h, location=(0, 0, -.002*h))
    floor = bpy.context.object
    floor.name = "Review floor"
    material = bpy.data.materials.new("Review floor")
    material.diffuse_color = (.52, .55, .58, 1)
    floor.data.materials.append(material)
    data = bpy.data.cameras.new("Review camera")
    camera = bpy.data.objects.new("Review camera", data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    data.type = "ORTHO"
    views = [
        ("front", (0, -3*h, .55*h), (0, 0, .5*h), 1.17*h),
        ("three-quarter", (2*h, -3*h, .7*h), (0, 0, .5*h), 1.22*h),
        ("side", (3*h, 0, .55*h), (0, 0, .5*h), 1.17*h),
        ("back", (0, 3*h, .6*h), (0, 0, .5*h), 1.17*h),
    ]
    if args.face:
        views.append(("face", (0, -3*h, .9*h), (0, 0, .9*h), .30*h))
    for name, location, target, scale in views:
        camera.location, data.ortho_scale = location, scale
        aim(camera, target)
        scene.render.filepath = str((args.out / (name + ".png")).resolve())
        bpy.ops.render.render(write_still=True)
    (args.out / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str((args.out / "review.blend").resolve()))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
