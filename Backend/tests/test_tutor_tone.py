"""Tone routing, composition, scope and caching; not a linguistic-quality study."""
from concurrent.futures import ThreadPoolExecutor
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
from tutor_comparison_service import TutorComparisons, _AuditedModel
from tutor_generation import TutorGenerator, generation_context
from tutor_session import TutorSessions
from tutor_state import DEFAULT_SETTINGS, TONE_GUIDANCE, TutorState
from test_tutor_generation import GenerationFixture, parts
from test_tutor_multidomain import proposal
from test_tutor_session import chat
from test_tutor_interpretation import tailoring


class ToneFixture(GenerationFixture):
    """Distinct deterministic components prove routing, not model style quality."""
    def generate_tutor(self, context):
        tone = context["tone_style"]["mode"]
        return self._return("generate", context, parts(tone + " key", tone + " reason", tone + " example"))


class ToneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = ToneFixture()
        self.sessions = TutorSessions(self.model, self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def change(self, view, op="request", **data):
        return self.sessions.mutate(view["session_id"], op, {
            "request_id": uuid.uuid4().hex, "expected_revision": view["revision"], **data})

    def request(self, view, patch, scope="session", question="How should I revise?"):
        self.model.raw = proposal(patch, scope=scope)
        if question:
            self.model.raw.update(kind="mixed", conversation_query=question)
        return self.change(view, query="Public tone request")

    def generate(self, view, index=-1):
        return self.change(view, "generate", job_id=view["generation_jobs"][index]["job_id"])

    def chat(self, view):
        self.model.raw = chat()
        return self.change(view, query="Why does that help?")

    def test_nine_tone_length_combinations_compose_only_selected_parts(self):
        for tone in TONE_GUIDANCE:
            for length, count in (("brief", 1), ("balanced", 2), ("detailed", 3)):
                with self.subTest(tone=tone, length=length):
                    view = self.sessions.create({"condition": "E"})
                    view = self.generate(self.request(view, {"tone": tone, "reply_length": length}))
                    expected = "\n\n".join([tone + " key", tone + " reason", tone + " example"][:count])
                    self.assertEqual(view["response"]["text"], expected)
                    self.assertEqual(view["conversation"][-1]["messages"][-1]["content"], expected)
                    context = self.model.contexts[-1]
                    self.assertEqual(context["tone_style"], {"mode": tone, "guidance": TONE_GUIDANCE[tone]})
                    self.assertEqual(set(context), {"query", "reply_structure", "tone_style", "conversation"})

    def test_tone_only_preserves_length_voice_rate_and_appearance(self):
        initial = {**DEFAULT_SETTINGS, "reply_length": "detailed", "speech_rate": 1.2, "jacket_color": "purple"}
        view = self.sessions.create({"settings": initial})
        view = self.generate(self.request(view, {"tone": "friendly"}))
        self.assertEqual(view["settings"], {**initial, "tone": "friendly"})
        self.assertEqual(view["response"]["settings"], view["settings"])
        self.assertNotIn("speech_rate", self.model.contexts[-1])

    def test_persistent_tone_reaches_followup_without_relabeling_history(self):
        view = self.sessions.create({})
        view = self.generate(self.chat(view))
        original = deepcopy(view["conversation"][0])
        view = self.generate(self.request(view, {"tone": "friendly"}))
        view = self.generate(self.chat(view))
        self.assertEqual(view["conversation"][0], original)
        self.assertEqual([c["settings"]["tone"] for c in view["conversation"]], ["professional", "friendly", "friendly"])
        self.assertIn("professional key", self.model.contexts[-1]["conversation"][1]["content"])
        self.assertEqual(self.model.contexts[-1]["tone_style"]["mode"], "friendly")

    def test_single_answer_combination_does_not_change_persistent_settings(self):
        view = self.sessions.create({})
        view = self.generate(self.request(view, {"tone": "encouraging", "reply_length": "brief"}, scope="turn"))
        self.assertEqual(view["settings"], DEFAULT_SETTINGS)
        self.assertEqual(view["response"]["text"], "encouraging key")
        self.assertEqual(view["changes"], [])
        view = self.generate(self.chat(view))
        self.assertEqual(view["response"]["text"], "professional key\n\nprofessional reason")

    def test_standalone_and_noop_tone_reserve_correct_field(self):
        for tone in ("professional", "friendly"):
            view = self.sessions.create({})
            view = self.request(view, {"tone": tone}, scope="turn", question="")
            self.assertEqual(view["next_turn_override"], {"tone": tone})
            self.assertEqual(view["generation_jobs"], [])
            view = self.generate(self.chat(view))
            self.assertEqual(view["response"]["settings"]["tone"], tone)
            self.assertIsNone(view["next_turn_override"])

    def test_explicit_noop_length_in_one_turn_conjunction_is_retained(self):
        view = self.sessions.create({})
        view = self.request(view, {"tone": "friendly", "reply_length": "balanced"}, scope="turn", question="")
        self.assertEqual(view["next_turn_override"], {"tone": "friendly", "reply_length": "balanced"})

    def test_ask_waits_and_cancel_generates_with_unchanged_tone(self):
        view = self.request(self.sessions.create({"condition": "A"}), {"tone": "friendly"})
        self.assertEqual(view["settings"]["tone"], "professional")
        self.assertEqual(view["generation_jobs"], [])
        view = self.change(view, "cancel", question_id=view["question"]["question_id"])
        view = self.generate(view)
        self.assertEqual(view["response"]["settings"]["tone"], "professional")
        self.assertEqual(self.model.calls.count("generate"), 1)

    def test_free_text_confirmation_applies_tone_without_another_gate(self):
        view = self.request(self.sessions.create({"condition": "A"}), {"tone": "friendly"})
        self.model.resolved = proposal({"tone": "encouraging"})
        view = self.change(view, "answer", question_id=view["question"]["question_id"], option_id="other", free_text="Encouraging instead")
        view = self.generate(view)
        self.assertEqual(view["response"]["settings"]["tone"], "encouraging")
        events = [json.loads(line) for line in (self.sessions.log_dir / (view["session_id"] + ".jsonl")).read_text().splitlines()]
        self.assertEqual(sum(e["event"] == "gate_decision" for e in events), 1)

    def test_failed_generation_retry_preserves_one_turn_tone_and_replay(self):
        model = GenerationFixture()
        self.model = model
        self.sessions = TutorSessions(model, self.temp.name)
        view = self.request(self.sessions.create({}), {"tone": "friendly", "reply_length": "brief"}, scope="turn")
        model.answer_result = ModelError("Fixture failure")
        with self.assertRaises(APIError): self.generate(view)
        self.assertEqual(self.sessions.view(self.sessions.get(view["session_id"])), view)
        model.answer_result = parts("A friendly key point.")
        view = self.generate(view)
        self.assertEqual(view["response"]["settings"]["tone"], "friendly")
        self.assertEqual(view["settings"]["tone"], "professional")
        count = model.calls.count("generate")
        view = self.generate(view)
        self.assertEqual(model.calls.count("generate"), count)
        self.assertEqual(len(view["conversation"]), 1)

    def test_queued_answer_keeps_tone_snapshot_after_control_change(self):
        view = self.request(self.sessions.create({}), {"tone": "friendly"})
        view = self.change(view, "settings", patch={"tone": "encouraging"})
        view = self.generate(view)
        self.assertEqual(view["settings"]["tone"], "encouraging")
        self.assertEqual(view["response"]["settings"]["tone"], "friendly")

    def test_scoped_undo_preserves_newer_reply_length_and_clears_pending_override(self):
        view = self.change(self.sessions.create({}), "settings", patch={"tone": "friendly"})
        view = self.change(view, "settings", patch={"reply_length": "detailed"})
        view = self.request(view, {"tone": "encouraging"}, scope="turn", question="")
        view = self.change(view, "undo", field="tone")
        self.assertEqual((view["settings"]["tone"], view["settings"]["reply_length"]), ("professional", "detailed"))
        self.assertIsNone(view["next_turn_override"])

    def test_unsupported_property_cannot_partially_apply_tone(self):
        self.model.raw = tailoring(requested_fields=["tone", "other"])
        view = self.change(self.sessions.create({}), query="Friendly wording and change eye colour")
        self.assertEqual(view["decision"], "UNRESOLVED")
        self.assertEqual(view["settings"], DEFAULT_SETTINGS)
        self.assertEqual(view["generation_jobs"], [])
        for patch in ({}, {"tone": "friendly", "jacket_color": "green"}):
            with self.assertRaises(APIError): self.change(view, "settings", patch=patch)

    def test_cache_reuses_same_tone_but_separates_all_nine_combinations(self):
        adapter = _AuditedModel(self.model, lambda *args, **kwargs: None)
        generator = TutorGenerator(adapter)
        snapshot = TutorState().snapshot()
        jobs = [{"query": "Q", "settings": {**DEFAULT_SETTINGS, "tone": tone, "reply_length": length}}
                for tone in TONE_GUIDANCE for length in ("brief", "balanced", "detailed")]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda job: generator.generate(job, snapshot), jobs * 2))
        self.assertEqual(self.model.calls.count("generate"), 9)
        self.assertEqual([r["answer"] for r in results[:9]], [r["answer"] for r in results[9:]])
        self.assertEqual(len({r["answer"] for r in results}), 9)

    def test_tone_context_uses_job_not_later_state_and_excludes_private_fields(self):
        state = TutorState()
        state.commit({"tone": "encouraging"}, expected_revision=0, source="request")
        snapshot = state.snapshot(); snapshot["task_goal"] = "PRIVATE_GOAL"
        job = {"query": "Q", "settings": {**DEFAULT_SETTINGS, "tone": "friendly"}, "condition": "PRIVATE_S"}
        context = generation_context(job, snapshot)
        self.assertEqual(context["tone_style"]["mode"], "friendly")
        self.assertNotIn("PRIVATE", json.dumps(context))
        self.assertEqual(set(context), {"query", "reply_structure", "tone_style", "conversation"})


class ToneComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = ToneFixture()
        self.app = TutorComparisons(self.model, self.temp.name)
        self.task_id = self.app.create({"request_id": "create", "task_code": "TONE_FIXTURE", "domain": "tone"})["task_id"]

    def tearDown(self):
        self.app.shutdown()
        self.temp.cleanup()

    def current(self):
        return self.app.view(self.app.get(self.task_id))

    def change(self, operation, condition=None, **data):
        view = self.current()
        key = "expected_revision" if condition is None else "expected_branch_revision"
        rev = view["revision"] if condition is None else view["branches"][condition]["branch_revision"]
        return self.app.mutate(self.task_id, operation, {"request_id": uuid.uuid4().hex, key: rev, **data}, condition)

    def wait(self, check):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            view = self.current()
            if check(view): return view
            time.sleep(.005)
        self.fail("Comparison did not settle")

    def settled(self):
        return self.wait(lambda v: all(b["status"] not in ("idle", "processing") for b in v["branches"].values()))

    def start(self):
        self.model.raw = proposal({"tone": "friendly", "reply_length": "brief"})
        self.model.raw.update(kind="mixed", conversation_query="How should I revise?")
        self.change("start", query="Friendly and brief. How should I revise?")
        return self.settled()

    def answer(self, tone=None):
        view = self.current()
        if tone:
            self.model.resolved = proposal({"tone": tone, "reply_length": "brief"})
            response = {"option_id": "other", "text": "Use the requested alternative tone"}
        else:
            response = {"option_id": "c1"}
        self.change("answer", "A", question_id=view["branches"]["A"]["question"]["question_id"], response=response)
        return self.wait(lambda v: v["results_visible"])

    def test_tone_results_wait_for_ask_then_share_equivalent_generation(self):
        view = self.start()
        self.assertFalse(view["results_visible"])
        self.assertTrue(all(b["result"] is None for b in view["branches"].values()))
        self.assertNotIn("friendly key", json.dumps(view))
        view = self.answer()
        self.assertEqual(self.model.calls.count("interpret"), 1)
        self.assertEqual(self.model.calls.count("generate"), 1)
        for branch in view["branches"].values():
            state = branch["result"]["state"]
            self.assertEqual(state["settings"]["tone"], "friendly")
            self.assertEqual(state["conversation"][-1]["messages"][-1]["content"], "friendly key")

    def test_different_clarified_tone_uses_distinct_answer(self):
        self.start()
        view = self.answer("encouraging")
        self.assertEqual(self.model.calls.count("generate"), 2)
        for condition, branch in view["branches"].items():
            tone = "encouraging" if condition == "A" else "friendly"
            self.assertEqual(branch["result"]["state"]["conversation"][-1]["messages"][-1]["content"], tone + " key")

    def test_branch_tone_control_undo_followup_preserve_first_snapshot(self):
        self.start(); view = self.answer()
        first = deepcopy(view["first_reveal"])
        self.change("settings", "E", patch={"tone": "encouraging"}); self.settled()
        self.model.raw = chat()
        self.change("request", "E", query="Why does that help?"); view = self.settled()
        self.assertEqual(view["branches"]["E"]["result"]["state"]["conversation"][-1]["settings"]["tone"], "encouraging")
        self.assertEqual(view["branches"]["S"]["result"]["state"]["settings"]["tone"], "friendly")
        self.assertEqual(view["first_reveal"], first)
        self.change("undo", "E", field="tone"); view = self.settled()
        self.assertEqual(view["branches"]["E"]["result"]["state"]["settings"]["tone"], "friendly")
        self.assertEqual(view["first_reveal"], first)


if __name__ == "__main__":
    unittest.main()
