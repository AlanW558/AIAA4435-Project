# Appearance experiment backend

Python 3.10+ standard library only. This backend connects the Unity appearance client to DeepSeek, keeps experiment conditions separate from shared interpretation, and writes local JSONL audit logs. It does not generate executable code or arbitrary assets.

## Run

From the repository root:

```bash
# Credentials are supplied outside the repository. Never paste keys into Unity or this file.
set -a
. "$HOME/.config/aiaa4435/appearance.env"
set +a
python3 Backend/server.py --mode live --host 127.0.0.1 --port 8765
```

Required environment: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`. Optional `DEEPSEEK_BASE_URL` defaults to `https://api.deepseek.com`; the adapter appends `/chat/completions`. The configured model must be supported by that account/provider. There is no silent downgrade to a mock model. `/health` reports `mode` and requested model; JSONL model-call records preserve actual returned model identifiers. A model alias is not an immutable snapshot.

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
