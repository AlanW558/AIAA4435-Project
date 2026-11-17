"""One shared initial interpretation per comparison, with read-only gate plans.

Obtain via comparison.shared_initial(model). No state commits, answer generation,
HTTP routes or participant-visible results. Later repairs use branch context.
"""
from copy import deepcopy
import threading
import uuid

from core import APIError
from model import ModelError, sha
from tutor_comparison import CONDITIONS
from tutor_interpretation import TutorInterpreter, build_context
from tutor_policy import common_question, evaluate_gate


class _Memo:
    """Single-flight outcome cache. Failures require an explicit numbered retry."""
    def __init__(self):
        self.lock = threading.RLock()
        self.result = None
        self.error = None
        self.attempts = []

    def _raise_error(self):
        error = self.error
        if error["type"] == "model":
            raise ModelError(error["message"], deepcopy(error["records"]))
        raise APIError(error["status"], error["code"], error["message"])

    def run(self, callback, retry_attempt=None):
        with self.lock:
            if retry_attempt is not None:
                if type(retry_attempt) is not int or retry_attempt != len(self.attempts) or self.error is None:
                    raise APIError(409, "stale_retry", "Only the current failed attempt can be explicitly retried.")
                self.error = None
            if self.result is not None:
                return deepcopy(self.result)
            if self.error is not None:
                self._raise_error()
            try:
                result = callback()
            except ModelError as exc:
                self.error = {"type": "model", "message": str(exc), "records": deepcopy(exc.records)}
            except APIError as exc:
                self.error = {"type": "api", "status": exc.status, "code": exc.code, "message": exc.message}
            except Exception:
                # An unexpected adapter exception must not silently trigger more
                # paid calls when the other branches request the same input.
                self.error = {"type": "api", "status": 500, "code": "preparation_error",
                              "message": "Shared request preparation failed; no result was published."}
            if self.error is not None:
                self.attempts.append({"attempt": len(self.attempts) + 1, "status": "failed",
                                      "error": self.error.get("code", "model_error"),
                                      "model_calls": deepcopy(self.error.get("records", []))})
                self._raise_error()
            self.result = deepcopy(result)
            self.attempts.append({"attempt": len(self.attempts) + 1, "status": "ready",
                                  "model_calls": deepcopy(result.get("model_calls", []))})
            return deepcopy(self.result)

    def status(self):
        with self.lock:
            return {"status": "ready" if self.result is not None else "failed" if self.error is not None else "not_started",
                    "attempts": deepcopy(self.attempts)}


class SharedInitialRequest:
    """Server-only preparation owned by a single comparison task attempt.

    Inputs and gate plans must not be exposed through a UI/debug endpoint during
    the pre-reveal phase. participant_view remains the only participant view.
    """
    def __init__(self, comparison, model):
        self.comparison, self.model = comparison, model
        self._task_id = comparison.task_id
        self._source = comparison.initial_request_input()
        self._context = build_context(self._source["query"], self._source["snapshot"], preferences=self._source["preferences"])
        self._shared = _Memo()
        # Native can be slow; its lock must not hold up E/A/S decision planning.
        self._gates = {c: _Memo() for c in CONDITIONS}

    def _active(self):
        source = self.comparison.initial_request_input()
        if self.comparison.task_id != self._task_id or source != self._source:
            raise APIError(409, "shared_input_changed", "A task's initial input cannot be replaced.")

    def _scope(self, ticket):
        self._active()
        work = self.comparison.worker_input(ticket)
        if work["request_kind"] != "initial" or work["answers"] or work["query"] != self._source["query"] or work["state"].snapshot() != self._source["snapshot"]:
            raise APIError(409, "not_initial_work", "Clarification answers and later repairs require their own branch context.")
        return work["condition"]

    def _build(self):
        self._active()
        if not callable(getattr(self.model, "interpret_tutor", None)):
            raise APIError(503, "model_unavailable", "Shared interpretation needs an explicit tutor model adapter.")
        source = self._source
        result = TutorInterpreter(self.model).interpret(source["query"], source["snapshot"], preferences=source["preferences"])
        interpretation = result["interpretation"]
        proposal = interpretation["proposal"]
        question = common_question(source["query"], interpretation, self._context["settings"]) if proposal and proposal["supported"] else None
        self._active()
        return {"shared_id": uuid.uuid4().hex, "task_id": self._task_id,
                "context_sha256": sha(self._context), "question": question, **result}

    def prepare(self):
        self._active()
        result = self._shared.run(self._build)
        self._active()
        return result

    def retry_preparation(self, *, expected_attempt):
        """Only explicit retry after failure; a successful proposal is frozen."""
        self._active()
        if type(expected_attempt) is not int:
            raise APIError(400, "invalid_attempt", "Use the failed attempt number.")
        result = self._shared.run(self._build, retry_attempt=expected_attempt)
        self._active()
        return result

    def input_for(self, ticket):
        condition = self._scope(ticket)
        prepared = self.prepare()
        self._scope(ticket)
        # Shared model-call records are deliberately absent from per-branch input;
        # the future audit writer records that call once under shared_id.
        return {"condition": condition, "branch_id": ticket.branch_id,
                **{k: prepared[k] for k in ("task_id", "shared_id", "context_sha256", "version",
                                            "based_on_revision", "query", "interpretation", "question")}}

    def _decision(self, ticket, retry_attempt=None):
        branch_input = self.input_for(ticket)
        condition = branch_input["condition"]
        def calculate():
            return evaluate_gate(self.model, condition, self._context, branch_input["interpretation"], branch_input["question"])
        decision = self._gates[condition].run(calculate, retry_attempt=retry_attempt)
        self._scope(ticket)
        return {"input": branch_input, "gate": decision}

    def decision_for(self, ticket):
        """Read-only plan; ASK/ACT here does not change or reveal branch state."""
        return self._decision(ticket)

    def retry_decision(self, ticket, *, expected_attempt):
        if type(expected_attempt) is not int:
            raise APIError(400, "invalid_attempt", "Use the failed gate attempt number.")
        return self._decision(ticket, retry_attempt=expected_attempt)

    def status(self):
        """Server-only audit state; not a participant projection."""
        self._active()
        return {"task_id": self._task_id, "interpretation": self._shared.status(),
                "gates": {c: self._gates[c].status() for c in CONDITIONS}}

    def preparation_status(self):
        return self._shared.status()

    def decision_status(self, condition):
        if condition not in CONDITIONS:
            raise APIError(400, "invalid_condition", "Choose E/A/N/S.")
        return self._gates[condition].status()
