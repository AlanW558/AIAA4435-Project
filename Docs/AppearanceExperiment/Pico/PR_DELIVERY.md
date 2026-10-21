# Appearance Room development delivery

Updated 2026-10-21. This change adds the appearance experiment and its PICO
interaction flow to the existing cloud conversation room project. The standalone
demo additionally supports two reconstructed avatars, three human outfits,
masked recolouring, accessories, scale, clarification and atomic replacement undo.

## Entry points

- PICO scene: `Assets/Project/Scenes/AppearanceVR.unity`.
- Desktop capture scene: `Assets/Project/Scenes/AppearanceDesktopDemo.unity`.
- Backend and four shared policies: [Backend/README.md](../../../Backend/README.md).
- Device/controller instructions: [OPERATIONS.md](OPERATIONS.md).
- Frozen experiment: `study-v1`; additional avatar capabilities: debug-only
  `avatar-demo-v1`. The demo profile is rejected for formal and pilot collection.
- [Packed editable Blender project](../../../Art/AppearanceAvatars/README.md).
- [Actual Unity reference comparison](../Validation/avatar-v3/index.html).
- [60-second English-captioned desktop recording](../Demos/AppearanceRoom-Avatars-60s-en.mp4).
- [Questionnaire results and complete analysis](../Results/2026-10-21/问卷结果与完整分析.md).

The video shows actual live-backend state transitions, including clarification,
whole-avatar replacement and five-field undo. It is a fixed-camera Ubuntu Unity
window recording, not a headset capture or participant-study footage.

## Building from a checkout

Use Git LFS and Unity 2022.3.62f3c1 with Android Build Support. The external PICO
SDK and fixed Unity MCP dependency must be installed as described in the root
[README](../../../README.md); their existing package paths are preserved.

```bash
git lfs pull
python3 -m unittest discover -s Backend/tests -v
python3 -m unittest discover -s Tools/AppearanceExperiment/tests -v
python3 -m unittest discover -s Docs/AppearanceExperiment/Study/tests -v
python3 Tools/AppearanceExperiment/verify_source.py --out StudyData/source-checks.json
bash Tools/AppearanceExperiment/build_pico.sh
```

Set `APPEARANCE_UNITY` when the editor is installed elsewhere. On the development
desktop the build uses `DISPLAY=:1` and its user-session Xauthority. The build
script restores temporary project settings. API keys are server-side environment
configuration only; the primary credential is tried first, and the configured
backup is used only after HTTP 402.

For the published questionnaire snapshot, install the separate pinned
`Tools/AppearanceExperiment/requirements-survey-analysis.txt` in a virtual
environment. The report contains the exact analysis command and actual order.
Raw exports and row-level audit files are intentionally excluded from the public
repository; an authorized source workbook is required to recompute the results.

## Verified results and boundaries

- 50 backend tests, 54 device/material-tool tests and 11 study/export tests pass.
  The separate questionnaire analysis suite has 7 passing tests, with an
  independent ZIP/XML audit of the actual export and published aggregates.
  Backend HTTP tests require local loopback sockets; a socket-restricted sandbox
  cannot run those two tests. Static source/frozen-material audit: 10 checks pass.
- Avatar inspection: 7 state cases and 9 detail renders; all five observation
  fields, visible geometry bounds and legacy-study restoration verified.
- Android: build succeeded, 23 runtime logic checks pass, APK ZIP/package/v2
  signature checks pass. 0 errors and 11 existing SDK warnings; no new warnings.
- Linux: build succeeded and the actual player was recorded. Its build report
  retains one unused PICO SpatialAudio sample Wireframe shader diagnostic and
  nine warnings; the running player had no error lines. The SDK was not modified
  to hide that diagnostic.
- New APK SHA-256:
  `74305dce9b618bf9dec37f9539bc95d9fa26ccc484f0d05ee1b8649f8c553bca`.
  The APK itself stays under ignored `Builds/Pico/`; it is not a source asset.
- The researcher now confirms the 15 questionnaire respondents used PICO with
  the new blue-suit/Nailong avatars. This is reported study context, not a new
  instrumented device test by the agent. Respondent records have not been linked
  to an APK fingerprint, trial logs or frame-rate measurements. Earlier logged
  device validation used the legacy avatar; user likeness acceptance is not implied.

The [delivery receipt](../Validation/avatar-v3/delivery-verification.json),
[resource hashes](../Validation/avatar-v3/production-resource-install.json) and
[visual review](../Validation/avatar-v3/visual-review.json) preserve the measured
results. Historical `StudyData/...` and `Builds/...` paths in modelling notes refer
to local evidence; selected anonymous engineering evidence is included under
`Validation/avatar-v3/` for review from a fresh checkout.
WJX account-management screenshots remain local. Historical survey receipts
retain their original evidence paths; the public repository includes anonymous
questionnaire structure/settings audits and the published questionnaire QR code.

## Research-data scope

The 2026-10-21 workbook contains paper responses transcribed by the researcher.
The user confirmed PICO use with the new avatars, that every participant
experienced N→E→A→S, and that Q29 is a researcher summary rather than verbatim
speech. The report applies that order
and explicitly discusses its confounding with practice, fatigue and recency.
The original counterbalanced schedules remain unchanged as planned materials.
The old questionnaire's simulated answers are not included. No success-rate,
speed or causal-effect claim is inferred from subjective ratings alone.
