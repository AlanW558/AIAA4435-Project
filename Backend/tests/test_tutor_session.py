"""Policy/state/HTTP integration using explicit fixtures, never paid model calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
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
from model import ModelError, MockModel
from server import Server
from tutor_session import TutorSessions
from test_tutor_interpretation import tailoring, answer


def chat(query="What is active recall?"):
    return {"kind": "chat", "scope": "none", "conversation_query": query,
            "requested_fields": [], "proposal": None, "clarification": None}


class FixtureModel:
    mode, model = "mock", "explicit-tutor-test-fixture"

    def __init__(self):
        self.raw = tailoring("brief")
        self.resolved = tailoring("balanced")
        self.native = {"decision": "ACT", "reason": "Fixture decision."}
        self.contexts, self.calls = [], []

    def _return(self, role, context, raw):
        self.contexts.append(deepcopy(context))
        self.calls.append(role)
        if isinstance(raw, Exception):
            raise raw
        return deepcopy(raw), [{"role": role, "status": "fixture", "requested_model": self.model}]

    def interpret_tutor(self, context):
        return self._return("interpret", context, self.raw)

    def decide_tutor(self, context):
        return self._return("native", context, self.native)

    def resolve_tutor_answer(self, context):
        return self._return("resolve", context, self.resolved)


class TutorSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = FixtureModel()
        self.app = TutorSessions(self.model, self.temp.name)
        self.index = 0

    def tearDown(self):
        self.temp.cleanup()

    def create(self, condition="S", **kwargs):
        return self.app.create({"condition": condition, **kwargs})

    def mutate(self, view, operation="request", **kwargs):
        self.index += 1
        return self.app.mutate(view["session_id"], operation,
                               {"request_id": f"r{self.index}", "expected_revision": view["revision"], **kwargs})

    def ask(self, view, query="Key points only please"):
        return self.mutate(view, query=query)

    def choose(self, view, option="c1", **kwargs):
        return self.mutate(view, "answer", question_id=view["question"]["question_id"], option_id=option, **kwargs)

    def test_four_gates_share_interpretation_and_preserve_ask_state(self):
        for condition, decision in (("E", "ACT"), ("A", "ASK"), ("N", "ACT"), ("S", "ACT")):
            v = self.ask(self.create(condition))
            self.assertEqual(v["decision"], decision)
            self.assertEqual(v["settings"]["reply_length"], "balanced" if decision == "ASK" else "brief")
        contexts = [c for c in self.model.contexts if "interpretation" not in c]
        self.assertTrue(all(c == contexts[0] for c in contexts))
        native = self.model.contexts[3]
        self.assertNotIn("condition", native)
        self.assertNotIn("participant_id", native)
        self.assertNotIn("task_goal", native)
        self.assertEqual(self.model.calls.count("native"), 1)

    def test_shared_question_identical_across_asking_conditions(self):
        self.model.raw = tailoring("brief", "detailed")
        self.model.native["decision"] = "ASK"
        questions = []
        for condition in ("A", "N", "S"):
            v = self.ask(self.create(condition))
            question = deepcopy(v["question"])
            question.pop("question_id")
            questions.append(question)
        self.assertTrue(all(q == questions[0] for q in questions))

    def test_always_ask_applies_to_every_new_repair_but_not_answer(self):
        v = self.ask(self.create("A"))
        self.assertEqual(v["revision"], 1)
        self.assertEqual(v["state_revision"], 0)
        v = self.choose(v)
        self.assertEqual(v["decision"], "ACT")
        self.assertEqual(self.model.calls, ["interpret"])
        self.model.raw = tailoring("detailed")
        v = self.ask(v, "Actually explain it with an example")
        self.assertEqual(v["decision"], "ASK")
        self.assertEqual(v["settings"]["reply_length"], "brief")
        self.assertEqual(self.choose(v)["settings"]["reply_length"], "detailed")

    def test_selective_reference_and_categorical_divergence(self):
        self.model.raw = tailoring("brief", "balanced")
        self.assertEqual(self.ask(self.create())["reason"], "R3_MATERIAL_DIVERGENCE")
        self.model.raw["proposal"]["unresolved_references"] = ["Two earlier formats"]
        self.assertEqual(self.ask(self.create())["reason"], "R1_REFERENCE")
        self.model.raw = tailoring("brief")
        self.model.raw["proposal"]["unresolved_references"] = ["History missing"]
        v = self.ask(self.create())
        self.assertEqual((v["decision"], v["settings"]["reply_length"]), ("UNRESOLVED", "balanced"))

    def test_selective_soft_preference_and_explicit_override(self):
        prefs = [{"field": "reply_length", "value": "detailed"}]
        self.model.raw["proposal"]["possible_soft_preference_overrides"] = ["Usually detailed"]
        self.assertEqual(self.ask(self.create(soft_preferences=prefs))["reason"], "R2_SOFT_PREFERENCE")
        self.model.raw["proposal"]["explicit_override"] = True
        self.assertEqual(self.ask(self.create(soft_preferences=prefs))["decision"], "ACT")
        self.model.raw["proposal"]["explicit_override"] = False
        self.model.raw["proposal"]["possible_soft_preference_overrides"] = ["Usually detailed"]
        self.assertEqual(self.ask(self.create(soft_preferences=["Usually detailed"]))["decision"], "ASK")

    def test_soft_preference_trigger_needs_override_evidence_and_an_actual_change(self):
        prefs = [{"field": "reply_length", "value": "detailed"}]
        self.assertEqual(self.ask(self.create(soft_preferences=prefs))["decision"], "ACT")
        self.model.raw = tailoring("balanced")
        self.model.raw["proposal"]["possible_soft_preference_overrides"] = ["Usually detailed"]
        self.assertEqual(self.ask(self.create(soft_preferences=prefs))["decision"], "ACT")

    def test_common_unsupported_never_calls_native_or_changes_state(self):
        self.model.raw = tailoring(requested_fields=["reply_length", "voice"])
        for condition in "EANS":
            v = self.ask(self.create(condition))
            self.assertEqual(v["decision"], "UNRESOLVED")
            self.assertEqual(v["changes"], [])
            self.assertIsNone(v["question"])
        self.assertNotIn("native", self.model.calls)

    def test_native_can_remain_unresolved_and_cannot_change_patch(self):
        self.model.native["decision"] = "UNRESOLVED"
        self.assertEqual(self.ask(self.create("N"))["decision"], "UNRESOLVED")
        self.model.native = {"decision": "ACT", "reason": "fixture", "patch": {"tone": "friendly"}}
        v = self.create("N")
        with self.assertRaises(APIError) as caught:
            self.ask(v)
        self.assertEqual(caught.exception.code, "model_error")
        self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_cancel_preserves_settings_and_releases_mixed_question(self):
        self.model.raw = tailoring("brief", kind="mixed", conversation_query="What is recall?")
        v = self.ask(self.create("A"))
        self.assertEqual(v["generation_jobs"], [])
        v = self.mutate(v, "cancel", question_id=v["question"]["question_id"])
        self.assertEqual(v["decision"], "CANCELLED")
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(v["generation_jobs"][0]["settings"]["reply_length"], "balanced")

    def test_mixed_single_turn_override_is_bound_to_one_job_only(self):
        self.model.raw = tailoring("brief", kind="mixed", scope="turn", conversation_query="What is recall?")
        v = self.ask(self.create())
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(v["changes"], [])
        self.assertEqual(v["generation_jobs"][0]["settings"]["reply_length"], "brief")
        self.assertIsNone(v["next_turn_override"])
        self.model.raw = chat()
        v = self.ask(v, "And what is spacing?")
        self.assertEqual(v["generation_jobs"][1]["settings"]["reply_length"], "balanced")
        self.assertFalse(v["generation_available"])
        self.assertEqual(v["conversation"], [])

    def test_standalone_single_turn_override_waits_for_question(self):
        self.model.raw = tailoring("brief", scope="turn")
        v = self.ask(self.create())
        self.assertEqual(v["next_turn_override"], {"reply_length": "brief"})
        self.assertEqual(v["generation_jobs"], [])
        self.model.raw = chat()
        v = self.ask(v)
        self.assertEqual(v["generation_jobs"][0]["turn_override"], {"reply_length": "brief"})
        self.assertIsNone(v["next_turn_override"])

    def test_chat_does_not_trigger_gate_or_lose_pending_question(self):
        v = self.ask(self.create("A"))
        question = v["question"]
        self.model.raw = chat()
        v = self.ask(v, "What is recall?")
        self.assertEqual(v["decision"], "CHAT_QUEUED")
        self.assertEqual(v["question"], question)
        self.assertEqual(v["generation_jobs"][0]["settings"]["reply_length"], "balanced")
        self.assertEqual(self.model.calls, ["interpret", "interpret"])

    def test_spoken_answer_uses_existing_question_without_new_gate(self):
        v = self.ask(self.create("A"))
        self.model.raw = answer()
        v = self.ask(v, "Yes please")
        self.assertEqual(v["decision"], "ACT")
        events = [json.loads(line) for line in (self.app.log_dir / (v["session_id"] + ".jsonl")).read_text().splitlines()]
        self.assertEqual(sum(e["event"] == "gate_decision" for e in events), 1)

    def test_free_text_answer_resolves_once_without_reconfirming(self):
        v = self.ask(self.create("A"))
        v = self.choose(v, "other", free_text="Keep the key point and add a short reason")
        self.assertEqual(v["decision"], "ACT")
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(self.model.calls, ["interpret", "resolve"])
        self.assertIn("clarification_resolution", self.model.contexts[-1])

    def test_ambiguous_free_text_keeps_same_question_and_old_settings(self):
        v = self.ask(self.create("A"))
        question = v["question"]
        self.model.resolved = tailoring("brief", "detailed")
        v = self.choose(v, "other", free_text="I'm still not sure")
        self.assertEqual(v["decision"], "UNRESOLVED")
        self.assertEqual(v["question"], question)
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(self.choose(v)["settings"]["reply_length"], "brief")

    def test_resolution_cannot_silently_turn_one_answer_into_persistent_setting(self):
        self.model.raw = tailoring("brief", scope="turn")
        v = self.ask(self.create("A"))
        v = self.choose(v, "other", free_text="With a short reason")
        self.assertEqual(v["decision"], "UNRESOLVED")
        self.assertEqual(v["changes"], [])
        self.assertIsNotNone(v["question"])

    def test_controls_and_new_requests_locked_while_pending(self):
        v = self.ask(self.create("A"))
        for operation, kwargs in (("settings", {"patch": {"reply_length": "detailed"}}),
                                   ("undo", {"field": "reply_length"}), ("request", {"query": "Different setting"})):
            with self.subTest(operation=operation), self.assertRaises(APIError) as caught:
                self.mutate(v, operation, **kwargs)
            self.assertEqual(caught.exception.code, "pending_question")
            self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_direct_control_and_undo_bypass_gates_and_preserve_other_settings(self):
        v = self.create("A")
        v = self.mutate(v, "settings", patch={"reply_length": "detailed"})
        self.assertEqual(v["decision"], "ACT")
        self.assertEqual(v["changes"][0]["source"], "direct_control")
        v = self.mutate(v, "undo", field="reply_length")
        self.assertEqual(v["settings"]["reply_length"], "balanced")
        self.assertEqual(v["settings"]["accessory"], "glasses")
        self.assertEqual(self.model.calls, [])

    def test_idempotent_replay_never_calls_model_or_rolls_back_current_view(self):
        v = self.create()
        data = {"request_id": "once", "expected_revision": 0, "query": "Brief please"}
        v = self.app.mutate(v["session_id"], "request", data)
        v = self.mutate(v, "settings", patch={"reply_length": "detailed"})
        replay = self.app.mutate(v["session_id"], "request", data)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["settings"]["reply_length"], "detailed")
        self.assertEqual(replay["revision"], v["revision"])
        self.assertEqual(self.model.calls, ["interpret"])
        with self.assertRaises(APIError) as caught:
            self.app.mutate(v["session_id"], "request", {**data, "query": "Changed content"})
        self.assertEqual(caught.exception.code, "request_id_conflict")

    def test_failed_paid_call_is_cached_and_state_unchanged(self):
        self.model.raw = ModelError("Fixture outage", [{"status": "error"}])
        v = self.create()
        data = {"request_id": "failed", "expected_revision": 0, "query": "Brief"}
        for _ in range(2):
            with self.assertRaises(APIError) as caught:
                self.app.mutate(v["session_id"], "request", data)
            self.assertEqual(caught.exception.status, 502)
        self.assertEqual(self.model.calls, ["interpret"])
        self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_audit_failure_rolls_back_working_copy(self):
        v = self.create()
        original_log = self.app.log
        def fail_commit(s, event, **payload):
            if event == "operation_committed":
                raise OSError("disk fixture")
            original_log(s, event, **payload)
        with patch.object(self.app, "log", side_effect=fail_commit):
            with self.assertRaises(APIError) as caught:
                self.ask(v)
        self.assertEqual(caught.exception.code, "audit_unavailable")
        self.assertEqual(self.app.view(self.app.get(v["session_id"])), v)

    def test_stale_revision_or_question_cannot_commit_after_reset(self):
        v = self.ask(self.create("A"))
        old = deepcopy(v)
        v = self.mutate(v, "reset")
        with self.assertRaises(APIError) as caught:
            self.choose(old)
        self.assertEqual(caught.exception.code, "stale_revision")
        v = self.ask(v)
        with self.assertRaises(APIError) as caught:
            self.mutate(v, "answer", question_id=old["question"]["question_id"], option_id="c1")
        self.assertEqual(caught.exception.code, "stale_question")

    def test_concurrent_same_revision_only_one_runs_model(self):
        v = self.create()
        def call(index):
            try:
                self.app.mutate(v["session_id"], "request", {"request_id": str(index), "expected_revision": 0, "query": "Brief"})
                return "ok"
            except APIError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(call, (1, 2)))
        self.assertCountEqual(results, ["ok", "stale_revision"])
        self.assertEqual(self.model.calls, ["interpret"])

    def test_unsupported_mixed_question_retained_until_new_repair(self):
        self.model.raw = tailoring(kind="mixed", requested_fields=["voice"], conversation_query="What is recall?")
        v = self.ask(self.create())
        self.assertEqual(v["deferred_questions"], ["What is recall?"])
        self.model.raw = tailoring("brief")
        v = self.ask(v, "Just use key points instead")
        self.assertEqual(v["generation_jobs"][0]["query"], "What is recall?")
        self.assertEqual(v["deferred_questions"], [])

    def test_debug_only_and_private_fields_rejected(self):
        for phase in ("pilot", "formal"):
            with self.assertRaises(APIError):
                self.create(phase=phase)
        v = self.create()
        with self.assertRaises(APIError):
            self.mutate(v, query="Brief", task_goal="brief")
        self.assertEqual(self.model.calls, [])

    def test_legacy_mock_does_not_silently_interpret_tutor_requests(self):
        app = TutorSessions(MockModel(), self.temp.name)
        v = app.create({})
        with self.assertRaises(APIError) as caught:
            app.mutate(v["session_id"], "request", {"request_id": "one", "expected_revision": 0, "query": "Brief"})
        self.assertEqual(caught.exception.code, "model_unavailable")


class TutorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = FixtureModel()
        self.server = Server(("127.0.0.1", 0), Experiment(MockModel(), self.temp.name), TutorSessions(self.model, self.temp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def req(self, route, data=None):
        req = urllib.request.Request(self.base + route, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_http_create_ask_answer_undo_get_and_legacy_compatibility(self):
        code, view = self.req("/tutor/sessions", {"condition": "A"})
        self.assertEqual(code, 200)
        base = "/tutor/sessions/" + view["session_id"]
        code, view = self.req(base + "/request", {"request_id": "r1", "expected_revision": 0, "query": "Key points"})
        self.assertEqual((code, view["decision"]), (200, "ASK"))
        code, view = self.req(base + "/answer", {"request_id": "r2", "expected_revision": 1,
                                                "question_id": view["question"]["question_id"], "option_id": "c1"})
        self.assertEqual((code, view["settings"]["reply_length"]), (200, "brief"))
        code, view = self.req(base + "/undo", {"request_id": "r3", "expected_revision": 2, "field": "reply_length"})
        self.assertEqual(view["settings"]["reply_length"], "balanced")
        self.assertEqual(self.req(base), (200, view))
        code, error = self.req(base + "/request", {"request_id": "stale", "expected_revision": 0, "query": "Brief"})
        self.assertEqual((code, error["error"]), (409, "stale_revision"))
        self.assertEqual(self.req("/health")[0], 200)
        self.assertEqual(self.req("/sessions", {"participant_id": "TEST", "condition": "E"})[0], 200)
        # Generation is now a real endpoint; a job ID is required.
        self.assertEqual(self.req(base + "/generate", {"request_id": "r4", "expected_revision": 3})[0], 400)


if __name__ == "__main__":
    unittest.main()
