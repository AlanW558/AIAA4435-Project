"""Shared interpretation fairness, lifetime and retry contracts; no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import ModelError
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_policy import common_question
from tutor_session import TutorSessions
from tutor_state import TutorState
from test_tutor_session import FixtureModel, chat
from test_tutor_interpretation import tailoring


class SharedRequestTests(unittest.TestCase):
    def setUp(self):
        self.model = FixtureModel()
        self.task = TutorComparison(task_code="PRIVATE_TASK_CODE", scenario="C3")
        self.query = "Please adjust the reply structure."
        self.tickets = self.task.start(self.query, expected_revision=0)
        self.shared = self.task.shared_initial(self.model)

    def plans(self):
        return {c: self.shared.decision_for(self.tickets[c]) for c in CONDITIONS}

    def test_one_interpretation_and_one_common_question_for_all_four_inputs(self):
        self.model.raw = tailoring("brief", "detailed")
        self.model.native = {"decision": "ASK", "reason": "Fixture choice"}
        before = self.task.participant_view()
        with patch("tutor_shared_request.common_question", wraps=common_question) as make_question:
            plans = self.plans()
            self.assertEqual(make_question.call_count, 1)
        inputs = [{k: v for k, v in p["input"].items() if k not in ("condition", "branch_id")} for p in plans.values()]
        self.assertTrue(all(value == inputs[0] for value in inputs))
        self.assertEqual([plans[c]["gate"]["decision"] for c in CONDITIONS], ["ACT", "ASK", "ASK", "ASK"])
        self.assertEqual(self.model.calls, ["interpret", "native"])
        self.assertEqual(self.task.participant_view(), before)

    def test_preparation_owner_and_successful_outcome_are_reused(self):
        first = self.shared.prepare()
        self.assertIs(self.task.shared_initial(self.model), self.shared)
        self.assertEqual(first, self.task.shared_initial(self.model).prepare())
        with self.assertRaises(APIError): self.task.shared_initial(FixtureModel())
        with self.assertRaises(APIError): self.shared.retry_preparation(expected_attempt=1)
        self.assertEqual(self.model.calls, ["interpret"])

    def test_parallel_branches_and_duplicate_native_requests_only_call_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            plans = list(pool.map(lambda c: self.shared.decision_for(self.tickets[c]), [*CONDITIONS, "N", "N", "E", "S"]))
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("native"), 1)
        self.assertEqual(len({p["input"]["shared_id"] for p in plans}), 1)

    def test_shared_records_are_not_duplicated_into_branch_inputs(self):
        plans = self.plans()
        self.assertEqual(len(self.shared.prepare()["model_calls"]), 1)
        for c, p in plans.items():
            self.assertNotIn("model_calls", p["input"])
            self.assertEqual(len(p["gate"]["model_calls"]), int(c == "N"))
        self.assertEqual(len(self.shared.status()["interpretation"]["attempts"]), 1)

    def test_callers_and_native_adapter_cannot_mutate_shared_data(self):
        original = self.shared.prepare()
        edited = self.shared.input_for(self.tickets["E"])
        edited["interpretation"]["proposal"]["default_id"] = "invented"
        edited["question"]["options"].clear()
        def mutate(context):
            context["interpretation"]["proposal"]["candidates"].clear()
            context["settings"]["tone"] = "friendly"
            return {"decision": "ACT", "reason": "Fixture"}, []
        self.model.decide_tutor = mutate
        self.shared.decision_for(self.tickets["N"])
        self.assertEqual(self.shared.prepare(), original)
        status = self.shared.status(); status["interpretation"]["attempts"].clear()
        self.assertEqual(len(self.shared.status()["interpretation"]["attempts"]), 1)

    def test_model_inputs_exclude_task_identity_strategy_and_extra_privileges(self):
        self.plans()
        interpretation, native = self.model.contexts
        self.assertEqual(set(native), set(interpretation) | {"interpretation", "question"})
        for context in (interpretation, native):
            encoded = json.dumps(context)
            self.assertNotIn("PRIVATE_TASK_CODE", encoded)
            self.assertNotIn(self.task.task_id, encoded)
            self.assertTrue({"condition", "scenario", "task_goal", "scores", "policy_version"}.isdisjoint(context))
        self.assertEqual(native["interpretation"], self.shared.prepare()["interpretation"])

    def test_preparation_and_decisions_never_publish_hidden_outputs(self):
        self.model.raw["proposal"]["reason"] = "HIDDEN_INTERPRETATION_MARKER"
        self.plans()
        view = self.task.participant_view()
        self.assertNotIn("HIDDEN_INTERPRETATION_MARKER", json.dumps(view))
        self.assertFalse(view["results_visible"])
        self.assertTrue(all(b["question"] is None and b["result"] is None for b in view["branches"].values()))

    def test_chat_bypasses_every_gate_including_native(self):
        self.model.raw = chat()
        plans = self.plans()
        self.assertTrue(all(p["gate"]["decision"] == "CHAT_QUEUED" for p in plans.values()))
        self.assertTrue(all(p["input"]["question"] is None for p in plans.values()))
        self.assertEqual(self.shared.prepare()["interpretation"]["conversation_query"], self.query)
        self.assertEqual(self.model.calls, ["interpret"])

    def test_mixed_single_turn_scope_and_learning_question_survive_sharing(self):
        self.model.raw = tailoring("brief", kind="mixed", scope="turn", conversation_query="What is recall?")
        for p in self.plans().values():
            self.assertEqual(p["input"]["interpretation"]["scope"], "turn")
            self.assertEqual(p["input"]["interpretation"]["conversation_query"], "What is recall?")
            self.assertIn("next answer only", p["input"]["question"]["text"])
        self.assertEqual(self.task.participant_view()["baseline"]["settings"]["reply_length"], "balanced")

    def test_unsupported_and_cross_attribute_requests_stay_unresolved(self):
        self.model.raw = tailoring(requested_fields=["reply_length", "voice"])
        plans = self.plans()
        self.assertTrue(all(p["gate"]["decision"] == "UNRESOLVED" for p in plans.values()))
        self.assertEqual(self.model.calls, ["interpret"])
        self.assertTrue(all(p["input"]["question"] is None for p in plans.values()))

    def test_candidate_deduplication_and_default_mapping_are_shared(self):
        self.model.raw = tailoring("brief", "brief", "detailed")
        self.model.raw["proposal"]["default_id"] = "c2"
        for p in self.plans().values():
            proposal = p["input"]["interpretation"]["proposal"]
            self.assertEqual(proposal["default_id"], "c1")
            self.assertEqual(len(proposal["candidates"]), 2)
        self.assertEqual(self.model.calls.count("interpret"), 1)

    def test_public_history_and_preferences_are_the_same_input_to_each_gate(self):
        baseline = TutorState()
        baseline.commit({"tone": "friendly"}, expected_revision=0, source="direct_control")
        baseline.record_exchange("Earlier public question", "Earlier public answer", expected_revision=1)
        task = TutorComparison(task_code="HISTORY", baseline=baseline,
                               preferences=[{"field": "reply_length", "value": "detailed"}])
        tickets = task.start("Only key points please", expected_revision=0)
        self.model.raw["proposal"]["possible_soft_preference_overrides"] = ["Existing preference for detail"]
        shared = task.shared_initial(self.model)
        plans = {c: shared.decision_for(tickets[c]) for c in CONDITIONS}
        self.assertEqual(plans["S"]["gate"]["reason"], "R2_SOFT_PREFERENCE")
        self.assertEqual(plans["E"]["gate"]["decision"], "ACT")
        interpreter, native = self.model.contexts
        for field in ("settings", "change_history", "conversation", "soft_preferences"):
            self.assertEqual(interpreter[field], native[field])
        self.assertEqual(interpreter["conversation"][0]["messages"][1]["content"], "Earlier public answer")
        self.assertEqual(shared.prepare()["based_on_revision"], 2)

    def test_concurrent_explicit_retry_of_same_failure_runs_only_once(self):
        self.model.raw = ModelError("Fixture failure")
        with self.assertRaises(ModelError): self.shared.prepare()
        self.model.raw = tailoring("brief")
        def retry(_):
            try:
                self.shared.retry_preparation(expected_attempt=1)
                return "ready"
            except APIError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(retry, (0, 1)))
        self.assertCountEqual(result, ["ready", "stale_retry"])
        self.assertEqual(self.model.calls, ["interpret", "interpret"])

    def test_failed_shared_call_is_cached_until_explicit_retry(self):
        self.model.raw = ModelError("Fixture outage", [{"status": "error", "role": "interpret"}])
        for c in CONDITIONS:
            with self.assertRaises(ModelError): self.shared.input_for(self.tickets[c])
        self.assertEqual(self.model.calls, ["interpret"])
        self.assertEqual(self.shared.status()["interpretation"]["status"], "failed")
        self.model.raw = tailoring("detailed")
        with self.assertRaises(ModelError): self.shared.prepare()
        with self.assertRaises(APIError): self.shared.retry_preparation(expected_attempt=0)
        self.shared.retry_preparation(expected_attempt=1)
        self.plans()
        self.assertEqual(self.model.calls, ["interpret", "interpret", "native"])
        self.assertEqual([a["status"] for a in self.shared.status()["interpretation"]["attempts"]], ["failed", "ready"])

    def test_malformed_interpretation_is_not_reinterpreted_for_each_branch(self):
        self.model.raw = {"kind": "invented"}
        for c in CONDITIONS:
            with self.assertRaises(ModelError) as failure: self.shared.input_for(self.tickets[c])
            self.assertEqual(len(failure.exception.records), 1)
        self.assertEqual(self.model.calls, ["interpret"])
        self.assertFalse(self.task.participant_view()["can_reveal"])

    def test_unexpected_adapter_failure_does_not_repeat_calls(self):
        calls = []
        def broken(context):
            calls.append(context)
            raise RuntimeError("Private transport detail")
        self.model.interpret_tutor = broken
        for c in CONDITIONS:
            with self.assertRaises(APIError) as failure: self.shared.input_for(self.tickets[c])
            self.assertNotIn("Private transport detail", str(failure.exception))
        self.assertEqual(len(calls), 1)

    def test_native_failure_does_not_block_other_gates_or_change_candidates(self):
        self.model.native = ModelError("Native outage")
        before = self.shared.prepare()
        with self.assertRaises(ModelError): self.shared.decision_for(self.tickets["N"])
        for c, expected in (("E", "ACT"), ("A", "ASK"), ("S", "ACT")):
            self.assertEqual(self.shared.decision_for(self.tickets[c])["gate"]["decision"], expected)
        with self.assertRaises(ModelError): self.shared.decision_for(self.tickets["N"])
        self.model.native = {"decision": "ASK", "reason": "Recovered"}
        self.assertEqual(self.shared.retry_decision(self.tickets["N"], expected_attempt=1)["gate"]["decision"], "ASK")
        self.assertEqual(self.shared.prepare(), before)
        self.assertEqual(self.model.calls, ["interpret", "native", "native"])

    def test_native_cannot_supply_patch_or_rewrite_common_inputs(self):
        self.model.native = {"decision": "ACT", "reason": "Fixture", "patch": {"reply_length": "detailed"}}
        with self.assertRaises(ModelError): self.shared.decision_for(self.tickets["N"])
        self.assertEqual(self.shared.input_for(self.tickets["E"])["interpretation"]["proposal"]["candidates"][0]["patch"], {"reply_length": "brief"})

    def test_blocked_native_does_not_hold_comparison_or_other_gate_locks(self):
        entered, release = threading.Event(), threading.Event()
        def slow(context):
            entered.set()
            if not release.wait(5): raise RuntimeError("Test release timed out")
            return {"decision": "ACT", "reason": "Fixture"}, []
        self.model.decide_tutor = slow
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(self.shared.decision_for, self.tickets["N"])
            try:
                self.assertTrue(entered.wait(3))
                e = pool.submit(self.shared.decision_for, self.tickets["E"])
                self.assertEqual(e.result(timeout=2)["gate"]["decision"], "ACT")
                self.assertFalse(self.task.participant_view()["results_visible"])
            finally:
                release.set()
            future.result(timeout=3)

    def test_task_closed_during_interpretation_cannot_publish_result(self):
        entered, release = threading.Event(), threading.Event()
        original = self.model.interpret_tutor
        def slow(context):
            entered.set(); release.wait(5)
            return original(context)
        self.model.interpret_tutor = slow
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.shared.prepare)
            try:
                self.assertTrue(entered.wait(3))
                self.task.close(expected_revision=self.task.participant_view()["revision"])
            finally:
                release.set()
            with self.assertRaises(APIError): future.result(timeout=3)
        with self.assertRaises(APIError): self.shared.prepare()
        self.assertFalse(self.task.participant_view()["results_visible"])

    def test_branch_stopped_during_preparation_rejects_its_plan_but_keeps_common_input(self):
        entered, release = threading.Event(), threading.Event()
        original = self.model.interpret_tutor
        def slow(context):
            entered.set(); release.wait(5)
            return original(context)
        self.model.interpret_tutor = slow
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.shared.input_for, self.tickets["E"])
            try:
                self.assertTrue(entered.wait(3))
                self.task.stop_branch("E", expected_branch_revision=1)
            finally:
                release.set()
            with self.assertRaises(APIError): future.result(timeout=3)
        self.shared.input_for(self.tickets["A"])
        self.assertEqual(self.model.calls, ["interpret"])

    def test_clarification_and_identical_worded_repairs_cannot_reuse_initial_path(self):
        prepared = self.shared.prepare()
        self.task.ask(self.tickets["A"], {"question_id": "q1", **prepared["question"]})
        ticket = self.task.answer("A", "q1", {"option_id": "c1"}, expected_branch_revision=2)
        with self.assertRaises(APIError): self.shared.decision_for(ticket)
        self.task.finish(ticket, self.task.worker_input(ticket)["state"])
        for c in ("E", "N", "S"):
            self.task.finish(self.tickets[c], self.task.worker_input(self.tickets[c])["state"])
        self.task.reveal(expected_revision=self.task.participant_view()["revision"])
        revision = self.task.participant_view()["branches"]["E"]["branch_revision"]
        repair = self.task.begin_repair("E", self.query, expected_branch_revision=revision)
        with self.assertRaises(APIError): self.shared.input_for(repair)
        self.assertEqual(self.model.calls, ["interpret"])

    def test_identical_input_in_another_task_has_its_own_interpretation(self):
        other = TutorComparison(task_code="PRIVATE_TASK_CODE")
        tickets = other.start(self.query, expected_revision=0)
        with self.assertRaises(APIError): self.shared.input_for(tickets["E"])
        a = self.shared.prepare()
        b = other.shared_initial(self.model).prepare()
        self.assertNotEqual(a["shared_id"], b["shared_id"])
        self.assertEqual(self.model.calls, ["interpret", "interpret"])

    def test_single_session_and_shared_pipeline_use_the_same_gate_rules(self):
        self.model.raw = tailoring("brief", "detailed")
        self.model.native = {"decision": "UNRESOLVED", "reason": "Fixture native judgment"}
        shared = self.plans()
        with tempfile.TemporaryDirectory() as logs:
            sessions = TutorSessions(self.model, logs)
            for c in CONDITIONS:
                v = sessions.create({"condition": c})
                v = sessions.mutate(v["session_id"], "request", {"request_id": "same", "expected_revision": 0, "query": self.query})
                self.assertEqual(v["decision"], shared[c]["gate"]["decision"])
                if v["question"]:
                    q = deepcopy(v["question"]); q.pop("question_id")
                    self.assertEqual(q, shared[c]["input"]["question"])


if __name__ == "__main__":
    unittest.main()
