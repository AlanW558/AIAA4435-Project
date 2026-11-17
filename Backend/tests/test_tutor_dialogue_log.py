"""Text evidence, replay, hidden results and export provenance; no paid calls."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import ModelError
from tutor_dialogue_log import annotate, export_rows
from export_tutor_dialogue import export_file
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from test_tutor_generation import GenerationFixture, parts
from test_tutor_interpretation import tailoring
from test_tutor_session import chat


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.model.answer_result = parts("A tutor answer.")
        self.app = TutorSessions(self.model, self.temp.name)
        self.comparisons = None
        self.i = 0

    def tearDown(self):
        if self.comparisons: self.comparisons.shutdown()
        self.temp.cleanup()

    def mutate(self, v, op, **kw):
        self.i += 1
        return self.app.mutate(v["session_id"], op, {"request_id": f"r{self.i}", "expected_revision": v["revision"], **kw})

    def records(self, path):
        return [json.loads(s) for s in path.read_text().splitlines()]

    def rows(self, path):
        return list(export_rows(enumerate(self.records(path), 1)))

    def path(self, v):
        return self.app.log_dir / (v["session_id"] + ".jsonl")

    def test_default_logging_preserves_exact_input_not_interpreted_query(self):
        self.model.raw = chat("Rewritten query")
        v = self.app.create({"condition": "E", "participant_id": "P01"})
        original = "  My own words — 保留文本.  "
        v = self.mutate(v, "request", query=original)
        v = self.mutate(v, "generate", job_id=v["generation_jobs"][0]["job_id"])
        rows = self.rows(self.path(v))
        users = [r for r in rows if r["role"] == "participant"]
        self.assertEqual([r["text"] for r in users], [original])
        answer = next(r for r in rows if r["kind"] == "answer")
        self.assertEqual(answer["text"], "A tutor answer.")
        self.assertEqual(answer["status"], "generated_not_presentation")
        self.assertEqual(answer["settings"]["tone"], "professional")
        self.assertEqual(answer["request_id"], "r2")
        self.assertTrue(any(r.get("request_id") == "r1" and answer["job_id"] in r.get("queued_job_ids", []) for r in rows))
        self.assertEqual(users[0]["participant_id"], "P01")
        self.assertEqual(users[0]["input_source"], "submitted_text")
        self.assertTrue(any(answer["job_id"] in r.get("completed_job_ids", []) for r in rows))
        self.assertNotIn("dialogue_entries", self.app.view(self.app.get(v["session_id"])))

    def test_same_request_id_and_completed_job_replay_do_not_duplicate_dialogue(self):
        self.model.raw = chat()
        v = self.app.create({"condition": "E"})
        body = {"request_id": "original", "expected_revision": 0, "query": "Hi tutor"}
        v = self.app.mutate(v["session_id"], "request", body)
        self.app.mutate(v["session_id"], "request", body)
        job = v["generation_jobs"][0]["job_id"]
        v = self.mutate(v, "generate", job_id=job)
        v = self.mutate(v, "generate", job_id=job)
        rows = self.rows(self.path(v))
        self.assertEqual(sum(r["kind"] == "request" for r in rows), 1)
        self.assertEqual(sum(r["kind"] == "answer" for r in rows), 1)

    def test_clarification_question_and_free_text_preserved(self):
        v = self.app.create({"condition": "A"})
        v = self.mutate(v, "request", query="Make it easier")
        qid = v["question"]["question_id"]
        v = self.mutate(v, "answer", question_id=qid, option_id="other", free_text="Only a short reason, please.")
        rows = self.rows(self.path(v))
        q = next(r for r in rows if r["kind"] == "clarification")
        a = next(r for r in rows if r["kind"] == "clarification_answer")
        self.assertEqual(q["question_id"], a["question_id"])
        self.assertEqual(a["text"], "Only a short reason, please.")
        self.assertEqual(q["origin"], "controller")
        self.assertTrue(q["options"])

    def test_button_selection_is_not_invented_speech(self):
        v = self.app.create({"condition": "A"})
        v = self.mutate(v, "request", query="Brief please")
        v = self.mutate(v, "answer", question_id=v["question"]["question_id"], option_id="c1")
        selection = next(r for r in self.rows(self.path(v)) if r["kind"] == "option_selection")
        self.assertNotIn("text", selection)
        self.assertEqual(selection["input_source"], "button")

    def test_model_failure_keeps_input_without_fake_reply(self):
        self.model.raw = ModelError("Fixture unavailable")
        v = self.app.create({"condition": "E"})
        with self.assertRaises(APIError): self.mutate(v, "request", query="Please help")
        rows = self.rows(self.path(v))
        self.assertEqual(sum(r["kind"] == "request" for r in rows), 1)
        self.assertEqual(sum(r["kind"] == "answer" for r in rows), 0)
        self.assertTrue(any(r["kind"] == "failure" for r in rows))

    def test_audit_failure_does_not_claim_generated_answer_was_committed(self):
        self.model.raw = chat()
        v = self.mutate(self.app.create({"condition": "E"}), "request", query="Question")
        original = self.app.log
        def log(s, event, **kw):
            if event == "operation_committed": raise OSError("Fixture disk failure")
            original(s, event, **kw)
        with patch.object(self.app, "log", side_effect=log), self.assertRaises(APIError):
            self.mutate(v, "generate", job_id=v["generation_jobs"][0]["job_id"])
        rows = self.rows(self.path(v))
        answer = next(r for r in rows if r["kind"] == "answer")
        self.assertEqual(answer["status"], "generated_not_presentation")
        self.assertFalse(any(answer["job_id"] in r.get("completed_job_ids", []) for r in rows))
        self.assertEqual(self.app.get(v["session_id"]).state.snapshot()["conversation"], [])

    def test_comparison_shared_request_hidden_outputs_and_reveal_links(self):
        app = self.comparisons = TutorComparisons(self.model, self.temp.name)
        self.model.raw = tailoring("brief", kind="mixed", conversation_query="What is recall?")
        v = app.create({"request_id": "create", "task_code": "T01", "domain": "tone", "scenario": "C1"})
        tid = v["task_id"]
        app.mutate(tid, "start", {"request_id": "start", "expected_revision": v["revision"], "query": "My shared words"})
        def wait(predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                view = app.view(app.get(tid))
                if predicate(view): return view
                time.sleep(.005)
            self.fail("Comparison timed out")
        v = wait(lambda x: x["branches"]["E"]["status"] == "waiting" and x["branches"]["A"]["status"] == "awaiting_clarification")
        path = app.log_dir / (tid + ".jsonl")
        rows = self.rows(path)
        self.assertEqual([r["text"] for r in rows if r["kind"] == "request"], ["My shared words"])
        self.assertEqual(next(r for r in rows if r["kind"] == "request")["scope"], "shared")
        self.assertTrue(any(r["kind"] == "answer" and r["scope"] == "E" for r in rows))
        self.assertFalse(v["results_visible"])
        self.assertNotIn("A tutor answer.", json.dumps(v))
        b = v["branches"]["A"]
        app.mutate(tid, "answer", {"request_id": "answer", "expected_branch_revision": b["branch_revision"], "question_id": b["question"]["question_id"], "response": {"option_id": "c1"}}, "A")
        v = wait(lambda x: x["results_visible"])
        rows = self.rows(path)
        self.assertEqual(sum(r["kind"] == "answer" for r in rows), 4)
        self.assertEqual(next(r for r in rows if r["kind"] == "answer" and r["scope"] == "E")["request_id"], "start")
        self.assertEqual(next(r for r in rows if r["kind"] == "answer" and r["scope"] == "A")["request_id"], "answer")
        reveal = next(r for r in rows if r["kind"] == "first_reveal")
        self.assertEqual(reveal["reveal_id"], v["first_reveal"]["reveal_id"])
        self.assertEqual(reveal["branches"]["E"]["branch_revision"], v["branches"]["E"]["branch_revision"])
        self.assertFalse(any(r["kind"] == "panel_presented" for r in rows))
        self.assertEqual(reveal["domain"], "tone")

    def test_feedback_and_presentation_are_evidence_not_dialogue(self):
        records = [annotate({"event": "feedback_saved", "task_id": "t", "condition": "S", "draft": {"feedback_revision": 1, "branch_revision": 4, "reveal_id": "r", "answers": {"note": "My rating reason"}}}),
                   annotate({"event": "panel_presented", "task_id": "t", "condition": "S", "page": "conversation", "branch_revision": 4, "results_visible": True, "reveal_id": "r"})]
        rows = list(export_rows(enumerate(records, 1)))
        self.assertEqual([r["role"] for r in rows], ["evidence", "evidence"])
        self.assertEqual(rows[0]["draft"]["branch_revision"], rows[1]["branch_revision"])
        self.assertNotIn("text", rows[0])

    def test_export_excludes_prompts_keys_and_seed_history(self):
        records = [{"event": "provider_finished", "prompt": "SECRET_PROMPT", "api_key": "SECRET_KEY"},
                   {"event": "comparison_created", "baseline": {"conversation": [{"user": "SEEDED_WORDS"}]}},
                   {"event": "command_received", "request_id": "r", "operation": "start", "data": {"query": "actual input", "private": "SECRET_TARGET"}}]
        rendered = json.dumps(list(export_rows(enumerate(records, 1))))
        self.assertNotIn("SECRET", rendered)
        self.assertNotIn("SEEDED_WORDS", rendered)
        self.assertIn("actual input", rendered)

    def test_bad_input_does_not_break_audit_projection(self):
        for response in (None, "bad", 3, []):
            record = annotate({"event": "command_received", "operation": "answer", "data": {"response": response}})
            self.assertNotIn("dialogue_entries", record)
        record = annotate({"event": "operation_started", "operation": "request", "input": {}})
        self.assertNotIn("dialogue_entries", record)

    def test_export_is_stable_and_never_overwrites_evidence(self):
        self.model.raw = chat()
        v = self.mutate(self.app.create({"condition": "E"}), "request", query="Exact words")
        source = self.path(v)
        destination = Path(self.temp.name) / "dialogue.jsonl"
        self.assertGreater(export_file(source, destination), 0)
        rows = self.records(destination)
        self.assertTrue(all(r["source_file"] == source.name and r["source_line"] > 0 for r in rows))
        with self.assertRaises(FileExistsError): export_file(source, destination)
        with self.assertRaises(ValueError): export_file(source, source)
        self.assertEqual(rows, self.records(destination))

    def test_checkpoint_identifies_exact_answer_when_one_job_has_multiple_attempts(self):
        records = [{"event": "answer_generated", "job_id": "j", "answer": "Uncommitted output"},
                   {"event": "answer_generated", "job_id": "j", "answer": "Committed output"},
                   {"event": "operation_committed", "request_id": "r", "result": {"revision": 1, "generation_jobs": [
                       {"job_id": "j", "status": "completed", "answer": "Committed output", "exchange_id": 1}]}}]
        rows = list(export_rows(enumerate(records, 1)))
        answers = [r for r in rows if r["kind"] == "answer"]
        checkpoint = next(r for r in rows if r["kind"] == "checkpoint")
        digest = checkpoint["completed_answers"][0]["text_sha256"]
        self.assertEqual([r["text"] for r in answers if r["text_sha256"] == digest], ["Committed output"])

    def test_truncated_source_is_reported_not_silently_omitted(self):
        source = Path(self.temp.name) / "bad.jsonl"
        source.write_text('{"event":"partial"')
        destination = Path(self.temp.name) / "out.jsonl"
        with self.assertRaises(json.JSONDecodeError): export_file(source, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__": unittest.main()
