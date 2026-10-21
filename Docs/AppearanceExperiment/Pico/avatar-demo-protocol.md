# Avatar demo protocol

`avatar-demo-v1` is an optional **debug-only** capability profile. Omitted profiles
remain `study-v1`. Pilot and formal sessions reject the demo profile. The frozen
task cards, questionnaire, trial schedule, three-field study states, two-repair
budget and 120-second study limit are unchanged.

## Launch

For desktop builds, set:

```bash
export APPEARANCE_CAPABILITY_PROFILE=avatar-demo-v1
export APPEARANCE_PHASE=debug
export APPEARANCE_CONDITION=S
export APPEARANCE_PARTICIPANT_ID=DEBUGAVATAR
```

Do not set `APPEARANCE_TASK_ID` or `APPEARANCE_ASSIGNED=1` for this profile. For
Pico, use the existing researcher controller with an explicit profile:

```bash
python3 Tools/AppearanceExperiment/pico.py --serial HEADSET_SERIAL configure \
  --session-file /path/to/debug-session.json \
  --capability-profile avatar-demo-v1
python3 Tools/AppearanceExperiment/pico.py --serial HEADSET_SERIAL launch
python3 Tools/AppearanceExperiment/pico.py --serial HEADSET_SERIAL status
```

`configure` defaults to `--capability-profile study-v1`. The profile flag selects
the contract; the session file supplies validated identity. Demo configuration
rejects pilot/formal identities and any frozen task before changing device files.
The generated local `appearance-session.json` contains the selected profile:

```json
{
  "schema_version": "appearance-session-v1",
  "participant_id": "DEBUGAVATAR",
  "phase": "debug",
  "study_session_id": "debug_avatar_demo",
  "condition": "S",
  "task_id": "",
  "assigned": false,
  "capability_profile": "avatar-demo-v1",
  "backend_url": "http://127.0.0.1:8765"
}
```

Use the appropriate existing backend route for the device. These examples do not
start, restart or reconfigure a service. The server's existing live model and
credential selection remain in force: primary credentials first, fallback only
under the existing insufficient-balance rule. The new profile selects a richer
DeepSeek interpretation prompt; it does not substitute mock responses for live
requests. Explicit `--mode mock` remains a development fixture.

## State

| Field | Values and meaning |
| --- | --- |
| `avatar_id` | `liang`, `nailong` |
| `outfit` | Liang: `suit`, `sport`, `none`; Nailong: `none` only |
| `jacket_color` | `blue`, `orange`, `green`, `gray`, `red`, `purple`, `yellow` |
| `accessory` | `none`, `hat`, `glasses` on either avatar |
| `scale` | 0.85–1.15 in 0.05 steps |

The default is Liang Wenfeng with a muscular build, short black hair, blue suit
and glasses:

```json
{"avatar_id":"liang","outfit":"suit","jacket_color":"blue","accessory":"glasses","scale":1.0}
```

On Liang, color affects clothing; with `outfit=none`, it affects training shorts.
On Nailong, color affects the character's body. The fixed hair and muscle geometry
are part of the Liang model, not extra editable state fields.

“全部替换”, “全部换掉”, “整个换掉”, “全都换掉”, “换成奶龙”, and the user aliases “奶蛙” /
“奶娃” request one atomic replacement with these defaults:

```json
{"avatar_id":"nailong","outfit":"none","jacket_color":"yellow","accessory":"none","scale":1.0}
```

An explicit instruction to preserve a supported field takes precedence over a
replacement default. For example, “换成奶龙，但保留颜色、眼镜和大小” keeps the current
color, accessory and scale. A request requiring Nailong to keep a suit is
unsupported; the system must not silently discard that requirement. Ordinary
color, accessory, outfit and size edits preserve identity.

## HTTP flow

Create a session:

```http
POST /sessions
Content-Type: application/json

{"participant_id":"DEBUGAVATAR","phase":"debug","condition":"S","capability_profile":"avatar-demo-v1"}
```

The returned view includes `session_id`, `capability_profile`, the full state
with `revision`, `max_repairs: 12`, and `trial_limit_seconds: 600`.

Send each natural-language edit through the existing request route. Replace
`SESSION_ID` with the returned ID and always use the latest revision:

```http
POST /sessions/SESSION_ID/request
Content-Type: application/json

{"request_id":"demo-edit-1","expected_revision":0,"query":"换成运动装，颜色改成紫色，比例改为1.10"}
```

Subsequent independent demo requests still run the configured gate, so an
ambiguous request can return `ASK` after an earlier edit. When it does, the
rendered state remains unchanged until an answer:

```http
POST /sessions/SESSION_ID/answer
Content-Type: application/json

{"request_id":"demo-answer-1","expected_revision":2,"option_id":"c1","free_text":""}
```

Use an option ID from the actual response rather than assuming `c1` is the desired
choice. `cancel` keeps the current appearance; `other` requires free text and
uses the existing shared resolver. The revision above is illustrative.

To replace the complete avatar:

```http
POST /sessions/SESSION_ID/request
Content-Type: application/json

{"request_id":"demo-replace-1","expected_revision":3,"query":"全部换掉"}
```

Undo supports `all`, `jacket_color`, `accessory`, `scale`, `avatar_id`, and `outfit`:

```http
POST /sessions/SESSION_ID/undo
Content-Type: application/json

{"request_id":"demo-undo-1","expected_revision":4,"field":"all"}
```

`all` restores the still-active fields of the most recent change. A full avatar
replacement is one change. A partial undo changes only its named field and
preserves later edits to other fields. If a partial undo would produce an invalid
avatar/outfit combination, the server returns `409 invalid_undo_combination`
without changing state, revision or repair count. Replaying a successful
request ID does not apply an edit or undo twice; stale replays return the current
authoritative state.

The first request and its answers do not consume a repair. Later requests and
successful undos share the demo's 12-repair budget. The 600-second clock starts
at the first request.

## Rendering and compatibility

Unity enables the demo renderer only after launch configuration validation and
before creating the backend session. Missing resources or failed initialization
stop interaction. `Apply` must succeed before the client acknowledges a state.
Both ordinary acknowledgements and persistence probes compare all five observed
fields against the authoritative state.

Demo `render_ack` / `probe` payloads require all five fields. Missing fields and
invalid combinations are rejected; a valid but different observation is logged
with `server_computed_match: false` and causes the client to fail the check.
`AppearanceWire` uses explicit study DTOs so study resets, histories,
acknowledgements and probes contain only the original three editable fields
plus the existing revision.

The device status file exposes `capability_profile` and all demo observation
fields. Participant panels expose appearance controls only; the additional
“形象” and “服装” undo choices appear only in the demo.

The researcher controller accepts `avatar_id` and `outfit` undo values only when
fresh device status explicitly reports `capability_profile=avatar-demo-v1` and
`phase=debug`:

```bash
python3 Tools/AppearanceExperiment/pico.py --serial HEADSET_SERIAL command undo --value avatar_id
python3 Tools/AppearanceExperiment/pico.py --serial HEADSET_SERIAL command undo --value outfit
```

Legacy status files without a profile remain valid study status and do not enable
these extra commands. Unknown profiles or demo profiles outside debug are
rejected. The researcher web console displays the active profile, shows avatar
and outfit observations and their undo buttons only in demo, and labels Nailong's
color as body color. This changes no participant interface.

## Verification

Run backend unit and temporary localhost HTTP tests from the repository root:

```bash
python3 -m unittest discover -s Backend/tests -v
python3 -m unittest discover -s Tools/AppearanceExperiment/tests -p 'test_pico.py' -v
```

Coverage includes strict study/demo separation, aliases, atomic replacement,
preservation, repeated S clarification, invalid combinations, full and partial
undo replay, repair/time budgets, model-prompt selection and five-field render
observations. These tests use fixtures; they do not establish live model accuracy
or headset rendering quality. Controller tests mock every ADB operation, including
configuration rejection before writes and profile-specific undo validation.
