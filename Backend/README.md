# Appearance experiment backend

Python 3.10+ standard library only. This backend connects the Unity appearance client to DeepSeek, keeps experiment conditions separate from shared interpretation, and writes local JSONL audit logs. It does not generate executable code or arbitrary assets.

The new tutor implementation is tracked in [Stage 1 implementation plan](../Docs/TutorPersonalization/STAGE_1_IMPLEMENTATION_PLAN.md). `tutor_state.py` provides settings and histories; `tutor_interpretation.py` interprets chat/tailoring/mixed/clarification requests. `tutor_session.py` exposes debug-only `/tutor/sessions` with E/A/N/S decisions, confirmation/cancel, Reply length controls/undo, idempotency and JSONL logs. `tutor_generation.py` now generates real English answers via `/tutor/sessions/{id}/generate`, using each queued question's settings and completed conversation. Failed generation preserves the job for explicit retry; completed jobs reuse their answer without duplicate model calls/history. See [Tutor HTTP contract](../Docs/TutorPersonalization/TUTOR_BACKEND_API.md). Single-session Unity integration and desktop acceptance are complete; audio remains unconnected and headset acceptance is deferred. The appearance API below remains unchanged.

Stage 2 steps 1–6 are implemented and locally checked: `tutor_comparison.py` owns isolated branch state and the first-results barrier; `tutor_shared_request.py` and `tutor_policy.py` share one initial interpretation; `tutor_comparison_service.py` executes branches asynchronously via debug-only `/tutor/comparisons`. Clarifications route to their own branch, generation completes before automatic reveal, and equivalent generation contexts reuse one result within the task. Private branch sessions cannot be read through the old session API. Explicit retries, request deduplication, stale-work rejection and JSONL audit checkpoints are covered by 27 new tests (205 backend tests total). Unity comparison is connected in dedicated Desktop/VR scenes; 93 local comparison checks pass; 26 original single-session checks passed in step 4. See [Unity comparison setup](../Docs/TutorPersonalization/UNITY_COMPARISON.md). Debug lifecycle APIs now support pause/resume, version-bound Q1–Q7 drafts, frozen submission, and isolated linked next tasks (25 additional backend tests, 230 total). See [lifecycle contract](../Docs/TutorPersonalization/TASK_LIFECYCLE_API.md). Step 6 found and fixed partial initial settings in comparison creation; 233 backend tests and 93 Unity fixture checks now pass. Additional fault checks and two real-model comparisons (10 provider attempts) are documented with the initial interruption and continuation in [Stage 2 acceptance](../Docs/TutorPersonalization/STAGE_2_ACCEPTANCE.md). Full questionnaire UI/task scheduling, other attributes, speech and headset testing remain pending. See [comparison HTTP contract](../Docs/TutorPersonalization/COMPARISON_BACKEND_API.md) and [Stage 2 plan](../Docs/TutorPersonalization/STAGE_2_IMPLEMENTATION_PLAN.md).

Stage 4 step 1 (2026-11-10): candidate voice/rate/tone mapping and 15 real TTS samples are ready for human listening. 30 TTS requests were used including 15 initial download failures; evidence is retained. WAV/manifest checks pass; perceptual quality and runtime audio integration remain pending. See [speech capability contract](../Docs/TutorPersonalization/STAGE_4_SPEECH_CAPABILITY_CONTRACT.md).

Stage 4 step 2 (2026-11-10): five selected voices are now **A/B/C/D/E**, mapped from the previous B/C/D/G/H; default **Voice D** is Adrian Gao (previous G). Internal STT/TTS service adapters, cancellation, validation and bounded memory caching are implemented. **352 backend tests and 101 Unity controls checks pass**. No new paid calls; Unity microphone/playback and visibility-bound speech routes remain disconnected. See [backend speech contract](../Docs/TutorPersonalization/STAGE_4_BACKEND_SPEECH.md).

Stage 4 step 3 (2026-11-10): Unity microphone capture, read-only transcript review and explicit Send now connect to session-bound STT routes. One initial transcription feeds the four strategies; clarification input remains bound to its captured context. **363 backend tests and 26 Unity synthetic speech checks pass**. Speech defaults to disabled; enable with `--speech-mode qwen` after configuring standard workspace credentials. Real microphone/cloud/headset validation and TTS playback remain pending. No new paid calls. See [Unity STT implementation](../Docs/TutorPersonalization/STAGE_4_UNITY_STT.md).

Stage 4 step 4 (2026-11-10): **Play sample and Play reply are connected** through authoritative, visibility-gated TTS routes. Samples use current settings; replies use their recorded generation snapshots. Playback cancels on context changes and never starts automatically. **375 backend tests and 43 Unity silent-audio checks pass**. Real cloud/headset listening remains pending; no new paid calls. See [Unity TTS implementation](../Docs/TutorPersonalization/STAGE_4_UNITY_TTS.md). Client playback-event logging is the next step.

Stage 4 step 5 (2026-11-10): client playback start/stop/completion/failure reports now use a persistent text-only outbox and idempotent server audit, bound to the original audio/task/branch even after task changes or server restart. Unified dialogue export links audio, playback and feedback evidence. **386 backend tests and 51 end-to-end Unity checks pass**, including a lost acknowledgement and outbox reload. These are client-reported playback events, not proof of hearing. No paid calls or headset testing. See [playback audit implementation](../Docs/TutorPersonalization/STAGE_4_PLAYBACK_AUDIT.md).

## Run

Current (2026-11-08, Stage 3 step 7): **331 backend tests, 69 combined fixture checks and 93 Unity regression checks pass**. The live sequence exposed a task-start/default-rate confusion; immutable public `task_start_settings` and interpreter guidance were added, with targeted live verification. Original failed evidence is retained. Initial + follow-up used **16 provider attempts (18 maximum)**; 27 evidence audits pass. This is not a clean full live rerun. Versions: state v2, interpretation v4, comparison execution v6. Audio/STT/TTS and revised study questionnaires remain pending. See [Stage 3 acceptance and limitations](../Docs/TutorPersonalization/STAGE_3_ACCEPTANCE.md).

Dialogue logging supplement (2026-11-08): submitted participant text and tutor outputs are recorded by default in the existing audit JSONL, with `tutor-dialogue-v1` entries, request/job/version links, and separate clarification/feedback/presentation evidence. No audio or VR notice/toggle is added. STT remains pending. All 322 backend tests pass (13 new). Export one task/session with `Backend/export_tutor_dialogue.py`; see [dialogue evidence](../Docs/TutorPersonalization/DIALOGUE_LOGGING.md).

Stage 3 step 6 snapshot (2026-11-08): Unity now exposes all four dialogue controls and a field-scoped History undo selector, with shared editing gates, drag cancellation across state/page changes, and per-answer settings captions. Voice/rate settings remain parameters; audio and Play sample are not connected. **309 backend tests, 83 controls checks and the original 93 Unity comparison checks pass**, with explicit fixtures and no paid calls. See [controls implementation and acceptance](../Docs/TutorPersonalization/STAGE_3_CONTROLS.md).

Stage 3 step 5 (2026-11-08): appearance requests and scoped undo now execute alongside all four dialogue properties (`tutor-comparison-execution-v5`). `CONTROL_FIELDS` still limits direct settings to the four dialogue controls; no appearance editor/tab was added. The existing Unity renderer consumes only the baseline/visible-result projection. Shared History now shows actual changed fields and opens at the newest record. **309 backend tests and 70 final Unity appearance checks pass**, without paid calls; a 93-check original Unity regression also passed before the final history-scroll adjustment. See [appearance implementation and acceptance](../Docs/TutorPersonalization/STAGE_3_APPEARANCE.md). The following paragraphs retain earlier stage snapshots.

Stage 3 step 4 snapshot: **all four dialogue settings** support persistent/one-answer requests, backend controls, history and scoped undo. Speech-rate expressions use captured public settings; unsupported precision/range returns explained unresolved outcomes without partial edits. Rate/voice remain parameters with `audio_available:false`; no audio is generated. Text uses Tone + Reply length and retains independent speech snapshots when shared. That step used `tutor-interpretation-v3`, `tutor-answer-v4`, `tutor-comparison-execution-v4`; **299** backend tests passed (16 new), with no paid calls. See [speech settings](../Docs/TutorPersonalization/STAGE_3_SPEECH_SETTINGS.md) and [Tone generation](../Docs/TutorPersonalization/STAGE_3_TONE_GENERATION.md).

Stage 3 step 2 adds read-only five-domain interpretation and shared gate plans (`tutor-interpretation-v2`, `tutor-gates-v2`), deterministic speech-rate expressions, conjunction/keep validation, expanded avatar candidates and general English clarification options. Runtime execution remains restricted to connected Reply length effects; other requests return unresolved without partial application until subsequent steps connect their outputs. All 266 backend tests pass (33 new); no new live-model or Unity acceptance was run. See [Stage 3 request planning](../Docs/TutorPersonalization/STAGE_3_REQUEST_PLANNING.md) for schema, thresholds and rollout boundaries.

From the repository root:

```bash
# Credentials are supplied outside the repository. Never paste keys into Unity or this file.
set -a
. "$HOME/.config/aiaa4435/appearance.env"
set +a
python3 Backend/server.py --mode live --host 127.0.0.1 --port 8765
```

Required environment: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`. Optional `DEEPSEEK_BASE_URL` defaults to `https://api.deepseek.com`; the adapter appends `/chat/completions`. The configured model must be supported by that account/provider. There is no silent downgrade to a mock model. `/health` reports `mode` and requested model; JSONL model-call records preserve actual returned model identifiers. A model alias is not an immutable snapshot.

The authorized credential order is teacher first, personal backup only on documented DeepSeek HTTP 402 (insufficient balance). `start_backend.sh` loads the teacher key from `~/.config/aiaa4435/deepseek-teacher.key` when present, retaining the existing private environment's key as `DEEPSEEK_FALLBACK_API_KEY`. The adapter switches once per process after a 402; authentication errors, throttling, invalid JSON and connection errors never trigger account switching. Model-call logs record `credential_slot` and the switch reason without keys or key hashes. Restarting the backend tries the teacher account first again. Both keys stay outside the repository and APK. See [DeepSeek error codes](https://api-docs.deepseek.com/quick_start/error_codes/).

For deterministic development without API charges:

```bash
python3 Backend/server.py --mode mock --port 8765
python3 -m unittest discover -s Backend/tests -v
```

Mock sessions are restricted to `phase: debug`; mock mode is visibly returned by the API. Mock interpretation is a small development fixture, not a general language model or a substitute for participant results. Tests use fixtures and never spend API credits. The HTTP test binds a temporary localhost port.

Default log directory: `Backend/logs/`, ignored by Git. Override with `--log-dir PATH`. Default API timeout is 20 seconds per attempt (`--timeout`); at most two attempts per model call, no retry on authentication or other permanent 4xx errors. The initial Native-gate path has at most four provider attempts (shared proposal plus Native decision, each bounded at two). Schema-invalid parsed proposals fail closed without extra retries. Formal collection should freeze the timeout and budget after the pilot.

The server binds localhost by default. For a headset reaching the backend over a trusted lab network, explicitly bind the private interface or tunnel the connection. This development server has no authentication or TLS and must not be exposed to the public Internet. API credentials stay on the backend. Active sessions are memory-only; JSONL persists across restart, but a restarted server cannot resume active sessions. Record interruptions and start a new session rather than fabricating continuity.

## Shared implementation and conditions

All initial requests use identical `PROPOSER_PROMPT`, public context, schema validation, candidate deduplication, default selection, question wording/options and allowed state changes. The proposer receives no condition, participant ID, task ID, hidden target, expected score or evaluator labels. Question ordering uses a deterministic hash of public query/state/history and the concrete option labels; the default is not automatically placed first.

- **E** executes the shared default.
- **A** asks the shared question once, including confirmation for a clear single candidate.
- **N** gives the same proposal, public context and question to a separate real DeepSeek decision call. It may choose ACT, ASK or UNRESOLVED. This is Native-gate, not an unconstrained agent.
- **S** applies R1 unresolved required reference, R2 possible unspecified soft-preference override, small reversible scale exception, R3 materially different candidates, then ACT. R1 with no distinct alternatives is UNRESOLVED. R2 can ask for confirmation of an override. R3 is computed from final effects, not model confidence or tag keywords. Duplicate final outcomes are merged.

R1 and R2 language interpretation still depend on the model. R2 accepts existing public preference text and model-provided override evidence, or structured preferences checked against candidate changes; explicit override authorization suppresses R2. These are fallible observations, not calibrated facts. Preserve proposal and gate errors as separate analyses.

There is at most one initial policy clarification per trial and two subsequent repair/undo actions. All conditions use one common repair resolver. A free-text “other” answer is interpreted once; ambiguous/unsupported results remain UNRESOLVED, without another policy question. Cancel and unsupported requests preserve appearance. The backend enforces a 120-second monotonic deadline from the first received request: no late edit or new clarification can commit. The Unity task timer starts on submission and records the user-visible completion/timeout marker, so network overhead is included there. A provider request already in flight may finish after the deadline, but its appearance edit is rejected.

Allowed state: `jacket_color` = blue/orange/green/gray/red/purple; `accessory` = none/hat/glasses; `scale` = 0.85–1.15 on a 0.05 grid. Float32 serialization differences within 0.00001 of a valid grid value are canonicalized; actual off-grid values such as 1.051 remain invalid. Initial state is blue/none/1.00. A reset applies each task's required initial state, including a hat where appropriate.

## HTTP contract

All POST requests use `Content-Type: application/json`. Responses include:

```json
{"session_id":"uuid","state":{"revision":1,"jacket_color":"blue","accessory":"none","scale":1.0},"decision":"ASK","message":"请补充一个信息后再执行。","condition":"S","phase":"debug","task_id":"A_T3","trial_id":"uuid","mode":"live","repairs_used":0,"max_repairs":2,"finished":false,"question":{"text":"你希望进行哪项修改？","options":[{"id":"c1","label":"外衣改为橙色"},{"id":"c2","label":"配饰改为帽子"},{"id":"other","label":"其他／都不是（请补充）"},{"id":"cancel","label":"取消，保持当前外形"}]}}
```

`question` exists only while a question is pending. Other decisions: READY, ACT, UNRESOLVED, ERROR, FINISHED. Error HTTP responses include `error`, `message`, `decision: ERROR` and the current session view where available. Always show error feedback; never silently treat a failure as an executed edit.

| Endpoint | Body / behavior |
| --- | --- |
| GET `/health` | `{ok,mode,model,policy_version,durability}` |
| POST `/sessions` | `{participant_id:"P001",condition:"S",phase:"debug"}`; phase defaults to debug; creates separate state and log |
| GET `/sessions/{id}` | Current view; use after a network error |
| POST `/sessions/{id}/reset` | `{request_id,expected_revision,state:{jacket_color,accessory,scale},history:[],soft_preferences:[],task_id}`; begins a new trial UUID, clears pending question/history/undo/limits, reopens a finished session |
| POST `/sessions/{id}/request` | `{request_id,expected_revision,query}`; first request uses policy; later requests consume shared repair budget |
| POST `/sessions/{id}/answer` | `{request_id,expected_revision,option_id,free_text:""}`; `other` requires nonempty free_text; `cancel` preserves appearance |
| POST `/sessions/{id}/undo` | `{request_id,expected_revision,field:"all"}`; field can also be jacket_color/accessory/scale; restores latest eligible edit for that field and preserves newer unrelated edits |
| POST `/sessions/{id}/events` | `{event,payload}`; audit only, never changes state/revision, never forwarded to the model |
| POST `/sessions/{id}/finish` | `{request_id,expected_revision}`; marks current trial finished; reset required before another task |

Identifiers use ASCII letters/numbers/underscore/hyphen, up to 80 characters (participant ID 48). Use anonymous codes such as P001 or ENGINEERING. State revision is a **session concurrency token**, incremented on each accepted mutation, including an ASK that changes no visible property. Always update the client's revision from responses. Pending questions cannot survive a newer reset/request/undo. Stale revisions return HTTP 409.

A request ID is idempotent across the session: retry identical operation/body without another model call. Reusing an ID for different content returns 409. If newer operations occurred after the original result, replay returns the current view with `idempotent_replay: true` and `original_decision`, so the renderer cannot accidentally roll back to a cached older response. Session mutations are serialized under a lock.

History accepts public `{query?,state?,before?,after?,patch?}` objects or bare state dictionaries from the authored cards. Public preferences accept strings or `{field,value,text?}`. A state may contain a convenience `revision` field, which is ignored in reset/history/render payloads; the outer expected_revision controls concurrency. Extra task goal/category fields in mutation endpoints are rejected, not forwarded.

## Renderer and timing events

`render_ack` / `probe` payload:

```json
{"revision":2,"state":{"jacket_color":"orange","accessory":"hat","scale":1.0},"probe_index":1,"client_build":"build identifier","trial_id":"uuid","task_id":"A_T1","block":1,"within_block":1,"duration_ms":14.2}
```

Also accepted: screenshot, matched, message, timing, kind, value, elapsed_seconds. The backend requires the current revision, validates the actual reported state, and records its own `server_computed_match`; a client-supplied `matched` value does not determine this check. Read actual Unity material/accessory/transform properties before sending these acknowledgments. A matching JSON patch alone is not renderer evidence. Probe indices 1/2/3 are separate client observations; the backend cannot verify a human wore the headset or that screenshots are real.

`client_marker` is bounded local metadata only. Planned marker payloads include `{study_session_id,trial_id,task_id,kind:"trial_start",block,within_block,elapsed_seconds,client_build}` and completion `{kind:"completion",value:"participant_done"|"timeout",...}`. Keep hidden targets, names and contact information out of these logs. `client_error` and `trial_rating` may also carry bounded payload dictionaries. Events do not get forwarded into future model context.

Every log line includes UTC time, `monotonic_ms`, `run_id` (server-process UUID), mode, phase, session/participant/condition/task/trial IDs, revision and policy version. Only subtract monotonic times within the same run_id. Model calls include `started_monotonic_ms`, `duration_seconds`, requested/returned model, attempt/error/usage, request/output hashes, prompt hash and generation settings; no keys or request authorization headers.

Important events: session_created, trial_reset, user_request, proposal, gate_decision, clarification_answer, commit, undo, model_call, operation_completed, operation_error, operation_rejected, client_render_ack, client_probe, client_marker, trial_finished. `commit.first_commit` uses an explicit per-trial counter, including no-op commits. `trial_finished` contains the final state and repair/question counts. Since finish itself increments revision, pre-finish probes should be matched to final appearance values rather than requiring identical revision numbers.

Use actual renderer evidence and three probes for stable success; missing evidence must stay missing. The study exporter owns private-target scoring outside this backend. Keep debug/pilot/mock records out of formal analysis unless explicitly reporting those phases separately.
