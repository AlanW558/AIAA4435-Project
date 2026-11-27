"""Malformed qualitative rate suggestions recover by asking, never by rounding.

All model responses are explicit fixtures. These tests exercise the shared and
single-session controllers without provider calls or rewriting study results.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import ModelError
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_comparison_service import TutorComparisons
from tutor_interpretation import build_context, normalize_interpretation
from tutor_policy import common_question, evaluate_gate, selective_decision
from tutor_session import TutorSessions
from tutor_state import DEFAULT_SETTINGS, FIELDS, TutorState
from test_tutor_generation import GenerationFixture, parts
from test_tutor_interpretation import answer
from test_tutor_multidomain import proposal
from test_tutor_session import FixtureModel


QUERY = "I want a different feel to the way you speak."
BASELINE = {**DEFAULT_SETTINGS, "speech_rate": 1.15, "voice": "voice_a"}
INVALID_RATE = {"basis": "current", "operation": "multiply", "value": .95}


def uncertain(*patches, query=QUERY, **kwargs):
    raw = proposal(*patches, required=[], **kwargs)
    raw["proposal"]["ambiguities"] = [
        {"kind": "dimension", "fields": ["tone", "voice", "speech_rate"], "evidence": query}]
    return raw


def voice_resolution():
    return proposal({"voice": "voice_e"}, preserved=[f for f in FIELDS if f != "voice"])


class CandidateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.state = TutorState(BASELINE)

    def normalize(self, raw, query=QUERY):
        return normalize_interpretation(raw, build_context(query, self.state.snapshot()))

    def test_invalid_rate_alternative_does_not_erase_valid_voice_or_tone_choices(self):
        raw = uncertain({"tone": "friendly"}, {"voice": "voice_e"}, {"speech_rate": INVALID_RATE})
        raw["proposal"]["default_id"] = "c3"
        original = deepcopy(raw)
        result = self.normalize(raw)
        p = result["proposal"]
        self.assertTrue(p["supported"])
        self.assertEqual([c["patch"] for c in p["candidates"]], [{"tone": "friendly"}, {"voice": "voice_e"}])
        self.assertEqual(p["ambiguities"], raw["proposal"]["ambiguities"])
        self.assertEqual(p["default_id"], "")
        self.assertEqual(p["candidate_recovery"]["rejected_candidates"][0]["id"], "c3")
        self.assertEqual(raw, original)
        self.assertEqual(self.state.snapshot()["settings"], BASELINE)
        model = FixtureModel()
        context = build_context(QUERY, self.state.snapshot())
        question = common_question(QUERY, result, BASELINE)
        for condition in CONDITIONS:
            self.assertEqual(evaluate_gate(model, condition, context, result, question)["decision"], "ASK")
        self.assertEqual(model.calls, [])
        self.assertNotIn("1.0925", json.dumps(question))

    def test_all_invalid_candidates_give_an_open_question_without_invented_defaults(self):
        raw = uncertain({"speech_rate": INVALID_RATE}, {"speech_rate": 1.0925})
        result = self.normalize(raw)
        self.assertEqual(result["proposal"]["candidates"], [])
        self.assertEqual(result["proposal"]["default_id"], "")
        self.assertEqual(selective_decision(result["proposal"], BASELINE, [])[0], "ASK")
        question = common_question(QUERY, result, BASELINE)
        self.assertEqual([o["id"] for o in question["options"]], ["other", "cancel"])
        self.assertIn("Please explain", question["text"])
        self.assertIn("0.70–1.30", question["text"])
        # Same public pending validator is used by session and comparison paths.
        context = build_context("Use the other male voice.", self.state.snapshot(), pending=question,
                                answering_pending_question=True)
        self.assertEqual(context["pending"], question)

    def test_valid_default_is_preserved_but_never_auto_executed_after_filtering(self):
        raw = uncertain({"tone": "friendly"}, {"speech_rate": 1.0925})
        result = self.normalize(raw)
        self.assertEqual(result["proposal"]["default_id"], "c1")
        self.assertEqual(selective_decision(result["proposal"], BASELINE, [])[0], "ASK")
        self.assertEqual(len(result["proposal"]["candidates"]), 1)

    def test_cross_attribute_alternatives_recover_even_when_model_omits_ambiguities(self):
        raw = proposal({"speech_rate": INVALID_RATE}, {"tone": "friendly"}, required=[])
        result = self.normalize(raw)
        self.assertTrue(result["proposal"]["supported"])
        self.assertEqual(result["proposal"]["ambiguities"], [])
        self.assertEqual(result["proposal"]["candidates"][0]["patch"], {"tone": "friendly"})
        question = common_question(QUERY, result, BASELINE)
        self.assertIn("What would you like to change", question["text"])
        self.assertIn("Speech rate, Tone", question["text"])
        context = build_context(QUERY, self.state.snapshot())
        for c in CONDITIONS:
            self.assertEqual(evaluate_gate(FixtureModel(), c, context, result, question)["decision"], "ASK")

    def test_all_invalid_without_public_uncertainty_stays_conservatively_unresolved(self):
        raw = proposal({"speech_rate": INVALID_RATE}, {"speech_rate": 1.0925}, required=[])
        result = self.normalize(raw)
        self.assertFalse(result["proposal"]["supported"])
        self.assertEqual(result["proposal"]["candidates"], [])
        self.assertNotIn("candidate_recovery", result["proposal"])

    def test_invalid_conjunctive_candidate_is_removed_whole_not_partially_applied(self):
        query = "Make the delivery slower and friendlier."
        raw = uncertain({"tone": "friendly", "speech_rate": 1.0925},
                        {"tone": "friendly", "speech_rate": .9}, query=query)
        raw["required_fields"] = ["tone", "speech_rate"]
        result = self.normalize(raw, query)
        self.assertEqual(result["required_fields"], ["tone", "speech_rate"])
        self.assertEqual(result["proposal"]["candidates"], [
            {"id": "c2", "patch": {"speech_rate": .9, "tone": "friendly"},
             "evidence": "Public fixture request/history."}])

    def test_explicit_unsupported_arithmetic_or_precision_is_not_recovered_or_rounded(self):
        cases = [
            ("Use 1.0925 times the default speed.", 1.0925),
            ("Use one point zero nine two five times the default speed.", 1.0925),
            ("Make it five percent slower than now.", INVALID_RATE),
            ("Make it half the current speed.", {"basis": "current", "operation": "multiply", "value": .5}),
            ("Use 1.50 times default speed.", 1.5),
            ("Use seventy-seven point seven percent of default speed.", .777),
        ]
        for query, value in cases:
            with self.subTest(query=query):
                # Even erroneous ambiguity metadata cannot turn explicit numeric
                # instructions into permission to choose another valid candidate.
                raw = uncertain({"speech_rate": value}, {"speech_rate": .9}, query=query)
                result = self.normalize(raw, query)
                self.assertFalse(result["proposal"]["supported"])
                self.assertEqual(result["proposal"]["candidates"], [])
                self.assertNotIn("candidate_recovery", result["proposal"])
                for c in CONDITIONS:
                    self.assertEqual(evaluate_gate(FixtureModel(), c, build_context(query, self.state.snapshot()), result, None)["decision"], "UNRESOLVED")
        self.assertEqual(self.state.snapshot()["settings"], BASELINE)

    def test_absent_public_uncertainty_and_unrelated_schema_errors_still_fail_closed(self):
        result = self.normalize(proposal({"speech_rate": 1.0925}))
        self.assertFalse(result["proposal"]["supported"])
        for patch in ({"speech_rate": "slow"}, {"voice": "invented_voice"}, {"tone": "angry"}):
            with self.subTest(patch=patch), self.assertRaises(ModelError):
                self.normalize(uncertain(patch))
        raw = uncertain({"speech_rate": 1.0925})
        raw["proposal"]["candidate_recovery"] = {"reason": "invented"}
        with self.assertRaises(ModelError): self.normalize(raw)

    def test_shared_interpretation_keeps_common_choices_without_private_task_data(self):
        model = FixtureModel()
        model.raw = uncertain({"tone": "friendly"}, {"speech_rate": INVALID_RATE})
        task = TutorComparison(task_code="PRIVATE_CASE_ID", baseline=self.state)
        tickets = task.start(QUERY, expected_revision=0)
        shared = task.shared_initial(model)
        plans = [shared.decision_for(tickets[c]) for c in CONDITIONS]
        self.assertTrue(all(p["gate"]["decision"] == "ASK" for p in plans))
        self.assertEqual(model.calls, ["interpret"])
        self.assertNotIn("PRIVATE_CASE_ID", json.dumps(model.contexts))
        self.assertTrue(all(p["input"]["question"] == plans[0]["input"]["question"] for p in plans))
        self.assertFalse(task.participant_view()["results_visible"])

    def test_single_selective_open_question_resolves_full_text_and_keeps_other_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            model = FixtureModel(); model.raw = uncertain({"speech_rate": INVALID_RATE})
            sessions = TutorSessions(model, folder)
            view = sessions.create({"condition": "S", "settings": BASELINE})
            def mutate(op, **kwargs):
                return sessions.mutate(view["session_id"], op, {"request_id": uuid.uuid4().hex,
                    "expected_revision": view["revision"], **kwargs})
            view = mutate("request", query=QUERY)
            self.assertEqual(view["decision"], "ASK")
            self.assertEqual(view["settings"], BASELINE)
            self.assertEqual([o["id"] for o in view["question"]["options"]], ["other", "cancel"])
            model.raw = answer("other"); model.resolved = voice_resolution()
            text = "I mean Male voice 2. Keep the speed, tone, length and appearance as they are."
            view = mutate("request", query=text, question_id=view["question"]["question_id"])
            self.assertEqual(view["decision"], "ACT")
            self.assertIsNone(view["question"])
            self.assertEqual(view["settings"], {**BASELINE, "voice": "voice_e"})
            self.assertEqual(model.contexts[-1]["clarification_resolution"]["answer"], text)

    def test_unsupported_numeric_answer_leaves_open_question_live_and_state_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            model = FixtureModel(); model.raw = uncertain({"speech_rate": INVALID_RATE})
            sessions = TutorSessions(model, folder)
            view = sessions.create({"condition": "S", "settings": BASELINE})
            def mutate(op, **kwargs):
                return sessions.mutate(view["session_id"], op, {"request_id": uuid.uuid4().hex,
                    "expected_revision": view["revision"], **kwargs})
            view = mutate("request", query=QUERY)
            question_id = view["question"]["question_id"]
            model.resolved = proposal({"speech_rate": 1.0925})
            view = mutate("answer", question_id=question_id, option_id="other", free_text="Use 1.0925 times default speed.")
            self.assertEqual(view["decision"], "UNRESOLVED")
            self.assertEqual(view["question"]["question_id"], question_id)
            self.assertEqual(view["settings"], BASELINE)
            model.resolved = voice_resolution()
            view = mutate("answer", question_id=question_id, option_id="other", free_text="Use Male voice 2 and keep everything else.")
            self.assertEqual(view["settings"], {**BASELINE, "voice": "voice_e"})

    def test_comparison_all_open_questions_accept_text_before_joint_reveal(self):
        with tempfile.TemporaryDirectory() as folder:
            model = GenerationFixture()
            model.raw = uncertain({"speech_rate": INVALID_RATE})
            model.answer_result = parts("The selected voice is now active.", "The other settings remain unchanged.")
            app = TutorComparisons(model, folder)
            try:
                created = app.create({"request_id": "create", "task_code": "PRIVATE_CASE_ID", "settings": BASELINE})
                task_id = created["task_id"]
                def current(): return app.view(app.get(task_id))
                def mutate(op, condition=None, **payload):
                    v = current()
                    key = "expected_revision" if condition is None else "expected_branch_revision"
                    revision = v["revision"] if condition is None else v["branches"][condition]["branch_revision"]
                    return app.mutate(task_id, op, {"request_id": uuid.uuid4().hex, key: revision, **payload}, condition)
                def settled():
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        v = current()
                        if all(b["status"] not in ("idle", "processing") for b in v["branches"].values()): return v
                        time.sleep(.005)
                    self.fail("Comparison fixture timed out: " + json.dumps(current()))
                mutate("start", query=QUERY)
                view = settled()
                self.assertFalse(view["results_visible"])
                self.assertTrue(all(b["status"] == "awaiting_clarification" for b in view["branches"].values()))
                for b in view["branches"].values():
                    self.assertEqual([o["id"] for o in b["question"]["options"]], ["other", "cancel"])
                    self.assertIsNone(b["result"])
                model.raw = answer("other"); model.resolved = voice_resolution()
                for i, c in enumerate(CONDITIONS):
                    question_id = current()["branches"][c]["question"]["question_id"]
                    mutate("answer", c, question_id=question_id,
                           response={"text": "Use Male voice 2 and keep every other setting the same."})
                    view = settled()
                    self.assertEqual(view["results_visible"], i == len(CONDITIONS) - 1)
                for b in view["branches"].values():
                    self.assertEqual(b["result"]["state"]["settings"], {**BASELINE, "voice": "voice_e"})
                self.assertEqual(model.calls.count("resolve"), 4)
                self.assertEqual(model.calls.count("native"), 0)
            finally:
                app.shutdown()


if __name__ == "__main__":
    unittest.main()
