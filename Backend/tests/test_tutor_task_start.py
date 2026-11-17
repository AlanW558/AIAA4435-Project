"""Task-start settings are public, immutable and distinct from app defaults."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tutor_state import TutorState, DEFAULT_SETTINGS
from tutor_interpretation import build_context
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from test_tutor_generation import GenerationFixture


class TaskStartTests(unittest.TestCase):
    def test_start_survives_history_window_clone_undo_and_external_mutation(self):
        state = TutorState({**DEFAULT_SETTINGS, 'speech_rate': 1.2})
        for i in range(24):
            state.commit({'speech_rate': .9 if i % 2 else 1.1}, expected_revision=state.snapshot()['revision'], source='direct_control')
        copy = state.clone()
        copy.undo('speech_rate', expected_revision=copy.snapshot()['revision'])
        context = build_context('Restore task start', copy.snapshot())
        self.assertEqual(context['task_start_settings']['speech_rate'], 1.2)
        self.assertEqual(len(context['change_history']), 20)
        context['task_start_settings']['speech_rate'] = .7
        self.assertEqual(copy.snapshot()['task_start_settings']['speech_rate'], 1.2)
        self.assertEqual(state.snapshot()['task_start_settings']['speech_rate'], 1.2)

    def test_comparison_public_setup_is_before_task_start_for_every_private_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            app = TutorComparisons(GenerationFixture(), folder)
            try:
                v = app.create({'request_id': 'create', 'settings': {'speech_rate': 1.2}, 'public_setup': [
                    {'kind': 'setting', 'patch': {'speech_rate': 1.1}, 'query': 'Demonstration before participant starts'}]})
                self.assertEqual(v['baseline']['task_start_settings']['speech_rate'], 1.1)
                rt = app.get(v['task_id'])
                for branch in rt.branches.values():
                    self.assertEqual(branch.session.state.snapshot()['task_start_settings']['speech_rate'], 1.1)
            finally: app.shutdown()

    def test_single_reset_replaces_task_start_with_new_initial_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            app = TutorSessions(GenerationFixture(), folder)
            v = app.create({'settings': {**DEFAULT_SETTINGS, 'speech_rate': 1.2}})
            v = app.mutate(v['session_id'], 'settings', {'request_id': 'edit', 'expected_revision': v['revision'], 'patch': {'speech_rate': .9}})
            self.assertEqual(v['task_start_settings']['speech_rate'], 1.2)
            v = app.mutate(v['session_id'], 'reset', {'request_id': 'reset', 'expected_revision': v['revision'], 'settings': {**DEFAULT_SETTINGS, 'speech_rate': .8}})
            self.assertEqual(v['task_start_settings']['speech_rate'], .8)

    def test_missing_legacy_start_is_unknown_not_default_or_current(self):
        snapshot = TutorState({'speech_rate':1.2, **{k:v for k,v in DEFAULT_SETTINGS.items() if k!='speech_rate'}}).snapshot()
        del snapshot['task_start_settings']
        context = build_context('Restore task start', snapshot)
        self.assertIsNone(context['task_start_settings'])
        self.assertEqual(context['settings']['speech_rate'], 1.2)

    def test_baseline_projection_does_not_pass_private_targets(self):
        snapshot = TutorState().snapshot()
        snapshot['task_start_settings']['private_target'] = 'never-send'
        context = build_context('Question', snapshot)
        self.assertNotIn('private_target', context['task_start_settings'])


if __name__ == '__main__': unittest.main()
