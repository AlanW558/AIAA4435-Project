"""Asynchronous comparison execution and HTTP privacy; explicit fixtures only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import ModelError
from server import Server
from tutor_comparison_service import TutorComparisons
from test_tutor_generation import GenerationFixture, parts
from test_tutor_interpretation import tailoring, answer
from test_tutor_session import chat


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.model.answer_result = parts("HIDDEN_ANSWER", "HIDDEN_REASON", "HIDDEN_EXAMPLE")
        self.app = TutorComparisons(self.model, self.temp.name)
        self.view = self.app.create({"request_id": "create", "task_code": "TASK"})
        self.task_id = self.view["task_id"]

    def tearDown(self):
        self.app.shutdown()
        self.temp.cleanup()

    def current(self):
        return self.app.view(self.app.get(self.task_id))

    def mutate(self, op, condition=None, **payload):
        v = self.current()
        key = "expected_revision" if condition is None else "expected_branch_revision"
        rev = v["revision"] if condition is None else v["branches"][condition]["branch_revision"]
        return self.app.mutate(self.task_id, op, {"request_id": uuid.uuid4().hex, key: rev, **payload}, condition)

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            v = self.current()
            if predicate(v): return v
            time.sleep(.005)
        self.fail("Timed out: " + json.dumps(self.current()))

    def settled(self):
        return self.wait(lambda v: all(b["status"] not in ("idle", "processing") for b in v["branches"].values()))

    def start(self, mixed=False):
        self.model.raw = tailoring("brief", kind="mixed", conversation_query="What is recall?") if mixed else tailoring("brief")
        self.mutate("start", query="Change reply length.")
        return self.settled()

    def respond(self, c="A", response=None):
        qid = self.current()["branches"][c]["question"]["question_id"]
        return self.mutate("answer", c, question_id=qid, response=response or {"option_id": "c1"})

    def test_shared_followup_waits_for_clarification_and_preserves_first_reveal(self):
        self.start();self.respond();first=self.wait(lambda v:v["results_visible"])
        original=deepcopy(first["first_reveal"])
        self.model.raw=tailoring("balanced")
        self.mutate("round_request",query="Now give balanced answers.")
        waiting=self.settled()
        self.assertFalse(waiting["results_visible"])
        self.assertEqual(waiting["round_index"],2)
        self.assertTrue(all(b["result"] is None for b in waiting["branches"].values()))
        self.assertEqual(waiting["branches"]["A"]["status"],"awaiting_clarification")
        with self.assertRaises(APIError):self.mutate("round_request",query="Do not overlap rounds")
        self.respond();done=self.wait(lambda v:v["results_visible"])
        self.assertEqual(done["first_reveal"],original)
        self.assertNotEqual(done["latest_reveal"]["reveal_id"],original["reveal_id"])
        for b in done["branches"].values():self.assertEqual(b["result"]["state"]["settings"]["reply_length"],"balanced")

    def test_shared_followup_chat_reaches_every_branch_and_survives_checkpoint(self):
        from study_runtime import comparison_dump, comparison_load
        self.start();self.respond();first=self.wait(lambda v:v["results_visible"])
        self.model.raw=chat()
        self.mutate("round_request",query="Give one example.")
        done=self.wait(lambda v:v["results_visible"] and v["round_index"]==2)
        for c,b in done["branches"].items():
            self.assertEqual(len(b["result"]["state"]["conversation"]),len(first["branches"][c]["result"]["state"]["conversation"])+1)
        restored=comparison_load(self.app,comparison_dump(self.app.get(self.task_id)))
        self.assertEqual(restored.comparison.participant_view()["latest_reveal"],done["latest_reveal"])
        self.assertEqual(restored.comparison.participant_view()["round_index"],2)

    def test_shared_controls_and_undo_do_not_depend_on_viewed_strategy(self):
        self.start();self.respond();self.wait(lambda v:v["results_visible"])
        self.mutate("round_settings",patch={"speech_rate":.9})
        done=self.wait(lambda v:v["results_visible"] and v["round_index"]==2)
        for b in done["branches"].values():self.assertEqual(b["result"]["state"]["settings"]["speech_rate"],.9)
        self.mutate("round_undo",field="speech_rate")
        done=self.wait(lambda v:v["results_visible"] and v["round_index"]==3)
        for b in done["branches"].values():self.assertEqual(b["result"]["state"]["settings"]["speech_rate"],1.)

    def test_act_result_hidden_until_ask_answer_then_all_results_reveal(self):
        v = self.start(mixed=True)
        self.assertEqual(v["branches"]["A"]["status"], "awaiting_clarification")
        self.assertNotIn("HIDDEN_", json.dumps(v))
        self.assertEqual(v["baseline"]["settings"]["reply_length"], "balanced")
        self.assertTrue(all(b["result"] is None for b in v["branches"].values()))
        self.respond()
        v = self.wait(lambda v: v["results_visible"])
        for b in v["branches"].values():
            self.assertEqual(b["result"]["state"]["settings"]["reply_length"], "brief")
            self.assertEqual(len(b["result"]["state"]["conversation"]), 1)
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("native"), 1)
        self.assertEqual(self.model.calls.count("generate"), 1)

    def test_all_asking_branches_have_distinct_ids_and_independent_answers(self):
        self.model.raw = tailoring("brief", "detailed")
        self.model.native = {"decision": "ASK", "reason": "Fixture"}
        self.mutate("start", query="Make it easier."); v = self.settled()
        questions = [v["branches"][c]["question"] for c in ("A", "N", "S")]
        self.assertEqual(len({q["question_id"] for q in questions}), 3)
        self.assertEqual(questions[0]["options"], questions[2]["options"])
        self.respond("A"); self.settled()
        self.assertFalse(self.current()["results_visible"])
        self.respond("N", {"option_id": "c2"}); self.settled()
        self.assertFalse(self.current()["results_visible"])
        self.respond("S", {"option_id": "cancel"})
        v = self.wait(lambda v: v["results_visible"])
        self.assertEqual(v["branches"]["N"]["result"]["state"]["settings"]["reply_length"], "detailed")
        self.assertEqual(v["branches"]["S"]["result"]["outcome"], "cancelled")
        self.assertEqual(v["branches"]["S"]["result"]["state"]["settings"]["reply_length"], "balanced")

    def test_free_text_answer_uses_its_own_pending_question(self):
        self.start()
        self.model.raw = answer("c1")
        self.respond(response={"text": "Yes, key points please."})
        self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("interpret"), 2)
        self.assertEqual(self.model.contexts[-1]["pending"]["original_query"], "Change reply length.")
        self.assertEqual(self.model.calls.count("native"), 1)

    def test_unresolved_clarification_asks_again_with_new_id(self):
        self.start()
        old_id = self.current()["branches"]["A"]["question"]["question_id"]
        self.model.resolved = tailoring("brief", "detailed")
        self.respond(response={"option_id": "other", "text": "Still unsure."})
        v = self.settled()
        self.assertNotEqual(v["branches"]["A"]["question"]["question_id"], old_id)
        self.assertFalse(v["results_visible"])
        with self.assertRaises(APIError):
            self.mutate("answer", "A", question_id=old_id, response={"option_id": "c1"})
        self.respond(); self.wait(lambda v: v["results_visible"])

    def test_chat_is_generated_once_but_recorded_in_all_four_branches(self):
        self.model.raw = chat()
        self.mutate("start", query="What is recall?")
        v = self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls, ["interpret", "generate"])
        self.assertTrue(all(len(b["result"]["state"]["conversation"]) == 1 for b in v["branches"].values()))

    def test_single_turn_override_and_followup_keep_scope(self):
        self.model.raw = tailoring("brief", kind="mixed", scope="turn", conversation_query="What is recall?")
        self.mutate("start", query="Just this answer, key points: what is recall?"); self.settled()
        self.respond(); v = self.wait(lambda v: v["results_visible"])
        e = v["branches"]["E"]["result"]["state"]
        self.assertEqual(e["settings"]["reply_length"], "balanced")
        self.assertEqual(e["conversation"][0]["settings"]["reply_length"], "brief")
        first = deepcopy(v["first_reveal"])
        self.model.raw = chat()
        self.mutate("request", "E", query="Why does it help?")
        v = self.settled()
        self.assertEqual(v["branches"]["E"]["result"]["state"]["conversation"][-1]["settings"]["reply_length"], "balanced")
        self.assertEqual(v["first_reveal"], first)
        self.assertEqual(len(v["branches"]["A"]["result"]["state"]["conversation"]), 1)

    def test_controls_and_undo_are_branch_local_after_reveal(self):
        self.start(); self.respond(); self.wait(lambda v: v["results_visible"])
        self.mutate("settings", "E", patch={"reply_length": "detailed"}); v = self.settled()
        self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["reply_length"], "detailed")
        self.assertEqual(v["branches"]["S"]["result"]["state"]["settings"]["reply_length"], "brief")
        self.mutate("undo", "E", field="reply_length"); v = self.settled()
        self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["reply_length"], "brief")

    def test_controls_cannot_bypass_initial_barrier(self):
        self.start()
        for op, payload in (("settings", {"patch": {"reply_length": "detailed"}}), ("request", {"query": "Do something else"})):
            with self.assertRaises(APIError) as error: self.mutate(op, "E", **payload)
            self.assertEqual(error.exception.code, "results_hidden")

    def test_generation_failure_preserves_commit_and_retry_does_not_apply_twice(self):
        self.model.answer_result = ModelError("Fixture failure")
        v = self.start(mixed=True)
        self.assertEqual(v["branches"]["E"]["status"], "failed")
        self.assertEqual(self.model.calls.count("generate"), 1)
        self.assertNotIn("HIDDEN_", json.dumps(v))
        self.model.answer_result = parts("Recovered")
        for c in ("E", "N", "S"):
            self.mutate("retry", c)
        self.settled(); self.respond(); v = self.wait(lambda v: v["results_visible"])
        for b in v["branches"].values():
            self.assertEqual(len(b["result"]["state"]["changes"]), 1)
            self.assertEqual(len(b["result"]["state"]["conversation"]), 1)
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("native"), 1)
        self.assertEqual(self.model.calls.count("generate"), 2)

    def test_invalid_generated_json_can_be_explicitly_retried(self):
        self.model.answer_result = {"unexpected": "not an answer"}
        self.start(mixed=True)
        self.model.answer_result = parts("Valid now")
        for c in ("E", "N", "S"): self.mutate("retry", c)
        self.settled(); self.respond(); self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("generate"), 2)

    def test_shared_failure_retry_occurs_once_for_all_branches(self):
        self.model.raw = ModelError("Interpretation failed")
        self.mutate("start", query="Key points please"); v = self.settled()
        self.assertTrue(all(b["status"] == "failed" for b in v["branches"].values()))
        self.assertEqual(self.model.calls.count("interpret"), 1)
        with self.assertRaises(APIError): self.mutate("retry", "E")
        self.model.raw = tailoring("brief")
        self.mutate("retry_shared", expected_attempt=v["shared_preparation"]["attempt"])
        self.settled(); self.respond(); self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("interpret"), 2)

    def test_shared_retry_cannot_restart_explicitly_stopped_task(self):
        self.model.raw = ModelError("Interpretation failed")
        self.mutate("start", query="Key points please")
        v = self.settled()
        for c in ("E", "A", "N", "S"):
            self.mutate("stop", c)
        self.assertTrue(self.current()["results_visible"])
        with self.assertRaises(APIError) as raised:
            self.mutate("retry_shared", expected_attempt=v["shared_preparation"]["attempt"])
        self.assertEqual(raised.exception.code, "no_pending_shared_work")
        self.assertEqual(self.model.calls.count("interpret"), 1)

    def test_native_failure_is_isolated_and_retry_keeps_shared_input(self):
        self.model.native = ModelError("Native failed")
        self.start()
        self.assertEqual(self.current()["branches"]["N"]["status"], "failed")
        self.respond(); self.settled()
        self.assertFalse(self.current()["results_visible"])
        self.model.native = {"decision": "ACT", "reason": "Recovered"}
        self.mutate("retry", "N"); self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("native"), 2)

    def test_stop_pending_branch_is_explicitly_incomplete(self):
        self.start()
        self.mutate("stop", "A"); v = self.wait(lambda v: v["results_visible"])
        self.assertEqual(v["branches"]["A"]["result"]["outcome"], "incomplete")
        self.assertEqual(v["branches"]["A"]["result"]["state"]["settings"]["reply_length"], "balanced")

    def test_idempotent_create_start_answer_and_conflicting_id(self):
        replay = self.app.create({"request_id": "create", "task_code": "TASK"})
        self.assertEqual(replay["task_id"], self.task_id)
        start = {"request_id": "start", "expected_revision": 0, "query": "Key points"}
        self.app.mutate(self.task_id, "start", start); self.settled()
        self.assertTrue(self.app.mutate(self.task_id, "start", start)["idempotent_replay"])
        v = self.current(); a = v["branches"]["A"]
        payload = {"request_id": "answer", "expected_branch_revision": a["branch_revision"], "question_id": a["question"]["question_id"], "response": {"option_id": "c1"}}
        self.app.mutate(self.task_id, "answer", payload, "A"); self.wait(lambda v: v["results_visible"])
        replay = self.app.mutate(self.task_id, "answer", payload, "A")
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(len(replay["branches"]["A"]["result"]["state"]["changes"]), 1)
        with self.assertRaises(APIError): self.app.mutate(self.task_id, "answer", {**payload, "response": {"option_id": "cancel"}}, "A")
        self.assertEqual(self.model.calls.count("interpret"), 1)

    def test_slow_native_does_not_block_get_or_other_branches(self):
        entered, release = threading.Event(), threading.Event()
        def native(context):
            entered.set(); release.wait(5)
            return {"decision": "ACT", "reason": "Released"}, []
        self.model.decide_tutor = native
        self.mutate("start", query="Key points")
        try:
            self.assertTrue(entered.wait(2))
            v = self.wait(lambda v: v["branches"]["E"]["status"] == "waiting" and v["branches"]["A"]["question"] is not None)
            self.assertEqual(v["branches"]["N"]["status"], "processing")
            self.assertFalse(v["results_visible"])
        finally: release.set()
        self.settled()

    def test_close_during_provider_call_discards_late_results_and_records_call(self):
        entered, release = threading.Event(), threading.Event()
        original = self.model.interpret_tutor
        def slow(context):
            entered.set(); release.wait(5); return original(context)
        self.model.interpret_tutor = slow
        self.mutate("start", query="Key points")
        try:
            self.assertTrue(entered.wait(2))
            self.mutate("close")
        finally: release.set()
        self.app.pool.shutdown(wait=True)
        v = self.current()
        self.assertEqual(v["phase"], "closed")
        self.assertFalse(v["results_visible"])
        records = self.logs()
        self.assertEqual(len([r for r in records if r["event"] == "provider_finished"]), 1)

    def logs(self):
        return [json.loads(line) for line in (self.app.log_dir / (self.task_id + ".jsonl")).read_text().splitlines()]

    def test_audit_records_shared_call_once_and_first_reveal_once(self):
        self.start(mixed=True); self.respond(); self.wait(lambda v: v["results_visible"])
        logs = self.logs()
        self.assertEqual(len([r for r in logs if r["event"] == "shared_prepared"]), 1)
        self.assertEqual(len([r for r in logs if r["event"] == "first_reveal"]), 1)
        methods = [r["method"] for r in logs if r["event"] == "provider_finished"]
        self.assertCountEqual(methods, ["interpret_tutor", "decide_tutor", "generate_tutor"])

    def test_failed_reveal_audit_keeps_results_hidden_until_explicit_retry(self):
        original = self.app._log
        def failing(rt, event, **payload):
            if event == "first_reveal": raise OSError("Fixture disk error")
            return original(rt, event, **payload)
        with patch.object(self.app, "_log", side_effect=failing):
            self.start(); self.respond(); v = self.settled()
            self.assertFalse(v["results_visible"])
            self.assertEqual(v["publication_error"], "audit_unavailable")
        self.mutate("retry_reveal"); self.assertTrue(self.current()["results_visible"])

    def test_private_metadata_invalid_controls_and_formal_mode_are_rejected(self):
        for data in ({"phase": "formal"}, {"private_goal": "brief"}, {"public_setup": [{"kind": "setting", "patch": {}, "query": "public", "scores": [7]}]}):
            with self.assertRaises(APIError): self.app.create({"request_id": uuid.uuid4().hex, **data})
        self.start()
        with self.assertRaises(APIError):
            self.app.mutate(self.task_id, "select", {"request_id": "bad-select", "expected_revision": self.current()["revision"], "condition": "bad"})
        self.assertNotIn("HIDDEN_", json.dumps(self.current()))

    def test_error_response_does_not_leak_early_completed_result(self):
        self.start(mixed=True)
        with self.assertRaises(APIError) as error:
            self.app.mutate(self.task_id, "answer", {"request_id": "stale-answer", "expected_branch_revision": 0,
                                                    "question_id": "old", "response": {"option_id": "c1"}}, "A")
        body = error.exception.body()
        self.assertNotIn("HIDDEN_", json.dumps(body))
        self.assertFalse(body["results_visible"])
        self.assertTrue(all(b["result"] is None for b in body["branches"].values()))

    def test_shared_audit_failure_retries_cached_interpretation_without_new_call(self):
        original = self.app._log
        def failing(rt, event, **payload):
            if event == "shared_prepared": raise OSError("Fixture audit failure")
            return original(rt, event, **payload)
        with patch.object(self.app, "_log", side_effect=failing):
            self.mutate("start", query="Key points"); v = self.settled()
            self.assertEqual(v["shared_preparation"]["status"], "failed")
        self.mutate("retry_shared", expected_attempt=1); self.settled()
        self.respond(); self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("interpret"), 1)

    def test_checkpoint_failure_never_publishes_unlogged_edit(self):
        original = self.app._log
        def failing(rt, event, **payload):
            if event == "branch_checkpoint" and payload.get("condition") == "E": raise OSError("Fixture checkpoint failure")
            return original(rt, event, **payload)
        with patch.object(self.app, "_log", side_effect=failing):
            self.start()
            self.assertEqual(self.current()["branches"]["E"]["status"], "failed")
            rb = self.app.get(self.task_id).branches["E"]
            self.assertEqual(rb.session.state.snapshot()["settings"]["reply_length"], "balanced")
        self.mutate("retry", "E"); self.settled(); self.respond()
        v = self.wait(lambda v: v["results_visible"])
        self.assertEqual(len(v["branches"]["E"]["result"]["state"]["changes"]), 1)
        self.assertEqual(self.model.calls.count("interpret"), 1)

    def test_different_effective_generation_context_is_not_reused(self):
        self.model.raw = tailoring("brief", "detailed", kind="mixed", conversation_query="What is recall?")
        self.mutate("start", query="Change the structure and explain recall."); self.settled()
        self.respond("A", {"option_id": "c2"}); self.settled()
        self.respond("S", {"option_id": "c1"}); v = self.wait(lambda v: v["results_visible"])
        e = v["branches"]["E"]["result"]["state"]["conversation"][0]
        a = v["branches"]["A"]["result"]["state"]["conversation"][0]
        self.assertEqual(e["settings"]["reply_length"], "brief")
        self.assertEqual(a["settings"]["reply_length"], "detailed")
        self.assertNotEqual(e["messages"][1]["content"], a["messages"][1]["content"])
        self.assertEqual(self.model.calls.count("generate"), 2)

    def test_public_history_seed_is_shared_but_private_task_metadata_is_not(self):
        v = self.app.create({"request_id": "seeded", "task_code": "PRIVATE_CODE",
                             "soft_preferences": ["I prefer a friendly style."],
                             "public_setup": [{"kind": "setting", "patch": {"reply_length": "detailed"}, "query": "Detailed replies please"},
                                              {"kind": "exchange", "user": "Earlier question", "assistant": "Earlier answer"}]})
        self.task_id = v["task_id"]
        self.mutate("start", query="Key points now"); self.settled()
        context = next(c for c in self.model.contexts if "interpretation" not in c)
        self.assertEqual(context["settings"]["reply_length"], "detailed")
        self.assertEqual(context["conversation"][0]["messages"][1]["content"], "Earlier answer")
        self.assertNotIn("PRIVATE_CODE", json.dumps(context))

    def test_stop_during_generation_invalidates_late_branch_result(self):
        entered, release = threading.Event(), threading.Event()
        original = self.model.generate_tutor
        def slow(context):
            entered.set(); release.wait(5); return original(context)
        self.model.generate_tutor = slow
        self.model.raw = tailoring("brief", kind="mixed", conversation_query="What is recall?")
        self.mutate("start", query="Key points and explain recall")
        try:
            self.assertTrue(entered.wait(2))
            self.mutate("stop", "E")
        finally: release.set()
        self.settled(); self.respond(); v = self.wait(lambda v: v["results_visible"])
        self.assertEqual(v["branches"]["E"]["result"]["outcome"], "incomplete")
        self.assertEqual(v["branches"]["E"]["result"]["state"]["conversation"], [])
        self.assertEqual(len(v["branches"]["S"]["result"]["state"]["conversation"]), 1)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.server = Server(("127.0.0.1", 0), Experiment(self.model, self.temp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def http(self, path, data=None):
        request = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=3) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as exc: return exc.code, json.load(exc)

    def test_http_acceptance_polling_privacy_and_private_sessions_inaccessible(self):
        code, v = self.http("/tutor/comparisons", {"request_id": "create"})
        self.assertEqual(code, 200)
        path = "/tutor/comparisons/" + v["task_id"]
        code, v = self.http(path + "/start", {"request_id": "start", "expected_revision": 0, "query": "Only key points"})
        self.assertEqual(code, 202)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            _, v = self.http(path)
            if v["branches"]["A"]["question"]: break
            time.sleep(.005)
        self.assertFalse(v["results_visible"])
        self.assertTrue(all(b["result"] is None for b in v["branches"].values()))
        rt = self.server.comparisons.get(v["task_id"])
        for rb in rt.branches.values():
            self.assertEqual(self.http("/tutor/sessions/" + rb.session.session_id)[0], 404)
        a = v["branches"]["A"]
        code, _ = self.http(path + "/branches/A/answer", {"request_id": "answer", "expected_branch_revision": a["branch_revision"], "question_id": a["question"]["question_id"], "response": {"option_id": "c1"}})
        self.assertEqual(code, 202)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            _, v = self.http(path)
            if v["results_visible"]: break
            time.sleep(.005)
        self.assertTrue(v["results_visible"])
        self.assertEqual(self.http(path + "/raw")[0], 404)
        self.assertEqual(self.http("/tutor/sessions", {"condition": "S"})[0], 200)


if __name__ == "__main__": unittest.main()
