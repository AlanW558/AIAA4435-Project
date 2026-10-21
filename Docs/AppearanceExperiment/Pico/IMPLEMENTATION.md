# PICO 外形实验实施与验收

Goal: integrate the existing E/A/N/S appearance experiment into the cloud conversation room, operate researcher-managed studies on PICO, and record a real ~60-second debug demonstration.

Architecture: keep the shared backend, appearance state, policy and renderer observations. Add an Android launch configuration and command/status mailbox, an XR world-space Chinese interaction panel, a dedicated scene/APK, and a local researcher controller. Backend credentials remain on the Ubuntu desktop. USB ADB and an SSH tunnel connect the locally attached headset to that backend.

Tech: Unity 2022.3.62f3c1, installed PICO SDK 3.4.0, installed XR Interaction Toolkit, UGUI, Python standard library, Android ADB, ffmpeg. Reuse the current feature checkout; preserve unrelated questionnaire and midterm changes. No public push.

Constraints: participant UI has no phase, participant ID, condition, task cards or round counter. All four conditions share animation, UI, proposer, candidates, execution and repair limits. Formal tasks follow the frozen 16-row schedule and stop between blocks for the questionnaire. Debug is never participant data. New package preserves the original installed room app.

## Task 1 — Expressive shared avatar

- [x] Improve the procedural character in `Assets/Project/Scripts/AppearanceExperiment/AppearanceAvatar.cs` only, with coherent proportions, friendly stylized face, clothing detail and clearly distinguishable accessories.
- [x] Preserve `Create`, `Apply`, `Material`, `Shape`, `ObservedColor`, `ObservedAccessory`, `ObservedScale`. The avatar faces local -Z and feet remain at y=0. Default height stays approximately 2.15 m. No assets or external packages required.
- [x] Add subtle breathing, blinking, bounded gaze toward Camera.main and brief response gestures through an optional public `SetInteraction(string mode)` API (idle, thinking, ask, act, done). The same modes work for all conditions. No motion changes the experimental root scale or observed material/accessory state; state changes apply immediately.
- [x] Make Create idempotent. Avoid per-frame allocations/material creation and keep the mobile primitive count modest (<100 renderers). No policy/backend/UI changes.
- [x] Report source-level checks honestly. The controller runs Unity compilation and device visuals. No commit or git operation by the implementer; shared checkout contains unrelated edits.

## Task 2 — Portable experiment runtime and XR interface

- [x] Read Android StreamingAssets asynchronously, fail closed on missing tasks or schedule, load validated `appearance-session-v1` identity from persistent storage, compute the installed APK SHA-256.
- [x] Expose common guarded interaction methods; retain the desktop UI and smoke workflow. Handle disconnected backend and missing researcher configuration with participant-safe status.
- [x] Add mailbox commands and researcher-only status. Only debug supports scripted queries/answers/undo. Formal conditions/tasks cannot be overridden. Status carries observed render values and evidence paths.
- [x] Formal next advances only a finished trial, pauses after each block, requires explicit resume and never wraps after trial 16. Preserve the 120-second timeout, repair budget and three renderer probes.
- [x] XR panel provides free Chinese input, clarifications including cancellation/other, per-field undo, submit and completion. Use installed XR UI raycaster/input module, bundled CJK font and readable world-space layout. No study labels.
- [x] Keep the original cloud room and desktop scenes. Add an appearance room scene with the shared avatar, panel and existing seating/locomotion.

## Task 3 — Researcher tools, deployment and evidence

- [x] Local Python CLI/controller validates existing session metadata, stages a configuration via ADB, launches the dedicated app, sends commands, reads status, retrieves captures and exposes a loopback-only browser control page.
- [x] Add a repeatable Android build method and script with config restoration, explicit package, INTERNET/HTTP, arm64 IL2CPP, installed SDK configuration, build report and fingerprint.
- [x] Verify backend health through SSH forwarding, Windows ADB reverse and an actual headset HTTP request. Install the successful APK and confirm the correct package/version is running.
- [x] Test invalid identity, formal override rejection, schedule/block boundaries and duplicate command behavior. Run affected backend/study checks once plus installed-runtime smoke checks.

## Task 4 — Headset validation and demonstration

- [x] Inspect real headset screenshots, logcat, Chinese rendering and XR startup; fix concrete defects. Validate actual color/accessory/scale commits, clarification, partial undo, completion and three probes under a debug identity.
- [x] Exercise all four conditions through the same client and preserve actual backend/runtime evidence. Verify formal scheduling separately without fabricating participant results.
- [x] Record the wearer’s confirmation of pointing/text entry; document that seating comfort and sustained wearing remain pilot checks.
- [x] Recording scope updated by the user: complete the recording from the desktop. Recorded 60 seconds of actual Unity desktop-window interaction using the shared room / avatar / client / live backend, inspected and captioned the MP4, and explicitly labeled it desktop debug rather than headset footage.
- [x] Update the operator runbook, handoff and honest readiness report, including pilot requirements and any physical-test limits. A working demo is not a completed human study.

Execution: use the scoped subagent workflow for Task 1 and, sequentially, the independent researcher tooling part of Task 3; controller owns runtime/UI/build integration. Review each delegated task's scope and quality; final review covers the integrated change. No additional approval is needed for these authorized reversible implementation steps.
