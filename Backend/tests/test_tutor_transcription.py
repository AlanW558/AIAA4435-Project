import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import MockModel
from server import Server
from speech import SpeechError
from tutor_transcription import TutorTranscription
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from test_speech import wav_bytes
from unity_comparison_fixture_server import ComparisonFixture


class FakeSpeech:
    def __init__(self):
        self.calls = 0
        self.text = 'Compare an easier explanation.'
        self.error = None
        self.hook = lambda: None

    def transcribe(self, audio):
        self.calls += 1
        self.hook()
        if self.error: raise self.error
        return {'text': self.text}


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = ComparisonFixture()
        self.sessions = TutorSessions(self.model, self.temp.name)
        self.comparisons = TutorComparisons(self.model, self.temp.name)
        self.fake = FakeSpeech()
        self.gateway = TutorTranscription(self.sessions, self.comparisons, self.fake)
        self.v = self.comparisons.create({'request_id': 'create', 'task_code': 'SPEECH'})
        self.id = self.v['task_id']

    def tearDown(self):
        self.comparisons.shutdown()
        self.temp.cleanup()

    def view(self): return self.comparisons.view(self.comparisons.get(self.id))

    def body(self):
        v = self.view()
        return {'request_id': uuid.uuid4().hex, 'expected_revision': v['revision'],
                'condition': v['selected_condition'],
                'question_id': (v['branches'][v['selected_condition']].get('question') or {}).get('question_id', ''),
                'audio_base64': base64.b64encode(wav_bytes()).decode()}

    def call(self, body=None): return self.gateway.transcribe('comparisons', self.id, body or self.body())

    def mutate(self, op, **payload):
        return self.comparisons.mutate(self.id, op, {'request_id': uuid.uuid4().hex, 'expected_revision': self.view()['revision'], **payload})

    def settled(self):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if all(b['status'] not in ('idle', 'processing') for b in self.view()['branches'].values()): return
            time.sleep(.005)
        self.fail('comparison did not settle')

    def test_review_does_not_start_task_or_log_audio(self):
        body = self.body()
        result = self.call(body)
        self.assertEqual(result['text'], self.fake.text)
        self.assertEqual(self.view()['phase'], 'awaiting_input')
        logs = '\n'.join(p.read_text() for p in Path(self.temp.name).rglob('*.jsonl'))
        self.assertNotIn(body['audio_base64'], logs)
        self.assertNotIn(self.fake.text, logs)
        self.assertNotIn(body['audio_base64'], repr(self.gateway.entries))

    def test_same_recording_replay_and_concurrent_replay_only_call_once(self):
        body = self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: self.call(body), range(4)))
        self.assertTrue(all(v == values[0] for v in values))
        self.assertEqual(self.fake.calls, 1)

    def test_request_id_cannot_be_reused_for_different_context(self):
        body = self.body(); self.call(body)
        self.mutate('select', condition='A')
        new = self.body(); new['request_id'] = body['request_id']
        with self.assertRaisesRegex(APIError, 'already used'): self.call(new)
        self.assertEqual(self.fake.calls, 1)

    def test_failure_is_memoized_without_automatic_retry(self):
        body = self.body(); self.fake.error = SpeechError('provider_timeout')
        for _ in range(2):
            with self.assertRaises(APIError) as caught: self.call(body)
            self.assertEqual(caught.exception.body()['error'], 'provider_timeout')
        self.assertEqual(self.fake.calls, 1)

    def test_stale_or_wrong_question_rejected_before_provider(self):
        for patch in ({'expected_revision': -1}, {'condition': 'A'}, {'question_id': 'wrong'}, {'expected_revision': True}):
            with self.assertRaises(APIError): self.call({**self.body(), **patch})
        self.assertEqual(self.fake.calls, 0)

    def test_pause_while_asr_pending_discards_result_without_blocking_pause(self):
        self.fake.hook = lambda: self.mutate('pause')
        with self.assertRaises(APIError) as caught: self.call()
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.view()['lifecycle'], 'paused')
        self.assertEqual(self.fake.calls, 1)

    def test_pause_resume_does_not_resurrect_recording(self):
        body = self.body(); self.mutate('pause'); self.mutate('resume')
        with self.assertRaises(APIError): self.call(body)
        self.assertEqual(self.fake.calls, 0)

    def test_disabled_invalid_audio_and_capacity_do_not_call_provider(self):
        self.gateway.speech = None
        with self.assertRaises(APIError) as caught: self.call()
        self.assertEqual(caught.exception.status, 503)
        self.gateway.speech = self.fake
        for audio in ('', 'invalid base64', base64.b64encode(b'not wav').decode()):
            with self.assertRaises(APIError): self.call({**self.body(), 'audio_base64': audio})
        self.gateway.limit = 0
        with self.assertRaises(APIError): self.call()
        self.assertEqual(self.fake.calls, 0)

    def test_one_initial_transcript_shared_and_clarification_isolated(self):
        transcript = self.call()['text']; self.mutate('start', query=transcript); self.settled()
        self.assertEqual(self.fake.calls, 1)
        self.assertEqual(self.view()['initial_query'], transcript)
        self.assertFalse(self.view()['results_visible'])
        self.mutate('select', condition='A')
        before = self.view(); body = self.body()
        self.fake.text = 'Yes, use the first option.'
        response = self.call(body)
        self.assertEqual(self.view()['branches'], before['branches'])
        self.comparisons.mutate(self.id, 'answer', {'request_id': 'answer-speech',
            'expected_branch_revision': before['branches']['A']['branch_revision'], 'question_id': body['question_id'],
            'response': {'text': response['text']}}, 'A')
        self.settled()
        self.assertEqual(self.view()['branches']['S']['question'], before['branches']['S']['question'])
        self.assertFalse(self.view()['results_visible'])
        self.assertEqual(self.fake.calls, 2)
        logs = '\n'.join(p.read_text() for p in Path(self.temp.name).rglob('*.jsonl'))
        self.assertIn(transcript, logs)
        self.assertIn(response['text'], logs)
        self.assertNotIn(body['audio_base64'], logs)

    def test_single_session_uses_same_transcription_boundary(self):
        v = self.sessions.create({'condition': 'S'})
        body = {**self.body(), 'expected_revision': v['revision'], 'condition': 'S', 'question_id': ''}
        result = self.gateway.transcribe('sessions', v['session_id'], body)
        self.assertEqual(result['text'], self.fake.text)
        self.assertEqual(self.sessions.view(self.sessions.get(v['session_id']))['revision'], v['revision'])


class TranscriptionHTTPTests(unittest.TestCase):
    def test_real_routes_limits_and_disabled_status(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = FakeSpeech()
            server = Server(('127.0.0.1', 0), Experiment(MockModel(), folder), speech=fake)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = 'http://127.0.0.1:' + str(server.server_address[1])
            def request(path, body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(base + path, data, {'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=5) as response: return json.load(response)
            try:
                self.assertTrue(request('/speech/status')['configured'])
                v = request('/tutor/comparisons', {'request_id': 'http-create'})
                body = {'request_id': 'http-stt', 'expected_revision': v['revision'], 'condition': 'E', 'question_id': '',
                        'audio_base64': base64.b64encode(wav_bytes()).decode()}
                route = '/tutor/comparisons/' + v['task_id'] + '/transcribe'
                self.assertEqual(request(route, body)['text'], fake.text)
                self.assertEqual(request(route, body)['text'], fake.text)
                self.assertEqual(fake.calls, 1)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/tutor/comparisons', {'padding': 'x' * 66000})
                self.assertEqual(caught.exception.code, 413)
                server.transcription.speech = None
                self.assertFalse(request('/speech/status')['configured'])
                with self.assertRaises(urllib.error.HTTPError) as caught: request(route, body)
                self.assertEqual(caught.exception.code, 503)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
