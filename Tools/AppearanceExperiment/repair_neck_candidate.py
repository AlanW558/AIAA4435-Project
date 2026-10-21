#!/usr/bin/env python3
"""Isolated neck-bridge experiment; never writes the main AvatarDemo staging."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = Path(__file__).with_name("assemble_reference_avatars.py")
base = None


def _load_base():
    """Delay loading so the main assembler may import these repair helpers."""
    global base
    if base is None:
        spec = importlib.util.spec_from_file_location("neck_candidate_base", BASE_PATH)
        base = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(base)
    return base


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


def smooth_bare_neck_boundary(body, neck_axis_xy, iterations=12, reference_head=None):
    """Remove the bare body's anterior cut-edge spikes without moving clothing."""
    _load_base()
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    ring, _ = base.neck_ring(bm)
    before = {vertex: vertex.co.copy() for vertex in bm.verts}
    depth = {vertex: 0 for vertex in ring}
    frontier = set(ring)
    for level in range(1, 4):
        following = {edge.other_vert(vertex) for vertex in frontier
                     for edge in vertex.link_edges} - depth.keys()
        depth.update({vertex: level for vertex in following})
        frontier = following
    axis = np.asarray(neck_axis_xy, dtype=np.float64)

    def s(value):
        value = max(0., min(1., value))
        return value*value*(3-2*value)

    weights = {}
    for vertex, level in depth.items():
        x, y, z = before[vertex]
        front = 1-s((y-(axis[1]-.065))/.080)
        lateral = 1-s((abs(x-axis[0])-.055)/.045)
        weights[vertex] = float(front*lateral*(1., .60, .25, 0.)[level])
    for _ in range(iterations):
        updates = {}
        for vertex, weight in weights.items():
            if weight <= 0:
                continue
            neighbors = [edge.other_vert(vertex).co for edge in vertex.link_edges]
            mean = sum(neighbors, Vector())/len(neighbors)
            proposed = vertex.co + .45*weight*(mean-vertex.co)
            shift = proposed-before[vertex]
            if shift.length > .012:
                proposed = before[vertex] + shift.normalized()*.012
            updates[vertex] = proposed
        for vertex, point in updates.items():
            vertex.co = point
    retractions = {}
    if reference_head is not None:
        reference = reference_head.data
        tree = BVHTree.FromPolygons(
            [vertex.co.copy() for vertex in reference.vertices],
            [list(polygon.vertices) for polygon in reference.polygons], all_triangles=True,
        )
        for vertex in ring:
            x, y, z = vertex.co
            lateral = 1-s((abs(x-axis[0])-.045)/.020)
            front = 1-s((y-(axis[1]-.055))/.045)
            if front*lateral <= 0:
                continue
            point, _, _, _ = tree.ray_cast(
                Vector((x, -1., max(z, 1.55)+.020)), Vector((0, 1, 0)), 2.,
            )
            if point is not None:
                retractions[vertex] = max(0., point.y+.001-y)*front*lateral
        # Transfer the boundary correction smoothly into the same two body
        # rings; do not touch the chest or alter UVs/topology.
        seeds = list(retractions)
        if seeds:
            seed_xyz = np.asarray([list(vertex.co) for vertex in seeds])
            seed_shift = np.asarray([retractions[vertex] for vertex in seeds])
            for vertex, level in depth.items():
                if level == 0:
                    vertex.co.y += float(retractions.get(vertex, 0.))
                elif level < 3:
                    distances = np.linalg.norm(seed_xyz-np.asarray(vertex.co), axis=1)
                    nearest = np.argsort(distances)[:3]
                    inverse_distances = 1/np.maximum(distances[nearest], .001)
                    shift = float(np.sum(seed_shift[nearest]*inverse_distances)/inverse_distances.sum())
                    fade = (1., .60, .25)[level]*(1-s(float(distances[nearest[0]])/.025))
                    vertex.co.y += shift*fade
    # A triangle-cut body boundary can make short backward angular steps at
    # the trapezius. A sparse bridge fan crossing such a notch folds over
    # itself even when every edge is manifold. Regularize only those local
    # posterior notches, preserving the topological vertex order and UVs.
    posterior_before = {vertex: vertex.co.copy() for vertex in bm.verts}
    ordered, _, _ = angular_positions(ring)
    xy = np.asarray([list(vertex.co)[:2] for vertex in ordered])
    angles = np.unwrap(np.arctan2(xy[:, 1]-axis[1], xy[:, 0]-axis[0]))
    bad_edges = [index for index in range(len(ordered)-1)
                 if angles[index+1] < angles[index]-1e-5
                 and min(ordered[index].co.y, ordered[index+1].co.y) > axis[1]+.005]
    selected = {ordered[(index+offset) % len(ordered)]
                for index in bad_edges for offset in range(-3, 5)}
    for _ in range(24):
        updates = {}
        for index, vertex in enumerate(ordered):
            if vertex not in selected:
                continue
            mean = (ordered[index-1].co+ordered[(index+1) % len(ordered)].co)/2
            proposed = vertex.co + .40*(mean-vertex.co)
            displacement = proposed-posterior_before[vertex]
            if displacement.length > .006:
                proposed = posterior_before[vertex] + displacement.normalized()*.006
            updates[vertex] = proposed
        for vertex, proposed in updates.items():
            vertex.co = proposed
    posterior_shifts = {vertex: vertex.co-posterior_before[vertex]
                        for vertex in selected
                        if (vertex.co-posterior_before[vertex]).length > 1e-8}
    if posterior_shifts:
        seeds = list(posterior_shifts)
        xyz = np.asarray([list(posterior_before[vertex]) for vertex in seeds])
        for vertex, level in depth.items():
            if level not in (1, 2):
                continue
            distances = np.linalg.norm(xyz-np.asarray(posterior_before[vertex]), axis=1)
            nearest = np.argsort(distances)[:3]
            inverse = 1/np.maximum(distances[nearest], .001)
            shift = sum((posterior_shifts[seeds[i]]*weight for i, weight in zip(nearest, inverse)), Vector())/inverse.sum()
            fade = (0., .45, .15)[level]*(1-s(float(distances[nearest[0]])/.018))
            vertex.co += shift*fade
    posterior_moved = [(vertex.co-posterior_before[vertex]).length for vertex in bm.verts]
    moved = [(vertex.co-before[vertex]).length for vertex in bm.verts]
    report = {
        "method": "Anterior bare-neck Laplacian smoothing on the actual boundary and two adjacent rings",
        "iterations": iterations,
        "moved_vertices": sum(distance > 1e-8 for distance in moved),
        "maximum_displacement_m": max(moved),
        "front_boundary_y_before_m": min(before[vertex].y for vertex in ring),
        "front_boundary_y_after_m": min(vertex.co.y for vertex in ring),
        "anterior_reference_surface_retraction_max_m": max(retractions.values(), default=0.),
        "boundary_vertices": len(ring),
        "topology_and_uv_unchanged": True,
        "posterior_notch_regularization": {
            "backward_edges_detected": len(bad_edges),
            "boundary_vertices_selected": len(selected),
            "moved_vertices": sum(distance > 1e-8 for distance in posterior_moved),
            "maximum_displacement_m": max(posterior_moved),
            "displacement_limit_m": .006,
            "neighbor_ring_fades": [.45, .15],
        },
    }
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return report


def cut_head_above_collar(head, body, minimum_height, neck_axis_xy=None,
                          anatomical_nape_height=None, anatomical_front_height=1.56):
    """Cut low under the chin, high behind the neck; preserve the whole jaw."""
    _load_base()
    bm = bmesh.new()
    bm.from_mesh(body.data)
    lower, _ = base.neck_ring(bm)
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
    if anatomical_nape_height is not None:
        # Independent of clothing: preserve the jaw/front neck while removing
        # the reconstructed long hair behind the ears and at the nape.
        backness = -np.cos(sample_phases*math.tau)
        progress = np.clip((backness+.25)/.50, 0, 1)
        progress = progress*progress*(3-2*progress)
        anatomical = (anatomical_front_height
                      + (anatomical_nape_height-anatomical_front_height)*progress)
        heights = np.maximum(heights, anatomical)
    bm.free()
    if neck_axis_xy is None:
        coords = base.coordinates(head)
        neck = coords[(coords[:, 2] > 1.58) & (coords[:, 2] < 1.64)]
        center = (neck[:, :2].min(axis=0) + neck[:, :2].max(axis=0)) / 2
    else:
        center = np.asarray(neck_axis_xy, dtype=np.float64)

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
            "angular_center": center.tolist(),
            "anatomical_nape_height_m": anatomical_nape_height,
            "anatomical_front_height_m": anatomical_front_height if anatomical_nape_height else None}


def bake_neck_transition(
    body, bm, faces, vertex_parameters, loft_samples, lower, lower_parameters,
    head_material_index, projection_mesh, texture_directory,
    material_name="Fixed_LiangNeck_suit", width=512, height=256, blend_distance=.020,
    extend_neck_skin=False,
):
    """Bake bridge colors only; preserve existing geometry, UVs and materials."""
    assert projection_mesh is not None
    bridge_faces = set(faces)
    original_faces = [face for face in bm.faces if face not in bridge_faces]
    uv_layer = bm.loops.layers.uv.active

    def source_signature():
        coords = np.asarray([tuple(v.co) for v in bm.verts], dtype=np.float32)
        uv = np.asarray([tuple(loop[uv_layer].uv) for face in original_faces
                         for loop in face.loops], dtype=np.float32)
        materials = np.asarray([face.material_index for face in original_faces], dtype=np.int32)
        return hashlib.sha256(coords.tobytes() + uv.tobytes() + materials.tobytes()).hexdigest()

    before = source_signature()
    cache = {}

    def image_for_material(index):
        mat = body.data.materials[index]
        return next(node.image for node in mat.node_tree.nodes
                    if node.type == "TEX_IMAGE" and node.image)

    def sample(image, coordinates):
        key = image.as_pointer()
        if key not in cache:
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            cache[key] = pixels.reshape(image.size[1], image.size[0], 4)[:, :, :3]
        pixels = cache[key]
        uv = np.asarray(coordinates, dtype=np.float64)
        # Blender byte-image pixels contain the encoded sRGB values. The
        # one-pixel calibration preserves 128/64/32 exactly through save().
        x = uv[..., 0] * pixels.shape[1] - .5
        y = uv[..., 1] * pixels.shape[0] - .5
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = (x - x0)[..., None], (y - y0)[..., None]
        x0, y0 = x0 % pixels.shape[1], y0 % pixels.shape[0]
        x1, y1 = (x0 + 1) % pixels.shape[1], (y0 + 1) % pixels.shape[0]
        return ((pixels[y0, x0] * (1 - fx) + pixels[y0, x1] * fx) * (1 - fy)
                + (pixels[y1, x0] * (1 - fx) + pixels[y1, x1] * fx) * fy)

    def is_skin(rgb):
        r, g, b = rgb
        return (r > .18 and r > 1.05*g and r > 1.10*b and g > .95*b
                and (max(rgb) - min(rgb)) / max(max(rgb), .001) > .15)

    lower_colors = np.zeros((len(lower), 3), dtype=np.float64)
    valid = np.zeros(len(lower), dtype=bool)
    for index, vertex in enumerate(lower):
        colors = []
        for face in vertex.link_faces:
            if face in bridge_faces:
                continue
            image = image_for_material(face.material_index)
            center_uv = np.mean([tuple(loop[uv_layer].uv) for loop in face.loops], axis=0)
            vertex_uv = next(loop[uv_layer].uv for loop in face.loops if loop.vert is vertex)
            center_color = sample(image, center_uv)
            color = sample(image, tuple(vertex_uv))
            # Both the face interior and edge texel must be skin. White/blue
            # collar texels never contribute to the neck transition color.
            if is_skin(center_color) and is_skin(color):
                colors.append(color)
        if colors:
            lower_colors[index] = np.median(colors, axis=0)
            valid[index] = True
    assert valid.any(), "No body skin samples at the lower neck boundary"
    padding = 8
    horizontal = np.clip((np.arange(width) + .5 - padding) / (width - 2*padding), 0, 1)
    vertical = np.clip((np.arange(height) + .5 - padding) / (height - 2*padding), 0, 1)
    lower_angles = np.asarray(lower_parameters[:-1])
    valid_angles = lower_angles[valid]
    valid_colors = lower_colors[valid]
    expanded_angles = np.r_[valid_angles[-1]-1, valid_angles, valid_angles[0]+1]
    expanded_colors = np.vstack([valid_colors[-1], valid_colors, valid_colors[0]])
    body_rgb = np.column_stack([np.interp(horizontal, expanded_angles, expanded_colors[:, c])
                                for c in range(3)])
    skin_mask = np.interp(horizontal, lower_parameters, np.r_[valid.astype(float), float(valid[0])])
    grid_phases = np.linspace(0, 1, len(loft_samples[0]) + 1)
    sampled_rings = []
    for ring in loft_samples:
        periodic = np.vstack([ring, ring[0]])
        sampled_rings.append(np.column_stack([
            np.interp(horizontal, grid_phases, periodic[:, axis]) for axis in range(3)
        ]))
    sampled_rings = np.asarray(sampled_rings)
    phase_levels = np.linspace(0, 1, len(sampled_rings))
    positions = np.empty((height, width, 3), dtype=np.float32)
    for row, value in enumerate(vertical):
        interval = min(int(value * (len(phase_levels) - 1)), len(phase_levels) - 2)
        blend = (value - phase_levels[interval]) / (phase_levels[interval+1] - phase_levels[interval])
        positions[row] = sampled_rings[interval] * (1-blend) + sampled_rings[interval+1] * blend
    project = source_uv_projector(projection_mesh)
    projected_uv = np.asarray([tuple(project(Vector(point)))
                               for point in positions.reshape(-1, 3)]).reshape(height, width, 2)
    head_rgb = sample(image_for_material(head_material_index), projected_uv)
    removed_hair_pixels = 0
    if extend_neck_skin:
        # The source projection mesh still contains the removed long hair.
        # Fill only the new posterior bridge from valid skin samples; retain
        # the original head color over the last 4 mm at the hairline.
        backness = -np.cos(horizontal*math.tau)
        posterior = np.clip((backness+.25)/.50, 0, 1)
        posterior = posterior*posterior*(3-2*posterior)
        upper_distance = np.linalg.norm(positions-sampled_rings[-1][None, :, :], axis=2)
        beyond_hairline = np.clip(upper_distance/.004, 0, 1)
        beyond_hairline = beyond_hairline*beyond_hairline*(3-2*beyond_hairline)
        replacement = posterior[None, :]*beyond_hairline
        removed_hair_pixels = int(np.count_nonzero(replacement > .5))
        head_rgb = (head_rgb*(1-replacement[:, :, None])
                    + body_rgb[None, :, :]*replacement[:, :, None])
    distance = np.linalg.norm(positions - sampled_rings[0][None, :, :], axis=2)
    progress = np.clip(distance / blend_distance, 0, 1)
    body_weight = (1 - progress*progress*(3 - 2*progress)) * skin_mask[None, :]
    # A very short rear bridge must still meet the unchanged upper head color.
    body_weight *= (1 - vertical*vertical*(3-2*vertical))[:, None]

    def to_linear(rgb):
        return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)

    def to_srgb(rgb):
        return np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)

    linear = (to_linear(head_rgb) * (1-body_weight[:, :, None])
              + to_linear(body_rgb)[None, :, :] * body_weight[:, :, None])
    # Only soften azimuthal stripes inside the new bridge. Both attachment
    # edges retain their exact samples, and every original mesh UV is untouched.
    sigma = 6.0
    offsets = np.arange(-18, 19)
    weights = np.exp(-.5*(offsets/sigma)**2)
    weights /= weights.sum()
    core = linear[:, padding:-padding, :]
    blurred_core = np.zeros_like(core)
    for offset, weight in zip(offsets, weights):
        blurred_core += np.roll(core, int(offset), axis=1) * weight
    blurred = np.concatenate([
        np.repeat(blurred_core[:, :1, :], padding, axis=1),
        blurred_core,
        np.repeat(blurred_core[:, -1:, :], padding, axis=1),
    ], axis=1)
    smoothing = (.85*np.sin(math.pi*vertical)**2)[:, None, None]
    linear = linear*(1-smoothing) + blurred*smoothing
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(to_srgb(linear), 0, 1)
    image = bpy.data.images.new(material_name + "_Albedo", width, height,
                                alpha=False, float_buffer=False)
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(rgba.ravel())
    texture_directory = Path(texture_directory)
    texture_directory.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str((texture_directory / (image.name + ".png")).resolve())
    image.file_format = "PNG"
    image.save()
    stored = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(stored)
    saved_image = bpy.data.images.load(image.filepath_raw, check_existing=False)
    saved = np.empty(len(saved_image.pixels), dtype=np.float32)
    saved_image.pixels.foreach_get(saved)
    roundtrip_error = float(np.max(np.abs(saved-stored))*255)
    quantization_error = float(np.max(np.abs(saved.reshape(height, width, 4)[:, :, :3]
                                             - rgba[:, :, :3]))*255)
    assert roundtrip_error < .001, "PNG saving changed encoded byte-image RGB"
    assert quantization_error <= .501, "Atlas PNG has an unexpected color transform"
    bpy.data.images.remove(saved_image)
    mat = body.data.materials[head_material_index].copy()
    mat.name = material_name
    texture = next(node for node in mat.node_tree.nodes if node.type == "TEX_IMAGE")
    texture.image = image
    texture.extension = "EXTEND"
    body.data.materials.append(mat)
    material_index = len(body.data.materials) - 1
    for face in faces:
        parameters = [list(vertex_parameters[loop.vert]) for loop in face.loops]
        if max(p[0] for p in parameters) - min(p[0] for p in parameters) > .5:
            for p in parameters:
                if p[0] < .5:
                    p[0] += 1
        face.material_index = material_index
        for loop, (angle, blend) in zip(face.loops, parameters):
            loop[uv_layer].uv = (
                (padding + angle*(width-2*padding))/width,
                (padding + blend*(height-2*padding))/height,
            )
    after = source_signature()
    assert before == after, "Atlas bake changed original geometry/UVs/material assignments"
    texture_path = Path(image.filepath_raw)
    return {
        "material": mat.name, "texture": str(texture_path.relative_to(ROOT)),
        "texture_size": [width, height], "texture_sha256": hashlib.sha256(texture_path.read_bytes()).hexdigest(),
        "blend_distance_m": blend_distance, "valid_skin_boundary_vertices": int(valid.sum()),
        "posterior_skin_extension": bool(extend_neck_skin),
        "posterior_pixels_extended_from_body_skin": removed_hair_pixels,
        "upper_hairline_blend_distance_m": .004 if extend_neck_skin else None,
        "angular_smoothing_sigma_texels": sigma,
        "smoothing_strength_at_attachment_edges": 0,
        "png_roundtrip_max_error_8bit": roundtrip_error,
        "png_quantization_max_error_8bit": quantization_error,
        "total_boundary_vertices": len(lower), "excluded_non_skin_vertices": int((~valid).sum()),
        "sampled_skin_rgb_min": valid_colors.min(axis=0).tolist(),
        "sampled_skin_rgb_max": valid_colors.max(axis=0).tolist(),
        "original_geometry_uv_materials_sha256": before, "original_data_preserved": True,
    }


def connect_neck(body, source_head, intermediate_rings=7, projection_mesh=None,
                 transition_texture_dir=None, neck_material_name="Fixed_LiangNeck_suit",
                 extend_neck_skin=False, match_upper_tangent=False,
                 neck_reference_mesh=None, neck_axis_xy=None):
    _load_base()
    bm_body = bmesh.new()
    bm_body.from_mesh(body.data)
    boundary, _ = base.neck_ring(bm_body)
    boundary_coords = [tuple(v.co) for v in boundary]
    bm_body.free()
    bm_head = bmesh.new()
    bm_head.from_mesh(source_head.data)
    head_boundary, _ = base.neck_ring(bm_head)
    upper_coords = [tuple(v.co) for v in head_boundary]
    boundary_set = set(head_boundary)
    tangent_lookup = {}
    for index, vertex in enumerate(head_boundary):
        neighbors = [edge.other_vert(vertex).co for edge in vertex.link_edges
                     if edge.other_vert(vertex) not in boundary_set]
        direction = (sum(neighbors, Vector())/len(neighbors)-vertex.co
                     if neighbors else Vector((0, 0, 1)))
        around = (head_boundary[(index+1) % len(head_boundary)].co
                  - head_boundary[index-1].co).normalized()
        direction -= direction.dot(around)*around
        if direction.length < 1e-7 or direction.z <= 0:
            direction = Vector((0, 0, 1))
        tangent_lookup[tuple(vertex.co)] = tuple(direction.normalized())
    bm_head.free()
    copy = source_head.copy()
    copy.data = source_head.data.copy()
    bpy.context.collection.objects.link(copy)
    base.join_objects([body, copy], body)
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
    samples = 128
    phases = np.arange(samples) / samples
    vertex_parameters = {vertex: (phase, 0.0) for vertex, phase in zip(lower, a)}
    vertex_parameters.update({vertex: (phase, 1.0) for vertex, phase in zip(upper, b)})

    def interpolate(ring, parameters):
        xyz = np.array([list(v.co) for v in [*ring, ring[0]]])
        return np.column_stack([np.interp(phases, parameters, xyz[:, axis])
                                for axis in range(3)])

    lower_samples = interpolate(lower, a)
    upper_samples = interpolate(upper, b)
    tangent_values = np.asarray([tangent_lookup[tuple(vertex.co)] for vertex in upper])
    tangent_values = np.vstack([tangent_values, tangent_values[0]])
    upper_tangents = np.column_stack([
        np.interp(phases, b, tangent_values[:, axis]) for axis in range(3)
    ])
    for _ in range(2):
        upper_tangents = (.5*upper_tangents + .25*np.roll(upper_tangents, 1, axis=0)
                          + .25*np.roll(upper_tangents, -1, axis=0))
    upper_tangents /= np.maximum(np.linalg.norm(upper_tangents, axis=1)[:, None], 1e-8)
    chords = upper_samples-lower_samples
    upper_derivatives = upper_tangents*np.linalg.norm(chords, axis=1)[:, None]
    backness = -np.cos(phases*math.tau)
    posterior = np.clip((backness+.25)/.5, 0, 1)
    front_weight = (1-posterior*posterior*(3-2*posterior))[:, None]
    reference_tree = None
    inset_report = {"enabled": neck_reference_mesh is not None,
                    "reference_hits": 0, "retracted_vertices": 0,
                    "maximum_displacement_m": 0.}
    if neck_reference_mesh is not None:
        assert neck_axis_xy is not None
        neck_axis = np.asarray(neck_axis_xy, dtype=np.float64)
        reference_tree = BVHTree.FromPolygons(
            [vertex.co.copy() for vertex in neck_reference_mesh.vertices],
            [list(polygon.vertices) for polygon in neck_reference_mesh.polygons],
            all_triangles=True,
        )
        # The clothed paths retain their existing front-only tangent match.
        # The bare nape must initially descend along the head surface instead
        # of continuing the wide collar chord down toward the shoulders.
        tangent_weight = np.ones_like(front_weight)
    else:
        tangent_weight = front_weight
    loft_samples = [lower_samples]
    if intermediate_rings:
        for level in range(1, intermediate_rings + 1):
            blend = level / (intermediate_rings + 1)
            xyz = lower_samples * (1 - blend) + upper_samples * blend
            if match_upper_tangent:
                t = blend
                hermite = ((2*t**3-3*t**2+1)*lower_samples
                           + (t**3-2*t**2+t)*chords
                           + (-2*t**3+3*t**2)*upper_samples
                           + (t**3-t**2)*upper_derivatives)
                xyz = xyz*(1-tangent_weight)+hermite*tangent_weight
            # Smooth collar sampling noise in free interior vertices only.
            # Every original collar/head boundary edge remains exactly fixed.
            amount = .45 * math.sin(math.pi * blend)
            for _ in range(6):
                neighbors = (np.roll(xyz, 1, axis=0) + np.roll(xyz, -1, axis=0)) * .5
                xyz += amount * (neighbors - xyz)
            if reference_tree is not None:
                side_back = np.clip((backness+.60)/.35, 0, 1)
                side_back = side_back*side_back*(3-2*side_back)
                profile = math.sin(math.pi*blend)**2
                for index, point in enumerate(xyz):
                    radial = point[:2]-neck_axis
                    radius = float(np.linalg.norm(radial))
                    if radius < .001 or side_back[index] <= 0:
                        continue
                    direction = radial/radius
                    location, _, _, distance = reference_tree.ray_cast(
                        Vector((neck_axis[0], neck_axis[1], point[2])),
                        Vector((direction[0], direction[1], 0.)), .4,
                    )
                    if location is None or not (.01 < distance < .4):
                        continue
                    inset_report["reference_hits"] += 1
                    displacement = (min(max(radius-distance-.002, 0.), .05)
                                    * profile * side_back[index])
                    xyz[index, :2] -= direction*displacement
                    inset_report["retracted_vertices"] += int(displacement > 1e-7)
                    inset_report["maximum_displacement_m"] = max(
                        inset_report["maximum_displacement_m"], float(displacement))
            current = [bm.verts.new(co) for co in xyz]
            vertex_parameters.update({vertex: (phase, blend) for vertex, phase in zip(current, phases)})
            loft_samples.append(xyz)
            parameters = [*phases.tolist(), 1.0]
            stitch(previous, previous_parameters, current, parameters)
            previous, previous_parameters = current, parameters
    stitch(previous, previous_parameters, upper, b)
    loft_samples.append(upper_samples)
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
    atlas_report = None
    if transition_texture_dir:
        atlas_report = bake_neck_transition(
            body, bm, new_faces, vertex_parameters, loft_samples, lower, a,
            material_index, projection_mesh, transition_texture_dir, neck_material_name,
            extend_neck_skin=extend_neck_skin,
        )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    front_angles = []
    added_faces = set(new_faces)
    for vertex in upper:
        for edge in vertex.link_edges:
            if (edge.verts[0] not in upper or edge.verts[1] not in upper
                    or len(edge.link_faces) != 2):
                continue
            if not any(face in added_faces for face in edge.link_faces):
                continue
            midpoint = (edge.verts[0].co+edge.verts[1].co)/2
            if midpoint.y < -.005 and abs(midpoint.x) < .045:
                front_angles.append(math.degrees(edge.link_faces[0].normal.angle(edge.link_faces[1].normal)))
    report = {
        "lower": lo_report, "upper": hi_report,
        "bridge_faces": len(new_faces),
        "bridge_boundary_edges": sum(edge.is_boundary for face in new_faces
                                     for edge in face.edges),
        "bridge_zero_area_faces": sum(face.calc_area() < 1e-12 for face in new_faces),
        "lower_z_bounds": [min(v.co.z for v in lower), max(v.co.z for v in lower)],
        "upper_z_bounds": [min(v.co.z for v in upper), max(v.co.z for v in upper)],
        "intermediate_rings": intermediate_rings,
        "upper_front_tangent_matched": bool(match_upper_tangent),
        "bare_neck_reference_inset": inset_report,
        "front_upper_join_normal_angles_degrees": {
            "median": float(np.median(front_angles)) if front_angles else None,
            "p95": float(np.percentile(front_angles, 95)) if front_angles else None,
            "maximum": max(front_angles) if front_angles else None,
        },
        "projected_uv": projection_mesh is not None,
        "uv_seam_face_fallbacks": uv_seams,
        "transition_atlas": atlas_report,
    }
    assert report["bridge_boundary_edges"] == 0, "Neck bridge has an open edge"
    assert report["bridge_zero_area_faces"] == 0, "Neck bridge has a degenerate face"
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return report


def render_review(out):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1024, 1280
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("Candidate world")
    scene.world.use_nodes = True
    scene.world.color = (.24, .24, .24)
    scene.render.image_settings.file_format = "PNG"
    h = 1.85

    def aim(obj, point):
        obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

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
    floor.name = "Candidate floor"
    mat = bpy.data.materials.new("Candidate floor")
    mat.diffuse_color = (.52, .55, .58, 1)
    floor.data.materials.append(mat)
    data = bpy.data.cameras.new("Candidate camera")
    camera = bpy.data.objects.new("Candidate camera", data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    data.type = "ORTHO"
    for name, location, target, scale in [
        ("face", (0, -3*h, .9*h), (0, 0, .9*h), .30*h),
        ("front", (0, -3*h, .55*h), (0, 0, .5*h), 1.17*h),
        ("side", (3*h, 0, .55*h), (0, 0, .5*h), 1.17*h),
    ]:
        camera.location, data.ortho_scale = location, scale
        aim(camera, target)
        scene.render.filepath = str((out / (name + ".png")).resolve())
        bpy.ops.render.render(write_still=True)


def main():
    _load_base()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "StudyData/avatar-v3/neck-candidate/angular")
    parser.add_argument("--cut-height", type=float, default=1.60)
    parser.add_argument("--rings", type=int, default=0)
    parser.add_argument("--project-uv", action="store_true")
    parser.add_argument("--collar-following-cut", action="store_true")
    parser.add_argument("--bake-transition", action="store_true")
    parser.add_argument("--outfit", choices=("suit", "sport", "none"), default="suit")
    args = parser.parse_args()
    out = args.out.resolve()
    assert out != (ROOT / "StudyData/avatar-v3/unity-staging/AvatarDemo").resolve()
    assert "neck-candidate" in out.parts, "Use a separate neck-candidate subdirectory"
    out.mkdir(parents=True, exist_ok=True)
    textures = out / "Textures"
    textures.mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    generated = ROOT / "StudyData/avatar-v3/generated"
    head = base.load_mesh(generated / "liang-head/textured.glb", "Candidate head source", .335)
    points = base.coordinates(head)
    neck_blend = np.clip((.06 - points[:, 2]) / .06, 0, 1)
    points[:, 0] *= .92 * (1 + .25 * neck_blend)
    points[:, 1] = points[:, 1] * 1.05 - .025 + .06 * neck_blend
    points[:, 2] = np.interp(points[:, 2], [0, .025, .06, .12, .15, .335],
                            [1.525, 1.56, 1.65, 1.72, 1.745, 1.85])
    base.put_coordinates(head, points)
    projection_mesh = head.data.copy() if args.project_uv else None
    source, body_material = {
        "suit": ("liang", "Tint_LiangSuit_Reference"),
        "sport": ("liang-sport", "Tint_LiangSport_Reference"),
        "none": ("liang-bare", "Tint_LiangBare_Reference"),
    }[args.outfit]
    body = base.load_mesh(generated / source / "textured.glb", "Candidate " + args.outfit, 1.85)
    base.bind_texture(body, body_material, textures, False, "blue-cloth")
    base.remove_old_head(body)
    cut_report = None
    if args.collar_following_cut:
        cut_report = cut_head_above_collar(head, body, args.cut_height)
    else:
        base.cut_at(head, args.cut_height, False)
    base.bind_texture(head, "Fixed_Liang_DetailedHead", textures, False)
    report = connect_neck(body, head, args.rings, projection_mesh,
                          textures if args.bake_transition else None,
                          "Fixed_LiangNeck_" + args.outfit)
    report["collar_following_cut"] = cut_report
    report["outfit"] = args.outfit
    points = base.coordinates(head)
    eye_z = 1.739
    cheek = points[(np.abs(points[:, 2] - eye_z) < .012) &
                   (np.abs(points[:, 0]) > .025) & (np.abs(points[:, 0]) < .07)]
    eye_y = float(np.quantile(cheek[:, 1], .04)) - .029
    root = base.empty("LiangNeckCandidate")
    base.keep_world_parent(body, root)
    base.glasses(base.empty("Candidate glasses", root), (0, eye_y, eye_z),
                 width=.145, temple_spread=.015)
    bpy.data.objects.remove(head, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (root, *root.children_recursive):
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "Liang-neck-candidate.glb"),
                              export_format="GLB", use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(
        filepath=str(out / "Liang-neck-candidate.fbx"), use_selection=True,
        object_types={"EMPTY", "MESH"}, axis_forward="-Z", axis_up="Y",
        add_leaf_bones=False, bake_anim=False, apply_unit_scale=True,
        mesh_smooth_type="FACE", path_mode="RELATIVE",
    )
    report.update({"base_script_sha256": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest(),
                   "method": "anatomical angular correspondence", "bpy": bpy.app.version_string})
    (out / "diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    render_review(out)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "candidate.blend"))


if __name__ == "__main__":
    main()
