import base64
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_comparison_service import TutorComparisons
from tutor_session import TutorSessions
from tutor_transcription import TutorTranscription
from tutor_audio import TutorAudio
from tutor_dialogue_log import export_rows
from unity_comparison_fixture_server import ComparisonFixture
from test_tutor_transcription import FakeSpeech
from test_tutor_audio import FakeTTS
from test_speech import wav_bytes


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = ComparisonFixture()
        self.app = TutorComparisons(self.model, self.temp.name)
        self.sessions = TutorSessions(self.model, self.temp.name)
        self.id = self.app.create({'request_id': 'create', 'task_code': 'PREP',
                                  'require_preparation': True})['task_id']

    def tearDown(self):
        self.app.shutdown()
        self.temp.cleanup()

    def view(self):
        return self.app.view(self.app.get(self.id))

    def body(self, **values):
        return {'request_id': uuid.uuid4().hex, 'expected_revision': self.view()['revision'], **values}

    def mutate(self, operation, **values):
        return self.app.mutate(self.id, operation, self.body(**values))

    def records(self):
        return [json.loads(line) for p in Path(self.temp.name).rglob('*.jsonl')
                for line in p.read_text().splitlines()]

    def test_shared_controls_reach_all_detached_states_without_starting_model(self):
        settings = {'speech_rate': .87, 'reply_length': 'brief', 'tone': 'friendly', 'voice': 'voice_b'}
        with patch.object(self.model, 'interpret_tutor', side_effect=AssertionError('No model during setup')):
            v = self.mutate('prepare', patch=settings)
        self.assertFalse(v['results_visible'])
        self.assertIsNone(v['initial_query'])
        rt = self.app.get(self.id)
        for name, rb in rt.branches.items():
            self.assertIsNone(v['branches'][name]['result'])
            self.assertEqual(rb.session.state.snapshot(), v['baseline'])
            self.assertEqual(rt.comparison._branches[name].state.snapshot(), v['baseline'])
            for field, value in settings.items():
                self.assertEqual(v['baseline']['settings'][field], value)
        rt.branches['E'].session.state.commit({'tone': 'professional'},
            expected_revision=v['baseline']['revision'], source='direct_control')
        self.assertEqual(rt.branches['A'].session.state.snapshot()['settings']['tone'], 'friendly')
        self.assertEqual(self.view()['baseline']['settings']['tone'], 'friendly')

    def test_start_requires_confirmation_and_confirmation_freezes_baseline(self):
        with self.assertRaisesRegex(APIError, 'Confirm shared settings'):
            self.mutate('start', query='Compare an easier explanation.')
        self.mutate('prepare', patch={'voice': 'voice_a'})
        v = self.mutate('confirm_preparation')
        self.assertTrue(v['preparation_confirmed'])
        with self.assertRaises(APIError): self.mutate('prepare', patch={'voice': 'voice_b'})
        with self.assertRaises(APIError): self.mutate('confirm_preparation')
        started = self.mutate('start', query='Compare an easier explanation.')
        self.assertEqual(started['initial_query'], 'Compare an easier explanation.')
        self.assertEqual(started['baseline']['settings']['voice'], 'voice_a')
        self.assertFalse(started['results_visible'])

    def test_invalid_or_stale_settings_do_not_mutate_baseline(self):
        before = self.view()['baseline']
        for value in ({'outfit': 'suit'}, {}, {'speech_rate': 2}, {'voice': 'unknown'}):
            with self.assertRaises(APIError): self.mutate('prepare', patch=value)
        self.assertEqual(before, self.view()['baseline'])
        stale = self.body(patch={'tone': 'friendly'})
        self.mutate('prepare', patch={'voice': 'voice_a'})
        with self.assertRaises(APIError): self.app.mutate(self.id, 'prepare', stale)
        self.assertEqual(self.view()['baseline']['settings']['tone'], before['settings']['tone'])

    def test_pause_resume_and_closed_preparation(self):
        self.mutate('pause')
        for op, payload in [('prepare', {'patch': {'tone': 'friendly'}}), ('confirm_preparation', {})]:
            with self.assertRaises(APIError): self.mutate(op, **payload)
        self.mutate('resume')
        self.mutate('prepare', patch={'tone': 'friendly'})
        self.mutate('close')
        with self.assertRaises(APIError): self.mutate('confirm_preparation')

    def test_replayed_requests_do_not_duplicate_shared_evidence(self):
        for op, fields in [('prepare', {'patch': {'speech_rate': .9}}), ('confirm_preparation', {})]:
            body = self.body(**fields)
            first = self.app.mutate(self.id, op, body)
            replay = self.app.mutate(self.id, op, body)
            self.assertEqual(first['revision'], replay['revision'])
            self.assertTrue(replay['idempotent_replay'])
        records = self.records()
        for event in ('shared_settings_updated', 'preparation_confirmed'):
            self.assertEqual(sum(r['event'] == event for r in records), 1)
        kinds = [row['kind'] for row in export_rows(enumerate(records, 1))]
        self.assertIn('shared_settings_updated', kinds)
        self.assertIn('preparation_confirmed', kinds)

    def test_audit_failure_does_not_publish_settings_or_confirmation(self):
        before = self.view()
        original = self.app._log
        def fail(rt, event, **payload):
            if event in ('shared_settings_updated', 'preparation_confirmed'): raise OSError('test')
            return original(rt, event, **payload)
        with patch.object(self.app, '_log', side_effect=fail):
            for op, fields in [('prepare', {'patch': {'tone': 'friendly'}}), ('confirm_preparation', {})]:
                with self.assertRaises(APIError): self.mutate(op, **fields)
        self.assertEqual(self.view()['baseline'], before['baseline'])
        self.assertEqual(self.view()['revision'], before['revision'])
        self.assertFalse(self.view()['preparation_confirmed'])

    def test_stt_does_not_call_provider_before_confirmation(self):
        fake = FakeSpeech()
        stt = TutorTranscription(self.sessions, self.app, fake)
        def body():
            return self.body(condition='E', question_id='', audio_base64=base64.b64encode(wav_bytes()).decode())
        with self.assertRaises(APIError): stt.transcribe('comparisons', self.id, body())
        self.assertEqual(fake.calls, 0)
        self.mutate('confirm_preparation')
        self.assertEqual(stt.transcribe('comparisons', self.id, body())['text'], fake.text)
        self.assertEqual(fake.calls, 1)

    def test_sample_uses_shared_settings_and_discards_late_audio(self):
        fake = FakeTTS()
        audio = TutorAudio(self.sessions, self.app, fake)
        self.mutate('prepare', patch={'voice': 'voice_b', 'speech_rate': .9})
        def body(): return self.body(condition='E', purpose='sample', exchange_id=0)
        self.assertEqual(audio.synthesize('comparisons', self.id, body()), wav_bytes())
        self.assertEqual(fake.calls[0][1]['voice'], 'voice_b')
        ready = [r for r in self.records() if r['event'] == 'audio_ready'][0]
        self.assertEqual(ready['settings_scope'], 'shared_preparation')
        fake.hook = lambda: self.mutate('prepare', patch={'voice': 'voice_a'})
        with self.assertRaises(APIError): audio.synthesize('comparisons', self.id, body())
        self.assertEqual(sum(r['event'] == 'audio_ready' for r in self.records()), 1)

    def test_invalid_requirement_type_rejected(self):
        with self.assertRaises(APIError):
            self.app.create({'request_id': 'bad-create', 'task_code': 'BAD', 'require_preparation': 'true'})

    def test_next_task_requires_fresh_confirmation_and_own_baseline(self):
        from test_tutor_lifecycle import answers
        def wait_until(predicate):
            end = time.monotonic() + 5
            while not predicate(self.view()) and time.monotonic() < end: time.sleep(.005)
            self.assertTrue(predicate(self.view()))
        self.mutate('prepare', patch={'voice': 'voice_a'})
        self.mutate('confirm_preparation')
        self.mutate('start', query='Compare an easier explanation.')
        for condition in ('A', 'S'):
            wait_until(lambda v: all(b['status'] not in ('idle', 'processing') for b in v['branches'].values()))
            b = self.view()['branches'][condition]
            if b['status'] == 'awaiting_clarification':
                self.app.mutate(self.id, 'answer', {'request_id': uuid.uuid4().hex,
                    'expected_branch_revision': b['branch_revision'], 'question_id': b['question']['question_id'],
                    'response': {'option_id': 'c1'}}, condition)
        wait_until(lambda v: v['results_visible'])
        for condition, b in self.view()['branches'].items():
            self.app.mutate(self.id, 'feedback', {'request_id': uuid.uuid4().hex,
                'expected_branch_revision': b['branch_revision'], 'expected_feedback_revision': 0,
                'answers': answers()}, condition)
        self.mutate('submit')
        linked = self.mutate('next', next_task={'task_code': 'NEXT', 'domain': 'voice', 'scenario': 'C2'})
        successor = self.app.view(self.app.get(linked['next_task_id']))
        self.assertTrue(successor['preparation_required'])
        self.assertFalse(successor['preparation_confirmed'])
        self.assertEqual(successor['baseline']['settings']['voice'], 'voice_d')
        self.assertEqual(successor['baseline']['changes'], [])


if __name__ == '__main__': unittest.main()
