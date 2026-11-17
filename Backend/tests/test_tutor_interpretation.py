"""Contract/adapter tests. Fixtures do not measure real language interpretation."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import DeepSeekModel, ModelError
from tutor_interpretation import TutorInterpreter, build_context, normalize_interpretation, TUTOR_INTERPRETER_PROMPT
from tutor_state import TutorState


def tailoring(*lengths, **overrides):
    result = {"kind": "tailoring", "conversation_query": "", "scope": "session",
              "requested_fields": ["reply_length"], "clarification": None,
              "proposal": {"supported": bool(lengths), "reason": "Fixture interpretation.",
                           "candidates": [{"id": f"c{i+1}", "patch": {"reply_length": value},
                                           "evidence": "Public fixture evidence."} for i, value in enumerate(lengths)],
                           "default_id": "c1" if lengths else "", "unresolved_references": [],
                           "possible_soft_preference_overrides": [], "explicit_override": False}}
    result.update(overrides)
    return result


def answer(option="c1", text=""):
    return {"kind": "clarification", "conversation_query": "", "scope": "none", "requested_fields": [],
            "proposal": None, "clarification": {"option_id": option, "free_text": text}}


def pending():
    return {"original_query": "Only the key points, please.", "text": "Use Brief replies?",
            "options": [{"id": "c1", "label": "Brief: key points only"},
                        {"id": "other", "label": "Something else"}, {"id": "cancel", "label": "Cancel"}]}


class FixtureModel:
    def __init__(self, raw):
        self.raw, self.contexts = raw, []

    def interpret_tutor(self, context):
        self.contexts.append(deepcopy(context))
        return deepcopy(self.raw), [{"role": "tutor_interpreter", "status": "fixture"}]


class InterpretationTests(unittest.TestCase):
    def setUp(self):
        self.state = TutorState()

    def interpret(self, raw, query="Only give the key points.", **kwargs):
        model = FixtureModel(raw)
        result = TutorInterpreter(model).interpret(query, self.state.snapshot(), **kwargs)
        return result["interpretation"]

    def test_clear_structure_proposal_never_commits(self):
        before = self.state.snapshot()
        for length in ("brief", "balanced", "detailed"):
            result = self.interpret(tailoring(length))
            expected = {} if length == "balanced" else {"reply_length": length}
            self.assertEqual(result["proposal"]["candidates"][0]["patch"], expected)
            self.assertEqual(self.state.snapshot(), before)

    def test_chat_keeps_original_question_not_model_rewrite(self):
        raw = {"kind": "chat", "conversation_query": "model paraphrase", "scope": "none",
               "requested_fields": [], "proposal": None, "clarification": None}
        result = self.interpret(raw, "What does tone mean in writing?")
        self.assertEqual(result["conversation_query"], "What does tone mean in writing?")
        self.assertIsNone(result["proposal"])

    def test_mixed_preserves_learning_question_and_scope(self):
        result = self.interpret(tailoring("brief", kind="mixed", scope="turn",
                                         conversation_query="What is active recall?"))
        self.assertEqual(result["conversation_query"], "What is active recall?")
        self.assertEqual(result["scope"], "turn")
        self.assertEqual(result["proposal"]["candidates"][0]["patch"], {"reply_length": "brief"})

    def test_multiple_distinct_interpretations_remain_available(self):
        result = self.interpret(tailoring("brief", "balanced"))
        self.assertEqual(len(result["proposal"]["candidates"]), 2)

    def test_duplicate_effects_are_merged_and_default_remapped(self):
        raw = tailoring("brief", "brief", "balanced")
        raw["proposal"]["default_id"] = "c2"
        result = self.interpret(raw)["proposal"]
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["default_id"], "c1")

    def test_empty_patch_and_current_value_are_same_effect(self):
        raw = tailoring("balanced", "balanced")
        raw["proposal"]["candidates"][0]["patch"] = {}
        self.assertEqual(len(self.interpret(raw)["proposal"]["candidates"]), 1)

    def test_history_and_preferences_supplied_without_private_metadata(self):
        self.state.commit({"reply_length": "brief"}, expected_revision=0, source="request", query="Just the key points.")
        self.state.record_exchange("What is recall?", "Retrieving information from memory.", expected_revision=1)
        self.state.commit({"reply_length": "detailed"}, expected_revision=2, source="direct_control")
        snapshot = self.state.snapshot()
        snapshot.update(condition="SECRET_S", task_goal="SECRET_TARGET", participant_id="SECRET_ID")
        snapshot["changes"][0]["task_goal"] = "SECRET_TARGET"
        snapshot["conversation"][0]["messages"][0]["private"] = "SECRET_TARGET"
        model = FixtureModel(tailoring("brief"))
        result = TutorInterpreter(model).interpret("Restore the earlier format.", snapshot,
                                                  preferences=[{"field": "reply_length", "value": "brief"}])
        context = model.contexts[0]
        self.assertNotIn("SECRET", json.dumps(context))
        self.assertNotIn("condition", context)
        self.assertNotIn("revision", context)
        self.assertEqual(context["change_history"][0]["before"]["reply_length"], "balanced")
        self.assertEqual(context["conversation"][0]["settings"]["reply_length"], "brief")
        self.assertEqual(result["based_on_revision"], 3)
        self.assertEqual(result["query"], "Restore the earlier format.")

    def test_historical_ambiguity_and_explicit_override_flags_retained(self):
        raw = tailoring("brief", "detailed")
        raw["proposal"]["unresolved_references"] = ["Earlier may mean either prior format."]
        raw["proposal"]["possible_soft_preference_overrides"] = ["Usually brief."]
        raw["proposal"]["explicit_override"] = True
        result = self.interpret(raw, preferences=["I usually prefer brief answers."])["proposal"]
        self.assertTrue(result["explicit_override"])
        self.assertTrue(result["unresolved_references"])
        self.assertTrue(result["possible_soft_preference_overrides"])

    def test_missing_history_can_remain_unresolved_without_candidate(self):
        result = self.interpret(tailoring(), "Restore my previous format.")
        self.assertFalse(result["proposal"]["supported"])
        self.assertEqual(result["proposal"]["candidates"], [])

    def test_unimplemented_fields_and_cross_field_ambiguity_can_be_reported(self):
        for fields in (["voice"], ["reply_length", "tone"], ["reply_length", "speech_rate"], ["other"]):
            raw = tailoring(requested_fields=fields)
            self.assertFalse(self.interpret(raw)["proposal"]["supported"])

    def test_supported_subset_of_multi_property_request_rejected(self):
        with self.assertRaises(ModelError):
            self.interpret(tailoring("brief", requested_fields=["reply_length", "tone"]))

    def test_unsupported_mixed_keeps_learning_question(self):
        result = self.interpret(tailoring(kind="mixed", requested_fields=["voice"],
                                         conversation_query="How should I revise?"))
        self.assertFalse(result["proposal"]["supported"])
        self.assertEqual(result["conversation_query"], "How should I revise?")

    def test_clarification_select_cancel_and_other(self):
        for option in ("c1", "cancel", "other"):
            result = self.interpret(answer(option), "My original spoken answer.", pending=pending())
            self.assertEqual(result["kind"], "clarification")
            if option == "other":
                self.assertEqual(result["clarification"]["free_text"], "My original spoken answer.")

    def test_clarification_requires_pending_and_existing_option(self):
        with self.assertRaises(ModelError):
            self.interpret(answer())
        with self.assertRaises(ModelError):
            self.interpret(answer("unknown"), pending=pending())

    def test_pending_does_not_force_chat_or_new_request_to_be_answer(self):
        raw = {"kind": "chat", "conversation_query": "", "scope": "none", "requested_fields": [],
               "proposal": None, "clarification": None}
        self.assertEqual(self.interpret(raw, "What is active recall?", pending=pending())["kind"], "chat")
        self.assertEqual(self.interpret(tailoring("detailed"), pending=pending())["kind"], "tailoring")

    def test_malformed_results_fail_closed_and_retain_call_records(self):
        invalid = []
        for key, value in (("scope", "unspecified"), ("kind", "ACT"), ("conversation_query", "dropped question"),
                           ("requested_fields", [])):
            raw = tailoring("brief"); raw[key] = value; invalid.append(raw)
        for key, value in (("supported", 1), ("default_id", "missing"), ("explicit_override", "yes"),
                           ("unresolved_references", "earlier"), ("candidates", [])):
            raw = tailoring("brief"); raw["proposal"][key] = value; invalid.append(raw)
        for bad_patch in ({"tone": "friendly"}, {"reply_length": "short"}, {"reply_length": []}):
            raw = tailoring("brief"); raw["proposal"]["candidates"][0]["patch"] = bad_patch; invalid.append(raw)
        raw = tailoring("brief"); raw["private_goal"] = "x"; invalid.append(raw)
        for raw in invalid:
            before = self.state.snapshot()
            with self.subTest(raw=raw), self.assertRaises(ModelError) as caught:
                self.interpret(raw)
            self.assertEqual(caught.exception.records[0]["status"], "fixture")
            self.assertEqual(self.state.snapshot(), before)

    def test_preferences_validated_and_invented_flags_removed(self):
        raw = tailoring("brief")
        raw["proposal"]["possible_soft_preference_overrides"] = ["Invented usual format"]
        self.assertEqual(self.interpret(raw)["proposal"]["possible_soft_preference_overrides"], [])
        for pref in (False, [{"field": "reply_length", "value": "brief", "goal": "secret"}],
                     [{"field": "speech_rate", "value": "fast"}]):
            with self.assertRaises(APIError):
                self.interpret(raw, preferences=pref)
        self.interpret(raw, preferences=[{"field": "speech_rate", "value": 1.08}])

    def test_context_is_bounded_and_detached(self):
        for i in range(25):
            self.state.commit({"reply_length": "brief" if i % 2 == 0 else "detailed"},
                              expected_revision=2*i, source="request")
            self.state.record_exchange("Question", "Answer", expected_revision=2*i+1)
        snapshot = self.state.snapshot()
        context = build_context("Next", snapshot)
        self.assertEqual(len(context["change_history"]), 20)
        self.assertEqual(len(context["conversation"]), 6)
        context["settings"]["tone"] = "friendly"
        context["conversation"][0]["messages"][0]["content"] = "changed copy"
        self.assertEqual(snapshot, self.state.snapshot())

    def test_normalized_text_preferences_can_be_reused_as_public_context(self):
        snapshot = self.state.snapshot()
        context = build_context("Brief", snapshot, preferences=["Usually detailed"])
        repeated = build_context("Brief", snapshot, preferences=context["soft_preferences"])
        self.assertEqual(context, repeated)

    def test_provider_error_is_not_silently_replaced_with_fixture(self):
        model = FixtureModel(tailoring("brief"))
        with patch.object(model, "interpret_tutor", side_effect=ModelError("provider failure")):
            with self.assertRaises(ModelError):
                TutorInterpreter(model).interpret("Brief please", self.state.snapshot())

    def test_live_adapter_uses_existing_configured_call_path(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-not-real"}):
            model = DeepSeekModel("configured-model-fixture")
        context = build_context("Brief please", self.state.snapshot())
        with patch.object(model, "_call", return_value=(tailoring("brief"), [])) as call:
            model.interpret_tutor(context)
        call.assert_called_once_with("tutor_interpreter", TUTOR_INTERPRETER_PROMPT, context)
        self.assertEqual(model.model, "configured-model-fixture")


if __name__ == "__main__":
    unittest.main()
