"""Inspect actual upper-head sections before placing optional caps."""
import json
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
bpy.ops.wm.open_mainfile(filepath=str(
    ROOT / "StudyData/avatar-v3/unity-blender-staging/AvatarDemo/assembled.blend"))
report = {}
for name, heights in [
    ("BuiltLiang_Body_suit", [1.77, 1.78, 1.79, 1.80]),
    ("Nailong_reference_surface", [1.72, 1.74, 1.76, 1.78]),
]:
    obj = bpy.data.objects[name]
    xyz = np.array([list(v.co) for v in obj.data.vertices])
    sections = []
    for z in heights:
        band = xyz[np.abs(xyz[:, 2] - z) < .004]
        low, high = band.min(axis=0), band.max(axis=0)
        center = (low + high) / 2
        upper = xyz[xyz[:, 2] >= z] - np.array([center[0], center[1], z])
        radius = float(np.linalg.norm(upper / np.array([1, 1, .72]), axis=1).max()) + .004
        sections.append({"z": z, "center_xy": center[:2].tolist(),
                         "width_depth": (high - low)[:2].tolist(),
                         "required_radius": radius})
    report[name] = sections
print("CAP_SECTIONS " + json.dumps(report, indent=2), flush=True)
