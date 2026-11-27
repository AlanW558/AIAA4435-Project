"""Stage 3 planning contracts; deterministic fixtures, no provider/audio claims."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capabilities import DEMO_PROFILE
from core import APIError, selective_gate
from model import ModelError
from tutor_capabilities import APPEARANCE_FIELDS, public_capabilities
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_comparison_service import TutorComparisons
from tutor_interpretation import TutorInterpreter, build_context, normalize_interpretation
from tutor_policy import common_question, evaluate_gate, selective_decision
from tutor_session import TutorSessions
from tutor_state import TutorState
from test_tutor_session import FixtureModel
from test_tutor_interpretation import tailoring


def proposal(*patches, requested=None, required=None, preserved=(), scope="session"):
    fields = list(dict.fromkeys(f for p in patches for f in p)) if requested is None else requested
    raw = tailoring("brief", requested_fields=fields, scope=scope)
    raw["required_fields"] = fields if required is None else required
    raw["preserved_fields"] = list(preserved)
    raw["proposal"]["candidates"] = [
        {"id": f"c{i+1}", "patch": p, "evidence": "Public fixture request/history."}
        for i, p in enumerate(patches)]
    return raw


class MultiDomainTests(unittest.TestCase):
    def setUp(self):
        self.state = TutorState()
        self.model = FixtureModel()

    def interpret(self, raw, **kwargs):
        self.model.raw = raw
        return TutorInterpreter(self.model).interpret("Public request", self.state.snapshot(), **kwargs)["interpretation"]

    def gate(self, raw, preferences=None):
        result = self.interpret(raw, preferences=preferences)
        return selective_decision(result["proposal"], self.state.snapshot()["settings"], preferences or [])

    def test_each_direction_has_valid_read_only_proposal(self):
        for patch in ({"speech_rate": .9}, {"reply_length": "brief"}, {"tone": "friendly"},
                      {"voice": "voice_a"}, {"jacket_color": "green"}):
            with self.subTest(patch=patch):
                before = self.state.snapshot()
                self.assertEqual(self.interpret(proposal(patch))["proposal"]["candidates"][0]["patch"], patch)
                self.assertEqual(self.state.snapshot(), before)

    def test_public_capabilities_do_not_invent_voice_traits(self):
        caps = public_capabilities()
        descriptions = caps["voice_descriptions"]
        self.assertEqual({voice: info['catalog_gender'] for voice, info in descriptions.items()},
                         {'voice_a': 'female', 'voice_b': 'female', 'voice_c': 'female', 'voice_d': 'male', 'voice_e': 'male'})
        self.assertEqual(caps['voice_labels']['voice_b'], 'Female voice 2')
        self.assertEqual(caps['voice_labels']['voice_d'], 'Male voice 1')
        self.assertTrue(all(set(info) == {'catalog_gender', 'source'} for info in descriptions.values()))
        self.assertTrue(caps["voice_resources_bound"])
        caps['voice_descriptions']['voice_a']['catalog_gender'] = 'invented'
        self.assertEqual(public_capabilities()['voice_descriptions']['voice_a']['catalog_gender'], 'female')
        caps["avatar_defaults"]["liang"]["outfit"] = "invented"
        self.assertEqual(public_capabilities()["avatar_defaults"]["liang"]["outfit"], "suit")

    def test_rate_default_current_and_addition_are_distinct(self):
        self.state.commit({"speech_rate": 1.2}, expected_revision=0, source="request")
        for basis, op, value, expected in (("default", "multiply", .9, .9),
                                         ("current", "multiply", .9, 1.08),
                                         ("current", "add", -.1, 1.1)):
            with self.subTest(basis=basis, operation=op):
                raw = proposal({"speech_rate": {"basis": basis, "operation": op, "value": value}})
                patch = self.interpret(raw)["proposal"]["candidates"][0]["patch"]
                self.assertEqual(patch["speech_rate"], expected)

    def test_rate_expression_uses_captured_context_not_later_state(self):
        context = build_context("10% slower", self.state.snapshot())
        self.state.commit({"speech_rate": 1.2}, expected_revision=0, source="request")
        raw = proposal({"speech_rate": {"basis": "current", "operation": "multiply", "value": .9}})
        self.assertEqual(normalize_interpretation(raw, context)["proposal"]["candidates"][0]["patch"], {"speech_rate": .9})

    def test_unrepresentable_rates_fail_without_rounding_or_clamping(self):
        self.state.commit({"speech_rate": 1.15}, expected_revision=0, source="request")
        invalid = [True, float("nan"),
                   {"basis": "current", "operation": "multiply", "value": 0},
                   {"basis": "guess", "operation": "multiply", "value": .9},
                   {"basis": "default", "operation": "multiply", "value": True},
                   {"basis": "current", "operation": "multiply", "value": float("inf")}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ModelError):
                self.interpret(proposal({"speech_rate": value}))
        for value in (.69, 1.31, 1.0925,
                      {"basis": "current", "operation": "multiply", "value": .95},
                      {"basis": "default", "operation": "add", "value": .31}):
            with self.subTest(value=value):
                result = self.interpret(proposal({"speech_rate": value}))["proposal"]
                self.assertFalse(result["supported"])
                self.assertEqual(result["candidates"], [])
        self.assertEqual(self.state.snapshot()["settings"]["speech_rate"], 1.15)

    def test_equivalent_numeric_candidates_merge_and_default_remaps(self):
        raw = proposal({"speech_rate": .9}, {"speech_rate": {"basis": "default", "operation": "multiply", "value": .9}})
        raw["proposal"]["default_id"] = "c2"
        result = self.interpret(raw)["proposal"]
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["default_id"], "c1")

    def test_multifield_conjunction_keeps_both_effects(self):
        patch = {"tone": "friendly", "reply_length": "brief"}
        self.assertEqual(self.interpret(proposal(patch))["proposal"]["candidates"][0]["patch"], patch)

    def test_partial_conjunction_and_unrequested_change_rejected(self):
        for raw in (proposal({"tone": "friendly"}, requested=["tone", "reply_length"]),
                    proposal({"tone": "friendly", "speech_rate": .9}, requested=["tone"]),
                    proposal({"reply_length": "brief"}, requested=["reply_length", "other"])):
            with self.subTest(raw=raw), self.assertRaises(ModelError): self.interpret(raw)

    def test_alternative_fields_are_not_mistaken_for_conjunction(self):
        raw = proposal({"speech_rate": .9}, {"tone": "friendly"}, required=[])
        self.assertEqual(len(self.interpret(raw)["proposal"]["candidates"]), 2)
        self.assertEqual(self.gate(raw), ("ASK", "R3_MATERIAL_DIVERGENCE"))

    def test_keep_constraints_reject_direct_or_expanded_violation(self):
        for raw in (proposal({"tone": "friendly", "voice": "voice_a"}, requested=["tone"], preserved=["voice"]),
                    proposal({"avatar_id": "nailong"}, preserved=["outfit"])):
            with self.subTest(raw=raw), self.assertRaises(ModelError): self.interpret(raw)

    def test_avatar_candidate_expands_defaults_without_dialogue_reset(self):
        self.state.commit({"tone": "friendly", "speech_rate": .9}, expected_revision=0, source="request")
        patch = self.interpret(proposal({"avatar_id": "nailong"}))["proposal"]["candidates"][0]["patch"]
        self.assertEqual(set(patch), set(APPEARANCE_FIELDS))
        self.assertEqual((patch["outfit"], patch["jacket_color"], patch["accessory"]), ("none", "yellow", "none"))
        clone = self.state.clone()
        clone.commit(patch, expected_revision=1, source="request")
        self.assertEqual(clone.snapshot()["settings"]["tone"], "friendly")

    def test_avatar_compatible_keep_survives_actual_state_commit(self):
        raw = proposal({"avatar_id": "nailong"}, preserved=["jacket_color", "accessory", "scale"])
        patch = self.interpret(raw)["proposal"]["candidates"][0]["patch"]
        self.assertEqual((patch["jacket_color"], patch["accessory"]), ("blue", "glasses"))
        self.state.commit(patch, expected_revision=0, source="request")
        self.assertEqual(self.state.snapshot()["settings"]["accessory"], "glasses")

    def test_outfit_only_change_does_not_trigger_avatar_defaults(self):
        self.state.commit({"jacket_color": "purple", "scale": .95}, expected_revision=0, source="request")
        raw = proposal({"outfit": "sport"}, preserved=["jacket_color", "accessory", "scale"])
        patch = self.interpret(raw)["proposal"]["candidates"][0]["patch"]
        self.assertEqual(patch, {"outfit": "sport"})

    def test_invalid_appearance_and_enums_rejected_atomically(self):
        for patch in ({"avatar_id": "nailong", "outfit": "suit"}, {"scale": 1.08},
                      {"accessory": "hat_and_glasses"}, {"tone": "very_friendly"}, {"voice": "warm"}):
            with self.subTest(patch=patch), self.assertRaises(ModelError): self.interpret(proposal(patch))
        self.assertEqual(self.state.snapshot()["revision"], 0)

    def test_turn_scope_accepts_dialogue_only(self):
        raw = proposal({"tone": "friendly", "speech_rate": .9, "voice": "voice_a"}, scope="turn")
        self.assertEqual(self.interpret(raw)["scope"], "turn")
        with self.assertRaises(ModelError): self.interpret(proposal({"scale": 1.05}, scope="turn"))

    def test_malformed_constraint_lists_and_overlap_rejected(self):
        for name, value in (("required_fields", ["voice"]), ("preserved_fields", ["tone"]),
                            ("preserved_fields", ["voice", "voice"]), ("required_fields", "tone")):
            raw = proposal({"tone": "friendly"}); raw[name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ModelError): self.interpret(raw)

    def test_history_and_preferences_for_all_domains_are_public_only(self):
        self.state.commit({"voice": "voice_a", "tone": "friendly"}, expected_revision=0, source="request")
        self.state.commit({"voice": "voice_b", "tone": "encouraging"}, expected_revision=1, source="request")
        snapshot = self.state.snapshot(); snapshot["private_target"] = "SECRET_GOAL"
        context = build_context("Restore earlier voice", snapshot, preferences=[{"field": "voice", "value": "voice_a"}])
        self.assertNotIn("SECRET_GOAL", json.dumps(context))
        self.assertEqual(context["change_history"][0]["after"]["voice"], "voice_a")
        self.assertNotIn("task_code", context)
        self.assertNotIn("policy_version", context)

    def test_unique_history_restore_and_ambiguous_reference(self):
        self.state.commit({"voice": "voice_a"}, expected_revision=0, source="request")
        self.state.commit({"voice": "voice_b"}, expected_revision=1, source="request")
        self.assertEqual(self.gate(proposal({"voice": "voice_a"}))[0], "ACT")
        raw = proposal({"voice": "voice_d"}, {"voice": "voice_a"})
        raw["proposal"]["unresolved_references"] = ["Two public earlier voices"]
        self.assertEqual(self.gate(raw), ("ASK", "R1_REFERENCE"))

    def test_preference_conflicts_extend_to_numeric_and_categorical_fields(self):
        for field, target, pref in (("speech_rate", .95, 1.0), ("tone", "friendly", "professional"),
                                    ("voice", "voice_a", "voice_d"), ("jacket_color", "green", "blue")):
            raw = proposal({field: target}); raw["proposal"]["possible_soft_preference_overrides"] = ["Public preference"]
            preferences = [{"field": field, "value": pref}]
            self.assertEqual(self.gate(raw, preferences), ("ASK", "R2_SOFT_PREFERENCE"))
            raw["proposal"]["explicit_override"] = True
            self.assertEqual(self.gate(raw, preferences)[0], "ACT")

    def test_unchanged_preserved_preference_does_not_trigger_ask(self):
        raw = proposal({"tone": "friendly"}, preserved=["voice"])
        raw["proposal"]["possible_soft_preference_overrides"] = ["Spurious voice conflict"]
        self.assertEqual(self.gate(raw, [{"field": "voice", "value": "voice_d"}])[0], "ACT")

    def test_small_rate_step_and_larger_divergence(self):
        self.assertEqual(self.gate(proposal({"speech_rate": .95}, {"speech_rate": .9})), ("ACT", "SMALL_REVERSIBLE_STEP"))
        self.assertEqual(self.gate(proposal({"speech_rate": .9}, {"speech_rate": 1.1})), ("ASK", "R3_MATERIAL_DIVERGENCE"))
        self.assertEqual(self.gate(proposal({"speech_rate": .8})), ("ACT", "NO_TRIGGER"))

    def test_reference_and_preference_take_priority_over_small_rate_step(self):
        raw = proposal({"speech_rate": .95}, {"speech_rate": .9})
        raw["proposal"]["unresolved_references"] = ["Either earlier speed"]
        self.assertEqual(self.gate(raw), ("ASK", "R1_REFERENCE"))

    def test_discrete_and_cross_property_outcomes_trigger_material_divergence(self):
        for raw in (proposal({"tone": "friendly"}, {"tone": "encouraging"}),
                    proposal({"voice": "voice_a"}, {"voice": "voice_b"}),
                    proposal({"reply_length": "brief"}, {"speech_rate": 1.05}, required=[])):
            self.assertEqual(self.gate(raw), ("ASK", "R3_MATERIAL_DIVERGENCE"))

    def test_appearance_gate_matches_existing_cases(self):
        for raw in (proposal({"scale": 1.05}, {"scale": 1.1}),
                    proposal({"scale": .9}, {"scale": 1.1}),
                    proposal({"outfit": "sport"}, {"accessory": "none"}, required=[]),
                    proposal({"jacket_color": "green"}, {"jacket_color": "gray"}),
                    proposal({"scale": .85}, {"scale": .9})):
            result = self.interpret(raw)["proposal"]
            settings = self.state.snapshot()["settings"]
            self.assertEqual(selective_decision(result, settings, []), selective_gate(result, settings, [], DEMO_PROFILE))

    def test_clarification_labels_show_full_effect_scope_and_keeps(self):
        raw = proposal({"tone": "friendly", "speech_rate": .9}, preserved=["voice"], scope="turn")
        result = self.interpret(raw)
        q = common_question("Public request", result, self.state.snapshot()["settings"])
        self.assertIn("next answer only", q["text"])
        self.assertIn("Voice", q["text"])
        self.assertIn("Tone: Friendly", q["options"][0]["label"])
        self.assertIn("0.90× default speed", q["options"][0]["label"])
        self.assertEqual([o["id"] for o in q["options"]][-2:], ["other", "cancel"])
        # The generated question can itself be accepted as a later public pending question.
        build_context("Yes", self.state.snapshot(), pending=q)

    def test_avatar_question_discloses_expanded_reset(self):
        result = self.interpret(proposal({"avatar_id": "nailong"}))
        q = common_question("Change avatar", result, self.state.snapshot()["settings"])
        for label in ("Avatar: Nailong", "Outfit: None", "Colour: Yellow", "Accessory: None", "Scale: 1.00"):
            self.assertIn(label, q["options"][0]["label"])

    def test_shared_cross_domain_plan_runs_interpreter_once_and_stays_hidden(self):
        task = TutorComparison(task_code="PRIVATE_TASK")
        tickets = task.start("Calmer please", expected_revision=0)
        self.model.raw = proposal({"speech_rate": .9}, {"tone": "friendly"}, required=[])
        self.model.native = {"decision": "ASK", "reason": "Fixture judgment"}
        shared = task.shared_initial(self.model)
        before = task.participant_view()
        with ThreadPoolExecutor(max_workers=4) as pool:
            plans = list(pool.map(lambda c: shared.decision_for(tickets[c]), CONDITIONS))
        self.assertEqual([p["gate"]["decision"] for p in plans], ["ACT", "ASK", "ASK", "ASK"])
        self.assertEqual(len({p["input"]["shared_id"] for p in plans}), 1)
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("native"), 1)
        self.assertEqual(task.participant_view(), before)
        for context in self.model.contexts:
            self.assertNotIn("PRIVATE_TASK", json.dumps(context))

    def test_unsupported_request_bypasses_all_strategy_calls(self):
        raw = tailoring(requested_fields=["other"])
        result = self.interpret(raw)
        context = build_context("Unknown property", self.state.snapshot())
        for c in CONDITIONS:
            self.assertEqual(evaluate_gate(self.model, c, context, result, None)["reason"], "COMMON_UNSUPPORTED")
        self.assertNotIn("native", self.model.calls)

    def test_current_runtime_does_not_claim_unsupported_effects(self):
        with tempfile.TemporaryDirectory() as logs:
            sessions = TutorSessions(self.model, logs)
            for c in CONDITIONS:
                self.model.raw = tailoring(requested_fields=["other", "reply_length"])
                view = sessions.create({"condition": c})
                after = sessions.mutate(view["session_id"], "request", {
                    "request_id": "new", "expected_revision": 0, "query": "Change eye colour and use brief answers"})
                self.assertEqual(after["decision"], "UNRESOLVED")
                self.assertEqual(after["settings"], view["settings"])
                self.assertIsNone(after["question"])
                self.assertEqual(after["generation_jobs"], [])

    def test_free_text_clarification_cannot_bypass_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as logs:
            sessions = TutorSessions(self.model, logs)
            view = sessions.create({"condition": "A"})
            view = sessions.mutate(view["session_id"], "request", {
                "request_id": "ask", "expected_revision": 0, "query": "Brief please"})
            self.model.resolved = tailoring(requested_fields=["other"])
            after = sessions.mutate(view["session_id"], "answer", {
                "request_id": "answer", "expected_revision": view["revision"],
                "question_id": view["question"]["question_id"], "option_id": "other", "free_text": "Change eye colour instead"})
            self.assertEqual(after["decision"], "UNRESOLVED")
            self.assertIsNotNone(after["question"])
            self.assertEqual(after["settings"]["jacket_color"], "blue")

    def test_free_text_resolution_cannot_drop_an_original_keep_constraint(self):
        original = self.interpret(proposal({"reply_length": "brief"}, preserved=["tone"]))
        question = common_question("Brief, keep tone unchanged", original, self.state.snapshot()["settings"])
        interpreter = TutorInterpreter(self.model)
        self.model.resolved = proposal({"reply_length": "detailed"})
        result = interpreter.resolve_answer("Detailed instead", self.state.snapshot(), preferences=[],
                                            pending=question, scope="session", preserved_fields=["tone"])
        self.assertEqual(result["interpretation"]["preserved_fields"], ["tone"])
        self.model.resolved = proposal({"reply_length": "brief", "tone": "friendly"})
        with self.assertRaises(ModelError):
            interpreter.resolve_answer("Brief", self.state.snapshot(), preferences=[],
                                       pending=question, scope="session", preserved_fields=["tone"])

    def test_free_text_resolution_keeps_original_question_after_validation_failure(self):
        with tempfile.TemporaryDirectory() as logs:
            sessions = TutorSessions(self.model, logs)
            self.model.raw = proposal({"reply_length": "brief"}, preserved=["tone"])
            view = sessions.create({"condition": "A"})
            view = sessions.mutate(view["session_id"], "request", {
                "request_id": "ask", "expected_revision": 0, "query": "Brief, keep tone"})
            self.model.resolved = proposal({"reply_length": "brief", "tone": "friendly"})
            with self.assertRaises(APIError) as caught:
                sessions.mutate(view["session_id"], "answer", {
                    "request_id": "answer", "expected_revision": view["revision"],
                    "question_id": view["question"]["question_id"], "option_id": "other", "free_text": "Brief"})
            self.assertEqual(caught.exception.status, 502)
            after = sessions.view(sessions.get(view["session_id"]))
            self.assertEqual(after["question"], view["question"])
            self.assertEqual(after["settings"], view["settings"])

    def test_comparison_service_reports_unresolved_without_partial_commit(self):
        self.model.raw = tailoring(requested_fields=["other", "reply_length"])
        with tempfile.TemporaryDirectory() as logs:
            service = TutorComparisons(self.model, logs)
            try:
                view = service.create({"request_id": "new", "task_code": "debug"})
                task_id = view["task_id"]
                service.mutate(task_id, "start", {"request_id": "start", "expected_revision": view["revision"], "query": "Change eye colour and use brief answers"})
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    view = service.view(service.get(task_id))
                    if view["results_visible"]: break
                    time.sleep(.005)
                self.assertTrue(view["results_visible"])
                for branch in view["branches"].values():
                    self.assertEqual(branch["result"]["outcome"], "unresolved")
                    self.assertEqual(branch["result"]["state"]["settings"], view["baseline"]["settings"])
            finally:
                service.shutdown()


if __name__ == "__main__":
    unittest.main()
