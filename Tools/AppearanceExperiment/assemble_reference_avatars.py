#!/usr/bin/env python3
"""Assemble inspected reference reconstructions into editable Unity FBX assets.

Uses Blender's Python. Sources are never overwritten. --clay makes a geometry
review assembly in a staging folder; textured delivery requires all five inputs.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))


def coordinates(obj):
    values = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", values)
    return values.reshape(-1, 3)


def put_coordinates(obj, values):
    obj.data.vertices.foreach_set("co", np.asarray(values, dtype=np.float32).ravel())
    obj.data.update()


def load_mesh(path, name, height, yaw=0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    extras = [o for o in imported if o.type != "MESH"]
    if not meshes:
        raise ValueError(f"No geometry: {path}")
    world = {o: o.matrix_world.copy() for o in meshes}
    for obj in meshes:
        obj.data = obj.data.copy()
        obj.data.transform(Matrix.Rotation(math.radians(yaw), 4, "Z") @ world[obj])
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    for extra in extras:
        if extra.name in bpy.data.objects:
            bpy.data.objects.remove(extra, do_unlink=True)
    xyz = coordinates(obj)
    low, high = xyz.min(axis=0), xyz.max(axis=0)
    origin = (low + high) / 2
    origin[2] = low[2]
    xyz = (xyz - origin) * (height / (high[2] - low[2]))
    put_coordinates(obj, xyz)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


def keep_world_parent(obj, parent):
    matrix = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = matrix


def remove_old_head(obj):
    """Open a collar-shaped neck boundary without cutting the shoulders."""
    images = [node.image for mat in obj.data.materials if mat and mat.use_nodes
              for node in mat.node_tree.nodes if node.type == "TEX_IMAGE" and node.image]
    protected = set()
    if images and obj.data.uv_layers.active:
        image = images[0]
        pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(-1, 4)
        uv = obj.data.uv_layers.active.data
        w, h = image.size
        for face in obj.data.polygons:
            if not 1.56 < face.center.z < 1.64:
                continue
            sample = sum((uv[i].uv for i in face.loop_indices), Vector((0, 0))) / len(face.loop_indices)
            x, y = int(sample.x * w) % w, int(sample.y * h) % h
            r, g, b = pixels[y * w + x, :3]
            blue = b > r * 1.18 and b > g * 1.05
            white = min(r, g, b) > .4 and b > r * .95 and g > r * .95
            if blue or white:
                protected.add(face.index)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    remove = []
    for face in bm.faces:
        center = face.calc_center_median()
        if center.z > 1.64 or (center.z > 1.56 and abs(center.x) < .14
                              and face.index not in protected):
            remove.append(face)
    bmesh.ops.delete(bm, geom=remove, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    # Color boundaries can leave faces touching at a single vertex. Remove
    # those tiny pinches so the collar is a simple closed loop.
    for _ in range(12):
        pinched = [v for v in bm.verts if sum(edge.is_boundary for edge in v.link_edges) > 2]
        if not pinched:
            break
        faces = {face for v in pinched for face in v.link_faces}
        bmesh.ops.delete(bm, geom=list(faces), context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    # Discard detached collar pixels; keep the connected body surface.
    remaining = set(bm.verts)
    components = []
    while remaining:
        first = remaining.pop()
        component, pending = {first}, [first]
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    component.add(other)
                    pending.append(other)
        components.append(component)
    keep = max(components, key=len)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def cut_at(obj, z, keep_below):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # Weld only after simplification. Collapsing a welded UV atlas can blend
    # unrelated atlas islands, whereas per-face UV loops survive this weld.
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bmesh.ops.bisect_plane(
        bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), dist=1e-7,
        plane_co=(0, 0, z), plane_no=(0, 0, 1),
        clear_outer=keep_below, clear_inner=not keep_below,
    )
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def join_objects(objects, active):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    return active


def neck_ring(bm, z=None):
    edges = {edge for edge in bm.edges if edge.is_boundary and
             (z is None or all(abs(v.co.z - z) < 2e-5 for v in edge.verts))}
    rings = []
    while edges:
        seed = edges.pop()
        vertices, pending = set(seed.verts), list(seed.verts)
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                if edge not in edges:
                    continue
                edges.remove(edge)
                other = edge.other_vert(vertex)
                if other not in vertices:
                    vertices.add(other)
                    pending.append(other)
        if len(vertices) >= 3:
            center = sum((v.co for v in vertices), Vector()) / len(vertices)
            rings.append((abs(center.x), center, vertices))
    if not rings:
        raise ValueError(f"No neck boundary at {z}")
    _, center, vertices = max(rings, key=lambda item: len(item[2]))
    adjacent = {v: [edge.other_vert(v) for edge in v.link_edges
                    if edge.is_boundary and edge.other_vert(v) in vertices]
                for v in vertices}
    if any(len(others) != 2 for others in adjacent.values()):
        raise ValueError("Neck boundary branches; cannot bridge it safely.")
    first = min(vertices, key=lambda v: v.co.y)
    ordered, previous, current = [first], first, adjacent[first][0]
    while current is not first:
        ordered.append(current)
        following = next(v for v in adjacent[current] if v is not previous)
        previous, current = current, following
    area = sum(v.co.x * ordered[(i + 1) % len(ordered)].co.y -
               ordered[(i + 1) % len(ordered)].co.x * v.co.y
               for i, v in enumerate(ordered))
    if area < 0:
        ordered = [ordered[0], *reversed(ordered[1:])]
    return ordered, center


def smooth_collar_boundary(obj, maximum_displacement=.0025, iterations=16):
    """Soften the cut's triangle-sized teeth while preserving the collar shape.

    Only the boundary and its immediate neighbours move. Original UV loops,
    materials and topology stay intact, and every displacement is bounded.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ring, _ = neck_ring(bm)
    original = {vertex: vertex.co.copy() for vertex in bm.verts}
    boundary = set(ring)
    neighbours = {edge.other_vert(vertex) for vertex in ring
                  for edge in vertex.link_edges} - boundary
    for _ in range(iterations):
        updates = {}
        for index, vertex in enumerate(ring):
            mean = (ring[index - 1].co + ring[(index + 1) % len(ring)].co) / 2
            proposed = vertex.co + .45 * (mean - vertex.co)
            shift = proposed - original[vertex]
            if shift.length > maximum_displacement:
                proposed = original[vertex] + shift.normalized() * maximum_displacement
            updates[vertex] = proposed
        for vertex, point in updates.items():
            vertex.co = point
    # Fade the boundary displacement into one adjacent ring, without shrinking
    # the broader lapel or rounding away the collar's characteristic points.
    for vertex in neighbours:
        adjacent = [edge.other_vert(vertex) for edge in vertex.link_edges
                    if edge.other_vert(vertex) in boundary]
        if adjacent:
            vertex.co += .35 * sum((other.co - original[other] for other in adjacent),
                                    Vector()) / len(adjacent)
    displacements = [(vertex.co - original[vertex]).length for vertex in bm.verts]
    report = {
        "method": "Bounded smoothing of collar cut edge, faded into one adjacent ring",
        "boundary_vertices": len(ring), "iterations": iterations,
        "maximum_allowed_displacement_m": maximum_displacement,
        "maximum_actual_displacement_m": max(displacements),
        "moved_vertices": sum(distance > 1e-8 for distance in displacements),
        "topology_uv_and_materials_unchanged": True,
    }
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return report


def angular_positions(ring):
    """Keep topological order, but match front/right/back/left anatomically."""
    xyz = np.array([list(v.co) for v in ring])
    center = (xyz.min(axis=0) + xyz.max(axis=0)) / 2
    theta = (np.arctan2(xyz[:, 1] - center[1], xyz[:, 0] - center[0])
             + math.pi / 2) % math.tau
    start = int(np.argmin(theta))
    ordered = ring[start:] + ring[:start]
    theta = np.unwrap(np.roll(theta, -start))
    theta -= theta[0]
    # The collar has tiny in/out zigzags. Preserve its boundary topology while
    # preventing a backward angular step from crossing adjacent bridge strips.
    backwards = int(np.sum(np.diff(theta) < 0))
    theta = np.maximum.accumulate(theta)
    theta += np.arange(len(theta)) * 1e-8
    assert theta[-1] < math.tau
    return ordered, [*list(theta / math.tau), 1.0], {
        "vertices": len(ring), "center": center.tolist(),
        "backward_angle_steps_clamped": backwards,
        "start_xyz": list(ordered[0].co),
    }


def source_uv_projector(mesh):
    vertices = [v.co.copy() for v in mesh.vertices]
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    assert all(len(p) == 3 for p in polygons)
    uv = mesh.uv_layers.active.data
    triangle_uvs = [[Vector((*uv[i].uv, 0.0)) for i in p.loop_indices]
                    for p in mesh.polygons]
    tree = BVHTree.FromPolygons(vertices, polygons, all_triangles=True)

    def project(point):
        location, _, face_index, _ = tree.find_nearest(point)
        a, b, c = (vertices[i] for i in polygons[face_index])
        u, v, w = triangle_uvs[face_index]
        return barycentric_transform(location, a, b, c, u, v, w).xy
    return project


def cut_head_above_collar(head, body, minimum_height):
    """Cut low under the chin, high behind the neck; preserve the whole jaw."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    lower, _ = neck_ring(bm)
    lower, phases, _ = angular_positions(lower)
    xyz = np.array([list(v.co) for v in [*lower, lower[0]]])
    sample_phases = np.arange(256) / 256
    collar_z = np.interp(sample_phases, phases, xyz[:, 2])
    # A small circular envelope avoids dipping below a sawtoothed collar rim.
    envelope = np.maximum.reduce([np.roll(collar_z, step) for step in range(-4, 5)])
    for _ in range(4):
        envelope = (.5 * envelope + .25 * np.roll(envelope, 1)
                    + .25 * np.roll(envelope, -1))
    heights = np.maximum(minimum_height, np.maximum(envelope + .012, collar_z + .008))
    bm.free()
    coords = coordinates(head)
    neck = coords[(coords[:, 2] > 1.58) & (coords[:, 2] < 1.64)]
    center = (neck[:, :2].min(axis=0) + neck[:, :2].max(axis=0)) / 2

    def cut_z(point):
        phase = ((math.atan2(point.y - center[1], point.x - center[0])
                  + math.pi / 2) % math.tau) / math.tau
        return float(np.interp(phase, np.r_[sample_phases, 1],
                               np.r_[heights, heights[0]]))

    bm = bmesh.new()
    bm.from_mesh(head.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    for vertex in bm.verts:
        vertex.co.z -= cut_z(vertex.co)
    bmesh.ops.bisect_plane(
        bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), dist=1e-7,
        plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True,
    )
    for vertex in bm.verts:
        vertex.co.z += cut_z(vertex.co)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(head.data)
    bm.free()
    head.data.update()
    return {"minimum": float(heights.min()), "maximum": float(heights.max()),
            "angular_center": center.tolist()}


def connect_neck(body, source_head, intermediate_rings=7, projection_mesh=None):
    bm_body = bmesh.new()
    bm_body.from_mesh(body.data)
    boundary, _ = neck_ring(bm_body)
    boundary_coords = [tuple(v.co) for v in boundary]
    bm_body.free()
    bm_head = bmesh.new()
    bm_head.from_mesh(source_head.data)
    head_boundary, _ = neck_ring(bm_head)
    upper_coords = [tuple(v.co) for v in head_boundary]
    bm_head.free()
    copy = source_head.copy()
    copy.data = source_head.data.copy()
    bpy.context.collection.objects.link(copy)
    join_objects([body, copy], body)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    lookup = {tuple(v.co): v for v in bm.verts}
    lower = [lookup[co] for co in boundary_coords]
    upper = [lookup[co] for co in upper_coords]
    lower, a, lo_report = angular_positions(lower)
    upper, b, hi_report = angular_positions(upper)
    uv_layer = bm.loops.layers.uv.active
    front = min(upper, key=lambda v: v.co.y)
    neck_uv = front.link_loops[0][uv_layer].uv.copy()
    material_index = next(i for i, mat in enumerate(body.data.materials)
                          if mat.name.startswith("Fixed_Liang_DetailedHead"))
    new_faces = []

    def stitch(first, aa, second, bb):
        i = j = 0
        while i < len(first) or j < len(second):
            next_a = aa[i + 1] if i < len(first) else float("inf")
            next_b = bb[j + 1] if j < len(second) else float("inf")
            if next_a <= next_b:
                verts = (first[i % len(first)], first[(i + 1) % len(first)],
                         second[j % len(second)])
                i += 1
            else:
                verts = (first[i % len(first)], second[(j + 1) % len(second)],
                         second[j % len(second)])
                j += 1
            face = bm.faces.new(verts)
            face.material_index = material_index
            face.smooth = True
            for loop in face.loops:
                loop[uv_layer].uv = neck_uv
            new_faces.append(face)

    previous, previous_parameters = lower, a
    if intermediate_rings:
        samples = 128
        phases = np.arange(samples) / samples

        def interpolate(ring, parameters):
            xyz = np.array([list(v.co) for v in [*ring, ring[0]]])
            return np.column_stack([np.interp(phases, parameters, xyz[:, axis])
                                    for axis in range(3)])

        lower_samples = interpolate(lower, a)
        upper_samples = interpolate(upper, b)
        for level in range(1, intermediate_rings + 1):
            blend = level / (intermediate_rings + 1)
            xyz = lower_samples * (1 - blend) + upper_samples * blend
            # Smooth collar sampling noise in free interior vertices only.
            # Every original collar/head boundary edge remains exactly fixed.
            amount = .45 * math.sin(math.pi * blend)
            for _ in range(6):
                neighbors = (np.roll(xyz, 1, axis=0) + np.roll(xyz, -1, axis=0)) * .5
                xyz += amount * (neighbors - xyz)
            current = [bm.verts.new(co) for co in xyz]
            parameters = [*phases.tolist(), 1.0]
            stitch(previous, previous_parameters, current, parameters)
            previous, previous_parameters = current, parameters
    stitch(previous, previous_parameters, upper, b)
    uv_seams = 0
    if projection_mesh:
        project = source_uv_projector(projection_mesh)
        for face in new_faces:
            projected = [project(loop.vert.co) for loop in face.loops]
            # Do not interpolate across distant islands of the packed UV atlas.
            span = np.ptp(np.array([list(uv) for uv in projected]), axis=0)
            if max(span) > .08:
                projected = [project(face.calc_center_median())] * len(face.loops)
                uv_seams += 1
            for loop, uv in zip(face.loops, projected):
                loop[uv_layer].uv = uv
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    report = {
        "lower": lo_report, "upper": hi_report,
        "bridge_faces": len(new_faces),
        "bridge_boundary_edges": sum(edge.is_boundary for face in new_faces
                                     for edge in face.edges),
        "bridge_zero_area_faces": sum(face.calc_area() < 1e-12 for face in new_faces),
        "lower_z_bounds": [min(v.co.z for v in lower), max(v.co.z for v in lower)],
        "upper_z_bounds": [min(v.co.z for v in upper), max(v.co.z for v in upper)],
        "intermediate_rings": intermediate_rings,
        "projected_uv": projection_mesh is not None,
        "uv_seam_face_fallbacks": uv_seams,
    }
    assert report["bridge_boundary_edges"] == 0, "Neck bridge has an open edge"
    assert report["bridge_zero_area_faces"] == 0, "Neck bridge has a degenerate face"
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return report


def simplify(obj, budget):
    count = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if count <= budget:
        return
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("Mobile geometry budget", "DECIMATE")
    mod.ratio = budget / count
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)


def material(name, color=(.22, .24, .27, 1), metal=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    # User startup preferences may localize default node names in the native
    # desktop application. Node types remain stable across UI languages.
    shader = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = .72 if not metal else .32
    shader.inputs["Metallic"].default_value = metal
    return mat


def smoothstep(low, high, values):
    x = np.clip((values - low) / (high - low), 0, 1)
    return x * x * (3 - 2 * x)


def protect_fixed_regions(obj, pixels, mask, width, height, name):
    """Project fixed shoe/skin/white-fabric faces into the existing UV atlas."""
    uv = obj.data.uv_layers.active.data
    excluded = np.zeros((height, width), dtype=bool)
    is_suit = "Suit" in name
    for face in obj.data.polygons:
        coords = np.array([uv[i].uv[:] for i in face.loop_indices])
        center_uv = coords.mean(axis=0)
        x, y = int(center_uv[0] * width) % width, int(center_uv[1] * height) % height
        r, g, b = pixels[y * width + x, :3]
        value = max(r, g, b, .001)
        white = value > .25 and (value - min(r, g, b)) / value < .38
        skin = r > b * 1.25 and r > g * 1.08
        shoe = ((face.center.z < .14 and value < .28) if is_suit
                else face.center.z < .22)
        if not (white or skin or shoe):
            continue
        coords *= (width, height)
        for i in range(1, len(coords) - 1):
            a, b, c = coords[[0, i, i + 1]]
            low = np.maximum(np.floor(np.minimum(np.minimum(a, b), c)).astype(int), 0)
            high = np.minimum(np.ceil(np.maximum(np.maximum(a, b), c)).astype(int),
                              [width - 1, height - 1])
            if np.any(high < low):
                continue
            xx, yy = np.meshgrid(np.arange(low[0], high[0] + 1) + .5,
                                 np.arange(low[1], high[1] + 1) + .5)
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-8:
                continue
            u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
            v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
            excluded[low[1]:high[1] + 1, low[0]:high[0] + 1] |= (u >= 0) & (v >= 0) & (u + v <= 1)
    # A small guard band prevents filtering/mipmaps from tinting skin at seams.
    for _ in range(1):
        padded = np.pad(excluded, 1)
        excluded = np.logical_or.reduce([padded[y:y + height, x:x + width]
                                         for y in range(3) for x in range(3)])
    mask[excluded.ravel()] = 0
    return mask


def bind_texture(obj, name, output, clay, mask_kind=None):
    repair_report = None
    images = []
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            images.extend(node.image for node in mat.node_tree.nodes
                          if node.type == "TEX_IMAGE" and node.image)
    images = list(dict.fromkeys(images))
    mat = material(name, (1, 1, 1, 1) if not clay else (.22, .24, .27, 1))
    if not clay:
        if len(images) != 1:
            raise ValueError(f"{obj.name}: expected one albedo, found {len(images)}")
        image = images[0].copy()
        image.name = name + "_Albedo"
        if name == "Tint_LiangBare_Reference":
            from repair_bare_texture import repair_mirrored_skin
            # A source-GLB paint defect, measured by raycasting the Unity
            # side view. This box stays above the shorts and away from hands.
            repair_report = repair_mirrored_skin(
                obj, image, lower=(-.19, -.045, 1.09),
                upper=(-.115, .09, 1.23))
        image.filepath_raw = str((output / (image.name + ".png")).resolve())
        image.file_format = "PNG"
        image.save()
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        shader = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
        mat.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
        if mask_kind:
            pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(-1, 4)
            r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
            value = np.maximum(np.maximum(r, g), b)
            if mask_kind == "blue-cloth":
                # White shirts, skin and shoes remain fixed. Every clothing
                # variant starts blue, so its fabric supplies the mask.
                mask = smoothstep(.18, .26, (b - r) / np.maximum(value, .001))
                mask *= smoothstep(-.05, .025, (b - g) / np.maximum(value, .001))
                mask = protect_fixed_regions(obj, pixels, mask, image.size[0], image.size[1], name)
            elif mask_kind == "gold-body":
                # Saturated golden skin; exclude cream belly, green eyes and
                # dark olive fingers/feet from body color changes.
                mask = smoothstep(.42, .64, (np.minimum(r, g) - b) / np.maximum(value, .001))
                mask *= smoothstep(.34, .55, value)
                mask *= smoothstep(.9, 1.05, r / np.maximum(g, .001))
            else:
                raise ValueError(mask_kind)
            data = np.ones_like(pixels)
            data[:, :3] = mask[:, None]
            mask_image = bpy.data.images.new(
                name + "_Mask", width=image.size[0], height=image.size[1],
                alpha=False,
            )
            mask_image.colorspace_settings.name = "Non-Color"
            mask_image.pixels.foreach_set(data.ravel())
            mask_image.filepath_raw = str((output / (mask_image.name + ".png")).resolve())
            mask_image.file_format = "PNG"
            mask_image.save()
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.material_index = 0
    return repair_report


def tube(name, points, radius, mat, parent, closed=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 2
    data.bevel_depth = radius
    data.bevel_resolution = 3
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for target, point in zip(spline.points, points):
        target.co = (*point, 1)
    spline.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    keep_world_parent(obj, parent)
    return obj


def glasses(parent, eye_center, width=.155, lens_height=.028, temple_spread=.025, head_surface=None):
    x0, y0, z0 = eye_center
    slope = 0.

    def front_surface(x, z, fallback):
        if head_surface is None:
            return fallback
        hit, location, _, _ = head_surface.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), distance=2)
        return location.y if hit else fallback

    if head_surface is not None:
        # The reconstructed face is slightly turned; the bounding-box center
        # is not the nose bridge. Fit the frame to actual facial geometry.
        xyz = coordinates(head_surface)
        nose = xyz[(np.abs(xyz[:, 2] - (z0 - .024)) < .008) & (np.abs(xyz[:, 0]) < .075)]
        if len(nose):
            x0 = float(np.median(nose[nose[:, 1] < np.quantile(nose[:, 1], .03), 0]))
        left = front_surface(x0 - width * .258, z0, y0 + .008)
        right = front_surface(x0 + width * .258, z0, y0 + .008)
        y0 = (left + right) / 2 - .008
        slope = (right - left) / (width * .516)

    def frame_point(x, y, z):
        adjusted = y + slope * (x - x0)
        return (x, min(adjusted, front_surface(x, z, adjusted + .003) - .003), z)

    frame = material("Metal_Thin_Rectangular_Glasses", (.085, .09, .10, 1), .75)
    lens_width = width * .42
    centers = [-width * .258, width * .258]
    for side, cx in enumerate(centers):
        points = []
        for i in range(64):
            angle = i * math.tau / 64
            c, s = math.cos(angle), math.sin(angle)
            x = math.copysign(abs(c) ** .45, c) * lens_width / 2
            z = math.copysign(abs(s) ** .45, s) * lens_height / 2
            # Follow the cheek curvature without making opaque lenses.
            points.append(frame_point(x0 + cx + x, y0 + .005 * (abs(cx + x) / (width / 2)) ** 2, z0 + z))
        tube(f"Rectangular rim {side}", points, .00115, frame, parent, True)
    # Meet the actual inner rim points; a human-sized fixed bridge leaves
    # visible gaps when the same glasses are widened for the mascot.
    bridge_half = width * (.258 - .42 / 2)
    rim_y = y0 + .005 * (bridge_half / (width / 2)) ** 2
    tube("Nose bridge", [frame_point(*point) for point in [
        (x0 - bridge_half, rim_y, z0),
        (x0 - bridge_half * .45, y0 - .008, z0 + lens_height * .22),
        (x0 + bridge_half * .45, y0 - .008, z0 + lens_height * .22),
        (x0 + bridge_half, rim_y, z0),
    ]], .0011, frame, parent)
    for sign in [-1, 1]:
        x = x0 + sign * width * .485
        points = [
            (x, y0 + .004, z0 + .003), (x + sign * temple_spread, y0 + .045, z0 + .004),
            (x + sign * temple_spread, y0 + .09, z0),
            (x + sign * (temple_spread - .004), y0 + .105, z0 - .012),
        ]
        if head_surface is not None:
            hinge = frame_point(x, y0 + .004, z0 + .003)
            points = [hinge]
            for index in range(1, 7):
                y = hinge[1] + (.010 - hinge[1]) * index / 6
                z = z0 + .004 if index < 5 else z0 - .014 * (index - 4) / 2
                hit, location, _, _ = head_surface.ray_cast(
                    Vector((sign, y, z)), Vector((-sign, 0, 0)), distance=2)
                x = location.x + sign * .0025 if hit else points[-1][0]
                points.append((x, y, z))
        tube("Temple " + str(sign), points, .0012, frame, parent)


def fitted_cap_parameters(surface, base_height):
    """Fit an elliptical cap around the real upper head, including its offset."""
    xyz = coordinates(surface)
    band = xyz[np.abs(xyz[:, 2] - base_height) < .004]
    if len(band) < 12:
        raise ValueError("Insufficient head surface around the cap opening.")
    low, high = band.min(axis=0), band.max(axis=0)
    center = [(float(low[0]) + float(high[0])) / 2,
              (float(low[1]) + float(high[1])) / 2, base_height]
    depth_ratio = float((high[1] - low[1]) / (high[0] - low[0]))
    height_ratio = .72
    upper = xyz[xyz[:, 2] >= base_height] - np.asarray(center)
    radius = float(np.linalg.norm(upper / [1, depth_ratio, height_ratio], axis=1).max()) + .004
    return {"center": center, "radius": radius, "depth_ratio": depth_ratio,
            "height_ratio": height_ratio, "clearance_m": .004,
            "method": "Upper-head mesh sections, including actual front/back centre"}


def cap(parent, center, radius, depth_ratio=.9, height_ratio=.62, **_report):
    def clean_surface(mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

    fabric = material("Fixed_Cap_Charcoal", (.035, .045, .06, 1))
    vertices, faces = [], []
    cx, cy, z = center
    rings, sides = 12, 48
    for j in range(rings + 1):
        angle = .5 * math.pi * j / rings
        for i in range(sides):
            phi = math.tau * i / sides
            vertices.append((cx + radius * math.cos(angle) * math.cos(phi),
                             cy + radius * depth_ratio * math.cos(angle) * math.sin(phi),
                             z + radius * height_ratio * math.sin(angle)))
    for j in range(rings):
        for i in range(sides):
            a = j * sides + i
            b = j * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    mesh = bpy.data.meshes.new("Cap crown")
    mesh.from_pydata(vertices, [], faces)
    clean_surface(mesh)
    obj = bpy.data.objects.new("Cap crown", mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(fabric)
    for poly in mesh.polygons:
        poly.use_smooth = True
    keep_world_parent(obj, parent)
    # Join the visor to the front ellipse of the crown. The previous
    # independent arc left two disconnected-looking lines at its sides.
    verts, faces = [], []
    for layer in [-1, 1]:
        for ring in [0, 1]:
            for i in range(25):
                fraction = -1 + 2 * i / 24
                x = fraction * radius * .92
                inner = -radius * depth_ratio * math.sqrt(1 - (x / radius) ** 2)
                extension = ring * radius * .58 * math.sqrt(1 - fraction * fraction)
                verts.append((cx + x, cy + inner - extension,
                              z - .045 * extension + layer * .0018))
    for layer in range(2):
        off = layer * 50
        for i in range(24):
            faces.append((off + i, off + i + 1, off + i + 26, off + i + 25))
    for row in [0, 25]:
        for i in range(24):
            faces.append((row + i, row + i + 1, row + i + 51, row + i + 50))
    mesh = bpy.data.meshes.new("Cap brim")
    mesh.from_pydata(verts, [], faces)
    clean_surface(mesh)
    obj = bpy.data.objects.new("Cap brim", mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(fabric)
    keep_world_parent(obj, parent)


def export(root, output, default_groups):
    bpy.ops.object.select_all(action="DESELECT")
    all_objects = [root, *root.children_recursive]
    for obj in all_objects:
        obj.hide_render = False
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.fbx(
        filepath=str((output / (root.name + ".fbx")).resolve()),
        use_selection=True, object_types={"EMPTY", "MESH"},
        axis_forward="-Z", axis_up="Y", add_leaf_bones=False, bake_anim=False,
        apply_unit_scale=True, use_mesh_modifiers=True, mesh_smooth_type="FACE",
        path_mode="RELATIVE", use_custom_props=True,
    )
    bpy.ops.object.select_all(action="DESELECT")
    hidden = set()
    for obj in all_objects:
        if obj.name.startswith(("Outfit_", "Accessory_")) and obj.name not in default_groups:
            hidden.update([obj, *obj.children_recursive])
    for obj in all_objects:
        obj.select_set(obj not in hidden)
    bpy.ops.export_scene.gltf(
        filepath=str((output / (root.name + "-default.glb")).resolve()),
        export_format="GLB", use_selection=True, export_apply=True,
    )
    return {
        "triangles_all_variants": sum(sum(len(p.vertices) - 2 for p in o.data.polygons)
                                     for o in all_objects if o.type == "MESH"),
        "meshes": [{"name": o.name, "triangles": sum(len(p.vertices) - 2 for p in o.data.polygons),
                    "materials": [m.name for m in o.data.materials]}
                   for o in all_objects if o.type == "MESH"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, default=ROOT / "StudyData/avatar-v3/generated")
    parser.add_argument("--out", type=Path, default=ROOT / "StudyData/avatar-v3/unity-staging/AvatarDemo")
    parser.add_argument("--clay", action="store_true")
    script_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None
    args = parser.parse_args(script_args)
    args.out.mkdir(parents=True, exist_ok=True)
    textures = args.out / "Textures"
    textures.mkdir(exist_ok=True)
    # A background production export must not inherit a user's startup scene,
    # language-dependent node names, or object transforms.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = "textured.glb"
    names = ["liang", "liang-head", "liang-sport", "liang-bare", "nailong"]
    paths = {name: args.generated / name / suffix for name in names}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    sources = {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
               for name, path in paths.items()}
    from fit_landmark_head_candidate import prepare_reference_head, SUIT_NECK_AXIS
    import repair_neck_candidate as neck_repair

    liang = empty("Liang")
    # One landmark-fitted prototype is shared by every outfit. Only copies
    # receive collar-specific cuts, so changing clothes cannot move the face.
    head_axis = SUIT_NECK_AXIS.copy()
    head = load_mesh(paths["liang-head"], "Face_Hair_Ears_Neck", .315)
    head_report = prepare_reference_head(head, head_axis)
    bind_texture(head, "Fixed_Liang_DetailedHead", textures, args.clay)
    projection_mesh = head.data.copy()
    neck_reports = {}
    texture_repairs = {}
    for key, source, mat_name in [
        ("suit", "liang", "Tint_LiangSuit_Reference"),
        ("sport", "liang-sport", "Tint_LiangSport_Reference"),
        ("none", "liang-bare", "Tint_LiangBare_Reference"),
    ]:
        obj = load_mesh(paths[source], "Body_" + key, 1.85)
        neck_reference_mesh = obj.data.copy() if key == "none" else None
        texture_repair = bind_texture(obj, mat_name, textures, args.clay, "blue-cloth")
        if texture_repair:
            texture_repairs[key] = texture_repair
        remove_old_head(obj)
        boundary_report = (smooth_collar_boundary(obj) if key != "none" else
                           neck_repair.smooth_bare_neck_boundary(
                               obj, head_axis, reference_head=head))
        fitted_head = head.copy()
        fitted_head.data = head.data.copy()
        bpy.context.collection.objects.link(fitted_head)
        cut_report = neck_repair.cut_head_above_collar(
            fitted_head, obj, 1.55, neck_axis_xy=head_axis,
            anatomical_nape_height=1.665, anatomical_front_height=1.59)
        neck_reports[key] = neck_repair.connect_neck(
            obj, fitted_head, 7, projection_mesh,
            transition_texture_dir=None if args.clay else textures,
            neck_material_name="Fixed_LiangNeck_" + key,
            extend_neck_skin=True, match_upper_tangent=True,
            neck_reference_mesh=neck_reference_mesh, neck_axis_xy=head_axis)
        neck_reports[key]["cut"] = cut_report
        neck_reports[key]["boundary_smoothing"] = boundary_report
        neck_reports[key]["shared_head_prototype_sha256"] = head_report["prototype_coordinates_sha256"]
        bpy.data.objects.remove(fitted_head, do_unlink=True)
        keep_world_parent(obj, empty("Outfit_" + key, liang))
    points = coordinates(head)
    eye_z = head_report["final_eye_z_m"]
    # Vertices are stored in world coordinates before parenting; transforms
    # preserve this geometry. Sample only cheeks, away from nose protrusion.
    cheek = points[(np.abs(points[:, 2] - eye_z) < .012) &
                   (np.abs(points[:, 0] - head_axis[0]) > .025) &
                   (np.abs(points[:, 0] - head_axis[0]) < .075)]
    eye_y = float(np.quantile(cheek[:, 1], .04)) - .003
    pivot = empty("AccessoriesAnchor", liang)
    eyewear = empty("Accessory_glasses", pivot)
    glasses(eyewear, (float(head_axis[0]), eye_y, eye_z), width=.145 * 1.12,
            lens_height=.035, temple_spread=.015, head_surface=head)
    hat = empty("Accessory_hat", pivot)
    liang_cap = fitted_cap_parameters(head, 1.772)
    cap(hat, **liang_cap)
    bpy.data.objects.remove(head, do_unlink=True)
    liang_report = export(liang, args.out, {"Outfit_suit", "Accessory_glasses"})
    # Blender object names are global; the two independent FBX roots each need
    # exact Outfit_none / Accessory_* names for the runtime contract.
    for child in liang.children_recursive:
        child.name = "BuiltLiang_" + child.name
    nailong = empty("Nailong")
    obj = load_mesh(paths["nailong"], "Nailong_reference_surface", 1.84, yaw=90)
    simplify(obj, 55000)
    bind_texture(obj, "Tint_Nailong_Reference", textures, args.clay, "gold-body")
    keep_world_parent(obj, empty("Outfit_none", nailong))
    eyewear = empty("Accessory_glasses", nailong)
    glasses(eyewear, (0, -.218, 1.686), width=.30, lens_height=.100, head_surface=obj)
    hat = empty("Accessory_hat", nailong)
    nailong_cap = fitted_cap_parameters(obj, 1.74)
    cap(hat, **nailong_cap)
    nailong_report = export(nailong, args.out, {"Outfit_none"})
    bpy.ops.wm.save_as_mainfile(filepath=str((args.out / "assembled.blend").resolve()))
    report = {
        "clay_only": args.clay, "sources": sources, "liang": liang_report,
        "nailong": nailong_report,
        "geometry_revision": "blender-landmark-neck-fit-v3",
        "texture_revision": "blender-bare-skin-cleanup-v2",
        "texture_repairs": texture_repairs,
        "head_fit": head_report,
        "head_axis_xy_m": head_axis.tolist(),
        "neck_bridges": neck_reports,
        "cap_fits": {"liang": liang_cap, "nailong": nailong_cap},
        "body_head_cut": "continuous neck bridge around the preserved collar, no planar shoulder cut",
        "animation": "static reference reconstruction; no full-body tracking or facial rig claimed",
        "bpy_version": bpy.app.version_string,
    }
    (args.out / "assembly.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
