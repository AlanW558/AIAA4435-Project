"""Public uncertainty and spoken constraint preservation; no provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import ModelError
from tutor_comparison import CONDITIONS, TutorComparison
from tutor_interpretation import INTERPRETER_VERSION, TutorInterpreter, build_context, normalize_interpretation
from tutor_policy import POLICY_VERSION, common_question, selective_decision
from tutor_session import TutorSessions
from tutor_state import TutorState
from test_tutor_interpretation import answer
from test_tutor_multidomain import proposal
from test_tutor_session import FixtureModel

KEEP_OVERLAP = json.loads((Path(__file__).parent / "fixtures/tutor_requested_keep_overlap.json").read_text())


def uncertain(raw, query, kind="dimension", fields=("speech_rate", "reply_length")):
    raw["proposal"]["ambiguities"] = [{"kind": kind, "fields": list(fields), "evidence": query}]
    return raw


class AmbiguityContractTests(unittest.TestCase):
    def setUp(self):
        self.state = TutorState()

    def normalize(self, raw, query):
        return normalize_interpretation(raw, build_context(query, self.state.snapshot()))

    def gate(self, raw, query):
        normalized = self.normalize(raw, query)
        return selective_decision(normalized["proposal"], self.state.snapshot()["settings"], [])

    def test_versions_and_legacy_single_candidates_remain_usable(self):
        self.assertEqual(INTERPRETER_VERSION, "tutor-interpretation-v9")
        self.assertEqual(POLICY_VERSION, "tutor-gates-v4")
        for patch, query in (({"tone": "friendly"}, "Use a friendly tone."),
                             ({"tone": "professional"}, "Keep the current professional tone."),
                             ({"voice": "voice_c"}, "Use Female voice 3."),
                             ({"reply_length": "brief"}, "Just the essentials, please."),
                             ({"speech_rate": .8}, "Eighty percent of default speed, please.")):
            with self.subTest(query=query):
                result = self.normalize(proposal(patch), query)
                self.assertEqual(result["proposal"]["ambiguities"], [])
                self.assertEqual(selective_decision(result["proposal"], self.state.snapshot()["settings"], [])[0], "ACT")

    def test_single_noop_does_not_hide_flagged_dimension_uncertainty(self):
        query = "Make the explanation easier to follow without removing details."
        raw = uncertain(proposal({"reply_length": "balanced"}), query)
        result = self.normalize(raw, query)
        self.assertEqual(result["proposal"]["candidates"][0]["patch"], {})
        self.assertEqual(selective_decision(result["proposal"], self.state.snapshot()["settings"], []), ("ASK", "R4_EXPLICIT_AMBIGUITY"))

    def test_single_categorical_candidate_with_unclear_benefit_asks(self):
        query = "Help me understand, not just feel reassured."
        raw = uncertain(proposal({"tone": "encouraging"}), query, fields=("tone", "reply_length"))
        self.assertEqual(self.gate(raw, query), ("ASK", "R4_EXPLICIT_AMBIGUITY"))

    def test_reference_and_basis_uncertainty_override_small_step(self):
        for kind, query in (("reference", "Use the earlier speed."), ("basis", "Set the speed to ninety-five percent.")):
            raw = uncertain(proposal({"speech_rate": .95}), query, kind, ("speech_rate",))
            self.assertEqual(self.gate(raw, query), ("ASK", "R4_EXPLICIT_AMBIGUITY"))
        raw["proposal"]["unresolved_references"] = ["Unclear earlier setting"]
        self.assertEqual(self.gate(raw, query), ("ASK", "R1_REFERENCE"))

    def test_small_numeric_degree_remains_reversible_but_larger_unknown_amount_asks(self):
        query = "A little slower, please."
        raw = uncertain(proposal({"speech_rate": .95}), query, "degree", ("speech_rate",))
        self.assertEqual(self.gate(raw, query), ("ACT", "SMALL_REVERSIBLE_STEP"))
        raw = uncertain(proposal({"speech_rate": .8}), query, "degree", ("speech_rate",))
        self.assertEqual(self.gate(raw, query), ("ASK", "R4_EXPLICIT_AMBIGUITY"))
        raw = uncertain(proposal({"speech_rate": .95}), query, "degree", ("speech_rate", "voice"))
        self.assertEqual(self.gate(raw, query), ("ASK", "R4_EXPLICIT_AMBIGUITY"))

    def test_exact_numeric_arithmetic_and_unsupported_precision_are_not_rounded(self):
        self.state.commit({"speech_rate": 1.2}, expected_revision=0, source="request")
        query = "Twenty-five percent slower than now."
        raw = proposal({"speech_rate": {"basis": "current", "operation": "multiply", "value": .75}})
        result = self.normalize(raw, query)
        self.assertEqual(result["proposal"]["candidates"][0]["patch"], {"speech_rate": .9})
        self.assertEqual(self.gate(raw, query)[0], "ACT")
        raw = proposal({"speech_rate": {"basis": "current", "operation": "multiply", "value": .777}})
        result = self.normalize(raw, "Make it 77.7 percent of the current speed.")
        self.assertFalse(result["proposal"]["supported"])
        self.assertEqual(result["proposal"]["candidates"], [])

    def test_invalid_optional_rate_candidate_preserves_other_options_for_clarification(self):
        query = "Less intimidating, please."
        raw = uncertain(proposal({"tone": "friendly"}, {"speech_rate": 1.0925}, required=[]), query, fields=("tone", "speech_rate"))
        result = self.normalize(raw, query)
        self.assertTrue(result["proposal"]["supported"])
        self.assertEqual(result["proposal"]["candidates"][0]["patch"], {"tone": "friendly"})
        self.assertEqual(result["proposal"]["ambiguities"], raw["proposal"]["ambiguities"])
        self.assertEqual(selective_decision(result["proposal"], self.state.snapshot()["settings"], []), ("ASK", "COMMON_CANDIDATE_RECOVERY"))
        self.assertEqual(self.state.snapshot()["revision"], 0)

    def test_ambiguity_metadata_requires_bounded_literal_public_evidence(self):
        query = "Make it calmer."
        valid = {"kind": "dimension", "fields": ["tone", "speech_rate"], "evidence": "calmer"}
        invalids = [None, {}, [valid] * 5, [valid, valid],
                    [{**valid, "kind": "confidence"}], [{**valid, "fields": ["other"]}],
                    [{**valid, "fields": []}], [{**valid, "fields": ["tone", "tone"]}],
                    [{**valid, "fields": "tone"}], [{**valid, "evidence": "PRIVATE_TASK_TARGET"}],
                    [{**valid, "evidence": ""}], [{**valid, "score": .8}]]
        for ambiguity in invalids:
            raw = proposal({"tone": "friendly"}); raw["proposal"]["ambiguities"] = ambiguity
            with self.subTest(ambiguity=ambiguity), self.assertRaises(ModelError): self.normalize(raw, query)

    def test_question_identifies_uncertain_fields_without_echoing_evidence(self):
        for kind in ("dimension", "degree", "reference", "basis"):
            query = "PRIVATE_LOOKING_BUT_PUBLIC_PHRASE"
            raw = uncertain(proposal({"speech_rate": .8}, scope="turn", preserved=("voice",)), query, kind, ("speech_rate",))
            result = self.normalize(raw, query)
            question = common_question(query, result, self.state.snapshot()["settings"])
            self.assertIn("Speech rate", question["text"])
            self.assertIn("next answer only", question["text"])
            self.assertIn("Keep unchanged: Voice", question["text"])
            self.assertNotIn(query, question["text"])
            self.assertEqual([o["id"] for o in question["options"]][-2:], ["other", "cancel"])
            build_context("Yes", self.state.snapshot(), pending=question)

    def test_shared_uncertainty_is_identical_for_all_strategies_without_private_context(self):
        query = "Make this easier to follow."
        model = FixtureModel(); model.raw = uncertain(proposal({"reply_length": "balanced"}), query)
        task = TutorComparison(task_code="PRIVATE_TASK", scenario="C3")
        tickets = task.start(query, expected_revision=0); shared = task.shared_initial(model)
        before = task.participant_view()
        plans = {c: shared.decision_for(tickets[c]) for c in CONDITIONS}
        self.assertEqual([plans[c]["gate"]["decision"] for c in CONDITIONS], ["ACT", "ASK", "ACT", "ASK"])
        self.assertTrue(all(p["input"]["interpretation"] == plans["E"]["input"]["interpretation"] for p in plans.values()))
        self.assertTrue(all(p["input"]["question"] == plans["E"]["input"]["question"] for p in plans.values()))
        self.assertEqual(model.calls, ["interpret", "native"])
        self.assertNotIn("PRIVATE_TASK", json.dumps(model.contexts))
        self.assertTrue(all({"task_goal", "condition", "scenario"}.isdisjoint(context) for context in model.contexts))
        self.assertEqual(task.participant_view(), before)

    def test_dimension_question_covers_candidates_even_if_marker_names_one_field(self):
        query = 'Make this easier to follow.'
        raw = uncertain(proposal({'speech_rate': .8}, {'reply_length': 'detailed'}, required=[]),
                        query, fields=('reply_length',))
        result = self.normalize(raw, query)
        question = common_question(query, result, self.state.snapshot()['settings'])
        self.assertIn('Speech rate', question['text'])
        self.assertIn('Reply length', question['text'])

    def test_bound_nontrivial_option_keeps_full_answer_for_resolver(self):
        query = "Keep the detailed format, and slow down to eighty percent of default."
        initial = self.normalize(proposal({"reply_length": "detailed"}), "Use detailed replies.")
        pending = common_question("Use detailed replies.", initial, self.state.snapshot()["settings"])
        context = build_context(query, self.state.snapshot(), pending=pending, answering_pending_question=True)
        result = normalize_interpretation(answer("c1"), context)
        self.assertEqual(result["clarification"], {"option_id": "other", "free_text": query})
        for query in ("Yes.", "Yes, please!", "OK"):
            context = build_context(query, self.state.snapshot(), pending=pending, answering_pending_question=True)
            self.assertEqual(normalize_interpretation(answer("c1"), context)["clarification"], {"option_id": "c1", "free_text": ""})

    def test_bound_yes_does_not_pick_between_multiple_options(self):
        initial = self.normalize(proposal({"reply_length": "brief"}, {"reply_length": "detailed"}), "Change the length.")
        pending = common_question("Change the length.", initial, self.state.snapshot()["settings"])
        context = build_context("Yes", self.state.snapshot(), pending=pending, answering_pending_question=True)
        self.assertEqual(normalize_interpretation(answer("c1"), context)["clarification"], {"option_id": "other", "free_text": "Yes"})

    def test_direct_ui_option_id_does_not_invoke_text_resolver(self):
        with tempfile.TemporaryDirectory() as directory:
            model = FixtureModel(); model.raw = proposal({"reply_length": "brief"})
            app = TutorSessions(model, directory); view = app.create({"condition": "A"})
            view = app.mutate(view["session_id"], "request", {"request_id": "initial", "expected_revision": view["revision"], "query": "Use key points."})
            view = app.mutate(view["session_id"], "answer", {"request_id": "choose", "expected_revision": view["revision"], "question_id": view["question"]["question_id"], "option_id": "c1"})
            self.assertEqual(view["settings"]["reply_length"], "brief")
            self.assertNotIn("resolve", model.calls)

    def test_actual_redundant_requested_keep_replays_without_changing_intent(self):
        case = deepcopy(KEEP_OVERLAP); before = deepcopy(case)
        result = normalize_interpretation(case["response"], case["context"])
        self.assertEqual(result["requested_fields"], ["speech_rate", "tone"])
        self.assertEqual(result["preserved_fields"], ["reply_length"])
        self.assertEqual(result["required_fields"], [])
        self.assertEqual([c["patch"] for c in result["proposal"]["candidates"]], [{"speech_rate": 1.08}, {"tone": "friendly"}])
        self.assertEqual(selective_decision(result["proposal"], case["context"]["settings"], []), ("ASK", "R4_EXPLICIT_AMBIGUITY"))
        question = common_question(case["context"]["query"], result, case["context"]["settings"])
        self.assertIn("Keep unchanged: Reply length", question["text"])
        self.assertEqual(case, before)

    def test_requested_keep_overlap_never_repairs_missing_or_changed_candidate_values(self):
        for index in (0, 1):
            for mutation in ("missing", "contradictory"):
                with self.subTest(index=index, mutation=mutation):
                    case = deepcopy(KEEP_OVERLAP); patch = case["response"]["proposal"]["candidates"][index]["patch"]
                    if mutation == "missing": del patch["reply_length"]
                    else: patch["reply_length"] = "balanced"
                    with self.assertRaises(ModelError): normalize_interpretation(case["response"], case["context"])

    def test_requested_keep_overlap_requires_another_requested_field_and_supported_candidates(self):
        for mutation in ("keep_only", "unsupported", "empty_candidates"):
            with self.subTest(mutation=mutation):
                case = deepcopy(KEEP_OVERLAP); raw = case["response"]
                if mutation == "keep_only": raw["requested_fields"] = ["reply_length"]
                elif mutation == "unsupported": raw["proposal"]["supported"] = False
                else: raw["proposal"]["candidates"] = []
                with self.assertRaises(ModelError): normalize_interpretation(raw, case["context"])

    def test_requested_numeric_keep_overlap_does_not_compute_coerce_or_round(self):
        for value in (True, "1.2", 1.20001, {"basis": "current", "operation": "multiply", "value": 1}):
            case = deepcopy(KEEP_OVERLAP); raw = case["response"]
            raw["preserved_fields"].append("speech_rate")
            for candidate in raw["proposal"]["candidates"]: candidate["patch"]["speech_rate"] = value
            with self.subTest(value=value), self.assertRaises(ModelError): normalize_interpretation(raw, case["context"])

    def test_requested_keep_recovery_retains_required_change(self):
        case = deepcopy(KEEP_OVERLAP); raw = case["response"]
        raw["required_fields"] = ["speech_rate", "reply_length"]
        raw["proposal"]["candidates"][1]["patch"]["speech_rate"] = 1.08
        result = normalize_interpretation(raw, case["context"])
        self.assertEqual(result["required_fields"], ["speech_rate"])
        raw["proposal"]["candidates"][1]["patch"].pop("speech_rate")
        with self.assertRaises(ModelError): normalize_interpretation(raw, case["context"])


if __name__ == "__main__": unittest.main()
