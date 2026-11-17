"""Unified appearance execution, keeping dialogue state and reveal isolation."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from tutor_state import DEFAULT_SETTINGS
from test_tutor_generation import GenerationFixture
from test_tutor_multidomain import proposal
from unity_appearance_comparison_fixture_server import AppearanceComparisonFixture


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = GenerationFixture()
        self.app = TutorSessions(self.model, self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def change(self, view, op="request", **data):
        return self.app.mutate(view["session_id"], op, {"request_id": uuid.uuid4().hex, "expected_revision": view["revision"], **data})

    def ask(self, view, patch):
        self.model.raw = proposal(patch)
        return self.change(view, query="Public appearance request")

    def test_outfit_change_preserves_colour_accessory_scale_and_dialogue(self):
        start = {**DEFAULT_SETTINGS, "jacket_color": "purple", "scale": .95, "tone": "friendly", "speech_rate": 1.08, "voice": "voice_a"}
        view = self.ask(self.app.create({"settings": start}), {"outfit": "sport"})
        self.assertEqual(view["settings"], {**start, "outfit": "sport"})
        self.assertEqual(view["changes"][-1]["patch"], {"outfit": "sport"})

    def test_accessories_are_replaced_not_stacked(self):
        view = self.ask(self.app.create({}), {"accessory": "hat"})
        self.assertEqual(view["settings"]["accessory"], "hat")
        self.assertEqual(view["changes"][-1]["before"]["accessory"], "glasses")

    def test_avatar_replacement_and_whole_undo_keep_dialogue(self):
        start = {**DEFAULT_SETTINGS, "tone": "encouraging", "reply_length": "brief", "speech_rate": .9, "voice": "voice_b"}
        view = self.ask(self.app.create({"settings": start}), {"avatar_id": "nailong"})
        self.assertEqual(view["settings"], {**start, "avatar_id": "nailong", "outfit": "none", "jacket_color": "yellow", "accessory": "none"})
        view = self.change(view, "undo", field="all")
        self.assertEqual(view["settings"], start)

    def test_invalid_partial_avatar_undo_is_atomic(self):
        view = self.app.create({"settings": {**DEFAULT_SETTINGS, "avatar_id": "nailong", "outfit": "none"}})
        view = self.ask(view, {"avatar_id": "liang"})
        with self.assertRaises(APIError): self.change(view, "undo", field="avatar_id")
        self.assertEqual(self.app.view(self.app.get(view["session_id"])), view)
        view = self.change(view, "undo", field="all")
        self.assertEqual((view["settings"]["avatar_id"], view["settings"]["outfit"]), ("nailong", "none"))

    def test_scoped_undo_preserves_newer_appearance_and_dialogue(self):
        view = self.ask(self.app.create({}), {"jacket_color": "green", "outfit": "sport"})
        view = self.ask(view, {"scale": 1.05, "tone": "friendly"})
        view = self.change(view, "undo", field="jacket_color")
        self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, "outfit": "sport", "scale": 1.05, "tone": "friendly"})

    def test_avatar_keep_constraints_survive_clarification(self):
        self.model.raw = proposal({"avatar_id": "nailong"}, preserved=["jacket_color", "accessory"])
        view = self.change(self.app.create({"condition": "A"}), query="Nailong, keep colour and glasses")
        self.assertEqual(view["settings"], DEFAULT_SETTINGS)
        self.assertIn("Colour: Blue", view["question"]["options"][0]["label"])
        view = self.change(view, "answer", question_id=view["question"]["question_id"], option_id="c1")
        self.assertEqual((view["settings"]["avatar_id"], view["settings"]["jacket_color"], view["settings"]["accessory"]), ("nailong", "blue", "glasses"))

    def test_invalid_outfit_or_temporary_appearance_cannot_partially_apply_tone(self):
        for raw in (proposal({"avatar_id": "nailong", "outfit": "suit", "tone": "friendly"}),
                    proposal({"jacket_color": "green", "tone": "friendly"}, scope="turn")):
            self.model.raw = raw
            view = self.app.create({})
            with self.assertRaises(APIError): self.change(view, query="Invalid appearance request")
            self.assertEqual(self.app.view(self.app.get(view["session_id"])), view)

    def test_no_appearance_control_api_is_added(self):
        view = self.app.create({})
        with self.assertRaises(APIError): self.change(view, "settings", patch={"jacket_color": "green"})
        self.assertEqual(self.app.view(self.app.get(view["session_id"])), view)

    def test_cancel_appearance_mixed_request_keeps_original_settings(self):
        self.model.raw = proposal({"outfit": "sport"})
        self.model.raw.update(kind="mixed", conversation_query="What is recall?")
        view = self.change(self.app.create({"condition": "A"}), query="Sport outfit. What is recall?")
        self.assertEqual(view["generation_jobs"], [])
        view = self.change(view, "cancel", question_id=view["question"]["question_id"])
        self.assertEqual(view["generation_jobs"][0]["settings"], DEFAULT_SETTINGS)

    def test_four_branch_reveal_repair_and_history_isolation(self):
        service = TutorComparisons(AppearanceComparisonFixture(), self.temp.name)
        try:
            task_id = service.create({"request_id": "new", "domain": "appearance"})["task_id"]
            def current(): return service.view(service.get(task_id))
            def change(op, c=None, **data):
                v = current(); key = "expected_revision" if c is None else "expected_branch_revision"
                revision = v["revision"] if c is None else v["branches"][c]["branch_revision"]
                return service.mutate(task_id, op, {"request_id": uuid.uuid4().hex, key: revision, **data}, c)
            def settled():
                end = time.monotonic() + 5
                while time.monotonic() < end:
                    v = current()
                    if all(b["status"] not in ("processing", "idle") for b in v["branches"].values()): return v
                    time.sleep(.005)
                self.fail("Comparison did not settle")
            change("start", query="Compare a casual look."); v = settled()
            self.assertFalse(v["results_visible"])
            self.assertEqual(v["baseline"]["settings"], DEFAULT_SETTINGS)
            for c, option in (("A", "c2"), ("S", "c1")):
                change("answer", c, question_id=v["branches"][c]["question"]["question_id"], response={"option_id": option})
                v = settled()
                if c == "A": self.assertFalse(v["results_visible"])
            self.assertTrue(v["results_visible"])
            self.assertEqual(v["branches"]["A"]["result"]["state"]["settings"]["accessory"], "none")
            self.assertEqual(v["branches"]["S"]["result"]["state"]["settings"]["outfit"], "sport")
            first = deepcopy(v["first_reveal"])
            change("request", "E", query="Make it green and slightly larger."); settled()
            change("undo", "E", field="jacket_color"); v = settled()
            self.assertEqual(v["branches"]["E"]["result"]["state"]["settings"]["scale"], 1.05)
            self.assertEqual(v["branches"]["S"]["result"]["state"]["settings"]["scale"], 1.0)
            self.assertEqual(v["first_reveal"], first)
        finally: service.shutdown()


if __name__ == "__main__": unittest.main()
