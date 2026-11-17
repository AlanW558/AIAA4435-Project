"""Comparison isolation and first-reveal invariants. No HTTP/models/Unity calls."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_state import TutorState


def question(ident="q1"):
    return {"question_id": ident, "original_query": "Change the reply structure.",
            "text": "Use only key points?", "options": [
                {"id": "c1", "label": "Key points"}, {"id": "other", "label": "Something else"},
                {"id": "cancel", "label": "Cancel"}]}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        baseline = TutorState()
        baseline.commit({"tone": "friendly"}, expected_revision=0, source="direct_control")
        baseline.record_exchange("Public earlier question", "Public earlier answer", expected_revision=1)
        self.baseline = baseline
        self.task = TutorComparison(task_code="LENGTH_C1_01", baseline=baseline,
                                    preferences=[{"field": "tone", "value": "friendly"}])
        self.tickets = self.task.start("Change the reply structure.", expected_revision=0)

    def view(self):
        return self.task.participant_view()

    def revision(self, condition=None):
        v = self.view()
        return v["revision"] if condition is None else v["branches"][condition]["branch_revision"]

    def edited(self, ticket, length="brief"):
        state = self.task.worker_input(ticket)["state"]
        state.commit({"reply_length": length}, expected_revision=state.snapshot()["revision"], source="request", query="HIDDEN_CHANGE")
        state.record_exchange("HIDDEN_QUESTION", "HIDDEN_ANSWER", expected_revision=state.snapshot()["revision"])
        return state

    def finish(self, condition):
        self.task.finish(self.tickets[condition], self.edited(self.tickets[condition]))

    def reveal(self):
        return self.task.reveal(expected_revision=self.revision())

    def answer(self, condition="A", response=None, ident="q1"):
        return self.task.answer(condition, ident, response or {"text": "Only key points please."}, expected_branch_revision=self.revision(condition))

    def test_shared_baseline_and_context_are_detached_and_have_no_policy_metadata(self):
        context = self.task.initial_model_context()
        self.assertEqual(context["settings"]["tone"], "friendly")
        self.assertEqual(len(context["conversation"]), 1)
        self.assertTrue({"task_id", "task_code", "condition", "domain", "scenario", "task_goal", "scores"}.isdisjoint(context))
        self.baseline.commit({"tone": "professional"}, expected_revision=2, source="direct_control")
        for c in CONDITIONS:
            work = self.task.worker_input(self.tickets[c])
            self.assertEqual(work["state"].snapshot()["settings"]["tone"], "friendly")
            self.assertEqual(work["state"].snapshot(), self.view()["baseline"])
        context["settings"]["tone"] = "professional"
        self.assertEqual(self.task.initial_model_context()["settings"]["tone"], "friendly")

    def test_early_complete_result_never_leaks_in_participant_view(self):
        self.finish("E")
        self.task.ask(self.tickets["A"], question())
        v = self.view()
        self.assertEqual(v["phase"], "clarifying")
        self.assertEqual(v["branches"]["E"]["status"], "waiting")
        self.assertNotIn("HIDDEN_", json.dumps(v))
        self.assertTrue(all(b["result"] is None for b in v["branches"].values()))
        self.assertEqual(v["baseline"]["settings"]["reply_length"], "balanced")
        self.assertEqual(v["branches"]["A"]["question"]["question_id"], "q1")
        with self.assertRaises(APIError): self.reveal()

    def test_answer_does_not_reveal_until_resolution_and_generation_finish(self):
        for c in ("E", "N", "S"): self.finish(c)
        self.task.ask(self.tickets["A"], question())
        ticket = self.answer()
        self.assertFalse(self.view()["can_reveal"])
        with self.assertRaises(APIError): self.reveal()
        self.task.finish(ticket, self.edited(ticket))
        self.assertTrue(self.view()["can_reveal"])
        self.assertNotIn("HIDDEN_", json.dumps(self.view()))
        v = self.reveal()
        self.assertTrue(v["results_visible"])
        self.assertEqual(v["phase"], "revealed")
        self.assertTrue(all(b["result"]["state"]["settings"]["reply_length"] == "brief" for b in v["branches"].values()))

    def test_each_pending_branch_must_be_resolved(self):
        self.finish("E"); self.finish("N")
        for c in ("A", "S"): self.task.ask(self.tickets[c], question())
        t = self.answer("A")
        self.task.finish(t, self.edited(t))
        self.assertFalse(self.view()["can_reveal"])
        self.assertEqual(self.view()["branches"]["S"]["status"], "awaiting_clarification")

    def test_answers_are_isolated_and_copies_cannot_change_live_state(self):
        for c in ("A", "S"): self.task.ask(self.tickets[c], question())
        a = self.answer("A", {"text": "A_ONLY_REPLY"})
        s = self.answer("S", {"option_id": "cancel"})
        a_work = self.task.worker_input(a)
        self.assertNotIn("A_ONLY_REPLY", json.dumps(self.task.worker_input(s)["answers"]))
        a_work["answers"].clear()
        a_work["preferences"].clear()
        self.assertEqual(len(self.task.worker_input(a)["answers"]), 1)
        self.assertEqual(len(self.task.worker_input(a)["preferences"]), 1)

    def test_invalid_answer_and_wrong_question_are_atomic(self):
        self.task.ask(self.tickets["A"], question())
        for response in ({"option_id": "missing"}, {"text": ""}, {"option_id": "other"},
                         {"option_id": "c1", "text": "extra"}, {"text": "ok", "private_goal": "x"}):
            before = self.view()
            with self.assertRaises(APIError): self.answer(response=response)
            self.assertEqual(self.view(), before)
        with self.assertRaises(APIError): self.answer(ident="wrong")
        ticket = self.answer(response={"option_id": "other", "text": "My own wording"})
        self.assertEqual(self.task.worker_input(ticket)["answers"][0]["response"]["text"], "My own wording")

    def test_repeated_clarification_keeps_the_barrier_closed(self):
        for c in ("E", "N", "S"): self.finish(c)
        self.task.ask(self.tickets["A"], question())
        ticket = self.answer()
        with self.assertRaises(APIError): self.task.ask(ticket, question())
        self.task.ask(ticket, question("q2"))
        self.assertFalse(self.view()["can_reveal"])
        with self.assertRaises(APIError): self.answer(ident="q1")

    def test_failure_blocks_reveal_until_explicit_retry_or_stop(self):
        for c in ("E", "A", "S"): self.finish(c)
        self.task.fail(self.tickets["N"])
        self.assertEqual(self.view()["phase"], "needs_attention")
        with self.assertRaises(APIError): self.reveal()
        self.task.stop_branch("N", expected_branch_revision=self.revision("N"))
        v = self.reveal()
        self.assertEqual(v["branches"]["N"]["result"]["outcome"], "incomplete")
        self.assertEqual(v["branches"]["N"]["result"]["state"]["settings"]["reply_length"], "balanced")

    def test_retry_issues_new_ticket_and_obsolete_completion_is_rejected(self):
        old_state = self.edited(self.tickets["E"])
        self.task.fail(self.tickets["E"])
        new = self.task.retry("E", expected_branch_revision=self.revision("E"))
        with self.assertRaises(APIError): self.task.finish(self.tickets["E"], old_state)
        self.task.finish(new, self.edited(new))
        self.assertEqual(self.view()["branches"]["E"]["status"], "waiting")

    def test_stop_invalidates_inflight_work_and_pending_question(self):
        old_state = self.edited(self.tickets["E"])
        self.task.stop_branch("E", expected_branch_revision=self.revision("E"))
        with self.assertRaises(APIError): self.task.finish(self.tickets["E"], old_state)
        self.task.ask(self.tickets["A"], question())
        self.task.stop_branch("A", expected_branch_revision=self.revision("A"))
        self.assertIsNone(self.view()["branches"]["A"]["question"])
        with self.assertRaises(APIError): self.answer()

    def test_cancelled_and_unresolved_are_explicit_not_fake_success(self):
        self.finish("E"); self.finish("S")
        self.task.ask(self.tickets["A"], question())
        ticket = self.answer(response={"option_id": "cancel"})
        self.task.finish(ticket, self.task.worker_input(ticket)["state"], outcome="cancelled")
        self.task.finish(self.tickets["N"], self.task.worker_input(self.tickets["N"])["state"], outcome="unresolved")
        v = self.reveal()
        self.assertEqual(v["branches"]["A"]["result"]["outcome"], "cancelled")
        self.assertEqual(v["branches"]["N"]["result"]["outcome"], "unresolved")

    def test_switching_branches_changes_only_selection(self):
        self.finish("E")
        before = self.view()
        after = self.task.select("S", expected_revision=before["revision"])
        self.assertEqual(before["branches"], after["branches"])
        self.assertFalse(after["results_visible"])
        self.assertEqual(after["selected_condition"], "S")

    def test_first_reveal_is_immutable_after_branch_repair(self):
        for c in CONDITIONS: self.finish(c)
        initial = self.reveal()["first_reveal"]
        ticket = self.task.begin_repair("E", "Explain in more detail.", expected_branch_revision=self.revision("E"))
        self.assertEqual(self.task.worker_input(ticket)["query"], "Explain in more detail.")
        self.assertEqual(self.task.initial_model_context()["query"], "Change the reply structure.")
        self.task.finish(ticket, self.edited(ticket, "detailed"))
        v = self.view()
        self.assertEqual(v["first_reveal"], initial)
        self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["reply_length"], "detailed")
        self.assertEqual(v["branches"]["A"]["result"]["state"]["settings"]["reply_length"], "brief")
        v["first_reveal"]["branches"].clear()
        self.assertEqual(self.view()["first_reveal"], initial)
        with self.assertRaises(APIError): self.reveal()

    def test_repairs_are_not_allowed_before_first_reveal(self):
        self.finish("E")
        with self.assertRaises(APIError): self.task.begin_repair("E", "New repair", expected_branch_revision=self.revision("E"))

    def test_new_task_attempt_rejects_previous_work_and_starts_clean(self):
        other = TutorComparison(task_code="LENGTH_C1_01")
        other.start("Same question", expected_revision=0)
        self.assertNotEqual(other.task_id, self.task.task_id)
        with self.assertRaises(APIError): other.finish(self.tickets["E"], self.edited(self.tickets["E"]))
        self.assertEqual(other.participant_view()["baseline"]["conversation"], [])

    def test_close_before_reveal_keeps_results_hidden_and_rejects_work(self):
        state = self.edited(self.tickets["A"])
        self.finish("E")
        self.task.close(expected_revision=self.revision())
        self.assertEqual(self.view()["phase"], "closed")
        self.assertNotIn("HIDDEN_", json.dumps(self.view()))
        with self.assertRaises(APIError): self.task.finish(self.tickets["A"], state)
        with self.assertRaises(APIError): self.reveal()

    def test_parallel_completions_do_not_invalidate_other_branches(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(self.finish, CONDITIONS))
        self.assertTrue(self.view()["can_reveal"])
        self.assertTrue(self.reveal()["results_visible"])

    def test_duplicate_completion_can_only_publish_once(self):
        ticket = self.tickets["E"]
        state = self.edited(ticket)
        def complete(_):
            try:
                self.task.finish(ticket, state)
                return "published"
            except APIError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(complete, (0, 1)))
        self.assertCountEqual(result, ["published", "stale_work"])

    def test_invalid_revisions_are_not_optional(self):
        self.task.ask(self.tickets["A"], question())
        for rev in (None, True, "2", -1):
            with self.assertRaises(APIError): self.task.answer("A", "q1", {"option_id": "c1"}, expected_branch_revision=rev)
            with self.assertRaises(APIError): self.task.select("E", expected_revision=rev)

    def test_invalid_updates_leave_no_partial_state(self):
        for operation in (
            lambda: self.task.ask(self.tickets["E"], {**question(), "hidden_result": "x"}),
            lambda: self.task.finish(self.tickets["E"], TutorState()),
            lambda: self.task.finish(self.tickets["E"], self.edited(self.tickets["E"]), outcome="failed"),
            lambda: self.task.fail(self.tickets["E"], code="HIDDEN_PROVIDER_OUTPUT"),
            lambda: self.task.start("Another input", expected_revision=self.revision()),
        ):
            before = self.view()
            with self.assertRaises(APIError): operation()
            self.assertEqual(self.view(), before)

    def test_constructor_does_not_accept_private_goal_or_survey_fields(self):
        with self.assertRaises(TypeError): TutorComparison(task_code="TEST", private_goal="brief")
        with self.assertRaises(TypeError): TutorComparison(task_code="TEST", scores=[7])
        with self.assertRaises(APIError): TutorComparison(task_code="TEST", baseline={"settings": {}})


if __name__ == "__main__":
    unittest.main()
