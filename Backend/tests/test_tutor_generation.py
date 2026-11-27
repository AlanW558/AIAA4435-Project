"""Generation lifecycle invariants with explicit fixtures; no paid provider calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import DeepSeekModel, ModelError, MockModel
from server import Server
from tutor_generation import TutorGenerator, generation_context, TUTOR_ANSWER_PROMPT
from tutor_session import TutorSessions
from tutor_state import TutorState, DEFAULT_SETTINGS
from test_tutor_session import FixtureModel as SessionFixture, chat
from test_tutor_interpretation import tailoring


def parts(text="Use active recall.", reasoning="", example=""):
    return {"key_answer": text, "reasoning": reasoning, "example_or_steps": example}


class GenerationFixture(SessionFixture):
    def __init__(self):
        super().__init__()
        self.answer_result = parts()

    def generate_tutor(self, context):
        return self._return("generate", context, self.answer_result)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.app = TutorSessions(self.model, self.temp.name)
        self.index = 0

    def tearDown(self):
        self.temp.cleanup()

    def mutate(self, v, operation, **kwargs):
        self.index += 1
        return self.app.mutate(v["session_id"], operation,
                               {"request_id": f"r{self.index}", "expected_revision": v["revision"], **kwargs})

    def queue(self, v=None, query="How should I revise?"):
        v = v if v is not None else self.app.create({})
        self.model.raw = chat(query)
        return self.mutate(v, "request", query=query)

    def generate(self, v, index=-1):
        return self.mutate(v, "generate", job_id=v["generation_jobs"][index]["job_id"])

    def test_success_records_actual_answer_with_effective_settings(self):
        v = self.queue()
        self.assertTrue(v["generation_available"])
        self.assertEqual(v["generation_jobs"][0]["status"], "queued")
        v = self.generate(v)
        self.assertEqual(v["decision"], "ANSWER")
        self.assertEqual(v["response"]["text"], "Use active recall.")
        self.assertEqual(v["generation_jobs"][0]["status"], "completed")
        self.assertEqual(v["conversation"][0]["messages"], [
            {"role": "user", "content": "How should I revise?"},
            {"role": "assistant", "content": "Use active recall."}])
        self.assertEqual(v["conversation"][0]["settings"], v["settings"])
        self.assertEqual(v["changes"], [])

    def test_all_three_structures_reach_generator_without_strategy_labels(self):
        contexts = []
        for length in ("brief", "balanced", "detailed"):
            v = self.app.create({"condition": "N", "participant_id": "PRIVATEID",
                                 "settings": {**DEFAULT_SETTINGS, "reply_length": length}})
            self.generate(self.queue(v))
            contexts.append(self.model.contexts[-1])
        self.assertEqual([c["reply_structure"]["mode"] for c in contexts], ["brief", "balanced", "detailed"])
        self.assertEqual(len({c["reply_structure"]["guidance"] for c in contexts}), 3)
        for context in contexts:
            self.assertEqual(set(context), {"query", "reply_structure", "tone_style", "conversation"})
            self.assertNotIn("PRIVATEID", json.dumps(context))
        self.assertNotIn("native", self.model.calls)

    def test_followup_receives_prior_completed_answer_and_interpreter_also_sees_it(self):
        v = self.generate(self.queue())
        v = self.queue(v, "Why is that useful?")
        interpreted = self.model.contexts[-1]
        self.assertEqual(interpreted["conversation"][0]["messages"][1]["content"], "Use active recall.")
        self.model.answer_result = parts("It practises retrieving information.")
        v = self.generate(v)
        context = self.model.contexts[-1]
        self.assertEqual(context["conversation"][1]["content"], "Use active recall.")
        self.assertEqual(len(v["conversation"]), 2)

    def test_persistent_length_stays_brief_over_followup(self):
        v = self.app.create({})
        self.model.raw = tailoring("brief")
        v = self.mutate(v, "request", query="Key points from now on")
        v = self.generate(v)  # Complete the actual acknowledgement before follow-ups.
        for query in ("What is recall?", "Why use it?"):
            v = self.generate(self.queue(v, query))
            self.assertEqual(v["response"]["settings"]["reply_length"], "brief")
        self.assertEqual(v["settings"]["reply_length"], "brief")
        self.assertEqual(len(v["changes"]), 1)

    def test_adjustment_only_generates_real_outcome_grounded_reply(self):
        self.model.raw = tailoring("brief")
        v = self.mutate(self.app.create({"condition":"E"}), "request", query="Keep it short, please.")
        self.assertEqual(len(v["generation_jobs"]), 1)
        self.assertEqual(v["conversation"], [])
        self.model.answer_result = parts("I'll keep the key points concise.", "Supporting detail.", "Example.")
        v = self.generate(v)
        outcome = self.model.contexts[-1]["settings_response"]
        self.assertEqual(outcome["outcome"], "applied")
        self.assertEqual(outcome["changed_fields"]["reply_length"], {"before":"balanced","after":"brief"})
        self.assertEqual(v["response"]["text"], "I'll keep the key points concise.")
        self.assertEqual(outcome["voice_labels"]["voice_d"], "Male voice 1")
        self.assertEqual(v["conversation"][-1]["messages"][0]["content"], "Keep it short, please.")

    def test_clarification_waits_then_generates_one_adjustment_reply(self):
        self.model.raw = tailoring("brief")
        v = self.mutate(self.app.create({"condition":"A"}),"request",query="Keep it short.")
        self.assertEqual(v["generation_jobs"], [])
        v = self.mutate(v,"answer",question_id=v["question"]["question_id"],option_id="c1")
        self.assertEqual(len(v["generation_jobs"]),1)
        v = self.generate(v)
        self.assertEqual(self.model.contexts[-1]["settings_response"]["outcome"],"applied")

    def test_cancel_and_noop_replies_do_not_claim_a_change(self):
        self.model.raw = tailoring("brief")
        v = self.mutate(self.app.create({"condition":"A"}),"request",query="Keep it short.")
        v = self.mutate(v,"cancel",question_id=v["question"]["question_id"])
        v = self.generate(v)
        outcome=self.model.contexts[-1]["settings_response"]
        self.assertEqual(outcome["outcome"],"cancelled")
        self.assertEqual(outcome["changed_fields"],{})
        v=self.mutate(v,"settings",patch={"reply_length":"balanced"})
        self.generate(v)
        self.assertEqual(self.model.contexts[-1]["settings_response"]["outcome"],"unchanged")

    def test_confirmed_full_controls_generate_one_reply_with_all_new_settings(self):
        v = self.mutate(self.app.create({}),"settings",patch={"speech_rate":.7,"reply_length":"detailed","tone":"friendly","voice":"voice_a"})
        self.assertEqual(len(v["changes"]),1)
        self.assertEqual(len(v["generation_jobs"]),1)
        self.model.answer_result=parts("I have applied those choices.","A relevant explanation.","A next step.")
        v=self.generate(v)
        self.assertEqual(v["response"]["text"],"I have applied those choices.\n\nA relevant explanation.\n\nA next step.")
        self.assertEqual(v["response"]["settings"]["speech_rate"],.7)
        self.assertEqual(v["conversation"][-1]["messages"][0]["content"],"[Controls confirmed]")

    def test_one_turn_setting_is_recorded_without_changing_persistent_state(self):
        self.model.raw = tailoring("brief", kind="mixed", scope="turn", conversation_query="What is recall?")
        v = self.mutate(self.app.create({}), "request", query="Just this answer, key points: what is recall?")
        v = self.generate(v)
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(v["conversation"][0]["settings"]["reply_length"], "brief")
        self.assertEqual(v["response"]["settings"]["reply_length"], "brief")
        v = self.generate(self.queue(v, "Why is it helpful?"))
        self.assertEqual(v["conversation"][1]["settings"]["reply_length"], "balanced")
        self.assertEqual(v["changes"], [])

    def test_later_control_change_does_not_relabel_queued_or_prior_answer(self):
        v = self.queue()
        v = self.mutate(v, "settings", patch={"reply_length": "detailed"})
        v = self.generate(v)
        self.assertEqual(v["settings"]["reply_length"], "detailed")
        self.assertEqual(v["response"]["settings"]["reply_length"], "balanced")
        self.assertEqual(v["conversation"][0]["settings"]["reply_length"], "balanced")
        v = self.generate(self.queue(v, "And next?"))
        self.assertEqual(v["response"]["settings"]["reply_length"], "detailed")

    def test_questions_generate_in_order_to_preserve_followup_context(self):
        v = self.queue()
        v = self.queue(v, "Why that method?")
        with self.assertRaises(APIError) as caught:
            self.generate(v)
        self.assertEqual(caught.exception.code, "generation_order")
        self.assertNotIn("generate", self.model.calls)
        v = self.generate(v, 0)
        v = self.generate(v, 1)
        self.assertEqual(self.model.contexts[-1]["conversation"][1]["content"], "Use active recall.")

    def test_same_request_and_completed_job_new_request_never_duplicate_generation(self):
        v = self.queue()
        body = {"request_id": "generate-once", "expected_revision": v["revision"], "job_id": v["generation_jobs"][0]["job_id"]}
        v = self.app.mutate(v["session_id"], "generate", body)
        replay = self.app.mutate(v["session_id"], "generate", body)
        self.assertTrue(replay["idempotent_replay"])
        v = self.generate(replay)
        self.assertTrue(v["generation_replay"])
        self.assertEqual(self.model.calls.count("generate"), 1)
        self.assertEqual(len(v["conversation"]), 1)

    def test_provider_failure_can_retry_same_job_with_new_id_and_no_partial_history(self):
        self.model.raw = tailoring("brief", scope="turn", kind="mixed", conversation_query="How should I revise?")
        v = self.mutate(self.app.create({}), "request", query="Just this answer: key points. How should I revise?")
        before = deepcopy(v)
        self.model.answer_result = ModelError("Fixture timeout", [{"role": "tutor_answer", "status": "error"}])
        body = {"request_id": "failed", "expected_revision": v["revision"], "job_id": v["generation_jobs"][0]["job_id"]}
        for _ in range(2):
            with self.assertRaises(APIError) as caught:
                self.app.mutate(v["session_id"], "generate", body)
            self.assertEqual(caught.exception.status, 502)
        self.assertEqual(self.app.view(self.app.get(v["session_id"])), before)
        self.assertEqual(self.model.calls.count("generate"), 1)
        self.model.answer_result = parts()
        v = self.generate(v)
        self.assertEqual(v["response"]["settings"]["reply_length"], "brief")
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(len(v["conversation"]), 1)

    def test_invalid_or_empty_output_cannot_commit_answer_or_setting_changes(self):
        for raw in ({}, parts(" "), parts([]), parts("x" * 16001),
                    {**parts(), "patch": {"reply_length": "detailed"}}, {"answer": "Legacy unstructured output"}, None):
            with self.subTest(raw=str(raw)[:80]):
                v = self.queue()
                self.model.answer_result = raw
                with self.assertRaises(APIError) as caught:
                    self.generate(v)
                self.assertEqual(caught.exception.code, "model_error")
                self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_log_failure_after_model_success_does_not_publish_partial_answer(self):
        v = self.queue()
        original = self.app.log
        def fail_commit(s, event, **payload):
            if event == "operation_committed":
                raise OSError("Fixture disk failure")
            original(s, event, **payload)
        with patch.object(self.app, "log", side_effect=fail_commit):
            with self.assertRaises(APIError) as caught:
                self.generate(v)
        self.assertEqual(caught.exception.code, "audit_unavailable")
        self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_pending_mixed_question_cannot_generate_before_confirmation(self):
        self.model.raw = tailoring("brief", kind="mixed", conversation_query="What is recall?")
        v = self.mutate(self.app.create({"condition": "A"}), "request", query="Key points. What is recall?")
        self.assertEqual(v["generation_jobs"], [])
        with self.assertRaises(APIError):
            self.mutate(v, "generate", job_id="not-a-job")
        v = self.mutate(v, "answer", question_id=v["question"]["question_id"], option_id="c1")
        v = self.generate(v)
        self.assertEqual(v["response"]["settings"]["reply_length"], "brief")

    def test_chat_while_pending_uses_committed_settings_and_preserves_question(self):
        self.model.raw = tailoring("brief")
        v = self.mutate(self.app.create({"condition": "A"}), "request", query="Brief please")
        pending = deepcopy(v["question"])
        v = self.generate(self.queue(v))
        self.assertEqual(v["question"], pending)
        self.assertEqual(v["response"]["settings"]["reply_length"], "balanced")

    def test_reset_and_other_session_cannot_use_old_job(self):
        v = self.queue()
        job_id = v["generation_jobs"][0]["job_id"]
        for target in (self.app.create({}), self.mutate(v, "reset")):
            with self.assertRaises(APIError) as caught:
                self.mutate(target, "generate", job_id=job_id)
            self.assertEqual(caught.exception.code, "job_not_found")
        self.assertNotIn("generate", self.model.calls)

    def test_generation_context_is_bounded_and_strips_private_metadata(self):
        state = TutorState()
        for i in range(8):
            state.record_exchange(f"Q{i}", f"A{i}", expected_revision=i)
        snapshot = state.snapshot()
        snapshot.update(condition="PRIVATE_CONDITION", target="PRIVATE_GOAL")
        snapshot["conversation"][-1]["messages"][1]["private"] = "PRIVATE_GOAL"
        context = generation_context({"query": "Follow up", "settings": DEFAULT_SETTINGS,
                                      "target": "PRIVATE_GOAL"}, snapshot)
        self.assertEqual(len(context["conversation"]), 12)
        self.assertEqual(context["conversation"][0]["content"], "Q2")
        self.assertNotIn("PRIVATE", json.dumps(context))
        self.assertNotIn("settings", context)

    def test_invalid_generation_snapshot_cannot_write_partial_exchange(self):
        state = TutorState()
        before = state.snapshot()
        with self.assertRaises(APIError):
            state.record_exchange("Q", "A", expected_revision=0, generation_settings={"reply_length": "brief"})
        self.assertEqual(state.snapshot(), before)

    def test_only_selected_components_are_displayed_and_added_to_conversation(self):
        self.model.answer_result = parts("Key action.", "Supporting reason.", "Concrete example.")
        for length, expected in (("brief", "Key action."), ("balanced", "Key action.\n\nSupporting reason."),
                                 ("detailed", "Key action.\n\nSupporting reason.\n\nConcrete example.")):
            v = self.app.create({"settings": {**DEFAULT_SETTINGS, "reply_length": length}})
            v = self.generate(self.queue(v))
            self.assertEqual(v["response"]["text"], expected)
            self.assertEqual(v["conversation"][-1]["messages"][1]["content"], expected)
            self.assertNotIn("generated_components", v["generation_jobs"][-1])
            if length == "brief":
                self.assertNotIn("Supporting reason.", json.dumps(v))

    def test_omitted_optional_component_is_empty_not_a_generation_failure(self):
        self.model.answer_result = {"key_answer": "Key action.", "reasoning": "Supporting reason."}
        v = self.generate(self.queue())
        self.assertEqual(v["response"]["text"], "Key action.\n\nSupporting reason.")
        self.model.answer_result = {"key_answer": "Hello."}
        v = self.generate(self.queue())
        self.assertEqual(v["response"]["text"], "Hello.")

    def test_model_without_generator_reports_unavailability_not_fake_answer(self):
        app = TutorSessions(SessionFixture(), self.temp.name)
        app.model.raw = chat()
        v = app.create({})
        v = app.mutate(v["session_id"], "request", {"request_id": "r1", "expected_revision": 0, "query": "How?"})
        with self.assertRaises(APIError) as caught:
            app.mutate(v["session_id"], "generate", {"request_id": "r2", "expected_revision": 1,
                                                     "job_id": v["generation_jobs"][0]["job_id"]})
        self.assertEqual(caught.exception.code, "model_unavailable")

    def test_adapter_uses_configured_model_and_shared_transport(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-not-real"}):
            model = DeepSeekModel("configured-fixture")
        context = {"query": "Q"}
        with patch.object(model, "_call", return_value=({"answer": "A"}, [])) as call:
            model.generate_tutor(context)
        call.assert_called_once_with("tutor_answer", TUTOR_ANSWER_PROMPT, context)


class GenerationHTTPTests(unittest.TestCase):
    def test_full_http_request_generate_followup_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            model = GenerationFixture()
            server = Server(("127.0.0.1", 0), Experiment(MockModel(), temp), TutorSessions(model, temp))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            def post(route, data):
                request = urllib.request.Request(base + route, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    return json.load(response)
            try:
                v = post("/tutor/sessions", {"condition": "S"})
                route = "/tutor/sessions/" + v["session_id"]
                model.raw = tailoring("brief", kind="mixed", conversation_query="How should I revise?")
                v = post(route + "/request", {"request_id": "r1", "expected_revision": 0, "query": "Use key points. How should I revise?"})
                body = {"request_id": "g1", "expected_revision": 1, "job_id": v["generation_jobs"][0]["job_id"]}
                v = post(route + "/generate", body)
                self.assertEqual(v["response"]["text"], "Use active recall.")
                self.assertTrue(post(route + "/generate", body)["idempotent_replay"])
                model.raw = chat()
                v = post(route + "/request", {"request_id": "r2", "expected_revision": v["revision"], "query": "Why that?"})
                v = post(route + "/generate", {"request_id": "g2", "expected_revision": v["revision"], "job_id": v["generation_jobs"][-1]["job_id"]})
                self.assertEqual(len(v["conversation"]), 2)
                self.assertEqual(model.contexts[-1]["conversation"][1]["content"], "Use active recall.")
                self.assertEqual(model.calls.count("generate"), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
