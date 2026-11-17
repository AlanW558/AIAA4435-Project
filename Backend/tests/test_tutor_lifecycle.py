"""Debug task lifecycle, survey-version integrity and next-task isolation."""
from copy import deepcopy
import json
import threading
import time
import unittest
from unittest.mock import patch
import uuid
import test_tutor_comparison_service as common
from core import APIError
from test_tutor_interpretation import tailoring
from test_tutor_session import chat


def answers(completion="fully_met", score=4):
    return {"completion": completion, "ratings": {"q" + str(i): score for i in range(2, 8)}}


class LifecycleTests(unittest.TestCase):
    setUp = common.ServiceTests.setUp
    tearDown = common.ServiceTests.tearDown
    current = common.ServiceTests.current
    mutate = common.ServiceTests.mutate
    wait = common.ServiceTests.wait
    settled = common.ServiceTests.settled
    start = common.ServiceTests.start
    respond = common.ServiceTests.respond

    def reveal(self):
        self.start(mixed=True); self.respond()
        return self.wait(lambda v: v["results_visible"])

    def rate(self, c, value=None):
        return self.mutate("feedback", c, expected_feedback_revision=self.current()["feedback"][c]["feedback_revision"], answers=answers() if value is None else value)

    def rate_all(self):
        for c in ("E", "A", "N", "S"): self.rate(c)

    def rejected(self, code, fn):
        with self.assertRaises(APIError) as error: fn()
        self.assertEqual(error.exception.code, code)

    def logs(self):
        path = self.app.log_dir / (self.task_id + ".jsonl")
        return [json.loads(l) for l in path.read_text().splitlines()]

    def test_missing_feedback_blocks_submit_and_next(self):
        self.reveal()
        self.rejected("feedback_required", lambda: self.mutate("submit"))
        self.rejected("submission_required", lambda: self.mutate("next", next_task={}))
        self.assertFalse(self.current()["can_submit"])

    def test_feedback_rejected_until_reveal_without_leaking_hidden_results(self):
        self.start(mixed=True)
        self.rejected("result_not_ready", lambda: self.rate("E"))
        self.assertNotIn("HIDDEN_ANSWER", json.dumps(self.current()))

    def test_partial_answers_remain_missing_not_midpoint_or_unjudge(self):
        self.reveal(); self.rate("E", {"ratings": {"q2": 4}})
        f = self.current()["feedback"]["E"]
        self.assertFalse(f["complete"])
        self.assertEqual(f["draft"]["answers"]["ratings"], {"q2": 4})
        self.assertNotIn("completion", f["draft"]["answers"])

    def test_unable_to_judge_is_valid_and_never_fake_success(self):
        self.reveal()
        for c in ("E", "A", "N", "S"): self.rate(c, answers("unable_to_judge", "unable_to_judge"))
        self.assertTrue(self.current()["can_submit"])
        self.mutate("submit")
        self.assertEqual(self.current()["lifecycle"], "submitted")
        saved = self.app.get(self.task_id).submission
        self.assertEqual(saved["feedback"]["E"]["answers"]["completion"], "unable_to_judge")
        self.assertEqual(saved["feedback"]["E"]["answers"]["ratings"]["q2"], "unable_to_judge")

    def test_invalid_scores_and_unknown_audio_fields_are_rejected(self):
        self.reveal()
        for invalid in (0, 8, True, None, 4.5, "4"):
            with self.subTest(invalid=invalid): self.rejected("invalid_rating", lambda: self.rate("E", answers(score=invalid)))
        self.rejected("invalid_feedback", lambda: self.rate("E", {**answers(), "audio": "DO_NOT_SAVE_AUDIO"}))
        self.assertNotIn("DO_NOT_SAVE_AUDIO", json.dumps(self.logs()))

    def test_unconfirmed_text_never_enters_logs(self):
        self.reveal()
        self.rejected("unconfirmed_comment", lambda: self.rate("E", {**answers(), "comment": "UNCONFIRMED_PRIVATE_TEXT"}))
        self.assertNotIn("UNCONFIRMED_PRIVATE_TEXT", json.dumps(self.logs()))
        self.rate("E", {**answers(), "comment": "CONFIRMED_COMMENT", "comment_confirmed": True})
        self.assertIn("CONFIRMED_COMMENT", json.dumps(self.logs()))
        self.assertNotIn("CONFIRMED_COMMENT", json.dumps(self.model.contexts))

    def test_hidden_reasons_are_removed_when_completion_changes(self):
        self.reveal()
        self.rate("E", {**answers("not_met"), "reasons": ["target_mismatch", "not_maintained"]})
        self.assertEqual(self.current()["feedback"]["E"]["draft"]["answers"]["reasons"], ["target_mismatch"])
        self.rate("E", {**answers(), "reasons": ["target_mismatch"]})
        self.assertEqual(self.current()["feedback"]["E"]["draft"]["answers"]["reasons"], [])

    def test_repair_invalidates_only_its_feedback_even_if_setting_unchanged(self):
        self.reveal(); self.rate_all()
        old = deepcopy(self.current()["feedback"])
        self.mutate("settings", "E", patch={"reply_length": "brief"}); self.settled()
        v = self.current()
        self.assertFalse(v["feedback"]["E"]["current"])
        self.assertEqual(v["feedback"]["E"]["draft"], old["E"]["draft"])
        self.assertTrue(all(v["feedback"][c]["current"] for c in ("A", "N", "S")))
        self.rejected("feedback_required", lambda: self.mutate("submit"))
        self.rate("E"); self.assertTrue(self.current()["can_submit"])

    def test_switching_and_presenting_same_result_preserve_feedback(self):
        self.reveal(); self.rate_all()
        v = self.current()
        self.app.mutate(self.task_id, "select", {"request_id": "select", "expected_revision": v["revision"], "condition": "A"})
        self.mutate("presentation", "A", page="history")
        self.assertTrue(self.current()["can_submit"])
        records = [r for r in self.logs() if r["event"] == "panel_presented"]
        self.assertTrue(records[-1]["results_visible"])
        self.assertEqual(records[-1]["reveal_id"], self.current()["first_reveal"]["reveal_id"])

    def test_old_result_and_feedback_revisions_are_rejected(self):
        self.reveal(); v = self.current()
        payload = {"request_id": "rating", "expected_branch_revision": v["branches"]["E"]["branch_revision"], "expected_feedback_revision": 0, "answers": answers()}
        self.app.mutate(self.task_id, "feedback", payload, "E")
        self.assertTrue(self.app.mutate(self.task_id, "feedback", payload, "E")["idempotent_replay"])
        self.rejected("stale_feedback", lambda: self.app.mutate(self.task_id, "feedback", {**payload, "request_id": "another"}, "E"))
        self.mutate("settings", "E", patch={"reply_length": "detailed"}); self.settled()
        self.rejected("stale_revision", lambda: self.app.mutate(self.task_id, "feedback", {**payload, "request_id": "old-result"}, "E"))

    def test_pause_is_independent_of_questionnaire_and_blocks_commands(self):
        self.start(); self.mutate("pause")
        v = self.current()
        self.assertEqual(v["lifecycle"], "paused")
        self.rejected("task_paused", lambda: self.respond())
        self.rejected("task_paused", lambda: self.mutate("stop", "A"))
        self.rejected("task_paused", lambda: self.mutate("submit"))
        self.mutate("resume"); self.respond(); self.wait(lambda v: v["results_visible"])

    def test_pause_defers_first_reveal_until_resume_without_repeating_provider(self):
        entered, release = threading.Event(), threading.Event()
        original = self.model.generate_tutor
        def slow(context): entered.set(); release.wait(5); return original(context)
        self.model.generate_tutor = slow
        self.model.raw = chat("Recall?")
        self.mutate("start", query="Explain recall")
        try:
            self.assertTrue(entered.wait(2)); self.mutate("pause")
        finally: release.set()
        rt = self.app.get(self.task_id)
        deadline = time.monotonic() + 5
        while not rt.comparison.participant_view()["can_reveal"] and time.monotonic() < deadline: time.sleep(.005)
        self.assertTrue(rt.comparison.participant_view()["can_reveal"])
        self.assertFalse(self.current()["results_visible"])
        self.assertNotIn("first_reveal", [r["event"] for r in self.logs()])
        self.mutate("resume")
        self.wait(lambda v: v["results_visible"])
        self.assertEqual(self.model.calls.count("generate"), 1)

    def test_pause_freezes_already_visible_result_during_repair(self):
        self.reveal()
        entered, release = threading.Event(), threading.Event()
        original = self.model.generate_tutor
        def slow(context): entered.set(); release.wait(5); return original(context)
        self.model.generate_tutor = slow
        self.model.raw = chat("Another question")
        self.mutate("request", "E", query="Another question")
        try:
            self.assertTrue(entered.wait(2)); self.mutate("pause")
            frozen = deepcopy(self.current()["branches"]["E"])
        finally: release.set()
        rt = self.app.get(self.task_id)
        deadline = time.monotonic() + 5
        while rt.comparison.participant_view()["branches"]["E"]["status"] == "processing" and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertEqual(self.current()["branches"]["E"], frozen)
        self.mutate("resume")
        self.assertEqual(len(self.current()["branches"]["E"]["result"]["state"]["conversation"]), 2)

    def test_paused_time_excluded_and_exit_without_feedback_is_aborted(self):
        self.mutate("pause")
        rt = self.app.get(self.task_id)
        rt.paused_at -= 10; rt.started_at -= 10
        self.assertGreaterEqual(self.current()["elapsed_paused_seconds"], 10)
        self.assertLess(self.current()["elapsed_active_seconds"], 2)
        self.mutate("close")
        self.assertEqual(self.current()["lifecycle"], "aborted")
        self.assertIsNone(self.current()["submission_id"])
        self.rejected("task_closed", lambda: self.mutate("next", next_task={}))

    def test_submit_freezes_snapshot_and_exact_replay_is_idempotent(self):
        self.reveal(); self.rate_all()
        data = {"request_id": "submit", "expected_revision": self.current()["revision"]}
        first = self.app.mutate(self.task_id, "submit", data)
        replay = self.app.mutate(self.task_id, "submit", data)
        self.assertEqual(first["submission_id"], replay["submission_id"])
        self.rejected("task_closed", lambda: self.mutate("settings", "E", patch={"reply_length": "detailed"}))
        self.assertEqual(sum(r["event"] == "task_submitted" for r in self.logs()), 1)

    def test_next_uses_fresh_baseline_and_preserves_series_without_answers(self):
        self.reveal(); self.rate_all(); self.mutate("submit")
        old = self.current()
        spec = {"task_code": "NEXT", "domain": "reply_length", "scenario": "C2"}
        data = {"request_id": "next", "expected_revision": old["revision"], "next_task": spec}
        v = self.app.mutate(self.task_id, "next", data)
        replay = self.app.mutate(self.task_id, "next", data)
        self.assertEqual(v["next_task_id"], replay["next_task_id"])
        new = self.app.view(self.app.get(v["next_task_id"]))
        self.assertEqual((new["series_id"], new["sequence_index"], new["previous_task_id"]), (old["series_id"], 2, self.task_id))
        self.assertEqual(new["baseline"]["settings"]["reply_length"], "balanced")
        self.assertEqual(new["baseline"]["conversation"], [])
        self.assertTrue(all(f["draft"] is None for f in new["feedback"].values()))
        self.assertEqual(len(self.app.tasks), 2)
        self.rejected("already_advanced", lambda: self.mutate("next", next_task=spec))

    def test_next_explicit_history_is_shared_and_does_not_enter_previous_task(self):
        self.reveal(); self.rate_all(); self.mutate("submit")
        old = deepcopy(self.app.get(self.task_id).submission)
        v = self.mutate("next", next_task={"task_code": "HISTORY", "domain": "reply_length", "scenario": "C4", "public_setup": [
            {"kind": "setting", "patch": {"reply_length": "detailed"}, "query": "More detail"}]})
        new = self.app.get(v["next_task_id"])
        self.assertEqual(self.app.view(new)["baseline"]["settings"]["reply_length"], "detailed")
        self.assertEqual(self.app.get(self.task_id).submission, old)

    def test_partial_baseline_defaults_do_not_inherit_previous_results(self):
        self.reveal(); self.rate_all(); self.mutate("submit")
        v = self.mutate("next", next_task={"task_code": "PARTIAL", "domain": "reply_length", "scenario": "C3", "settings": {"reply_length": "detailed"}})
        new = self.app.view(self.app.get(v["next_task_id"]))
        from tutor_state import DEFAULT_SETTINGS
        self.assertEqual(new["baseline"]["settings"], {**DEFAULT_SETTINGS, "reply_length": "detailed"})
        self.assertEqual(new["baseline"]["conversation"], [])

    def test_partial_create_still_rejects_unknown_and_incompatible_settings(self):
        from tutor_state import DEFAULT_SETTINGS
        created = self.app.create({"request_id": "partial", "settings": {"reply_length": "brief"}})
        self.assertEqual(created["baseline"]["settings"], {**DEFAULT_SETTINGS, "reply_length": "brief"})
        for settings in (None, {"unknown": "value"}, {"reply_length": "too_long"}, {"avatar_id": "nailong"}):
            with self.subTest(settings=settings):
                with self.assertRaises(APIError): self.app.create({"request_id": uuid.uuid4().hex, "settings": settings})

    def test_feedback_audit_failure_keeps_previous_draft(self):
        self.reveal(); self.rate("E"); before = self.current()["feedback"]["E"]
        original = self.app._log
        def failing(rt, event, **kw):
            if event == "feedback_saved": raise OSError("disk")
            original(rt, event, **kw)
        with patch.object(self.app, "_log", side_effect=failing):
            self.rejected("audit_unavailable", lambda: self.rate("E", answers("not_met")))
        self.assertEqual(self.current()["feedback"]["E"], before)

    def test_submission_audit_failure_does_not_close_or_publish_submission(self):
        self.reveal(); self.rate_all()
        original = self.app._log
        def failing(rt, event, **kw):
            if event == "task_submitted": raise OSError("disk")
            original(rt, event, **kw)
        with patch.object(self.app, "_log", side_effect=failing): self.rejected("audit_unavailable", lambda: self.mutate("submit"))
        self.assertEqual(self.current()["lifecycle"], "active")
        self.mutate("submit"); self.assertEqual(self.current()["lifecycle"], "submitted")

    def test_link_audit_retry_reuses_created_successor(self):
        self.reveal(); self.rate_all(); self.mutate("submit")
        original = self.app._log
        def failing(rt, event, **kw):
            if event == "task_advanced": raise OSError("disk")
            original(rt, event, **kw)
        spec = {"task_code": "NEXT", "domain": "reply_length", "scenario": "C1"}
        with patch.object(self.app, "_log", side_effect=failing): self.rejected("audit_unavailable", lambda: self.mutate("next", next_task=spec))
        self.assertIsNone(self.current()["next_task_id"])
        self.mutate("next", next_task=spec)
        self.assertEqual(len(self.app.tasks), 2)

    def test_presentation_is_not_evidence_of_hearing_or_comprehension(self):
        self.start(mixed=True)
        self.mutate("presentation", "E", page="controls")
        self.rejected("not_selected", lambda: self.mutate("presentation", "A", page="conversation"))
        record = [r for r in self.logs() if r["event"] == "panel_presented"][-1]
        self.assertFalse(record["results_visible"])
        self.assertIsNone(record["reveal_id"])
        self.assertNotIn("heard", record)
        self.assertNotIn("HIDDEN_ANSWER", json.dumps(self.current()))

    def test_presentation_replay_does_not_double_count_exposure(self):
        self.reveal()
        data = {"request_id": "present", "expected_branch_revision": self.current()["branches"]["E"]["branch_revision"], "page": "conversation"}
        self.app.mutate(self.task_id, "presentation", data, "E")
        self.app.mutate(self.task_id, "presentation", data, "E")
        self.assertEqual(sum(r["event"] == "panel_presented" for r in self.logs()), 1)

    def test_pause_audit_failure_does_not_silently_pause(self):
        original = self.app._log
        def failing(rt, event, **kw):
            if event == "task_paused": raise OSError("disk")
            original(rt, event, **kw)
        with patch.object(self.app, "_log", side_effect=failing): self.rejected("audit_unavailable", lambda: self.mutate("pause"))
        self.assertEqual(self.current()["lifecycle"], "active")


class LifecycleHttpTests(unittest.TestCase):
    setUp = common.HttpTests.setUp
    tearDown = common.HttpTests.tearDown
    http = common.HttpTests.http

    def test_http_pause_exit_and_next_without_submission(self):
        _, view = self.http("/tutor/comparisons", {"request_id": "create"})
        path = "/tutor/comparisons/" + view["task_id"]
        code, view = self.http(path + "/pause", {"request_id": "pause", "expected_revision": view["revision"]})
        self.assertEqual((code, view["lifecycle"]), (202, "paused"))
        code, _ = self.http(path + "/start", {"request_id": "blocked", "expected_revision": view["revision"], "query": "Hello"})
        self.assertEqual(code, 409)
        code, view = self.http(path + "/close", {"request_id": "exit", "expected_revision": view["revision"]})
        self.assertEqual((code, view["lifecycle"]), (202, "aborted"))
        code, _ = self.http(path + "/next", {"request_id": "next", "expected_revision": view["revision"], "next_task": {}})
        self.assertEqual(code, 409)

    def test_http_feedback_does_not_enter_model_and_next_follows_submission(self):
        self.model.raw = chat("Recall?")
        _, v = self.http("/tutor/comparisons", {"request_id": "create"})
        path = "/tutor/comparisons/" + v["task_id"]
        self.http(path + "/start", {"request_id": "start", "expected_revision": v["revision"], "query": "Recall?"})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, v = self.http(path)
            if v["results_visible"]: break
            time.sleep(.005)
        self.assertTrue(v["results_visible"])
        for c in ("E", "A", "N", "S"):
            code, v = self.http(path + "/branches/" + c + "/feedback", {"request_id": "rate-" + c, "expected_branch_revision": v["branches"][c]["branch_revision"], "expected_feedback_revision": 0,
                "answers": {**answers("not_met"), "comment": "PRIVATE_SURVEY_COMMENT", "comment_confirmed": True}})
            self.assertEqual(code, 202)
        self.assertNotIn("PRIVATE_SURVEY_COMMENT", json.dumps(self.model.contexts))
        code, v = self.http(path + "/submit", {"request_id": "submit", "expected_revision": v["revision"]})
        self.assertEqual((code, v["lifecycle"]), (202, "submitted"))
        code, v = self.http(path + "/next", {"request_id": "next", "expected_revision": v["revision"], "next_task": {"task_code": "NEXT", "domain": "reply_length", "scenario": "C1", "settings": {"reply_length": "detailed"}}})
        self.assertEqual(code, 202)
        code, new = self.http("/tutor/comparisons/" + v["next_task_id"])
        self.assertEqual((code, new["sequence_index"]), (200, 2))
        self.assertEqual(new["baseline"]["settings"]["reply_length"], "detailed")


if __name__ == "__main__": unittest.main()
