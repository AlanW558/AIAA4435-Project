from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_playback import TutorPlaybackAudit
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from export_tutor_dialogue import export_file
import test_tutor_audio as audio_tests


class PlaybackTests(unittest.TestCase):
    tearDown = audio_tests.AudioTests.tearDown
    view = audio_tests.AudioTests.view
    mutate = audio_tests.AudioTests.mutate
    settled = audio_tests.AudioTests.settled
    body = audio_tests.AudioTests.body
    call = audio_tests.AudioTests.call
    reveal = audio_tests.AudioTests.reveal

    def setUp(self):
        audio_tests.AudioTests.setUp(self)
        self.audit = TutorPlaybackAudit(self.sessions, self.comparisons)
        def synthesize(text, settings):
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b'\0\0' * 16000)
            return {'audio': buf.getvalue()}
        self.tts.synthesize = synthesize
        self.audio_request = self.body(); self.call(self.audio_request)

    def event(self, state='started', **patch):
        reasons = {'started': 'play_requested', 'completed': 'natural_end', 'stopped': 'user_stop', 'failed': 'decode_error'}
        return {'event_id': uuid.uuid4().hex, 'audio_request_id': self.audio_request['request_id'], 'event': state,
                'reason': reasons[state], 'position_seconds': 1 if state == 'completed' else 0,
                'elapsed_seconds': 1 if state == 'completed' else 0,
                'client_time_utc': datetime.now(timezone.utc).isoformat(), **patch}

    def report(self, event): return self.audit.record('comparisons', self.id, event)
    def records(self):
        return [json.loads(line) for line in (self.comparisons.log_dir / (self.id + '.jsonl')).read_text().splitlines()]

    def test_duplicate_lost_ack_replay_logs_once(self):
        e = self.event(); self.assertFalse(self.report(e)['idempotent_replay'])
        self.assertTrue(self.report(e)['idempotent_replay'])
        self.assertEqual(len([r for r in self.records() if r['event'] == 'playback_report']), 1)
        with self.assertRaises(APIError): self.report({**e, 'position_seconds': .1})

    def test_delayed_reports_after_switch_pause_close_keep_original_binding(self):
        self.mutate('select', condition='A'); self.mutate('pause'); self.mutate('close')
        self.report(self.event()); self.report(self.event('stopped', reason='task_closed', position_seconds=.4, elapsed_seconds=.5))
        r = self.records()[-1]
        self.assertEqual(r['condition'], 'E')
        self.assertEqual(r['audio_request_id'], self.audio_request['request_id'])
        self.assertEqual(r['evidence_source'], 'client_reported_not_verified_hearing')
        self.assertEqual(self.view()['lifecycle'], 'aborted')

    def test_restart_recovers_binding_and_idempotency_from_audit(self):
        e = self.event(); self.report(e)
        other = TutorComparisons(self.model, self.temp.name)
        try:
            restarted = TutorPlaybackAudit(TutorSessions(self.model, self.temp.name), other)
            self.assertTrue(restarted.record('comparisons', self.id, e)['idempotent_replay'])
            self.assertTrue(restarted.record('comparisons', self.id, self.event('completed'))['recorded'])
            self.assertEqual(self.records()[-1]['receipt_run_id'], other.run_id)
        finally: other.shutdown()
        self.assertEqual(len([r for r in self.records() if r['event'] == 'playback_report']), 2)

    def test_completion_requires_start_and_clip_end(self):
        with self.assertRaises(APIError): self.report(self.event('completed'))
        self.report(self.event())
        for change in ({'position_seconds': .1}, {'elapsed_seconds': .1}):
            with self.assertRaises(APIError): self.report(self.event('completed', **change))
        self.report(self.event('completed'))
        with self.assertRaises(APIError): self.report(self.event('stopped'))

    def test_replay_requires_new_audio_request_not_second_start(self):
        self.report(self.event()); self.report(self.event('stopped'))
        with self.assertRaises(APIError): self.report(self.event())
        self.audio_request = self.body(); self.call(self.audio_request)
        self.assertTrue(self.report(self.event())['recorded'])

    def test_unknown_request_other_task_and_injected_fields_rejected(self):
        for change in ({'audio_request_id': 'unknown'}, {'condition': 'A'}, {'audio_base64': 'not-allowed'},
                       {'event': 'heard'}, {'reason': []}, {'position_seconds': float('nan')},
                       {'elapsed_seconds': -1}, {'client_time_utc': 'not-a-date'}):
            with self.assertRaises(APIError): self.report(self.event(**change))
        with self.assertRaises(APIError): self.audit.record('comparisons', 'other-task', self.event())
        with self.assertRaises(APIError): self.audit.record('comparisons', '../escape', self.event())

    def test_decode_failure_before_start_has_no_completion(self):
        self.report(self.event('failed'))
        with self.assertRaises(APIError): self.report(self.event())

    def test_export_links_audio_playback_and_feedback_without_audio_bytes(self):
        self.report(self.event()); self.report(self.event('completed'))
        destination = Path(self.temp.name) / 'playback-export.jsonl'
        export_file(self.comparisons.log_dir / (self.id + '.jsonl'), destination)
        rows = [json.loads(line) for line in destination.read_text().splitlines()]
        kinds = {r['kind'] for r in rows}
        self.assertTrue({'audio_ready', 'playback_report'} <= kinds)
        self.assertNotIn('audio_base64', destination.read_text())
        for r in rows:
            if r['kind'] == 'playback_report': self.assertEqual(r['audio_request_id'], self.audio_request['request_id'])

    def test_partial_audit_is_not_silently_skipped(self):
        with (self.comparisons.log_dir / (self.id + '.jsonl')).open('a') as stream: stream.write('{partial')
        with self.assertRaises(APIError) as caught: self.report(self.event())
        self.assertEqual(caught.exception.status, 503)

    def test_concurrent_replay_appends_once(self):
        e = self.event(); results = []
        threads = [threading.Thread(target=lambda: results.append(self.report(e))) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(results), 5)
        self.assertEqual(sum(not r['idempotent_replay'] for r in results), 1)

    def test_single_session_and_revealed_reply_binding(self):
        v = self.sessions.create({'condition': 'S'})
        body = {**self.body(), 'condition': 'S', 'expected_revision': v['revision']}
        self.audio.synthesize('sessions', v['session_id'], body)
        self.audit.record('sessions', v['session_id'], self.event(audio_request_id=body['request_id']))
        self.reveal(); exchange = self.view()['branches']['E']['result']['state']['conversation'][-1]
        self.audio_request = self.body('reply', exchange['id']); self.call(self.audio_request); self.report(self.event())
        r = self.records()[-1]
        self.assertEqual(r['exchange_id'], exchange['id']); self.assertEqual(r['purpose'], 'reply')
        self.assertEqual(r['branch_revision'], self.view()['branches']['E']['branch_revision'])
        self.assertEqual(r['reveal_id'], self.view()['first_reveal']['reveal_id'])


if __name__ == '__main__': unittest.main()
