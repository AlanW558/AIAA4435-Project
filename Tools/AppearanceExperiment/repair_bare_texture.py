"""Repair a bounded torso paint defect using the model's clean skin samples.

Runs inside Blender. The source GLB, geometry, UVs, and garment pixels remain
unchanged. The caller passes a copied image and measured world-space bounds.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import barycentric_transform


def repair_mirrored_skin(obj, image, lower, upper):
    mesh = obj.data
    vertices = np.asarray([vertex.co[:] for vertex in mesh.vertices])
    faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
    assert all(len(face) == 3 for face in faces)
    uv = mesh.uv_layers.active.data
    triangle_uvs = [[Vector((*uv[index].uv, 0.)) for index in polygon.loop_indices]
                    for polygon in mesh.polygons]
    tree = BVHTree.FromPolygons([Vector(point) for point in vertices], faces,
                               all_triangles=True)
    width, height = image.size
    original = np.asarray(image.pixels[:], dtype=np.float32).reshape(height, width, 4)
    output = original.copy()
    changed = np.zeros((height, width), dtype=bool)
    lower, upper = np.asarray(lower), np.asarray(upper)
    repaired_positions = []
    skipped = 0
    local_fallbacks = 0

    def sample(texture_uv):
        x = float(texture_uv.x) * width - .5
        y = float(texture_uv.y) * height - .5
        x = np.clip(x, 0, width - 1)
        y = np.clip(y, 0, height - 1)
        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, height - 1)
        dx, dy = x - x0, y - y0
        return ((1 - dx) * (1 - dy) * original[y0, x0]
                + dx * (1 - dy) * original[y0, x1]
                + (1 - dx) * dy * original[y1, x0]
                + dx * dy * original[y1, x1])

    def is_skin(color):
        return color[0] > color[2] * 1.12 and color[0] > color[1] * 1.03

    # Mirroring can land on another poorly reconstructed texel. Keep clean
    # nearby skin samples as a bounded fallback, so such texels are repaired
    # rather than leaving the original blue border around a repaired centre.
    local_samples = []
    for index, face in enumerate(faces):
        point = vertices[list(face)].mean(axis=0)
        if np.any(point < lower - .06) or np.any(point > upper + .06):
            continue
        color = sample(sum(triangle_uvs[index], Vector()) / 3)
        if is_skin(color):
            local_samples.append((point, color))
    assert local_samples, "No clean local skin samples surround the defect"
    clean_tree = KDTree(len(local_samples))
    for index, (point, _) in enumerate(local_samples):
        clean_tree.insert(Vector(point), index)
    clean_tree.balance()

    for face_index, face in enumerate(faces):
        xyz = vertices[list(face)]
        if np.any(xyz.max(axis=0) < lower) or np.any(xyz.min(axis=0) > upper):
            continue
        coords = np.asarray([value[:2] for value in triangle_uvs[face_index]]) * (width, height)
        low = np.maximum(np.floor(coords.min(axis=0)).astype(int), 0)
        high = np.minimum(np.ceil(coords.max(axis=0)).astype(int), [width - 1, height - 1])
        if np.any(high < low):
            continue
        a, b, c = coords
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-8:
            continue
        xx, yy = np.meshgrid(np.arange(low[0], high[0] + 1),
                             np.arange(low[1], high[1] + 1))
        u = ((b[1] - c[1]) * (xx + .5 - c[0])
             + (c[0] - b[0]) * (yy + .5 - c[1])) / denominator
        v = ((c[1] - a[1]) * (xx + .5 - c[0])
             + (a[0] - c[0]) * (yy + .5 - c[1])) / denominator
        w = 1 - u - v
        positions = u[..., None] * xyz[0] + v[..., None] * xyz[1] + w[..., None] * xyz[2]
        colors = original[yy, xx, :3]
        r, g, blue = colors[..., 0], colors[..., 1], colors[..., 2]
        selected = ((u >= 0) & (v >= 0) & (w >= 0)
                    & np.all(positions >= lower, axis=-1)
                    & np.all(positions <= upper, axis=-1)
                    & (blue > r * .95) & (blue > g * 1.02)
                    & ~changed[yy, xx])
        for row, column in np.argwhere(selected):
            point = positions[row, column]
            mirrored = Vector((-point[0], point[1], point[2]))
            hit, _, index, distance = tree.find_nearest(mirrored)
            color = None
            if hit is not None and distance <= .06:
                tri = [Vector(vertices[vertex]) for vertex in faces[index]]
                projected = barycentric_transform(hit, *tri, *triangle_uvs[index])
                proposed = sample(projected)
                if is_skin(proposed):
                    color = proposed
            # Do not copy clothing or another contaminated texel onto skin.
            if color is None:
                neighbours = [item for item in clean_tree.find_n(Vector(point), 12)
                              if item[2] < .10]
                if not neighbours:
                    skipped += 1
                    continue
                weights = np.asarray([1 / (distance + .004)**2
                                      for _, _, distance in neighbours])
                colors = np.asarray([local_samples[index][1] for _, index, _ in neighbours])
                color = np.average(colors, weights=weights, axis=0)
                local_fallbacks += 1
            x, y = int(xx[row, column]), int(yy[row, column])
            output[y, x, :3] = color[:3]
            changed[y, x] = True
            repaired_positions.append(point.tolist())
    if not repaired_positions:
        raise ValueError("The measured skin repair region contains no repairable blue texels")
    assert np.array_equal(original[~changed], output[~changed])
    assert np.array_equal(original[..., 3], output[..., 3])
    image.pixels.foreach_set(output.ravel())
    image.update()
    return {
        "method": "Bounded blue-paint cleanup using mirrored skin and clean local surface samples in Blender",
        "region_min_xyz_m": lower.tolist(), "region_max_xyz_m": upper.tolist(),
        "repaired_texels": int(changed.sum()), "skipped_samples": skipped,
        "local_skin_fallbacks": local_fallbacks,
        "actual_min_xyz_m": np.min(repaired_positions, axis=0).tolist(),
        "actual_max_xyz_m": np.max(repaired_positions, axis=0).tolist(),
        "outside_region_pixels_unchanged": True, "geometry_and_uv_unchanged": True,
    }
