"""Stage-two comparison state foundation, not an HTTP API or execution runner.

Controller-only mutations and worker inputs are separate from participant_view.
State transitions make no provider calls. shared_initial owns read-only request
preparation; there is no Unity, audio, private study data or disk persistence.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import threading
import uuid

from core import APIError, IDENTIFIER, text_value
from tutor_interpretation import _pending, _preferences, build_context
from tutor_state import TutorState


SCHEMA_VERSION = "tutor-comparison-v1"
CONDITIONS = ("E", "A", "N", "S")
DOMAINS = ("speech_rate", "reply_length", "tone", "voice", "appearance", "natural_scenario")
TERMINAL = ("ready", "stopped")
_UNSET = object()


@dataclass(frozen=True)
class WorkTicket:
    task_id: str
    branch_id: str
    revision: int


@dataclass
class _Branch:
    condition: str
    state: TutorState
    branch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    revision: int = 0
    status: str = "idle"
    query: str | None = None
    request_kind: str = "initial"
    question: dict | None = None
    answers: list = field(default_factory=list)
    outcome: str | None = None
    error_code: str | None = None
    message: str = ""


class TutorComparison:
    """One task attempt with four isolated branches and gated shared rounds.

Task revisions protect task commands; branch revisions allow parallel completion
without one branch invalidating another. Work tickets bind every completion to
one attempt/branch/revision. Follow-up requests start another shared round;
a new research task uses a new comparison instance. The first reveal remains
immutable while latest_reveal gates each round's current results.
"""

    def __init__(self, *, task_code, domain="reply_length", scenario="C1", baseline=None, preferences=None):
        if not isinstance(task_code, str) or not IDENTIFIER.fullmatch(task_code):
            raise APIError(400, "invalid_task_code", "Use an anonymous task code.")
        if domain not in DOMAINS or scenario not in ("C1", "C2", "C3", "C4"):
            raise APIError(400, "invalid_task_metadata", "Unknown domain or scenario.")
        if baseline is not None and not isinstance(baseline, TutorState):
            raise APIError(400, "invalid_baseline", "Use a public TutorState baseline.")
        self.task_id = uuid.uuid4().hex
        self.task_code, self.domain, self.scenario = task_code, domain, scenario
        self._baseline = TutorState() if baseline is None else baseline.clone()
        self._baseline.capture_task_start()
        self._preferences = _preferences([] if preferences is None else preferences)
        self._branches = {c: _Branch(c, self._baseline.clone()) for c in CONDITIONS}
        self._revision = 0
        self._query = None
        self._selected = "E"
        self._first_reveal = None
        self._latest_reveal = None
        self._round_index = 0
        self._round_query = None
        self._closed = False
        self._lock = threading.RLock()
        self._shared_initial = None

    def _open(self):
        if self._closed:
            raise APIError(409, "task_closed", "This comparison is closed.")

    def _expect_task(self, revision):
        self._open()
        if type(revision) is not int or revision != self._revision:
            raise APIError(409, "stale_task_revision", "Refresh the comparison before retrying.")

    def _branch(self, condition, revision=_UNSET):
        self._open()
        if not isinstance(condition, str) or condition not in self._branches:
            raise APIError(400, "invalid_condition", "Choose E/A/N/S.")
        b = self._branches[condition]
        if revision is not _UNSET and (type(revision) is not int or revision != b.revision):
            raise APIError(409, "stale_branch_revision", "Refresh this branch before retrying.")
        return b

    def _worker(self, ticket):
        self._open()
        if not isinstance(ticket, WorkTicket) or ticket.task_id != self.task_id:
            raise APIError(409, "stale_work", "Work belongs to another task attempt.")
        b = next((b for b in self._branches.values() if b.branch_id == ticket.branch_id), None)
        if b is None or type(ticket.revision) is not int or b.revision != ticket.revision or b.status != "processing":
            raise APIError(409, "stale_work", "This branch no longer accepts that work.")
        return b

    def _advance(self, b, status):
        b.status = status
        b.revision += 1
        self._revision += 1
        return WorkTicket(self.task_id, b.branch_id, b.revision)

    def _copy_state(self, b, state):
        if not isinstance(state, TutorState):
            raise APIError(400, "invalid_branch_state", "Use a validated TutorState result.")
        result = state.clone()
        if result.snapshot()["revision"] < b.state.snapshot()["revision"]:
            raise APIError(409, "stale_state", "An older tutor state cannot replace this branch.")
        return result

    def prepare_baseline(self, patch, *, expected_revision, before_commit):
        """Replace the shared starting state before any branch receives input."""
        with self._lock:
            self._expect_task(expected_revision)
            if self._query is not None:
                raise APIError(409, "already_started", "The initial request is already fixed.")
            state = self._baseline.clone()
            state.commit(patch, expected_revision=state.snapshot()["revision"], source="direct_control")
            state.capture_task_start()
            before_commit(state.snapshot())
            self._baseline = state
            for branch in self._branches.values():
                branch.state = state.clone()
                branch.revision += 1
            self._revision += 1
            return state.clone()

    def start(self, query, *, expected_revision):
        with self._lock:
            self._expect_task(expected_revision)
            if self._query is not None:
                raise APIError(409, "already_started", "The initial request is already fixed.")
            query = text_value(query, "query", 8000)
            # Validate public model context before publishing any transition.
            build_context(query, self._baseline.snapshot(), preferences=self._preferences)
            self._query = query
            self._round_query = query
            self._round_index = 1
            for b in self._branches.values():
                b.query = query
            return {c: self._advance(b, "processing") for c, b in self._branches.items()}

    def initial_request_input(self):
        """Detached immutable baseline inputs for the shared interpreter."""
        with self._lock:
            self._open()
            if self._query is None:
                raise APIError(409, "not_started", "Submit the common request first.")
            return {"query": self._query, "snapshot": self._baseline.snapshot(),
                    "preferences": deepcopy(self._preferences)}

    def initial_model_context(self):
        """Shared public model context: no task metadata or strategy label."""
        source = self.initial_request_input()
        return build_context(source["query"], source["snapshot"], preferences=source["preferences"])

    def shared_initial(self, model):
        """One preparation owner per task; acquiring it does not call a model."""
        from tutor_shared_request import SharedInitialRequest
        with self._lock:
            self.initial_request_input()
            if self._shared_initial is None:
                self._shared_initial = SharedInitialRequest(self, model)
            elif self._shared_initial.model is not model:
                raise APIError(409, "shared_model_changed", "Do not replace the shared interpreter within a task.")
            return self._shared_initial

    def worker_input(self, ticket):
        """Server-only detached work data. Never serialize this to participants.

        The future controller must use build_context for model calls; do not send
        this orchestration envelope (condition/answers/state object) to a model.
        """
        with self._lock:
            b = self._worker(ticket)
            return {"condition": b.condition, "query": b.query, "state": b.state.clone(),
                    "preferences": deepcopy(self._preferences), "answers": deepcopy(b.answers),
                    "request_kind": b.request_kind}

    def ask(self, ticket, question, *, state=None):
        with self._lock:
            b = self._worker(ticket)
            if not isinstance(question, dict) or set(question) != {"question_id", "original_query", "text", "options"}:
                raise APIError(400, "invalid_question", "Expected only public clarification fields.")
            ident = question["question_id"]
            if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident) or any(a["question_id"] == ident for a in b.answers):
                raise APIError(400, "invalid_question", "Use a new valid question ID.")
            pending = {"question_id": ident, **_pending(question)}
            updated = b.state.clone() if state is None else self._copy_state(b, state)
            b.state, b.question, b.outcome, b.error_code = updated, pending, None, None
            self._advance(b, "awaiting_clarification")

    def answer(self, condition, question_id, response, *, expected_branch_revision):
        """Record this branch's explicit response; do not resolve intent here."""
        with self._lock:
            b = self._branch(condition, expected_branch_revision)
            if b.status != "awaiting_clarification" or question_id != b.question["question_id"]:
                raise APIError(409, "stale_question", "This clarification is no longer active.")
            if not isinstance(response, dict) or set(response) not in ({"text"}, {"option_id"}, {"option_id", "text"}):
                raise APIError(400, "invalid_answer", "Provide speech text or a displayed option.")
            response = deepcopy(response)
            if "text" in response:
                response["text"] = text_value(response["text"], "answer_text", 8000)
            if "option_id" in response:
                ident = response["option_id"]
                if ident not in [o["id"] for o in b.question["options"]] or (ident == "other") != ("text" in response):
                    raise APIError(400, "invalid_answer", "Choose a displayed option; Other needs text.")
            b.answers.append({"question_id": question_id, "question": deepcopy(b.question), "response": response})
            b.question = None
            return self._advance(b, "processing")

    def finish(self, ticket, state, *, outcome="completed", message=""):
        with self._lock:
            b = self._worker(ticket)
            if outcome not in ("completed", "cancelled", "unresolved"):
                raise APIError(400, "invalid_outcome", "Use an explicit completed, cancelled or unresolved outcome.")
            updated = self._copy_state(b, state)
            message = text_value(message, "result_message", 2000, empty=True)
            b.state, b.question, b.outcome, b.error_code = updated, None, outcome, None
            b.message = message
            self._advance(b, "ready")

    def fail(self, ticket, *, code="model_error", state=None):
        with self._lock:
            b = self._worker(ticket)
            if code not in ("model_error", "transport_error", "invalid_result", "internal_error"):
                raise APIError(400, "invalid_error_code", "Use a generic failure category, not provider output.")
            updated = b.state.clone() if state is None else self._copy_state(b, state)
            b.state, b.question, b.outcome, b.error_code = updated, None, None, code
            self._advance(b, "failed")

    def retry(self, condition, *, expected_branch_revision):
        with self._lock:
            b = self._branch(condition, expected_branch_revision)
            if b.status != "failed":
                raise APIError(409, "not_failed", "Only failed work can be retried.")
            b.error_code = None
            return self._advance(b, "processing")

    def stop_branch(self, condition, *, expected_branch_revision, state=None):
        """Explicit controller action following participant/researcher choice.

        Never call automatically on timeout. Marks incomplete, not successful.
        """
        with self._lock:
            b = self._branch(condition, expected_branch_revision)
            if b.status not in ("processing", "awaiting_clarification", "failed"):
                raise APIError(409, "cannot_stop_branch", "This branch has no outstanding work.")
            if state is not None:
                b.state = self._copy_state(b, state)
            b.question, b.outcome = None, "incomplete"
            b.message = "This branch was explicitly ended before completion."
            self._advance(b, "stopped")

    def reveal(self, *, expected_revision, before_publish=None):
        with self._lock:
            self._expect_task(expected_revision)
            if self._latest_reveal is not None or not all(b.status in TERMINAL for b in self._branches.values()):
                raise APIError(409, "reveal_not_ready", "All clarifications and work must be handled before first reveal.")
            reveal = {"round_index": self._round_index, "reveal_id": uuid.uuid4().hex, "task_revision": self._revision + 1,
                      "branches": {c: self._result(b) for c, b in self._branches.items()}}
            if before_publish is not None:
                before_publish(deepcopy(reveal))
            self._revision += 1
            if self._first_reveal is None:
                self._first_reveal = reveal
            self._latest_reveal = reveal
            return self.participant_view()

    def begin_round(self, query, *, expected_revision):
        """All branches receive the same new input; retain their independent histories."""
        with self._lock:
            self._expect_task(expected_revision)
            if self._latest_reveal is None or not all(b.status in TERMINAL for b in self._branches.values()):
                raise APIError(409, "round_not_ready", "Finish the current round before sending another shared request.")
            query = text_value(query, "query", 8000)
            for b in self._branches.values():
                build_context(query, b.state.snapshot(), preferences=self._preferences)
            self._latest_reveal = None
            self._round_query = query
            self._round_index += 1
            for b in self._branches.values():
                b.query, b.request_kind = query, "repair"
                b.question, b.outcome, b.error_code = None, None, None
                b.answers = []
            return {c: self._advance(b, "processing") for c, b in self._branches.items()}

    def begin_repair(self, condition, query, *, expected_branch_revision):
        with self._lock:
            b = self._branch(condition, expected_branch_revision)
            if self._latest_reveal is None or b.status not in TERMINAL:
                raise APIError(409, "repair_not_ready", "A new repair starts after first reveal on an idle branch.")
            query = text_value(query, "query", 8000)
            b.query = query
            b.request_kind = "repair"
            b.outcome, b.error_code = None, None
            return self._advance(b, "processing")

    def touch(self, *, expected_revision):
        """Advance task-level lifecycle/feedback metadata without changing branches."""
        with self._lock:
            self._expect_task(expected_revision)
            self._revision += 1

    def select(self, condition, *, expected_revision):
        with self._lock:
            self._expect_task(expected_revision)
            self._branch(condition)
            self._selected = condition
            self._revision += 1
            return self.participant_view()

    def close(self, *, expected_revision):
        """Exit/abort: closing never forces a reveal or successful result.

        This terminal operation is not resumable pause; pause comes later.
        """
        with self._lock:
            self._expect_task(expected_revision)
            self._closed = True
            self._revision += 1

    @staticmethod
    def _result(b):
        return {"branch_id": b.branch_id, "branch_revision": b.revision,
                "status": b.status, "outcome": b.outcome, "message": b.message, "state": b.state.snapshot()}

    def participant_view(self):
        """Only this allowlisted projection may be used by the future UI API."""
        with self._lock:
            revealed = self._latest_reveal is not None
            can_reveal = not self._closed and not revealed and all(b.status in TERMINAL for b in self._branches.values())
            phase = "closed" if self._closed else "revealed" if revealed else "awaiting_input" if self._query is None else "ready_to_reveal" if can_reveal else "clarifying" if any(b.status == "awaiting_clarification" for b in self._branches.values()) else "needs_attention" if any(b.status == "failed" for b in self._branches.values()) else "preparing"
            branches = {}
            for c, b in self._branches.items():
                visible_status = "waiting" if not revealed and b.status in TERMINAL else b.status
                branches[c] = {"branch_id": b.branch_id, "branch_revision": b.revision,
                               "status": visible_status, "question": deepcopy(b.question),
                               "error_code": b.error_code, "result": self._result(b) if revealed else None}
            return {"schema_version": SCHEMA_VERSION, "task_id": self.task_id, "task_code": self.task_code,
                    "domain": self.domain, "scenario": self.scenario, "revision": self._revision,
                    "phase": phase, "selected_condition": self._selected, "initial_query": self._query,
                    "baseline": self._baseline.snapshot(), "results_visible": revealed,
                    "can_reveal": can_reveal, "branches": branches, "first_reveal": deepcopy(self._first_reveal),
                    "latest_reveal": deepcopy(self._latest_reveal), "round_index": self._round_index, "round_query": self._round_query}
