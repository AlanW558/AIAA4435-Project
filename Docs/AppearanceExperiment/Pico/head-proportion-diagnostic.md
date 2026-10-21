# Independent head-proportion check

These are diagnostic candidates, not accepted assets. The main assembler,
`Assets`, and main Unity staging were not modified by this experiment.

The existing three full-body references remain the target:
`liang-reference-v1.png`, `liang-sport-reference-v1.png`, and
`liang-bare-reference-v1.png`. No new reference or generated model was used.

## Measured causes

- The previous piecewise Z mapping has segment scales
  `1.4, 2.5714, 1.1667, 0.8333, 0.5676`. It lengthens the lower neck while
  compressing the upper head. Its X/Y scales also differ.
- At a native head-plus-neck height of 0.315 m, the real connected head width
  is 0.21169 m. The full bounding-box width is 0.25056 m because of floating
  fragments. Using the full bounding box displaces the visible head center.
- Welding coincident geometry at 1e-6 m, while preserving per-loop UVs, gives
  66 connected components. Retaining the main component keeps 48,995 vertices
  and removes 934 floating vertices.
- The low-neck band Z=0.025–0.045 m has XY center
  `(-0.01675943, 0.01116942)`. The suit collar boundary center is
  `(-0.00319180, 0.01932954)`.
- The native front cheek surface has mean normal
  `(-0.000904, -0.978838, -0.204636)`, corresponding to approximately 11.8°
  downward pitch. An X rotation of -15° makes this
  `(-0.000904, -0.998448, 0.055678)`, approximately 3.2° upward.

All measurements are saved in
`StudyData/avatar-v3/neck-candidate/head-proportion-diagnostic.json`.
The neck/face landmarks are approximate geometric bands, not semantic
landmarks from a face detector.

## Reproduced comparison

`Tools/AppearanceExperiment/inspect_uniform_head_candidate.py` produces:

- `neck-candidate/uniform-head-suit/{face,front,side}.png`
- `neck-candidate/uniform-pitch15-suit/{face,front,side}.png`

Each directory also contains the actual GLB, Blender scene and diagnostics on
the desktop host. PNGs and diagnostics are synchronized to the local project.
Both runs use the same 1.85 m suit body, native 0.315 m head proportions,
camera and lighting. Both bridge diagnostics have zero open edges and zero
degenerate faces. The original head/body source GLBs are unchanged.

The pure uniform transform after `load_mesh(..., height=.315)` is:

```python
points += (0.0135676265, 0.0081601236, 1.535)
```

For the tested -15° variant, with R being the X-axis rotation matrix:

```python
pivot = (-0.0167594254, 0.0111694168, 0.035)
scale = 1.0107166984  # One scalar after rotation; all axes remain equal.
translation = (-0.0031917989, 0.0193295404, 1.5615771466)
points = ((points - pivot) @ R.T) * scale + translation
```

The reported lens-center heights are 1.67250 m and 1.68448 m. Fixing the crown
at 1.85 m offsets part of the elevation from the rigid rotation; the eye
height does not rise to 1.72 m.

The collar cut uses minimum 1.55 m and an explicit low-neck XY axis. Its actual
suit range is 1.57206–1.65336 m. It does not reuse the old hardcoded
1.58–1.64 m neck sampling band, which overlaps the jaw after uniform placement.

```bash
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/inspect_uniform_head_candidate.py --out StudyData/avatar-v3/neck-candidate/uniform-head-suit --pitch-degrees 0
Builds/AvatarTools/venv/bin/python Tools/AppearanceExperiment/inspect_uniform_head_candidate.py --out StudyData/avatar-v3/neck-candidate/uniform-pitch15-suit --pitch-degrees -15
```

## Visual outcome and limits

The -15° result has a more natural neck and an intact jaw. The long, stretched
neck from the previous mapping is gone. However, both native-proportion
candidates still have an oversized crown and a face concentrated in the lower
half of the head. This is visible in the original reconstructed head geometry;
uniform scale and rigid rotation alone cannot remove it. Neither candidate
is claimed to match the approved reference closely enough for final delivery.

The texture-atlas experiment was paused. Completed outputs remain under
`neck-candidate/baked-smooth-{suit,none,sport}`. Their PNG roundtrip RGB error
was zero, quantization error was at most 0.501/255, and the atlas bake
preserved existing geometry and original UV/material assignments. They were
not imported into Unity or accepted as final assets.
