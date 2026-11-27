"""Offline auxiliary-batch invariants; fixtures are not participant evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'Backend'))
sys.path.insert(0, str(ROOT / 'Backend/tests'))
sys.path.insert(0, str(ROOT / 'Tools/TutorTextCheck'))

from batch import Batch, CONDITIONS, sha
from core import APIError
from model import ModelError
from speech import SpeechError
from tutor_study_materials import TASKS
from unity_comparison_fixture_server import ComparisonFixture
from test_tutor_audio import FakeTTS
from workbook import generate, parse, replace_fields


QUERY = 'Compare an easier explanation.'
ANSWER = 'Yes, use the first option.'


class BatchChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workbook = self.root / 'requests.md'
        generate(self.workbook)
        self.model = ComparisonFixture()
        self.tts = FakeTTS()
        self.batch = Batch(self.root / 'batch', self.model, self.tts)
        self.network = patch('urllib.request.urlopen', side_effect=AssertionError('No network is allowed in these tests.'))
        self.network.start()

    def tearDown(self):
        self.batch.close()
        self.network.stop()
        self.temporary.cleanup()

    def fill(self, code, field, text):
        current = self.workbook.read_text()
        self.workbook.write_text(replace_fields(current, {(code, field): text}))

    def start(self, code='R1-1'):
        self.fill(code, 'request', QUERY)
        self.batch.process(self.workbook)
        return self.batch.load(code)

    def answer_all(self, code='R1-1'):
        record = self.batch.load(code)
        questions = self.batch.questions(self.batch.view(record))
        self.assertTrue(questions)
        self.fill(code, 'clarification', '\n'.join(f'{c}: {ANSWER}' for c in questions))
        self.batch.process(self.workbook)
        self.assertFalse(self.batch.questions(self.batch.view(record)))
        return record

    def ready(self, code='R1-1'):
        self.start(code)
        record = self.answer_all(code)
        self.assertTrue(self.batch.view(record)['results_visible'])
        return record

    def legacy_feedback_fixture(self, result_file):
        """Retained task-level data is an explicit legacy fixture, never new UI output."""
        path = Path(result_file)
        release = json.loads(path.read_text())
        release['questionnaire_version'] = 'attribute-feedback-v3'
        path.write_text(json.dumps(release))
        return {'task_code': release['task_code'], 'release_id': release['release_id'],
                'questionnaire_version': 'attribute-feedback-v3',
                'conditions': {c: {'answers': {f'A{i}': {'status': 'unanswered', 'value': None} for i in range(5)},
                                   'extras': {'reasons': [], 'comment': '', 'comment_confirmed': False}} for c in CONDITIONS}}

    def test_blank_workbook_never_calls_model_or_tts(self):
        result = self.batch.process(self.workbook, limit=32)
        self.assertEqual(result['processed'], [])
        self.assertEqual(set(result['status'].values()), {'request_blank'})
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.tts.calls, [])
        self.assertFalse((self.root / 'batch/tasks').exists())

    def test_authorized_answer_provenance_survives_later_round(self):
        record = self.start()
        questions = self.batch.questions(self.batch.view(record))
        self.fill('R1-1', 'clarification', '\n'.join(f'{c}: {ANSWER}' for c in questions))
        self.batch.process(self.workbook, clarification_source='assistant_authored_user_authorized')
        self.batch.followup(self.workbook, 'What is active recall?', ['R1-1'])
        details = self.batch.clarification_details(record)
        self.assertTrue(details['A']['occurred'])
        self.assertEqual(details['A']['turns'][0]['source'], 'assistant_authored_user_authorized')
        self.assertEqual(details['A']['turns'][0]['question'], questions['A']['text'])
        self.assertFalse(details['E']['occurred'])

    def test_known_failed_task_is_preserved_without_fake_audio(self):
        self.fill('R1-1', 'request', QUERY)
        with patch.object(self.model, 'interpret_tutor', side_effect=ModelError('fixture failure')):
            self.batch.process(self.workbook)
        self.batch.stop_failed(self.workbook, 'R1-1')
        output = self.batch.publish(self.workbook)
        data = json.loads(Path(output['R1-1']).read_text())
        self.assertEqual(data['audio'], dict.fromkeys(CONDITIONS))
        self.assertEqual(set(data['technical_failures']), set(CONDITIONS))
        self.assertEqual(len(self.tts.calls), 0)
        self.assertNotIn('baseline_audio', data)
        self.assertTrue(list((self.root / 'batch/failures/R1-1').glob('*.json')))

    def test_request_kept_and_private_goal_never_becomes_model_input(self):
        record = self.start()
        self.assertEqual(record['request'], QUERY)
        start = next(op for op in record['operations'] if op['operation'] == 'start')
        self.assertEqual(start['body']['query'], QUERY)
        contexts = json.dumps(self.model.contexts, ensure_ascii=False)
        self.assertIn(QUERY, contexts)
        self.assertNotIn(TASKS['R1-1'][1]['instructions'], contexts)
        self.assertFalse(self.batch.view(record)['results_visible'])
        with self.assertRaises(ValueError):
            self.batch.publish(self.workbook)
        self.assertFalse(self.tts.calls)
        self.assertFalse((self.root / 'batch/results').exists())

    def test_clarifications_bound_to_each_strategy_and_consumed_once(self):
        record = self.start()
        questions = self.batch.questions(self.batch.view(record))
        self.assertEqual(set(questions), {'A', 'S'})
        self.fill('R1-1', 'clarification', f'A: {ANSWER}')
        self.batch.process(self.workbook)
        self.assertEqual(set(self.batch.questions(self.batch.view(record))), {'S'})
        self.assertEqual(set(record['answers']), {questions['A']['question_id']})
        self.assertFalse(self.batch.view(record)['results_visible'])
        self.fill('R1-1', 'clarification', f'S: {ANSWER}')
        self.batch.process(self.workbook)
        self.assertEqual(set(record['answers']), {q['question_id'] for q in questions.values()})
        self.assertTrue(self.batch.view(record)['results_visible'])
        self.assertEqual(parse(self.workbook)['R1-1']['clarification'], '')
        calls = list(self.model.calls)
        self.batch.process(self.workbook)
        self.assertEqual(self.model.calls, calls)
        self.assertTrue(list((self.root / 'batch/worksheet-history').glob('*.md')))

    def test_unlabelled_reply_is_rejected_if_two_strategies_ask(self):
        self.start()
        before = list(self.model.calls)
        self.fill('R1-1', 'clarification', ANSWER)
        with self.assertRaisesRegex(ValueError, 'separate'):
            self.batch.process(self.workbook)
        self.assertEqual(self.model.calls, before)
        self.assertEqual(parse(self.workbook)['R1-1']['clarification'], ANSWER)

    def test_batch_barrier_includes_not_yet_processed_requests(self):
        self.ready()
        self.fill('R1-2', 'request', QUERY)
        with self.assertRaises(ValueError):
            self.batch.publish(self.workbook, ['R1-1'])
        self.assertFalse(self.tts.calls)

    def test_stable_checkpoint_restores_without_replaying_request(self):
        record = self.start()
        rid = record['runtime_id']
        original_questions = deepcopy(self.batch.questions(self.batch.view(record)))
        self.batch.close()
        restored_model = ComparisonFixture()
        self.batch = Batch(self.root / 'batch', restored_model, self.tts)
        restored = self.batch.load('R1-1')
        self.assertEqual(restored['runtime_id'], rid)
        self.assertEqual(self.batch.questions(self.batch.view(restored)), original_questions)
        self.batch.process(self.workbook)
        self.assertEqual(restored_model.calls, [])
        self.answer_all()
        self.assertTrue(self.batch.view(restored)['results_visible'])

    def test_unresolved_operation_blocks_replay_after_restart(self):
        record = self.start()
        record['pending'] = {'operation': 'answer', 'body': {'query': 'unknown-result'}}
        self.batch.save(record)
        self.batch.close()
        restored_model = ComparisonFixture()
        self.batch = Batch(self.root / 'batch', restored_model, self.tts)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.batch.process(self.workbook)
        self.assertEqual(restored_model.calls, [])
        self.assertEqual(self.batch.status(self.workbook)['R1-1'], 'interrupted_do_not_replay')

    def test_all_32_tasks_initialize_independently_and_preserve_history(self):
        ids = []
        for code in TASKS:
            record = self.batch.load(code, create=True)
            ids.append(record['runtime_id'])
            view = self.batch.view(record)
            for branch in self.batch.service.get(record['runtime_id']).branches.values():
                self.assertEqual(branch.session.state.snapshot(), view['baseline'])
        self.assertEqual(len(set(ids)), 32)
        self.assertEqual(self.batch.view(self.batch.load('R1-1'))['baseline']['settings']['speech_rate'], 1.2)
        history = self.batch.view(self.batch.load('R4-1'))['baseline']
        self.assertEqual(history['settings']['speech_rate'], 1.25)
        self.assertEqual(history['changes'][0]['before']['speech_rate'], .75)
        voice = self.batch.view(self.batch.load('V4-3'))['baseline']['settings']
        self.assertEqual(voice['voice'], 'voice_d')
        self.assertEqual(voice['speech_rate'], 1.25)
        self.assertEqual(voice['tone'], 'friendly')
        self.assertEqual(self.model.calls, [])

    def test_changed_submitted_request_blocks_every_new_call(self):
        self.start()
        before = list(self.model.calls)
        self.fill('R1-1', 'request', 'A different request.')
        self.fill('R1-2', 'request', QUERY)
        with self.assertRaisesRegex(ValueError, 'Request changed|submitted Request changed'):
            self.batch.process(self.workbook)
        self.assertEqual(self.model.calls, before)
        self.assertIsNone(self.batch.load('R1-2'))

    def test_tampered_clarify_cannot_bind_a_user_reply(self):
        self.start()
        before = list(self.model.calls)
        self.fill('R1-1', 'clarify', 'A: an edited question')
        self.fill('R1-1', 'clarification', f'A: {ANSWER}')
        with self.assertRaisesRegex(ValueError, 'Clarify'):
            self.batch.process(self.workbook)
        self.assertEqual(self.model.calls, before)

    def test_audio_is_versioned_saved_and_reused_without_synthesis(self):
        record = self.ready()
        result = self.batch.publish(self.workbook)
        output = json.loads(Path(result['R1-1']).read_text())
        self.assertEqual(len(self.tts.calls), 4)
        self.assertNotIn('baseline_audio', output)
        self.assertNotIn('listening_materials', output)
        self.assertEqual(output['questionnaire_version'], 'attribute-summary-feedback-v3')
        self.assertFalse(Path(result['R1-1']).with_name('feedback.json').exists())
        for condition, item in output['audio'].items():
            path = self.root / 'batch' / item['file']
            self.assertEqual(sha(path.read_bytes()), item['sha256'])
            self.assertEqual(item['condition'], condition)
            self.assertEqual(item['runtime_id'], record['runtime_id'])
            self.assertEqual(item['playback'], 'not_observed')
            self.assertTrue(path.with_suffix('.json').exists())
        again = self.batch.publish(self.workbook)
        self.assertEqual(again, result)
        self.assertEqual(len(self.tts.calls), 4)
        path.write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'audio'):
            self.batch.publish(self.workbook)
        self.assertEqual(len(self.tts.calls), 4)

    def test_reply_audio_is_generated_and_legacy_feedback_remains_readable(self):
        self.ready('L1-1')
        result = self.batch.publish(self.workbook)
        output = json.loads(Path(result['L1-1']).read_text())
        for item in output['audio'].values():
            self.assertEqual(item['purpose'], 'reply')
            self.assertIn('Active recall', item['text'])
        feedback_path = Path(result['L1-1']).with_name('feedback.json')
        self.assertFalse(feedback_path.exists())
        data = self.legacy_feedback_fixture(result['L1-1'])
        feedback_path.write_text(json.dumps(data))
        self.assertEqual(data['questionnaire_version'], 'attribute-feedback-v3')
        with self.assertRaises(APIError):
            self.batch.save_feedback(feedback_path)
        self.assertFalse((self.root / 'batch/feedback').exists())
        for condition in CONDITIONS:
            data['conditions'][condition]['answers'] = {
                'A0': {'status': 'answered', 'value': 'partly_met'},
                'A1': {'status': 'answered', 'value': 5},
                'A2': {'status': 'answered', 'value': 4},
                'A3': {'status': 'unable_to_judge', 'value': None},
                'A4': {'status': 'answered', 'value': 6},
            }
        feedback_path.write_text(json.dumps(data))
        saved = json.loads(Path(self.batch.save_feedback(feedback_path)).read_text())
        self.assertEqual(saved['conditions']['A']['answers']['A3'], {'status': 'unable_to_judge', 'value': None})
        self.assertFalse(saved['formal_study_submission'])
        self.assertEqual(saved['questionnaire_version'], 'attribute-feedback-v3')
        self.batch.mutate(self.batch.load('L1-1'), 'settings', 'S', patch={'tone': 'friendly'})
        with self.assertRaisesRegex(ValueError, 'current published'):
            self.batch.save_feedback(feedback_path)

    def test_original_summary_batch_keeps_release_version_when_publishing(self):
        self.ready()
        self.batch.meta['questionnaire_version'] = 'attribute-summary-feedback-v1'
        result = self.batch.publish(self.workbook)
        self.assertEqual(json.loads(Path(result['R1-1']).read_text())['questionnaire_version'], 'attribute-summary-feedback-v1')

    def test_published_generated_reply_passes_report_evidence_validation(self):
        from report import collect
        self.ready()
        self.batch.publish(self.workbook)
        data = collect(self.root / 'batch')
        task = next(t for t in data['tasks'] if t['task_code'] == 'R1-1')
        self.assertEqual(task['status'], 'published')
        self.assertEqual(data['audio_count'], 4)
        self.assertTrue(all(c['purpose'] == 'reply' for c in task['conditions'].values()))

    def test_unknown_tts_result_is_not_automatically_retried(self):
        record = self.ready()
        self.tts.error = SpeechError('provider_connection_error')
        with self.assertRaises(APIError):
            self.batch.render_audio(record, 'E')
        self.assertEqual(record['pending']['operation'], 'tts')
        self.assertEqual(len(self.tts.calls), 1)
        self.batch.close()
        self.tts.error = None
        self.batch = Batch(self.root / 'batch', ComparisonFixture(), self.tts)
        restored = self.batch.load('R1-1')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.batch.render_audio(restored, 'E')
        self.assertEqual(len(self.tts.calls), 1)

    def test_model_and_tts_profiles_cannot_change_within_batch(self):
        changed = ComparisonFixture()
        changed.model = 'different-fixture-model'
        with self.assertRaisesRegex(ValueError, 'model_profile changed'):
            Batch(self.root / 'batch', changed, self.tts)
        changed_tts = FakeTTS()
        changed_tts.config = SimpleNamespace(tts_model='different-tts', base_url='fixture')
        with self.assertRaisesRegex(ValueError, 'tts_profile changed'):
            Batch(self.root / 'batch', self.model, changed_tts)
        before = json.loads((self.root / 'batch/batch.json').read_text())
        self.assertEqual(before['model_profile']['model'], self.model.model)
        self.assertEqual(before['tts_profile']['model'], 'fixture')
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.tts.calls, [])

    def test_deleting_a_processed_request_does_not_remove_release_barrier(self):
        record = self.ready()
        self.fill('R1-1', 'request', '')
        self.assertEqual(self.batch.status(self.workbook)['R1-1'], 'request_changed')
        with self.assertRaises(ValueError):
            self.batch.publish(self.workbook)
        self.assertEqual(record['request'], QUERY)
        self.assertEqual(self.tts.calls, [])

    def test_confirmed_preparation_can_resume_before_initial_request(self):
        record = self.batch.load('R1-1', create=True)
        self.batch.mutate(record, 'confirm_preparation')
        self.assertIsNone(record['request'])
        self.batch.close()
        model = ComparisonFixture()
        self.batch = Batch(self.root / 'batch', model, self.tts)
        self.fill('R1-1', 'request', QUERY)
        self.batch.process(self.workbook)
        restored = self.batch.load('R1-1')
        self.assertEqual(restored['request'], QUERY)
        self.assertEqual(sum(op['operation'] == 'confirm_preparation' for op in restored['operations']), 1)
        self.assertEqual(sum(op['operation'] == 'start' for op in restored['operations']), 1)
        self.assertIsNone(restored['pending'])

    def test_feedback_retry_is_idempotent_and_revision_keeps_original(self):
        self.ready()
        result = self.batch.publish(self.workbook)
        file = Path(result['R1-1']).with_name('feedback.json')
        data = self.legacy_feedback_fixture(result['R1-1'])
        for condition in CONDITIONS:
            data['conditions'][condition]['answers'] = {
                'A0': {'status': 'answered', 'value': 'fully_met'},
                **{f'A{i}': {'status': 'answered', 'value': 5} for i in range(1, 5)},
            }
        file.write_text(json.dumps(data))
        first = self.batch.save_feedback(file)
        repeated = self.batch.save_feedback(file)
        self.assertEqual(first, repeated)
        self.assertEqual(len(list((self.root / 'batch/feedback').glob('*.json'))), 1)
        first_record = json.loads(Path(first).read_text())
        data['conditions']['S']['answers']['A4']['value'] = 6
        file.write_text(json.dumps(data))
        revised = self.batch.save_feedback(file)
        self.assertNotEqual(first, revised)
        second_record = json.loads(Path(revised).read_text())
        self.assertEqual(second_record['supersedes'], first_record['submission_id'])
        self.assertEqual(json.loads(Path(first).read_text()), first_record)
        self.assertEqual(len(list((self.root / 'batch/feedback').glob('*.json'))), 2)


if __name__ == '__main__':
    unittest.main()
