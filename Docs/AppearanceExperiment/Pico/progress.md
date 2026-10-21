# Implementation evidence ledger

Updated 2026-10-20. All observed sessions below are engineering debug, not participant results.

- Dedicated PICO package installed: `com.iai.aiaa4435.appearance`, version 0.2.0. The original room app remains installed.
- Installed APK SHA-256: `2aeb202f2653f3d803c7a16ffb0e745e199bc43764015b662a218440f50fea6a`. Android build succeeded with zero build errors; 23 actual Unity class checks passed.
- User confirmed room, avatar and Chinese panel, then reported successful controller text input and an orange clothing change. That manual report is separate from the instrumented tests below.
- USB reconnection removes ADB reverse. Restored forwarding and verified an actual headset HTTP 200 response. `keep_pico_usb.py` now restores the selected device mapping; it never replays participant requests.
- Instrumented real-headset E/A/N/S runs all completed with four stored images each (first commit plus three probes). E=ACT, A=ASK, N=ACT for the explicit orange request; S=ASK for warm-color plus glasses. These are observed examples, not claims about every possible request.
- S additionally verified a rejected undo preserves ASK, option selection changes actual color/accessory, scale reaches 1.10, and color-only undo preserves glasses and scale.
- Logs, actual captures and audit are under `StudyData/pico/debug-20261020-eans`. Each condition has exactly three logged probes with positive measured duration. All six model calls used the teacher credential slot `primary`.
- Teacher credential is stored only in private backend configuration. Personal fallback is selected only on provider HTTP 402; no real fallback spend was used for these checks. Backend credential and regression tests: 30 passed.
- Researcher controller: 31 tests passed; actual configure/install/launch/command/status/collect used successfully. USB recovery tests: 3 passed. Browser page and device status endpoint returned HTTP 200 at localhost:8766.
- Error review fixes include stopping uncertain/provider failures, preserving pending questions on rejected undo, guarded completion, durable command deduplication, and publishing screenshots only after persistence. Independent source review approved those fixes.
- User changed recording workflow to the Ubuntu desktop. The recorded demonstration is a real Unity desktop window of the shared room/client/avatar, driven by the debug mailbox. It is explicitly not described as headset footage.
- Final real desktop recording: `Builds/Demos/AppearanceRoom-60s-debug.mp4`, exactly 60.000 seconds, 1920×1080, 30 fps / 1800 frames. English subtitles and top labels added at the user’s request. Inspected the key frames and corrected an internal field name in the undo message. Actual raw footage / event timestamps are under `StudyData/pico/desktop-demo/take-02`. Final SHA-256: `20ece4e2d352c659836cea7358d8177e41a92e62c583e9e48246f34d812c6f05`.
- Offline target cards: 16 self-contained Chinese HTML cards with 36 actual shared-Avatar Editor renderings, including all 20 acceptable target states; actual renderer receipt and source hashes verified locally. Python material tests: 14 passed. Initial image inspection confirms visible color/accessories/full character; physical printing still needs checking. Independent practices respect the 0.85–1.15 grid and two-repair limit. Frozen task SHA remains `37ce37e68abfb8edae4f4fb45c6cc38b03e6590aca322d7991d93d3205cc1fda`.
- Final PICO status after backend reload: initialized / READY / no fault, matching installed APK hash, new debug study session `debug_pico_ready_20261020`.
- Human pilot, long-session comfort/performance, printing checks and full live formal scheduling remain prerequisites to participant collection; no recruitment or completed study is claimed.
