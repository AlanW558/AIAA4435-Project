from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import MockModel
from server import Server
from speech import SpeechError
from tutor_audio import TutorAudio
from tutor_voice_catalog import SAMPLE_TEXT
from test_speech import wav_bytes
import test_tutor_transcription as stt_tests


class FakeTTS:
    def __init__(self):
        self.calls = []
        self.hook = lambda: None
        self.error = None
    def synthesize(self, text, settings):
        self.calls.append((text, deepcopy(settings)))
        self.hook()
        if self.error: raise self.error
        return {'audio': wav_bytes(), 'cache_hit': False}


class AudioTests(unittest.TestCase):
    tearDown = stt_tests.TranscriptionTests.tearDown
    view = stt_tests.TranscriptionTests.view
    mutate = stt_tests.TranscriptionTests.mutate
    settled = stt_tests.TranscriptionTests.settled

    def setUp(self):
        stt_tests.TranscriptionTests.setUp(self)
        self.tts = FakeTTS()
        self.audio = TutorAudio(self.sessions, self.comparisons, self.tts)

    def body(self, purpose='sample', exchange=0):
        v = self.view()
        return {'request_id': uuid.uuid4().hex, 'expected_revision': v['revision'],
                'condition': v['selected_condition'], 'purpose': purpose, 'exchange_id': exchange}

    def call(self, body=None): return self.audio.synthesize('comparisons', self.id, body or self.body())

    def reveal(self):
        self.mutate('start', query='Compare an easier explanation.'); self.settled()
        for c in ('A', 'S'):
            b = self.view()['branches'][c]
            self.comparisons.mutate(self.id, 'answer', {'request_id': uuid.uuid4().hex,
                'expected_branch_revision': b['branch_revision'], 'question_id': b['question']['question_id'],
                'response': {'option_id': 'c1'}}, c)
            self.settled()
        self.assertTrue(self.view()['results_visible'])

    def test_disabled_does_not_fallback_or_call(self):
        self.audio.speech = None
        with self.assertRaises(APIError) as caught: self.call()
        self.assertEqual(caught.exception.code, 'audio_unconfigured')
        self.assertFalse(self.audio.available)
        self.assertEqual(self.tts.calls, [])

    def test_sample_uses_fixed_text_current_default_settings_without_mutation(self):
        revision = self.view()['revision']; model_calls = list(self.model.calls)
        self.assertEqual(self.call(), wav_bytes())
        text, settings = self.tts.calls[-1]
        self.assertEqual(text, SAMPLE_TEXT)
        self.assertEqual(settings['voice'], 'voice_d')
        self.assertEqual(self.view()['revision'], revision)
        self.assertEqual(self.model.calls, model_calls)

    def test_hidden_reply_and_sample_rejected_before_any_synthesis(self):
        self.mutate('start', query='Compare an easier explanation.'); self.settled()
        for purpose in ('sample', 'reply'):
            with self.assertRaises(APIError) as caught: self.call(self.body(purpose, 0))
            self.assertEqual(caught.exception.code, 'audio_hidden')
        self.assertEqual(self.tts.calls, [])

    def test_wrong_selection_closed_and_paused_rejected(self):
        with self.assertRaises(APIError): self.call({**self.body(), 'condition': 'A'})
        self.mutate('pause')
        with self.assertRaises(APIError): self.call()
        self.mutate('close')
        with self.assertRaises(APIError): self.call()
        self.assertEqual(self.tts.calls, [])

    def test_forged_text_settings_purpose_and_exchange_are_rejected(self):
        for patch in ({'text': 'hidden'}, {'settings': {}}, {'purpose': 'question'}, {'exchange_id': True},
                      {'expected_revision': True}, {'request_id': ''}, {'exchange_id': 4}):
            with self.assertRaises(APIError): self.call({**self.body(), **patch})
        self.assertEqual(self.tts.calls, [])

    def test_reply_uses_recorded_settings_while_sample_uses_current_settings(self):
        self.reveal()
        snapshot = self.view()['branches']['E']['result']['state']; exchange = snapshot['conversation'][-1]
        b = self.view()['branches']['E']
        self.comparisons.mutate(self.id, 'settings', {'request_id': 'voice-change',
            'expected_branch_revision': b['branch_revision'], 'patch': {'voice': 'voice_a', 'speech_rate': 1.2, 'tone': 'friendly'}}, 'E')
        self.settled(); before_calls = list(self.model.calls)
        self.call(self.body('reply', exchange['id']))
        self.assertEqual(self.tts.calls[-1][1], exchange['settings'])
        self.assertEqual(self.tts.calls[-1][0], exchange['messages'][-1]['content'])
        self.call()
        self.assertEqual(self.tts.calls[-1][1]['voice'], 'voice_a')
        self.assertEqual(self.tts.calls[-1][1]['speech_rate'], 1.2)
        self.assertEqual(self.tts.calls[-1][1]['tone'], 'friendly')
        self.assertEqual(self.model.calls, before_calls)
        with self.assertRaises(APIError) as caught: self.call(self.body('reply', 999999))
        self.assertEqual(caught.exception.code, 'reply_not_found')

    def test_pause_during_synthesis_discards_bytes(self):
        self.tts.hook = lambda: self.mutate('pause')
        with self.assertRaises(APIError): self.call()
        self.assertEqual(self.view()['lifecycle'], 'paused')
        self.assertEqual(len(self.tts.calls), 1)
        logs = '\n'.join(p.read_text() for p in Path(self.temp.name).rglob('*.jsonl'))
        self.assertIn('audio_discarded', logs)
        self.assertNotIn('audio_ready', logs)

    def test_failure_is_safe_and_does_not_change_state(self):
        self.tts.error = SpeechError('provider_timeout')
        revision = self.view()['revision']
        with self.assertRaises(APIError) as caught: self.call()
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(self.view()['revision'], revision)
        self.assertEqual(len(self.tts.calls), 1)

    def test_audio_audit_has_snapshot_and_ids_without_binary_or_provider_response(self):
        body = self.body(); self.call(body)
        records = [json.loads(line) for p in Path(self.temp.name).rglob('*.jsonl') for line in p.read_text().splitlines()]
        ready = next(r for r in records if r['event'] == 'audio_ready')
        self.assertEqual(ready['audio_request_id'], body['request_id'])
        self.assertEqual(ready['speech_settings']['voice'], 'voice_d')
        for key in ('audio', 'audio_base64', 'url', 'api_key', 'text'): self.assertNotIn(key, ready)

    def test_single_session_snapshot_and_isolation(self):
        v = self.sessions.create({'condition': 'S'})
        body = {**self.body(), 'condition': 'S', 'expected_revision': v['revision']}
        self.assertEqual(self.audio.synthesize('sessions', v['session_id'], body), wav_bytes())
        self.assertEqual(self.tts.calls[-1][0], SAMPLE_TEXT)
        with self.assertRaises(APIError): self.audio.synthesize('sessions', 'not-found', body)

    def test_one_answer_override_is_spoken_without_replacing_persistent_settings(self):
        v = self.sessions.create({'condition': 'S'})
        session = self.sessions.get(v['session_id'])
        override = {**v['settings'], 'voice': 'voice_b', 'tone': 'encouraging', 'speech_rate': .9}
        state = session.state.record_exchange('What is recall?', 'Recall is retrieving information.',
            expected_revision=v['state_revision'], generation_settings=override)
        body = {**self.body('reply', state['conversation'][-1]['id']), 'condition': 'S', 'expected_revision': v['revision']}
        self.audio.synthesize('sessions', v['session_id'], body)
        self.assertEqual(self.tts.calls[-1][1], override)
        self.assertEqual(session.state.snapshot()['settings'], v['settings'])


class AudioHTTPTests(unittest.TestCase):
    def test_audio_bytes_runtime_capability_and_noncacheable_response(self):
        with tempfile.TemporaryDirectory() as folder:
            tts = FakeTTS(); server = Server(('127.0.0.1', 0), Experiment(MockModel(), folder), speech=tts)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = 'http://127.0.0.1:' + str(server.server_address[1])
            def request(path, data=None):
                return urllib.request.urlopen(urllib.request.Request(base + path,
                    json.dumps(data).encode() if data is not None else None, {'Content-Type': 'application/json'}), timeout=5)
            try:
                with request('/speech/status') as response: self.assertTrue(json.load(response)['audio_available'])
                with request('/tutor/comparisons', {'request_id': 'create'}) as response: v = json.load(response)
                self.assertTrue(v['audio_available'])
                with request('/tutor/comparisons/' + v['task_id'] + '/audio', {'request_id': 'audio',
                    'expected_revision': v['revision'], 'condition': 'E', 'purpose': 'sample', 'exchange_id': 0}) as response:
                    self.assertEqual(response.headers['Content-Type'], 'audio/wav')
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    self.assertEqual(response.read(), wav_bytes())
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
