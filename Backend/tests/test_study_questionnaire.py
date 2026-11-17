"""New survey versions, stale bindings and isolated optional comment STT."""
import base64
import json
import unittest
import uuid
from core import APIError
from tutor_feedback import (ATTRIBUTE_VERSION, NATURAL_VERSION, FEEDBACK_VERSION,
                            ATTRIBUTE_RATINGS, validate_feedback, complete)
from tutor_transcription import TutorTranscription
import test_tutor_lifecycle as lifecycle
from test_tutor_transcription import FakeSpeech
from test_speech import wav_bytes


def attribute():
    return {'completion': 'fully_met', 'ratings': {k: 5 for k in ATTRIBUTE_RATINGS}}


class Contracts(unittest.TestCase):
    def test_versions_and_required_fields(self):
        value = validate_feedback(attribute(), version=ATTRIBUTE_VERSION)
        self.assertTrue(complete(value, ATTRIBUTE_VERSION))
        self.assertFalse(complete(value, FEEDBACK_VERSION))
        for key in ATTRIBUTE_RATINGS:
            draft = attribute(); del draft['ratings'][key]
            self.assertFalse(complete(validate_feedback(draft, version=ATTRIBUTE_VERSION), ATTRIBUTE_VERSION))
        self.assertFalse(complete(validate_feedback({}, version=ATTRIBUTE_VERSION), ATTRIBUTE_VERSION))

    def test_reject_old_extra_and_invalid_ratings(self):
        for value in [0, 8, True, 1.5, None, '5']:
            a = attribute(); a['ratings']['control'] = value
            with self.assertRaises(APIError): validate_feedback(a, version=ATTRIBUTE_VERSION)
        for key in ['q2', 'interruption']:
            a = attribute(); a['ratings'][key] = 3
            with self.assertRaises(APIError): validate_feedback(a, version=ATTRIBUTE_VERSION)
        with self.assertRaises(APIError): validate_feedback(attribute(), version='unknown')

    def test_unjudge_is_an_explicit_valid_answer(self):
        a = attribute(); a['completion'] = 'unable_to_judge'; a['ratings'] = {k: 'unable_to_judge' for k in ATTRIBUTE_RATINGS}
        self.assertTrue(complete(validate_feedback(a, version=ATTRIBUTE_VERSION), ATTRIBUTE_VERSION))

    def test_natural_goal_fit_and_interruption_are_separate(self):
        a = {'goal_fit': 'partly_met', 'ratings': {**attribute()['ratings'], 'interruption': 7}}
        v = validate_feedback(a, version=NATURAL_VERSION)
        self.assertTrue(complete(v, NATURAL_VERSION)); self.assertEqual(v['ratings']['interruption'], 7)
        self.assertNotIn('completion', v); self.assertNotIn('reasons', v)
        with self.assertRaises(APIError): validate_feedback(a, version=ATTRIBUTE_VERSION)
        del a['ratings']['interruption']; self.assertFalse(complete(validate_feedback(a, version=NATURAL_VERSION), NATURAL_VERSION))

    def test_comments_and_conditional_reasons(self):
        a = attribute(); a.update(comment='I reached my goal.', comment_confirmed=True, reasons=['other'])
        self.assertEqual(validate_feedback(a, version=ATTRIBUTE_VERSION)['comment'], a['comment'])
        self.assertEqual(validate_feedback(a, version=ATTRIBUTE_VERSION)['reasons'], [])
        a['comment_confirmed'] = False
        with self.assertRaises(APIError): validate_feedback(a, version=ATTRIBUTE_VERSION)
        a['comment_confirmed'] = True; a['completion'] = 'partly_met'; a['reasons'] = ['not_maintained']
        self.assertEqual(validate_feedback(a, version=ATTRIBUTE_VERSION)['reasons'], [])
        self.assertEqual(validate_feedback(a, version=ATTRIBUTE_VERSION, later_interaction=True)['reasons'], ['not_maintained'])


class Integration(unittest.TestCase):
    tearDown = lifecycle.LifecycleTests.tearDown
    current = lifecycle.LifecycleTests.current
    mutate = lifecycle.LifecycleTests.mutate
    wait = lifecycle.LifecycleTests.wait
    start = lifecycle.LifecycleTests.start
    settled = lifecycle.LifecycleTests.settled
    respond = lifecycle.LifecycleTests.respond
    reveal = lifecycle.LifecycleTests.reveal
    logs = lifecycle.LifecycleTests.logs

    def setUp(self):
        lifecycle.LifecycleTests.setUp(self)
        self.task_id = self.app.create({'request_id': 'new-version', 'feedback_version': ATTRIBUTE_VERSION})['task_id']

    def rate(self, c, answers=None):
        return self.mutate('feedback', c, expected_feedback_revision=self.current()['feedback'][c]['feedback_revision'], answers=answers or attribute())

    def test_new_version_submit_inheritance_and_history(self):
        self.reveal()
        for c in 'EANS': self.rate(c)
        self.assertTrue(self.current()['can_submit'])
        self.mutate('submit')
        self.assertEqual(self.logs()[-1]['submission']['feedback_version'], ATTRIBUTE_VERSION)
        v = self.mutate('next', next_task={'task_code': 'NEXT', 'domain': 'tone', 'scenario': 'C2'})
        self.assertEqual(self.app.view(self.app.get(v['next_task_id']))['feedback_version'], ATTRIBUTE_VERSION)

    def test_draft_missing_and_updated_branch_need_reconfirmation(self):
        self.reveal(); self.rate('E', {'completion': 'fully_met', 'ratings': {}})
        self.assertFalse(self.current()['feedback']['E']['complete'])
        for c in 'EANS': self.rate(c)
        self.mutate('settings', 'E', patch={'reply_length': 'detailed'})
        self.assertFalse(self.current()['feedback']['E']['current']); self.assertFalse(self.current()['can_submit'])
        self.wait(lambda v: v['branches']['E']['status'] == 'ready')
        self.rate('E'); self.assertTrue(self.current()['can_submit'])

    def test_natural_not_accepted_as_comparison_version(self):
        with self.assertRaises(APIError): self.app.create({'request_id': 'bad', 'feedback_version': NATURAL_VERSION})

    def survey(self):
        v = self.current(); c = v['selected_condition']
        return {'request_id': uuid.uuid4().hex, 'expected_revision': v['branches'][c]['branch_revision'],
                'condition': c, 'question_id': '', 'audio_base64': base64.b64encode(wav_bytes()).decode()}

    def test_survey_stt_isolated_deduplicated_and_confirmed(self):
        self.reveal(); fake = FakeSpeech(); fake.text = 'OPTIONAL SURVEY COMMENT'
        gateway = TutorTranscription(None, self.app, fake); body = self.survey()
        before = self.current(); result = gateway.transcribe('survey', self.task_id, body)
        self.assertEqual(result, gateway.transcribe('survey', self.task_id, body)); self.assertEqual(fake.calls, 1)
        self.assertEqual(before['branches'], self.current()['branches']); self.assertEqual(before['revision'], self.current()['revision'])
        self.assertNotIn(fake.text, json.dumps(self.logs()))
        self.assertNotIn(body['audio_base64'], repr(gateway.entries))
        a = attribute(); a.update(comment=result['text'], comment_confirmed=True); self.rate(body['condition'], a)
        self.assertIn(fake.text, json.dumps(self.logs()))
        self.assertNotIn(fake.text, json.dumps(self.current()['branches']))

    def test_survey_stt_rejects_pre_reveal_pause_and_branch_change(self):
        fake = FakeSpeech(); gateway = TutorTranscription(None, self.app, fake)
        with self.assertRaises(APIError): gateway.transcribe('survey', self.task_id, self.survey())
        self.reveal(); body = self.survey(); self.mutate('pause')
        with self.assertRaises(APIError): gateway.transcribe('survey', self.task_id, body)
        self.mutate('resume'); self.app.mutate(self.task_id, 'select', {'request_id': uuid.uuid4().hex, 'expected_revision': self.current()['revision'], 'condition': 'A' if body['condition'] != 'A' else 'E'})
        with self.assertRaises(APIError): gateway.transcribe('survey', self.task_id, body)
        self.assertEqual(fake.calls, 0)

    def test_late_survey_stt_not_delivered_after_context_change(self):
        self.reveal(); fake = FakeSpeech(); gateway = TutorTranscription(None, self.app, fake)
        fake.hook = lambda: self.mutate('pause')
        with self.assertRaises(APIError): gateway.transcribe('survey', self.task_id, self.survey())
        self.assertNotIn(fake.text, json.dumps(self.logs()))
