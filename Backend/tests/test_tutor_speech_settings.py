"""Speech parameters and restoration; no speech provider or acoustic assertions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import MockModel, ModelError
from server import Server
from tutor_comparison_service import TutorComparisons
from tutor_session import TutorSessions
from tutor_state import DEFAULT_SETTINGS
from test_tutor_generation import GenerationFixture, parts
from test_tutor_multidomain import proposal
from test_tutor_session import chat


def rate(basis="current", operation="multiply", value=.9):
    return {"basis": basis, "operation": operation, "value": value}


class SpeechSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.app = TutorSessions(self.model, self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, condition="E", **settings):
        return self.app.create({"condition": condition, "settings": {**DEFAULT_SETTINGS, **settings}})

    def change(self, view, op="request", **data):
        return self.app.mutate(view["session_id"], op, {
            "request_id": uuid.uuid4().hex, "expected_revision": view["revision"], **data})

    def ask(self, view, patch, scope="session", question=""):
        self.model.raw = proposal(patch, scope=scope)
        if question: self.model.raw.update(kind="mixed", conversation_query=question)
        return self.change(view, query="Public speech setting request")

    def generate(self, view):
        return self.change(view, "generate", job_id=view["generation_jobs"][-1]["job_id"])

    def test_default_current_and_difference_apply_exact_values(self):
        for expression, expected in ((rate("default"), .9), (rate(), 1.08), (rate(operation="add", value=-.1), 1.1)):
            with self.subTest(expression=expression):
                view = self.ask(self.create(speech_rate=1.2), {"speech_rate": expression})
                self.assertEqual(view["settings"]["speech_rate"], expected)
                self.assertEqual(view["changes"][-1]["patch"], {"speech_rate": expected})
                self.assertFalse(view["audio_available"])
                self.assertIn("Audio playback is not connected", view["message"])

    def test_four_dialogue_settings_apply_atomically(self):
        target = {"speech_rate": 1.08, "voice": "voice_a", "tone": "friendly", "reply_length": "brief"}
        view = self.ask(self.create(speech_rate=1.2), {**target, "speech_rate": rate()})
        self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, **target})
        self.assertEqual(len(view["changes"]), 1)

    def test_same_request_replay_does_not_multiply_rate_twice(self):
        view = self.create(speech_rate=1.2)
        self.model.raw = proposal({"speech_rate": rate()})
        body = {"request_id": "once", "expected_revision": 0, "query": "90% of current"}
        view = self.app.mutate(view["session_id"], "request", body)
        replay = self.app.mutate(view["session_id"], "request", body)
        self.assertEqual(replay["settings"]["speech_rate"], 1.08)
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(len(replay["changes"]), 1)

    def test_ask_confirms_captured_rate_or_cancels_without_change(self):
        for choice, expected in (("c1", 1.08), ("cancel", 1.2)):
            view = self.ask(self.create("A", speech_rate=1.2), {"speech_rate": rate()})
            self.assertEqual(view["settings"]["speech_rate"], 1.2)
            self.assertIn("1.08", view["question"]["options"][0]["label"])
            with self.assertRaises(APIError): self.change(view, "settings", patch={"speech_rate": 1.1})
            view = self.change(view, "answer", question_id=view["question"]["question_id"], option_id=choice)
            self.assertEqual(view["settings"]["speech_rate"], expected)

    def test_selective_small_step_and_ambiguous_voice(self):
        view = self.ask(self.create("S"), {"speech_rate": .95})
        self.assertEqual(view["decision"], "ACT")
        self.assertEqual(view["reason"], "SMALL_REVERSIBLE_STEP")
        self.model.raw = proposal({"voice": "voice_a"}, {"voice": "voice_b"})
        view = self.change(view, query="Either public voice choice")
        self.assertEqual(view["decision"], "ASK")
        self.assertEqual(view["settings"]["voice"], "voice_d")
        view = self.change(view, "answer", question_id=view["question"]["question_id"], option_id="c2")
        self.assertEqual(view["settings"]["voice"], "voice_b")

    def test_voice_switch_preserves_multiplier_and_text_settings(self):
        initial = {"speech_rate": 1.15, "tone": "friendly", "reply_length": "detailed"}
        view = self.ask(self.create(**initial), {"voice": "voice_a"})
        self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, **initial, "voice": "voice_a"})
        view = self.ask(view, {"speech_rate": 1.0})
        self.assertEqual(view["settings"]["voice"], "voice_a")
        self.assertEqual(view["settings"]["speech_rate"], 1.0)

    def test_one_turn_speech_snapshot_and_next_question(self):
        view = self.ask(self.create(speech_rate=1.2), {"speech_rate": rate(), "voice": "voice_a"}, scope="turn")
        self.assertIsNone(view["next_turn_override"])
        self.assertEqual(view["generation_jobs"][-1]["turn_override"], {"speech_rate": 1.08, "voice": "voice_a"})
        self.assertEqual(view["generation_jobs"][-1]["response_kind"], "settings_response")
        view = self.generate(view)
        self.assertEqual(view["response"]["settings"]["speech_rate"], 1.08)
        self.assertEqual(view["response"]["settings"]["voice"], "voice_a")
        self.assertEqual(view["response"]["audio_status"], "not_connected")
        self.assertEqual(view["settings"]["speech_rate"], 1.2)
        self.assertEqual(view["changes"], [])
        self.model.raw = chat()
        view = self.generate(self.change(view, query="How should I revise?"))
        self.assertEqual(view["response"]["settings"]["voice"], "voice_d")
        self.assertEqual(view["response"]["settings"]["speech_rate"], 1.2)
        self.assertEqual(set(self.model.contexts[-1]), {"query", "tone_style", "reply_structure", "conversation"})

    def test_retry_and_old_answer_preserve_speech_snapshot(self):
        view = self.ask(self.create(), {"speech_rate": .9, "voice": "voice_b"}, scope="turn", question="How should I revise?")
        view = self.change(view, "settings", patch={"speech_rate": 1.1, "voice": "voice_a"})
        self.model.answer_result = ModelError("Fixture failure")
        with self.assertRaises(APIError): self.generate(view)
        self.assertEqual(self.app.view(self.app.get(view["session_id"])), view)
        self.model.answer_result = parts()
        view = self.generate(view)
        self.assertEqual(view["response"]["settings"]["voice"], "voice_b")
        self.assertEqual(view["conversation"][-1]["settings"]["speech_rate"], .9)
        self.assertEqual(view["settings"]["voice"], "voice_a")
        calls = self.model.calls.count("generate")
        self.generate(view)
        self.assertEqual(self.model.calls.count("generate"), calls)

    def test_scoped_history_undo_preserves_newer_changes(self):
        view = self.change(self.create(), "settings", patch={"speech_rate": .9, "voice": "voice_a"})
        view = self.change(view, "settings", patch={"speech_rate": 1.1, "tone": "friendly"})
        view = self.change(view, "undo", field="voice")
        self.assertEqual((view["settings"]["voice"], view["settings"]["speech_rate"], view["settings"]["tone"]), ("voice_d", 1.1, "friendly"))
        view = self.change(view, "undo", field="speech_rate")
        self.assertEqual((view["settings"]["speech_rate"], view["settings"]["tone"]), (.9, "friendly"))
        self.assertEqual(view["changes"][-1]["kind"], "undo")

    def test_history_restore_uses_public_context_and_preserves_other_properties(self):
        view = self.change(self.create(), "settings", patch={"voice": "voice_a", "speech_rate": .9})
        view = self.change(view, "settings", patch={"voice": "voice_b", "speech_rate": 1.15, "tone": "friendly"})
        self.model.raw = proposal({"voice": "voice_a"}, preserved=["speech_rate", "tone"])
        view = self.change(view, query="Restore the previous voice; keep current speed and tone")
        self.assertEqual(view["settings"]["voice"], "voice_a")
        self.assertEqual((view["settings"]["speech_rate"], view["settings"]["tone"]), (1.15, "friendly"))
        history = self.model.contexts[-1]["change_history"]
        self.assertEqual(history[0]["after"]["voice"], "voice_a")

    def test_invalid_numeric_intent_explained_for_every_strategy_without_partial_application(self):
        for condition in ("E", "A", "N", "S"):
            for value in (.65, 1.0925, rate(value=.95)):
                view = self.ask(self.create(condition, speech_rate=1.15), {"speech_rate": value, "voice": "voice_a", "tone": "friendly"})
                self.assertEqual(view["decision"], "UNRESOLVED")
                self.assertIn("speech rate", view["message"].lower())
                self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, "speech_rate": 1.15})
                self.assertIsNone(view["question"])
        self.assertNotIn("native", self.model.calls)

    def test_one_bad_candidate_rejects_whole_request_not_only_bad_option(self):
        self.model.raw = proposal({"speech_rate": .9}, {"speech_rate": 1.0925})
        view = self.change(self.create(), query="Ambiguous numeric request")
        self.assertEqual(view["decision"], "UNRESOLVED")
        self.assertEqual(view["settings"], DEFAULT_SETTINGS)

    def test_invalid_direct_settings_preserve_state_and_no_model_call(self):
        view = self.create()
        for patch in ({"speech_rate": 1.0925}, {"speech_rate": 1.31}, {"voice": "warm"},
                      {"voice": "voice_a", "jacket_color": "green"}):
            with self.assertRaises(APIError): self.change(view, "settings", patch=patch)
            self.assertEqual(self.app.view(self.app.get(view["session_id"])), view)
        self.assertEqual(self.model.calls, [])

    def test_precision_problem_in_clarification_keeps_question_and_reason(self):
        view = self.ask(self.create("A", speech_rate=1.15), {"speech_rate": .9})
        question = deepcopy(view["question"])
        self.model.resolved = proposal({"speech_rate": rate(value=.95)})
        view = self.change(view, "answer", question_id=question["question_id"], option_id="other", free_text="95% of current")
        self.assertEqual(view["decision"], "UNRESOLVED")
        self.assertIn("0.01", view["message"])
        self.assertEqual(view["question"], question)
        self.assertEqual(view["settings"]["speech_rate"], 1.15)


class SpeechComparisonTests(unittest.TestCase):
    def test_distinct_speech_snapshots_share_only_text_and_keep_first_results(self):
        model = GenerationFixture()
        model.raw = proposal({"speech_rate": rate(), "voice": "voice_a"})
        model.raw.update(kind="mixed", conversation_query="What is recall?")
        with tempfile.TemporaryDirectory() as temp:
            app = TutorComparisons(model, temp)
            try:
                task_id = app.create({"request_id": "new", "settings": {"speech_rate": 1.2}})["task_id"]
                def current(): return app.view(app.get(task_id))
                def change(op, condition=None, **data):
                    v = current()
                    key = "expected_revision" if condition is None else "expected_branch_revision"
                    rev = v["revision"] if condition is None else v["branches"][condition]["branch_revision"]
                    return app.mutate(task_id, op, {"request_id": uuid.uuid4().hex, key: rev, **data}, condition)
                def wait(check):
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        v = current()
                        if check(v): return v
                        time.sleep(.005)
                    self.fail("Comparison did not settle")
                def settled(): return wait(lambda v: all(b["status"] not in ("processing", "idle") for b in v["branches"].values()))
                change("start", query="Reduce current rate 10%, Voice A. What is recall?")
                v = settled()
                self.assertFalse(v["audio_available"])
                self.assertFalse(v["results_visible"])
                self.assertNotIn("1.08", json.dumps(v["baseline"]))
                self.assertTrue(all(b["result"] is None for b in v["branches"].values()))
                model.resolved = proposal({"speech_rate": rate("default"), "voice": "voice_b"})
                change("answer", "A", question_id=v["branches"]["A"]["question"]["question_id"],
                       response={"option_id": "other", "text": "90% of default and Voice B instead"})
                v = wait(lambda v: v["results_visible"])
                self.assertEqual(model.calls.count("interpret"), 1)
                self.assertEqual(model.calls.count("generate"), 1)
                for c, branch in v["branches"].items():
                    expected = (.9, "voice_b") if c == "A" else (1.08, "voice_a")
                    state = branch["result"]["state"]
                    self.assertEqual((state["settings"]["speech_rate"], state["settings"]["voice"]), expected)
                    self.assertEqual((state["conversation"][-1]["settings"]["speech_rate"], state["conversation"][-1]["settings"]["voice"]), expected)
                first = deepcopy(v["first_reveal"])
                change("settings", "E", patch={"speech_rate": 1.1, "voice": "voice_b"}); settled()
                change("undo", "E", field="voice"); v = settled()
                self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["voice"], "voice_a")
                self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["speech_rate"], 1.1)
                self.assertEqual(v["branches"]["S"]["result"]["state"]["settings"]["speech_rate"], 1.08)
                self.assertEqual(v["first_reveal"], first)
            finally:
                app.shutdown()


class SpeechSettingsHTTPTests(unittest.TestCase):
    def test_http_four_settings_and_scoped_undo(self):
        with tempfile.TemporaryDirectory() as temp:
            model = GenerationFixture()
            server = Server(("127.0.0.1", 0), Experiment(MockModel(), temp), TutorSessions(model, temp))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            def post(route, data):
                request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}" + route,
                    data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=5) as response: return json.load(response)
            try:
                v = post("/tutor/sessions", {})
                route = "/tutor/sessions/" + v["session_id"]
                v = post(route + "/settings", {"request_id": "settings", "expected_revision": v["revision"],
                    "patch": {"speech_rate": 1.08, "voice": "voice_a", "tone": "friendly", "reply_length": "brief"}})
                self.assertFalse(v["audio_available"])
                self.assertEqual(v["settings"]["speech_rate"], 1.08)
                v = post(route + "/undo", {"request_id": "undo", "expected_revision": v["revision"], "field": "speech_rate"})
                self.assertEqual(v["settings"]["speech_rate"], 1.0)
                self.assertEqual(v["settings"]["voice"], "voice_a")
                self.assertEqual(model.calls, [])
            finally:
                server.shutdown(); server.server_close(); worker.join()


if __name__ == "__main__":
    unittest.main()
