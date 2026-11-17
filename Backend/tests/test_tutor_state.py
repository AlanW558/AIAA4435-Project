"""State invariants only: no model calls, audio, Unity, or participant results."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_state import DEFAULT_SETTINGS, TutorState, validate_settings


class TutorStateTests(unittest.TestCase):
    def setUp(self):
        self.state = TutorState()

    def commit(self, patch, source="request"):
        return self.state.commit(patch, expected_revision=self.state.snapshot()["revision"], source=source)

    def undo(self, field):
        return self.state.undo(field, expected_revision=self.state.snapshot()["revision"])

    def test_baseline_and_detached_snapshots(self):
        initial = deepcopy(DEFAULT_SETTINGS)
        state = TutorState(initial)
        initial["reply_length"] = "brief"
        view = state.snapshot()
        self.assertEqual(view["settings"]["reply_length"], "balanced")
        self.assertEqual(view["settings"]["tone"], "professional")
        self.assertEqual(view["settings"]["accessory"], "glasses")
        view["settings"]["reply_length"] = "detailed"
        self.assertEqual(state.snapshot()["settings"], DEFAULT_SETTINGS)

    def test_length_edit_keeps_every_other_property(self):
        view = self.commit({"reply_length": "brief"})
        self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, "reply_length": "brief"})
        self.assertEqual(view["changes"][0]["patch"], {"reply_length": "brief"})
        self.assertEqual(view["changes"][0]["source"], "request")
        self.assertEqual(view["conversation"], [])

    def test_invalid_edits_are_atomic(self):
        for patch in ({"reply_length": "short"}, {"tone": []}, {"voice": "provider_name"},
                      {"speech_rate": True}, {"speech_rate": float("nan")},
                      {"speech_rate": float("inf")}, {"speech_rate": .69},
                      {"speech_rate": 1.31}, {"speech_rate": 1.081},
                      {"hidden_goal": "brief"},
                      {"reply_length": "brief", "jacket_color": "invisible"},
                      {"avatar_id": "nailong", "outfit": "suit"}):
            with self.subTest(patch=patch):
                before = self.state.snapshot()
                with self.assertRaises(APIError):
                    self.commit(patch)
                self.assertEqual(self.state.snapshot(), before)

    def test_rate_accepts_relative_result_and_unity_float_precision(self):
        self.assertEqual(self.commit({"speech_rate": 1.2 * .9})["settings"]["speech_rate"], 1.08)
        self.assertEqual(self.commit({"speech_rate": 1.0800000429153442})["settings"]["speech_rate"], 1.08)
        for rate in (.7, 1.0, 1.3):
            self.assertEqual(self.commit({"speech_rate": rate})["settings"]["speech_rate"], rate)

    def test_avatar_replacement_preserves_dialogue_and_explicit_overrides(self):
        self.commit({"reply_length": "detailed", "tone": "friendly"})
        view = self.commit({"avatar_id": "nailong", "accessory": "hat"})
        self.assertEqual(view["settings"]["outfit"], "none")
        self.assertEqual(view["settings"]["jacket_color"], "yellow")
        self.assertEqual(view["settings"]["accessory"], "hat")
        self.assertEqual(view["settings"]["reply_length"], "detailed")
        self.assertEqual(view["settings"]["tone"], "friendly")

    def test_undo_one_field_preserves_newer_unrelated_changes(self):
        self.commit({"reply_length": "brief", "jacket_color": "green"})
        self.commit({"tone": "friendly"}, source="direct_control")
        view = self.undo("reply_length")
        self.assertEqual(view["settings"], {**DEFAULT_SETTINGS, "jacket_color": "green", "tone": "friendly"})
        self.assertEqual(view["changes"][0]["remaining_fields"], ["jacket_color"])
        self.assertEqual(view["changes"][-1]["target_change_id"], 1)
        self.assertEqual(view["changes"][0]["after"]["reply_length"], "brief")
        self.undo("jacket_color")
        before = self.state.snapshot()
        with self.assertRaises(APIError):
            self.undo("reply_length")
        self.assertEqual(self.state.snapshot(), before)

    def test_repeated_undo_walks_back_latest_eligible_edits(self):
        self.commit({"reply_length": "brief"})
        self.commit({"reply_length": "detailed"})
        self.assertEqual(self.undo("reply_length")["settings"]["reply_length"], "brief")
        self.assertEqual(self.undo("reply_length")["settings"]["reply_length"], "balanced")

    def test_incompatible_partial_undo_fails_without_consuming_history(self):
        self.commit({"avatar_id": "nailong"})
        self.commit({"avatar_id": "liang"})
        before = self.state.snapshot()
        with self.assertRaises(APIError):
            self.undo("avatar_id")  # Would combine nailong with Liang's suit.
        self.assertEqual(self.state.snapshot(), before)
        restored = self.undo("all")["settings"]
        self.assertEqual((restored["avatar_id"], restored["outfit"]), ("nailong", "none"))

    def test_no_op_does_not_add_fake_change_or_block_previous_undo(self):
        self.commit({"reply_length": "brief"})
        view = self.commit({"reply_length": "brief"})
        self.assertEqual(view["revision"], 2)
        self.assertEqual(len(view["changes"]), 1)
        self.assertEqual(self.undo("reply_length")["settings"]["reply_length"], "balanced")

    def test_conversation_records_generation_settings_without_changing_them(self):
        self.commit({"reply_length": "brief"})
        view = self.state.record_exchange("How should I revise?", "Practise active recall.", expected_revision=1)
        self.assertEqual(len(view["conversation"]), 1)
        self.assertEqual(len(view["changes"]), 1)
        self.assertEqual(view["conversation"][0]["context_revision"], 1)
        self.commit({"reply_length": "detailed"})
        record = self.state.snapshot()["conversation"][0]
        self.assertEqual(record["settings"]["reply_length"], "brief")
        self.assertEqual(record["messages"][1]["role"], "assistant")
        record["messages"][1]["content"] = "mutated copy"
        self.assertEqual(self.state.snapshot()["conversation"][0]["messages"][1]["content"], "Practise active recall.")

    def test_obsolete_response_and_invalid_exchange_leave_no_partial_turn(self):
        self.commit({"reply_length": "brief"})
        for revision, answer in ((0, "An outdated detailed answer."), (1, "")):
            before = self.state.snapshot()
            with self.assertRaises(APIError):
                self.state.record_exchange("Question", answer, expected_revision=revision)
            self.assertEqual(self.state.snapshot(), before)

    def test_sessions_do_not_share_settings_histories_or_undo(self):
        other = TutorState(self.state.snapshot()["settings"])
        self.commit({"reply_length": "brief"})
        self.state.record_exchange("Question", "Answer", expected_revision=1)
        self.assertEqual(other.snapshot()["settings"], DEFAULT_SETTINGS)
        self.assertEqual(other.snapshot()["changes"], [])
        self.assertEqual(other.snapshot()["conversation"], [])

    def test_only_one_concurrent_mutation_with_same_revision_can_commit(self):
        def edit(length):
            try:
                self.state.commit({"reply_length": length}, expected_revision=0, source="request")
                return "committed"
            except APIError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ("brief", "detailed")))
        self.assertCountEqual(results, ["committed", "stale_revision"])
        self.assertEqual(len(self.state.snapshot()["changes"]), 1)

    def test_complete_state_does_not_accept_private_metadata_or_missing_fields(self):
        for settings in ({"reply_length": "brief"}, {**DEFAULT_SETTINGS, "task_goal": "brief"}):
            with self.assertRaises(APIError):
                validate_settings(settings)


if __name__ == "__main__":
    unittest.main()
