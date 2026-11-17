"""Debug-only asynchronous four-branch execution with a first-reveal barrier.

Private TutorSession objects reuse the validated conversation engine but are never
registered in /tutor/sessions. Only the comparison's allowlisted view leaves here.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import copy, deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import threading
import time
import uuid

from core import APIError, IDENTIFIER, text_value
from model import ModelError, sha
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_session import TutorSession, TutorSessions
from tutor_state import DEFAULT_SETTINGS, TutorState, validate_patch
from tutor_study_materials import is_preview, public_start
from tutor_dialogue_log import annotate
from tutor_interpretation import _preferences
from tutor_shared_request import _Memo
from tutor_generation import GENERATION_VERSION, validate_components
from tutor_feedback import FEEDBACK_VERSION, ATTRIBUTE_VERSION, validate_feedback, complete
from tutor_capabilities import AUDIO_AVAILABLE, CONTROL_FIELDS, EXECUTABLE_FIELDS

from tutor_preferences import validate_sequence, slots, sequence_view, validate_preference, preference_command

EXECUTION_VERSION = "tutor-comparison-execution-v9"


def clone_session(s):
    work = copy(s)
    work.state = s.state.clone()
    for name in ("preferences", "pending", "next_turn", "generation_jobs", "deferred_questions", "last"):
        setattr(work, name, deepcopy(getattr(s, name)))
    return work


class _Engine(TutorSessions):
    def __init__(self, model, writer):
        super().__init__(model, Path("."))
        self.writer = writer

    def log(self, session, event, **payload):
        if event == "model_call":
            return  # The audited adapter owns the one canonical provider record.
        # Engine events describe attempts; branch_checkpoint is the commit record.
        self.writer("engine_event", condition=session.condition, engine_event=event, engine_revision=session.revision, request_id=session.source_request_id, **payload)


class _AuditedModel:
    """Record calls even if a task is closed before their result can be used."""
    def __init__(self, model, writer):
        self.delegate, self.writer = model, writer
        self.scope = threading.local()
        self.generations = {}
        self.lock = threading.Lock()

    def __getattr__(self, name):
        value = getattr(self.delegate, name)
        if name not in ("interpret_tutor", "decide_tutor", "resolve_tutor_answer", "generate_tutor") or not callable(value):
            return value
        return lambda context: self._generate(value, context) if name == "generate_tutor" else self._invoke(name, value, context)

    def _invoke(self, name, method, context):
        call_id = uuid.uuid4().hex
        meta = {"call_id": call_id, "condition": getattr(self.scope, "condition", None), "method": name}
        self.writer("provider_started", context_sha256=sha(context), **meta)
        try:
            raw, records = method(deepcopy(context))
        except ModelError as exc:
            self.writer("provider_finished", status="failed", model_calls=exc.records, **meta)
            raise
        except Exception:
            self.writer("provider_finished", status="failed", model_calls=[], **meta)
            raise
        self.writer("provider_finished", status="returned", model_calls=records, **meta)
        return raw, records

    def _generate(self, method, context):
        key = sha({"version": GENERATION_VERSION, "model": self.delegate.model, "context": context})
        with self.lock:
            memo = self.generations.setdefault(key, _Memo())
        def call():
            raw, records = self._invoke("generate_tutor", method, context)
            validate_components(raw, records)
            return {"raw": raw, "model_calls": records}
        with memo.lock:
            status = memo.status()
            retry = len(status["attempts"]) if status["status"] == "failed" and getattr(self.scope, "retry", False) else None
            result = memo.run(call, retry_attempt=retry)
            reused = status["status"] == "ready"
        self.writer("generation_reference", condition=getattr(self.scope, "condition", None), generation_key=key, reused=reused)
        return result["raw"], result["model_calls"]


@dataclass
class _BranchRuntime:
    session: TutorSession
    ticket: object = None
    stage: str = "initial"
    action: str = ""
    data: dict = field(default_factory=dict)
    outcome: str = "completed"
    message: str = ""
    retry_requested: bool = False
    source_request_id: str | None = None


@dataclass
class _Runtime:
    comparison: TutorComparison
    participant_id: str
    feedback_version: str = FEEDBACK_VERSION
    sequence: dict | None = None
    preferences: dict = field(default_factory=dict)
    preference_revision: int = 0
    preference_paused: bool = False
    preference_exited: bool = False
    preparation_required: bool = False
    preparation_confirmed: bool = False
    branches: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)
    lock: object = field(default_factory=threading.RLock)
    audit_lock: object = field(default_factory=threading.RLock)
    shared: object = None
    engine: object = None
    shared_status: str = "not_started"
    shared_attempt: int = 0
    publication_error: bool = False
    series_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sequence_index: int = 1
    previous_task_id: str | None = None
    next_task_id: str | None = None
    lifecycle: str = "active"
    paused_view: dict | None = None
    feedback: dict = field(default_factory=dict)
    submission: dict | None = None
    started_at: float = field(default_factory=time.monotonic)
    paused_at: float | None = None
    paused_seconds: float = 0.0
    ended_at: float | None = None


class TutorComparisons:
    def __init__(self, model, log_dir, max_workers=8):
        self.model = model
        self.audio_available = AUDIO_AVAILABLE
        self.log_dir = Path(log_dir) / "comparisons" / "debug"
        self.run_id = uuid.uuid4().hex
        self.tasks, self.create_cache = {}, {}
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tutor-comparison")
        self.closed = False

    def _log(self, rt, event, **payload):
        record = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "monotonic_seconds": time.monotonic(),
                  "run_id": self.run_id, "task_id": rt.comparison.task_id, "task_code": rt.comparison.task_code,
                  "participant_id": rt.participant_id, "phase": "debug", "mode": self.model.mode,
                  "domain": rt.comparison.domain, "scenario": rt.comparison.scenario,
                  "execution_version": EXECUTION_VERSION, "series_id": rt.series_id, "sequence_index": rt.sequence_index,
                  "event": event, **payload}
        annotate(record)
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        with rt.audit_lock:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with (self.log_dir / (rt.comparison.task_id + ".jsonl")).open("a", encoding="utf-8") as stream:
                stream.write(encoded)

    def _safe_log(self, rt, event, **payload):
        try:
            self._log(rt, event, **payload)
        except OSError:
            pass

    @staticmethod
    def _identifier(value, name):
        value = text_value(value, name, 80)
        if not IDENTIFIER.fullmatch(value):
            raise APIError(400, "invalid_" + name, "Use an anonymous ASCII identifier.")
        return value

    def get(self, task_id):
        with self.lock:
            rt = self.tasks.get(task_id)
        if rt is None:
            raise APIError(404, "comparison_not_found", "This comparison does not exist.")
        return rt

    def view(self, rt):
        with rt.lock:
            live = rt.comparison.participant_view()
            shown = deepcopy(rt.paused_view) if rt.lifecycle == "paused" else live
            shown["revision"] = live["revision"]
            feedback = {}
            for c in CONDITIONS:
                entry = deepcopy(rt.feedback.get(c))
                current = bool(entry and entry["branch_revision"] == live["branches"][c]["branch_revision"])
                feedback[c] = {"feedback_revision": entry["feedback_revision"] if entry else 0, "draft": entry,
                               "current": current, "complete": bool(current and complete(entry["answers"], rt.feedback_version))}
            can_submit = rt.lifecycle == "active" and live["results_visible"] and all(b["status"] in ("ready", "stopped") for b in live["branches"].values()) and all(f["complete"] for f in feedback.values())
            end = rt.ended_at or time.monotonic()
            paused = rt.paused_seconds + (end - rt.paused_at if rt.paused_at is not None else 0)
            return {**shown, "mode": self.model.mode, "phase_mode": "debug",
                    "model": self.model.model, "execution_version": EXECUTION_VERSION,
                    "audio_available": self.audio_available,
                    "preparation_required": rt.preparation_required,
                    "preparation_confirmed": rt.preparation_confirmed,
                    "preparation_locked": is_preview(rt.sequence),
                    "shared_preparation": {"status": rt.shared_status, "attempt": rt.shared_attempt},
                    "publication_error": "audit_unavailable" if rt.publication_error else None,
                    "lifecycle": rt.lifecycle, "series_id": rt.series_id, "sequence_index": rt.sequence_index,
                    "previous_task_id": rt.previous_task_id, "next_task_id": rt.next_task_id,
                    "sequence": sequence_view(rt), "feedback_version": rt.feedback_version, "feedback": feedback, "can_submit": can_submit,
                    "submission_id": rt.submission["submission_id"] if rt.submission else None,
                    "elapsed_active_seconds": max(0, end - rt.started_at - paused), "elapsed_paused_seconds": paused}

    def create(self, data, *, lineage=None):
        allowed = {"request_id", "task_code", "domain", "scenario", "participant_id", "phase", "settings", "soft_preferences", "public_setup", "require_preparation", "feedback_version", "sequence"}
        if not isinstance(data, dict) or set(data) - allowed:
            raise APIError(400, "invalid_comparison", "Unknown comparison fields; private study targets are not accepted.")
        rid = self._identifier(data.get("request_id"), "request_id")
        signature = sha(data)
        with self.lock:
            if self.closed:
                raise APIError(503, "service_closed", "Comparison service is shutting down.")
            if rid in self.create_cache:
                old, tid = self.create_cache[rid]
                if old != signature:
                    raise APIError(409, "request_id_conflict", "Create request ID already used for different content.")
                return {**self.view(self.tasks[tid]), "idempotent_replay": True}
            if data.get("phase", "debug") != "debug":
                raise APIError(400, "debug_only", "Comparison execution is not registered for participant collection.")
            if type(data.get("require_preparation", False)) is not bool:
                raise APIError(400, "invalid_preparation", "Use a boolean preparation requirement.")
            version = data.get("feedback_version", FEEDBACK_VERSION)
            if version not in (FEEDBACK_VERSION, ATTRIBUTE_VERSION):
                raise APIError(400, "invalid_feedback_version", "Use an attribute comparison questionnaire version.")
            sequence = validate_sequence(data.get("sequence"))
            if sequence is not None:
                index = lineage[1] - 1 if lineage else 0
                plan = slots(sequence)
                if version != ATTRIBUTE_VERSION or not 0 <= index < len(plan) or any(data.get(k) != v for k, v in plan[index][2].items()):
                    raise APIError(400, "sequence_mismatch", "Start the registered attribute task with its questionnaire version.")
            prepared = public_start(sequence, data.get("task_code"))
            if prepared is not None:
                if set(data) & {"settings", "public_setup", "soft_preferences"}:
                    raise APIError(400, "fixed_study_baseline", "The registered study task supplies its own fixed baseline.")
                if data.get("require_preparation") is not True:
                    raise APIError(400, "preparation_required", "Study preview requires an explicit baseline confirmation.")
                data = {**data, **prepared}
            # Comparison task specifications may override only selected initial
            # fields. Fill from fresh defaults, never a preceding task's state;
            # TutorState still validates the complete appearance combination.
            baseline = TutorState({**DEFAULT_SETTINGS, **validate_patch(data.get("settings", {}))})
            setup = data.get("public_setup", [])
            if not isinstance(setup, list) or len(setup) > 30:
                raise APIError(400, "invalid_public_setup", "Use at most 30 public setup events.")
            for item in setup:
                if not isinstance(item, dict):
                    raise APIError(400, "invalid_public_setup", "Expected public setting or conversation events.")
                rev = baseline.snapshot()["revision"]
                if set(item) == {"kind", "patch", "query"} and item["kind"] == "setting":
                    baseline.commit(item["patch"], expected_revision=rev, source="request", query=item["query"])
                elif set(item) == {"kind", "user", "assistant"} and item["kind"] == "exchange":
                    baseline.record_exchange(item["user"], item["assistant"], expected_revision=rev)
                else:
                    raise APIError(400, "invalid_public_setup", "Only explicit public history is accepted.")
            baseline.capture_task_start()
            task = TutorComparison(task_code=data.get("task_code", "ENGINEERING"), domain=data.get("domain", "reply_length"),
                                   scenario=data.get("scenario", "C1"), baseline=baseline, preferences=data.get("soft_preferences"))
            pid = self._identifier(data.get("participant_id", "ENGINEERING"), "participant_id")
            rt = _Runtime(task, pid, sequence=sequence, feedback_version=version, preparation_required=data.get("require_preparation", False))
            if lineage:
                rt.series_id, rt.sequence_index, rt.previous_task_id = lineage
            writer = lambda event, **payload: self._log(rt, event, **payload)
            audited = _AuditedModel(self.model, writer)
            rt.engine = _Engine(audited, writer)
            rt.engine.audio_available = self.audio_available
            # Private runtime sessions are never inserted in any session registry.
            for c in CONDITIONS:
                rt.branches[c] = _BranchRuntime(TutorSession(uuid.uuid4().hex, pid, c, baseline.clone(), _preferences(data.get("soft_preferences", []))))
            try:
                self._log(rt, "comparison_created", baseline=baseline.snapshot(), preferences=data.get("soft_preferences", []),
                          preparation_required=rt.preparation_required, feedback_version=rt.feedback_version, sequence=rt.sequence)
            except OSError:
                raise APIError(503, "audit_unavailable", "Cannot create an unlogged comparison.") from None
            self.tasks[task.task_id] = rt
            self.create_cache[rid] = (signature, task.task_id)
            return self.view(rt)

    def mutate(self, task_id, operation, data, condition=None):
        rt = self.get(task_id)
        task_ops = {"round_request": {"query"}, "round_settings": {"patch"}, "round_undo": {"field"}, "start": {"query"}, "select": {"condition"}, "close": set(), "pause": set(), "resume": set(),
                    "prepare": {"patch"}, "confirm_preparation": set(),
                    "submit": set(), "next": {"next_task"},
                    "preference": {"scope", "expected_preference_revision", "answers"},
                    "preference_pause": {"expected_preference_revision"}, "preference_resume": {"expected_preference_revision"},
                    "preference_exit": {"expected_preference_revision"},
                    "retry_shared": {"expected_attempt"}, "retry_reveal": set()}
        branch_ops = {"answer": {"question_id", "response"}, "request": {"query"}, "settings": {"patch"},
                      "undo": {"field"}, "retry": set(), "stop": set(),
                      "feedback": {"expected_feedback_revision", "answers"}, "presentation": {"page"}}
        allowed = task_ops if condition is None else branch_ops
        revision_field = "expected_revision" if condition is None else "expected_branch_revision"
        if operation not in allowed or condition is not None and condition not in CONDITIONS:
            raise APIError(404, "endpoint_not_found", "Unknown comparison operation.")
        if not isinstance(data, dict) or set(data) - (allowed[operation] | {"request_id", revision_field}):
            raise APIError(400, "invalid_operation", "Unknown fields; private task data are not accepted.")
        rid = self._identifier(data.get("request_id"), "request_id")
        signature = sha({"operation": operation, "condition": condition, "data": data})
        # next acquires registry -> task, the same order as create/replay. Never
        # acquire the registry while holding a task lock in another command.
        with self.lock if operation == "next" or operation.startswith("preference") else nullcontext(), rt.lock:
            if rid in rt.cache:
                cached = rt.cache[rid]
                if cached["signature"] != signature:
                    raise APIError(409, "request_id_conflict", "Request ID already used for different content.", self.view(rt))
                view = {**self.view(rt), "idempotent_replay": True}
                if cached["error"]:
                    raise APIError(*cached["error"], view)
                return view
            error = None
            try:
                view = self.view(rt)
                if self.closed or view["phase"] == "closed" and not ((operation == "next" or operation.startswith("preference")) and rt.lifecycle == "submitted"):
                    raise APIError(409, "task_closed", "This comparison is closed.")
                if rt.lifecycle == "paused" and operation not in ("resume", "close"):
                    raise APIError(409, "task_paused", "Resume before interacting; exit is always available.")
                expected = view["revision"] if condition is None else view["branches"][condition]["branch_revision"]
                if type(data.get(revision_field)) is not int or data[revision_field] != expected:
                    raise APIError(409, "stale_revision", "Refresh the comparison before retrying.")
                # Validate optional feedback text before any log can retain it.
                if operation == "preference":
                    validate_preference(data.get("answers"))
                if operation == "feedback":
                    validate_feedback(data.get("answers"), version=rt.feedback_version)
                self._log(rt, "command_received", request_id=rid, operation=operation, condition=condition,
                          data={k: v for k, v in data.items() if k != "answers"})
                self._command(rt, operation, data, condition)
            except APIError as exc:
                error = (exc.status, exc.code, exc.message)
            except OSError:
                error = (503, "audit_unavailable", "Cannot write the comparison audit log.")
            rt.cache[rid] = {"signature": signature, "error": error}
            if error:
                raise APIError(*error, self.view(rt))
            return self.view(rt)

    def _command(self, rt, op, data, c):
        task = rt.comparison
        if c is None:
            rev = data["expected_revision"]
            if op.startswith("preference"):
                preference_command(self, rt, op, data)
            elif op in ("prepare", "confirm_preparation"):
                if not rt.preparation_required or rt.preparation_confirmed or task.participant_view()["phase"] != "awaiting_input":
                    raise APIError(409, "preparation_locked", "Shared preparation is not editable.")
                if op == "prepare":
                    if is_preview(rt.sequence):
                        raise APIError(409, "fixed_study_baseline", "Listen to the registered baseline, then confirm it without changing settings.")
                    patch = validate_patch(data.get("patch"))
                    if not patch or set(patch) - CONTROL_FIELDS:
                        raise APIError(400, "invalid_preparation_patch", "Adjust only the four dialogue controls.")
                    state = task.prepare_baseline(patch, expected_revision=rev,
                        before_commit=lambda snapshot: self._log(rt, "shared_settings_updated",
                            request_id=data["request_id"], baseline=snapshot))
                    for rb in rt.branches.values():
                        rb.session.state = state.clone()
                else:
                    self._log(rt, "preparation_confirmed", request_id=data["request_id"],
                              baseline=task.participant_view()["baseline"])
                    task.touch(expected_revision=rev)
                    rt.preparation_confirmed = True
            elif op == "pause":
                if rt.lifecycle != "active":
                    raise APIError(409, "not_active", "Only an active task can be paused.")
                frozen = task.participant_view()
                self._log(rt, "task_paused", task_revision=rev, results_visible=frozen["results_visible"])
                task.touch(expected_revision=rev)
                rt.paused_view, rt.paused_at, rt.lifecycle = frozen, time.monotonic(), "paused"
            elif op == "resume":
                if rt.lifecycle != "paused":
                    raise APIError(409, "not_paused", "This task is not paused.")
                self._log(rt, "task_resumed", paused_seconds=time.monotonic() - rt.paused_at)
                task.touch(expected_revision=rev)
                rt.paused_seconds += time.monotonic() - rt.paused_at
                rt.paused_view = rt.paused_at = None
                rt.lifecycle = "active"
                self._maybe_reveal(rt)
            elif op == "submit":
                if not self.view(rt)["can_submit"]:
                    raise APIError(409, "feedback_required", "Resolve or stop all branches and complete current questionnaire feedback for each strategy.")
                snapshot = task.participant_view()
                submission = {"submission_id": uuid.uuid4().hex, "feedback_version": rt.feedback_version,
                              "first_reveal": snapshot["first_reveal"], "final_results": {c: b["result"] for c, b in snapshot["branches"].items()},
                              "feedback": deepcopy(rt.feedback)}
                self._log(rt, "task_submitted", submission=submission)
                task.close(expected_revision=rev)
                rt.submission, rt.lifecycle, rt.ended_at = submission, "submitted", time.monotonic()
            elif op == "next":
                if rt.lifecycle != "submitted":
                    raise APIError(409, "submission_required", "Submit valid feedback before advancing. Exiting is not submitting.")
                if rt.next_task_id:
                    raise APIError(409, "already_advanced", "This task already has a successor; use next_task_id.")
                spec = data.get("next_task")
                allowed = {"task_code", "domain", "scenario", "settings", "soft_preferences", "public_setup"}
                if not isinstance(spec, dict) or set(spec) - allowed or not {"task_code", "domain", "scenario"} <= set(spec):
                    raise APIError(400, "invalid_next_task", "Provide the next task code/domain/scenario and its own public baseline.")
                if rt.sequence is not None:
                    plan = slots(rt.sequence); index = rt.sequence_index
                    gate = sequence_view(rt)
                    if rt.preference_paused or rt.preference_exited or index >= len(plan):
                        raise APIError(409, "sequence_complete_or_paused", "No next attribute task is available.")
                    if gate['at_module_end'] and not gate['attribute_saved']:
                        raise APIError(409, "preference_required", "Submit the attribute preference before the next module.")
                    if any(spec.get(k) != v for k, v in plan[index][2].items()):
                        raise APIError(400, "sequence_mismatch", "Advance to the next registered task only.")
                # Stable internal create ID also recovers an audit failure after
                # creation but before the link is recorded. Never inherit results.
                new = self.create({**spec, "request_id": "next_" + task.task_id, "participant_id": rt.participant_id,
                                   "require_preparation": rt.preparation_required, "feedback_version": rt.feedback_version, "sequence": rt.sequence},
                                  lineage=(rt.series_id, rt.sequence_index + 1, task.task_id))
                self._log(rt, "task_advanced", submission_id=rt.submission["submission_id"], next_task_id=new["task_id"])
                rt.next_task_id = new["task_id"]
            elif op == "start":
                if rt.preparation_required and not rt.preparation_confirmed:
                    raise APIError(409, "preparation_required", "Confirm shared settings before recording a request.")
                tickets = task.start(data.get("query"), expected_revision=rev)
                rt.shared = task.shared_initial(rt.engine.model)
                for name, ticket in tickets.items():
                    rt.branches[name].ticket = ticket
                    rt.branches[name].source_request_id = data["request_id"]
                    rt.branches[name].session.source_request_id = data["request_id"]
                rt.shared_status = "processing"
                self.pool.submit(self._prepare, rt, False)
            elif op in ("round_request", "round_settings", "round_undo"):
                if op == "round_request":
                    query = text_value(data.get("query"), "query", 8000)
                    action, action_data = "request", {"query": query}
                elif op == "round_settings":
                    patch = validate_patch(data.get("patch"))
                    if not patch or set(patch) - CONTROL_FIELDS:
                        raise APIError(400, "unsupported_control", "Only the four dialogue settings are connected.")
                    query, action, action_data = "Shared response settings control", "settings", {"patch": patch}
                else:
                    if data.get("field") not in (*EXECUTABLE_FIELDS, "all"):
                        raise APIError(400, "unsupported_control", "Choose a supported setting field or all.")
                    # Reject before dispatch if a branch cannot undo; never partially undo a comparison.
                    for rb in rt.branches.values():
                        changes = rb.session.state.snapshot()["changes"]
                        if not any(change.get("kind") == "commit" and (change.get("remaining_fields") if data["field"] == "all" else data["field"] in change.get("remaining_fields", [])) for change in changes):
                            raise APIError(409, "shared_undo_unavailable", "This field must have an undoable change in every strategy.")
                    query, action, action_data = "Undo response settings in all strategies", "undo", {"field": data["field"]}
                tickets = task.begin_round(query, expected_revision=rev)
                for name, ticket in tickets.items():
                    rb = rt.branches[name]
                    rb.ticket, rb.stage, rb.action, rb.data = ticket, "action", action, deepcopy(action_data)
                    rb.retry_requested = False
                    rb.source_request_id = data["request_id"]
                for name, ticket in tickets.items():
                    self.pool.submit(self._run_branch, rt, name, ticket)
            elif op == "retry_shared":
                if rt.shared_status != "failed" or type(data.get("expected_attempt")) is not int or data["expected_attempt"] != rt.shared_attempt:
                    raise APIError(409, "stale_retry", "Retry the current failed shared preparation only.")
                current = task.participant_view()
                affected = [name for name, b in current["branches"].items() if b["status"] == "failed" and rt.branches[name].stage == "shared"]
                if current["results_visible"] or not affected:
                    raise APIError(409, "no_pending_shared_work", "There are no unfinished branches awaiting shared interpretation.")
                for name, branch in current["branches"].items():
                    if branch["status"] == "failed" and rt.branches[name].stage == "shared":
                        rt.branches[name].ticket = task.retry(name, expected_branch_revision=branch["branch_revision"])
                rt.shared_status = "processing"
                self.pool.submit(self._prepare, rt, True)
            elif op == "select":
                selected = data.get("condition")
                if not isinstance(selected, str) or selected not in CONDITIONS:
                    raise APIError(400, "invalid_condition", "Choose E/A/N/S.")
                before = task.participant_view()
                self._log(rt, "strategy_selected", previous=before["selected_condition"], selected=selected,
                          results_visible=before["results_visible"], branch_revision=before["branches"][selected]["branch_revision"])
                task.select(data.get("condition"), expected_revision=rev)
            elif op == "close":
                self._log(rt, "task_aborted", results_visible=task.participant_view()["results_visible"],
                          feedback=deepcopy(rt.feedback), was_paused=rt.lifecycle == "paused")
                task.close(expected_revision=rev)
                rt.ended_at = time.monotonic()
                if rt.paused_at is not None:
                    rt.paused_seconds += rt.ended_at - rt.paused_at
                rt.paused_view = rt.paused_at = None
                rt.lifecycle = "aborted"
            else:
                if not rt.publication_error:
                    raise APIError(409, "not_failed", "There is no failed reveal to retry.")
                self._maybe_reveal(rt)
            return
        rb = rt.branches[c]
        view = task.participant_view()
        rev = data["expected_branch_revision"]
        if op == "presentation":
            page = data.get("page")
            if page not in ("conversation", "controls", "history"):
                raise APIError(400, "invalid_page", "Choose a displayed panel page.")
            if c != view["selected_condition"]:
                raise APIError(409, "not_selected", "Only the selected branch can be presented.")
            self._log(rt, "panel_presented", condition=c, page=page, results_visible=view["results_visible"],
                      branch_revision=rev, state_revision=view["branches"][c]["result"]["state"]["revision"] if view["results_visible"] else view["baseline"]["revision"],
                      reveal_id=view["latest_reveal"]["reveal_id"] if view["results_visible"] else None)
            return
        if op == "feedback":
            branch = view["branches"][c]
            if not view["results_visible"] or branch["status"] not in ("ready", "stopped"):
                raise APIError(409, "result_not_ready", "Rate a revealed, settled branch only.")
            old = rt.feedback.get(c)
            feedback_revision = old["feedback_revision"] if old else 0
            if type(data.get("expected_feedback_revision")) is not int or data["expected_feedback_revision"] != feedback_revision:
                raise APIError(409, "stale_feedback", "Refresh this feedback draft before editing it.")
            first = view["first_reveal"]["branches"][c]["state"]
            later = len(branch["result"]["state"]["conversation"]) > len(first["conversation"])
            entry = {"feedback_version": rt.feedback_version, "feedback_revision": feedback_revision + 1, "branch_revision": rev,
                     "state_revision": branch["result"]["state"]["revision"], "reveal_id": view["first_reveal"]["reveal_id"],
                     "answers": validate_feedback(data.get("answers"), later_interaction=later, version=rt.feedback_version)}
            self._log(rt, "feedback_saved", condition=c, draft=entry)
            rt.feedback[c] = entry
            task.touch(expected_revision=view["revision"])
            return
        if op == "stop":
            task.stop_branch(c, expected_branch_revision=rev, state=rb.session.state)
            rb.session.pending = rb.session.next_turn = None
            rb.session.generation_jobs = [j for j in rb.session.generation_jobs if j["status"] == "completed"]
            rb.session.deferred_questions = []
            self._maybe_reveal(rt)
            return
        if op == "retry":
            if rb.stage == "shared":
                raise APIError(409, "shared_retry_required", "Retry the shared interpretation once for all affected branches.")
            rb.ticket = task.retry(c, expected_branch_revision=rev)
            rb.retry_requested = True
        elif op == "answer":
            rb.ticket = task.answer(c, data.get("question_id"), data.get("response"), expected_branch_revision=rev)
            response = data["response"]
            if "option_id" in response:
                rb.action, rb.data = "answer", {"question_id": data["question_id"], "option_id": response["option_id"], "free_text": response.get("text", "")}
            else:
                rb.action, rb.data = "request", {"query": response["text"], "question_id": data["question_id"]}
            rb.stage = "action"
            rb.retry_requested = False
        else:
            if not view["results_visible"]:
                raise APIError(409, "results_hidden", "Resolve clarifications before editing or repairing results.")
            if op == "request":
                query = text_value(data.get("query"), "query", 8000)
                action_data = {"query": query}
            elif op == "settings":
                patch = validate_patch(data.get("patch"))
                if not patch or set(patch) - CONTROL_FIELDS:
                    raise APIError(400, "unsupported_control", "Only the four dialogue settings are connected.")
                query, action_data = "Response settings control", {"patch": patch}
            else:
                if data.get("field") not in (*EXECUTABLE_FIELDS, "all"):
                    raise APIError(400, "unsupported_control", "Choose a supported setting field or all for undo.")
                query, action_data = "Undo response settings", {"field": data["field"]}
            rb.ticket = task.begin_repair(c, query, expected_branch_revision=rev)
            rb.stage, rb.action, rb.data = "action", op, action_data
            rb.retry_requested = False
        if op != "retry":
            rb.source_request_id = data["request_id"]
        self.pool.submit(self._run_branch, rt, c, rb.ticket)

    def _valid(self, rt, ticket):
        try:
            rt.comparison.worker_input(ticket)
            return True
        except APIError:
            return False

    def _prepare(self, rt, retry):
        try:
            rt.engine.model.scope.condition = None
            rt.engine.model.scope.retry = retry
            with rt.lock:
                if rt.comparison.participant_view()["phase"] == "closed":
                    return
            status = rt.shared.preparation_status()
            prepared = rt.shared.retry_preparation(expected_attempt=len(status["attempts"])) if retry and status["status"] == "failed" else rt.shared.prepare()
            with rt.lock:
                if rt.comparison.participant_view()["phase"] == "closed":
                    return
                self._log(rt, "shared_prepared", prepared=prepared)
                rt.shared_status = "ready"
                rt.shared_attempt = len(rt.shared.preparation_status()["attempts"])
                for c, rb in rt.branches.items():
                    if self._valid(rt, rb.ticket):
                        rb.stage = "initial"
                        self.pool.submit(self._run_branch, rt, c, rb.ticket)
        except Exception as exc:
            with rt.lock:
                rt.shared_status = "failed"
                rt.shared_attempt = len(rt.shared.preparation_status()["attempts"])
                self._safe_log(rt, "shared_failed", model_calls=getattr(exc, "records", []), error=self._error_code(exc))
                for rb in rt.branches.values():
                    if self._valid(rt, rb.ticket):
                        rb.stage = "shared"
                        rt.comparison.fail(rb.ticket, code=self._error_code(exc))
                self._maybe_reveal(rt)

    @staticmethod
    def _error_code(exc):
        return "model_error" if isinstance(exc, ModelError) else "internal_error" if isinstance(exc, OSError) else "invalid_result"

    def _checkpoint(self, rt, c, ticket, work, stage, outcome, message):
        with rt.lock:
            if not self._valid(rt, ticket):
                return False
            work.revision = rt.branches[c].session.revision + 1
            self._log(rt, "branch_checkpoint", condition=c, stage=stage, ticket_revision=ticket.revision,
                      result=rt.engine.view(work), outcome=outcome, request_id=work.source_request_id)
            rb = rt.branches[c]
            rb.session, rb.stage, rb.outcome, rb.message = work, stage, outcome, message
            return True

    def _run_branch(self, rt, c, ticket):
        try:
            with rt.lock:
                if not self._valid(rt, ticket): return
                rb = rt.branches[c]
                work, stage, action, data = clone_session(rb.session), rb.stage, rb.action, deepcopy(rb.data)
                work.source_request_id = rb.source_request_id
                outcome, message = rb.outcome, rb.message
                rt.engine.model.scope.condition = c
                rt.engine.model.scope.retry = rb.retry_requested
            if stage == "initial":
                status = rt.shared.decision_status(c)
                plan = rt.shared.retry_decision(ticket, expected_attempt=len(status["attempts"])) if status["status"] == "failed" else rt.shared.decision_for(ticket)
                self._log(rt, "branch_gate_plan", condition=c, shared_id=plan["input"]["shared_id"], gate=plan["gate"])
                interpreted = plan["input"]["interpretation"]
                if interpreted["kind"] == "chat":
                    rt.engine._queue(work, [interpreted["conversation_query"]])
                    work.last = {"decision": "CHAT_QUEUED", "message": "Question queued for an answer."}
                else:
                    gate = plan["gate"]
                    rt.engine.apply_gate_plan(work, plan["input"]["query"], interpreted, gate["decision"], gate["reason"], plan["input"]["question"])
            elif stage == "action":
                rt.engine._execute(work, action, data)
            if stage in ("initial", "action"):
                outcome = {"CANCELLED": "cancelled", "UNRESOLVED": "unresolved"}.get(work.last["decision"], "completed")
                message = work.last.get("message", "")
                # A response which does not resolve the ambiguity creates a new
                # question instance; the old question ID can never be replayed.
                if work.pending:
                    work.pending["id"] = uuid.uuid4().hex
                if not self._checkpoint(rt, c, ticket, work, "generate", outcome, message): return
            while True:
                with rt.lock:
                    if not self._valid(rt, ticket): return
                    rb = rt.branches[c]
                    work = clone_session(rb.session)
                    job = next((j for j in work.generation_jobs if j["status"] != "completed"), None)
                if job is None: break
                rt.engine._generate(work, job["job_id"])
                if not self._checkpoint(rt, c, ticket, work, "generate", rb.outcome, rb.message): return
            with rt.lock:
                if not self._valid(rt, ticket): return
                rb = rt.branches[c]
                if rb.session.pending:
                    p = rb.session.pending
                    rt.comparison.ask(ticket, {"question_id": p["id"], **p["question"]}, state=rb.session.state)
                else:
                    rt.comparison.finish(ticket, rb.session.state, outcome=rb.outcome, message=rb.message)
                rb.stage = "idle"
                self._maybe_reveal(rt)
        except Exception as exc:
            with rt.lock:
                if not self._valid(rt, ticket): return
                rb = rt.branches[c]
                self._safe_log(rt, "branch_failed", condition=c, stage=rb.stage, error=self._error_code(exc))
                rt.comparison.fail(ticket, code=self._error_code(exc), state=rb.session.state)
                self._maybe_reveal(rt)

    def _maybe_reveal(self, rt):
        if rt.lifecycle != "active":
            return
        view = rt.comparison.participant_view()
        if not view["can_reveal"]:
            return
        try:
            rt.comparison.reveal(expected_revision=view["revision"],
                                 before_publish=lambda snapshot: self._log(rt, "first_reveal" if rt.comparison._first_reveal is None else "round_reveal", snapshot=snapshot))
            rt.publication_error = False
        except OSError:
            rt.publication_error = True

    def shutdown(self, wait=True):
        with self.lock:
            self.closed = True
            tasks = list(self.tasks.values())
        for rt in tasks:
            with rt.lock:
                view = rt.comparison.participant_view()
                if view["phase"] != "closed":
                    rt.comparison.close(expected_revision=view["revision"])
        self.pool.shutdown(wait=wait, cancel_futures=True)
