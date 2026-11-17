"""Debug tutor session controller: shared proposals, E/A/N/S, HTTP-ready state.

Generation jobs keep their settings snapshot and complete in conversation order.
All mutations are serialized, transactional and idempotent within a live process.
"""
from copy import copy, deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

from core import APIError, IDENTIFIER, text_value
from model import ModelError, sha
from tutor_interpretation import TutorInterpreter, build_context, _preferences
from tutor_state import TutorState, validate_patch
from tutor_dialogue_log import annotate, input_fields
from tutor_generation import GENERATION_VERSION, TutorGenerator
from tutor_policy import POLICY_VERSION, NATIVE_PROMPT, common_question, selective_decision, evaluate_gate
from tutor_capabilities import AUDIO_AVAILABLE, CONTROL_FIELDS, EXECUTABLE_FIELDS, execution_connected


RESOLUTION_INSTRUCTION = '''
This call resolves a free-text answer to an existing clarification, supplied in
clarification_resolution. Interpret the answer together with the original request
and question. Return tailoring/mixed with a proposal, never kind=clarification.
Retain original_scope. If the answer changes scope, requests an unsupported field,
or cannot resolve the original request, return supported=false with a reason.
Do not discard constraints explicitly preserved in the original request. A clear
answer can give one candidate. Do not invent a learning question from 'yes/no'.
Do not decide ASK/ACT; the controller consumes the clarified interpretation.'''


@dataclass
class TutorSession:
    session_id: str
    participant_id: str
    condition: str
    state: TutorState
    preferences: list
    revision: int = 0
    source_request_id: str | None = None
    pending: dict | None = None
    next_turn: dict | None = None
    generation_jobs: list = field(default_factory=list)
    deferred_questions: list = field(default_factory=list)
    last: dict = field(default_factory=lambda: {"decision": "READY", "message": "Tutor session ready."})
    cache: dict = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


class TutorSessions:
    def __init__(self, model, log_dir):
        self.model = model
        self.audio_available = AUDIO_AVAILABLE
        self.interpreter = TutorInterpreter(model)
        self.generator = TutorGenerator(model)
        self.log_dir = Path(log_dir) / "tutor" / "debug"
        self.sessions = {}
        self.lock = threading.Lock()
        self.run_id = uuid.uuid4().hex

    def log(self, s, event, **payload):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        record = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "monotonic_seconds": time.monotonic(),
                  "run_id": self.run_id, "session_id": s.session_id, "participant_id": s.participant_id,
                  "phase": "debug", "condition": s.condition, "mode": self.model.mode,
                  "policy_version": POLICY_VERSION, "revision": s.revision, "request_id": s.source_request_id, "event": event, **payload}
        annotate(record)
        with (self.log_dir / (s.session_id + ".jsonl")).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

    def view(self, s):
        with s.lock:
            snapshot = s.state.snapshot()
            snapshot["state_revision"] = snapshot.pop("revision")
            return deepcopy({**snapshot, "session_id": s.session_id, "revision": s.revision,
                             "condition": s.condition, "phase": "debug", "mode": self.model.mode,
                             "model": self.model.model, "policy_version": POLICY_VERSION,
                             "soft_preferences": s.preferences, "question": (
                                 {"question_id": s.pending["id"], **s.pending["question"]} if s.pending else None),
                             "next_turn_override": s.next_turn, "generation_jobs": s.generation_jobs,
                             "deferred_questions": s.deferred_questions,
                             "generation_available": callable(getattr(self.model, "generate_tutor", None)),
                             "audio_available": self.audio_available,
                             "generation_version": GENERATION_VERSION, **s.last})

    def get(self, sid):
        with self.lock:
            s = self.sessions.get(sid)
        if s is None:
            raise APIError(404, "session_not_found", "Tutor session does not exist.")
        return s

    def create(self, data):
        if not isinstance(data, dict) or set(data) - {"participant_id", "condition", "phase", "settings", "soft_preferences"}:
            raise APIError(400, "invalid_session", "Unknown tutor session fields.")
        if data.get("phase", "debug") != "debug":
            raise APIError(400, "debug_only", "The tutor pipeline is not ready for pilot/formal collection.")
        condition = data.get("condition", "S")
        if condition not in ("E", "A", "N", "S"):
            raise APIError(400, "invalid_condition", "Condition must be E/A/N/S.")
        pid = text_value(data.get("participant_id", "ENGINEERING"), "participant_id", 48)
        if not IDENTIFIER.fullmatch(pid):
            raise APIError(400, "invalid_participant_id", "Use an anonymous ASCII code.")
        state = TutorState(data["settings"]) if "settings" in data else TutorState()
        preferences = _preferences(data.get("soft_preferences", []))
        s = TutorSession(uuid.uuid4().hex, pid, condition, state, preferences)
        self.log(s, "session_created", settings=state.snapshot()["settings"], soft_preferences=preferences)
        with self.lock:
            self.sessions[s.session_id] = s
        return self.view(s)

    def mutate(self, sid, operation, data):
        s = self.get(sid)
        allowed = {"request": {"query", "question_id"}, "answer": {"question_id", "option_id", "free_text"},
                   "cancel": {"question_id"}, "settings": {"patch"}, "undo": {"field"},
                   "reset": {"settings", "soft_preferences"}, "generate": {"job_id"}}
        if operation not in allowed:
            raise APIError(404, "endpoint_not_found", "Unknown tutor operation.")
        if not isinstance(data, dict) or set(data) - (allowed[operation] | {"request_id", "expected_revision"}):
            raise APIError(400, "invalid_operation", "Unknown operation fields; private study targets are not accepted.")
        request_id = text_value(data.get("request_id"), "request_id", 80)
        if not IDENTIFIER.fullmatch(request_id):
            raise APIError(400, "invalid_request_id", "Use an ASCII request ID.")
        signature = sha({"operation": operation, "data": data})
        with s.lock:
            if request_id in s.cache:
                previous = s.cache[request_id]
                if previous["signature"] != signature:
                    raise APIError(409, "request_id_conflict", "Request ID already used for different content.", self.view(s))
                view = {**self.view(s), "idempotent_replay": True, "original_decision": previous["decision"]}
                if previous["error"]:
                    code, error, message = previous["error"]
                    raise APIError(code, error, message, view)
                return view
            if type(data.get("expected_revision")) is not int or data["expected_revision"] != s.revision:
                raise APIError(409, "stale_revision", "Refresh tutor state before retrying.", self.view(s))
            work = copy(s)
            work.source_request_id = request_id
            work.state = s.state.clone()
            for name in ("pending", "next_turn", "generation_jobs", "deferred_questions", "last"):
                setattr(work, name, deepcopy(getattr(s, name)))
            error = None
            try:
                self.log(s, "operation_started", request_id=request_id, operation=operation, input=input_fields(operation, data))
                self._execute(work, operation, data)
                work.revision += 1
                # Write the resulting snapshot before publishing; a disk failure
                # must not return an unlogged successful mutation.
                self.log(work, "operation_committed", request_id=request_id, operation=operation, result=self.view(work))
            except ModelError:
                error = (502, "model_error", "The model call or its output failed. No changes were applied; use a new request ID to retry.")
            except APIError as exc:
                error = (exc.status, exc.code, exc.message)
            except OSError:
                error = (503, "audit_unavailable", "Cannot write the local audit log; no changes were applied.")
            if error:
                s.cache[request_id] = {"signature": signature, "decision": "ERROR", "error": error}
                try:
                    self.log(s, "operation_error", request_id=request_id, operation=operation, code=error[1])
                except OSError:
                    pass
                raise APIError(*error, self.view(s))
            for name in ("state", "preferences", "revision", "pending", "next_turn", "generation_jobs", "deferred_questions", "last"):
                setattr(s, name, getattr(work, name))
            s.cache[request_id] = {"signature": signature, "decision": s.last["decision"], "error": None}
            return self.view(s)

    def _model_result(self, s, method, *args, **kwargs):
        try:
            result = method(*args, **kwargs)
        except ModelError as exc:
            for record in exc.records:
                self.log(s, "model_call", record=record)
            raise
        records = result[1] if isinstance(result, tuple) else result["model_calls"]
        for record in records:
            self.log(s, "model_call", record=record)
        return result

    def _queue(self, s, queries):
        for query in queries:
            if not query:
                continue
            settings = s.state.snapshot()["settings"]
            override = s.next_turn
            if override:
                settings.update(override)
            s.generation_jobs.append({"job_id": uuid.uuid4().hex, "query": query, "settings": settings,
                                      "turn_override": deepcopy(override),
                                      "status": "queued" if callable(getattr(self.model, "generate_tutor", None)) else "awaiting_generator",
                                      "queued_at_revision": s.revision + 1})
            # The override is now bound to this job (including a future retry),
            # never to all later questions. Persistent settings remain unchanged.
            s.next_turn = None

    def _generate(self, s, job_id):
        job_id = text_value(job_id, "job_id", 80)
        job = next((item for item in s.generation_jobs if item["job_id"] == job_id), None)
        if job is None:
            raise APIError(404, "job_not_found", "This question is not queued in the current session.")
        replay = job["status"] == "completed"
        if not replay:
            earliest = next(item for item in s.generation_jobs if item["status"] != "completed")
            if job is not earliest:
                raise APIError(409, "generation_order", "Generate earlier questions first so follow-ups use the completed conversation.")
            if not callable(getattr(self.model, "generate_tutor", None)):
                raise APIError(503, "model_unavailable", "Tutor answer generation is unavailable in this model adapter.")
            snapshot = s.state.snapshot()
            self.log(s, "generation_started", job_id=job_id, query=job["query"], settings=job["settings"],
                     context_revision=snapshot["revision"])
            result = self._model_result(s, self.generator.generate, job, snapshot)
            updated = s.state.record_exchange(job["query"], result["answer"], expected_revision=snapshot["revision"],
                                             generation_settings=job["settings"])
            job.update(status="completed", answer=result["answer"], exchange_id=updated["conversation"][-1]["id"],
                       generation_version=result["version"], completed_at_revision=s.revision + 1)
            self.log(s, "answer_generated", job_id=job_id, context=result["context"],
                     answer=job["answer"], settings=deepcopy(job["settings"]), generated_components=result["components"],
                     exchange_id=job["exchange_id"], generation_version=result["version"])
        # A new request ID for an already completed job still reuses its answer.
        # It never calls the provider again or duplicates a conversation turn.
        s.last = {"decision": "ANSWER", "message": job["answer"], "generation_replay": replay,
                  "response": {"job_id": job_id, "text": job["answer"], "settings": deepcopy(job["settings"]),
                               "audio_status": "available_on_request" if self.audio_available else "not_connected",
                               "exchange_id": job["exchange_id"]}}

    def _apply(self, s, interpretation, candidate, query, source, questions):
        if self._execution_blocked(s, interpretation):
            if s.pending:
                s.pending["questions"] = questions
            else:
                s.deferred_questions = questions
            return
        patch = candidate["patch"]
        if interpretation["scope"] == "turn":
            settings = s.state.snapshot()["settings"]
            # Include explicit required no-ops: reserving the current tone for
            # one answer must not accidentally become a reply-length override.
            fields = set(patch) | set(interpretation.get("required_fields", []))
            if not fields:
                fields = set(interpretation["requested_fields"])
            s.next_turn = {f: patch.get(f, settings[f]) for f in settings if f in fields}
        else:
            s.state.commit(patch, expected_revision=s.state.snapshot()["revision"], source=source, query=query)
            s.next_turn = None
        s.pending = None
        self._queue(s, questions)
        s.deferred_questions = []
        s.last = {"decision": "ACT", "message": ("Response settings reserved for one answer." if interpretation["scope"] == "turn" else "Response settings applied."),
                  "applied_scope": interpretation["scope"]}
        if {"speech_rate", "voice"} & set(interpretation["requested_fields"]):
            s.last["message"] += " Audio playback is not connected yet."

    def _gate(self, s, query, interpretation):
        proposal = interpretation["proposal"]
        settings = s.state.snapshot()["settings"]
        question = common_question(query, interpretation, settings) if proposal["supported"] else None
        context = build_context(query, s.state.snapshot(), preferences=s.preferences)
        result = self._model_result(s, evaluate_gate, self.model, s.condition, context, interpretation, question)
        decision, reason = result["decision"], result["reason"]
        self.apply_gate_plan(s, query, interpretation, decision, reason, question)

    def apply_gate_plan(self, s, query, interpretation, decision, reason, question):
        """Internal controller entry for an already validated shared gate plan."""
        proposal = interpretation["proposal"]
        self.log(s, "gate_decision", decision=decision, reason=reason, interpretation=interpretation, question=question)
        questions = s.deferred_questions + ([interpretation["conversation_query"]] if interpretation["conversation_query"] else [])
        if proposal["supported"] and self._execution_blocked(s, interpretation):
            s.deferred_questions = questions
            return
        if decision == "ASK":
            s.pending = {"id": uuid.uuid4().hex, "query": query, "interpretation": interpretation,
                         "question": question, "questions": questions}
            s.deferred_questions = []
            s.last = {"decision": "ASK", "reason": reason, "message": question["text"]}
        elif decision == "ACT":
            candidate = next(c for c in proposal["candidates"] if c["id"] == proposal["default_id"])
            self._apply(s, interpretation, candidate, query, "request", questions)
            s.last["reason"] = reason
        else:
            s.deferred_questions = questions
            s.last = {"decision": "UNRESOLVED", "reason": reason, "message": proposal["reason"] if not proposal["supported"] else "The request remains unresolved; settings were preserved."}

    def _execution_blocked(self, s, interpretation):
        if execution_connected(interpretation):
            return False
        s.last = {"decision": "UNRESOLVED", "reason": "EXECUTION_NOT_CONNECTED",
                  "message": "This request can be planned, but its setting effects are not connected yet. No settings were changed."}
        self.log(s, "execution_not_connected", requested_fields=interpretation["requested_fields"])
        return True

    def _check_question(self, s, question_id):
        if not s.pending or question_id != s.pending["id"]:
            raise APIError(409, "stale_question", "This clarification is no longer active.")

    def _answer(self, s, option_id, free_text="", extra_question=""):
        pending = s.pending
        free_text = text_value(free_text, "free_text", 8000, empty=True)
        if option_id not in [o["id"] for o in pending["question"]["options"]]:
            raise APIError(400, "invalid_option", "Choose an offered option or explain another answer.")
        if option_id != "other" and free_text:
            raise APIError(400, "invalid_answer", "Free text is only accepted with the other option.")
        questions = pending["questions"] + ([extra_question] if extra_question else [])
        self.log(s, "clarification_answer", question_id=pending["id"], option_id=option_id, free_text=free_text)
        if option_id == "cancel":
            s.pending = None
            self._queue(s, questions)
            s.last = {"decision": "CANCELLED", "message": "Change cancelled; persistent settings were preserved."}
            return
        interpretation = pending["interpretation"]
        if option_id == "other":
            free_text = text_value(free_text, "free_text", 8000)
            if not hasattr(self.model, "resolve_tutor_answer"):
                raise APIError(503, "model_unavailable", "Free-text tutor clarification is unavailable in this model adapter.")
            result = self._model_result(s, self.interpreter.resolve_answer, free_text, s.state.snapshot(),
                                        preferences=s.preferences, pending=pending["question"], scope=interpretation["scope"],
                                        preserved_fields=interpretation.get("preserved_fields", []))
            resolved = result["interpretation"]
            proposal = resolved["proposal"]
            if resolved["kind"] not in ("tailoring", "mixed") or not proposal or not proposal["supported"] or len(proposal["candidates"]) != 1 or proposal["unresolved_references"] or resolved["scope"] != interpretation["scope"]:
                # Keep the same live question; don't run another policy gate or
                # invent an answer. Additional learning content is retained.
                pending["questions"] = questions + ([resolved["conversation_query"]] if resolved["conversation_query"] else [])
                message = proposal["reason"] if proposal and not proposal["supported"] else "The answer did not resolve this change."
                s.last = {"decision": "UNRESOLVED", "message": message + " Choose an option, clarify again, or cancel."}
                return
            interpretation = resolved
            candidate = proposal["candidates"][0]
            if resolved["conversation_query"]:
                questions.append(resolved["conversation_query"])
        else:
            candidate = next(c for c in interpretation["proposal"]["candidates"] if c["id"] == option_id)
        self._apply(s, interpretation, candidate, pending["query"], "clarification", questions)

    def _execute(self, s, operation, data):
        if operation == "generate":
            self._generate(s, data.get("job_id"))
            return
        if operation == "reset":
            s.state = TutorState(data["settings"]) if "settings" in data else TutorState()
            s.preferences = _preferences(data.get("soft_preferences", []))
            s.pending = s.next_turn = None
            s.generation_jobs, s.deferred_questions = [], []
            s.last = {"decision": "READY", "message": "Tutor session reset."}
            return
        if operation in ("answer", "cancel"):
            self._check_question(s, data.get("question_id"))
            self._answer(s, "cancel" if operation == "cancel" else data.get("option_id"), data.get("free_text", ""))
            return
        if operation in ("settings", "undo"):
            if s.pending:
                raise APIError(409, "pending_question", "Resolve or cancel the pending change first.")
            if operation == "settings":
                patch = validate_patch(data.get("patch"))
                if not patch or set(patch) - CONTROL_FIELDS:
                    raise APIError(400, "unsupported_control", "Only the four dialogue settings are connected in this stage.")
                s.state.commit(patch, expected_revision=s.state.snapshot()["revision"], source="direct_control")
            else:
                if data.get("field") not in (*EXECUTABLE_FIELDS, "all"):
                    raise APIError(400, "unsupported_control", "Choose a supported setting field or all for undo.")
                s.state.undo(data["field"], expected_revision=s.state.snapshot()["revision"])
            s.next_turn = None
            s.last = {"decision": "ACT", "message": "Response settings updated.", "applied_scope": "session"}
            if (operation == "settings" and {"speech_rate", "voice"} & set(patch)) or (operation == "undo" and data.get("field") in ("speech_rate", "voice", "all")):
                s.last["message"] += " Audio playback is not connected yet."
            return
        query = text_value(data.get("query"), "query", 8000)
        if "question_id" in data:
            self._check_question(s, data["question_id"])
        if not hasattr(self.model, "interpret_tutor"):
            raise APIError(503, "model_unavailable", "Tutor interpretation requires the live adapter or an explicit test fixture.")
        self.log(s, "user_request", query=query)
        result = self._model_result(s, self.interpreter.interpret, query, s.state.snapshot(),
                                   preferences=s.preferences, pending=s.pending["question"] if s.pending else None)
        interpretation = result["interpretation"]
        self.log(s, "interpretation", result=result)
        kind = interpretation["kind"]
        if kind == "chat":
            self._queue(s, [interpretation["conversation_query"]])
            s.last = {"decision": "CHAT_QUEUED", "message": (
                "Question queued for a tutor answer." if callable(getattr(self.model, "generate_tutor", None))
                else "Question saved; tutor answer generation is unavailable in this model adapter.")}
        elif kind == "clarification":
            answer = interpretation["clarification"]
            self._answer(s, answer["option_id"], answer["free_text"], interpretation["conversation_query"])
        else:
            if s.pending:
                raise APIError(409, "pending_question", "Resolve or cancel the pending change before starting a new one.")
            self._gate(s, query, interpretation)
