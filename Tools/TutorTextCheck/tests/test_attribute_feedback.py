"""Offline attribute summaries: unit boundaries, completeness and durable export."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attribute_feedback import (VERSION, LEGACY_VERSION, NUMERIC_SINGLE_VERSION, BUNDLE_SCHEMA, build_attributes, blank_feedback,
                                validate_feedback, save_submission, feedback_items)


class AttributeFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tasks = [{'domain': domain, 'title': domain, 'task_code': f'{domain}-{n}',
                       'status': 'published', 'release_id': f'{domain}-release-{n}',
                       'conditions': {c: {'audio_url': c + '.wav'} for c in 'EANS'}}
                      for domain in ('speech_rate', 'reply_length', 'tone', 'voice') for n in range(8)]
        self.current = {'batch_id': 'fixture-batch', 'attributes': build_attributes(self.tasks)}
        self.draft = blank_feedback('fixture-batch', self.current['attributes'][0])

    def tearDown(self):
        self.temp.cleanup()

    def completed(self, group=0):
        value = blank_feedback('fixture-batch', self.current['attributes'][group])
        for section in value['conditions'].values():
            for item in section['answers']:
                section['answers'][item] = {'status': 'answered', 'value': 5}
        value['preference'] = {'status': 'answered', 'value': ['S']}
        return value

    def test_four_summaries_replace_32_task_forms_without_default_answers(self):
        self.assertEqual(len(self.current['attributes']), 4)
        blanks = [blank_feedback('fixture-batch', g) for g in self.current['attributes']]
        self.assertEqual(sum(len(c['answers']) for d in blanks for c in d['conditions'].values()), 80)
        for draft in blanks:
            self.assertEqual(len(draft['task_releases']), 8)
            validate_feedback(draft, self.current, final=False)
            self.assertEqual(draft['preference'], {'status': 'unanswered', 'value': None})
        with self.assertRaises(ValueError):
            validate_feedback(self.draft, self.current)

    def test_20_answers_without_preference_is_incomplete(self):
        value = self.completed()
        value['preference'] = {'status': 'unanswered', 'value': None}
        with self.assertRaisesRegex(ValueError, 'Choose a strategy'):
            validate_feedback(value, self.current)
        for preference in ({'status': 'answered', 'value': ['no_preference']},
                           {'status': 'answered', 'value': ['E', 'A', 'N', 'S']}):
            value['preference'] = preference
            self.assertEqual(validate_feedback(value, self.current)['preference'], preference)

    def test_task_records_wrong_batch_missing_and_stale_releases_rejected(self):
        for kind in ('task', 'batch', 'missing', 'stale', 'wrong_version'):
            value = self.completed()
            if kind == 'task': value['task_code'] = 'R1-1'
            elif kind == 'batch': value['batch_id'] = 'another-batch'
            elif kind == 'missing': value['task_releases'].pop('speech_rate-7')
            elif kind == 'stale': value['task_releases']['speech_rate-7'] = 'old-release'
            else: value['questionnaire_version'] = 'attribute-feedback-v3'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_feedback(value, self.current)

    def test_changed_results_invalidate_summary_and_pending_attribute_is_blocked(self):
        changed = deepcopy(self.tasks)
        changed[7]['release_id'] = 'new-result'
        new = {'batch_id': 'fixture-batch', 'attributes': build_attributes(changed)}
        self.assertNotEqual(new['attributes'][0]['release_set_id'], self.current['attributes'][0]['release_set_id'])
        with self.assertRaises(ValueError): validate_feedback(self.completed(), new)
        changed[7]['status'] = 'pending'
        new['attributes'] = build_attributes(changed)
        self.assertEqual(new['attributes'][0]['status'], 'pending')
        with self.assertRaises(ValueError): validate_feedback(self.completed(), new)

    def test_technical_failure_keeps_task_in_attribute_scope(self):
        self.tasks[0]['conditions']['A'] = {'audio_url': None, 'technical_failure': {'error_code': 'invalid_result'}}
        group = build_attributes(self.tasks)[0]
        self.assertEqual(group['audio_count'], 31)
        self.assertEqual(group['technical_failure_count'], 1)
        self.assertEqual(len(group['task_codes']), 8)
        self.assertEqual(group['status'], 'published')

    def test_numeric_categories_and_missingness_do_not_coerce(self):
        for answer in ({'status': 'answered', 'value': True}, {'status': 'answered', 'value': '5'},
                       {'status': 'answered', 'value': 8}, {'status': 'unable_to_judge', 'value': 4}):
            value = self.completed(); value['conditions']['E']['answers']['A1'] = answer
            with self.assertRaises(ValueError): validate_feedback(value, self.current)
        value['conditions']['E']['answers']['A1'] = {'status': 'unable_to_judge', 'value': None}
        self.assertEqual(validate_feedback(value, self.current)['conditions']['E']['answers']['A1']['value'], None)

    def test_saved_record_is_idempotent_revision_preserves_prior_answers(self):
        original = self.completed()
        first = Path(save_submission(self.root, original, self.current))
        self.assertEqual(save_submission(self.root, original, self.current), str(first))
        revised = deepcopy(original); revised['preference']['value'] = ['A', 'N']
        second = Path(save_submission(self.root, revised, self.current))
        first_data, second_data = json.loads(first.read_text()), json.loads(second.read_text())
        self.assertEqual(first_data['preference']['value'], ['S'])
        self.assertEqual(second_data['supersedes'], first_data['submission_id'])
        self.assertFalse(second_data['formal_study_submission'])
        self.assertFalse((self.root / 'feedback').exists())

    def test_completed_bundle_validates_all_records_before_any_write(self):
        bundle = {'schema': BUNDLE_SCHEMA, 'batch_id': 'fixture-batch', 'questionnaire_version': VERSION,
                  'kind': 'completed_attributes', 'exported_at': '2026-11-27T00:00:00Z',
                  'records': [self.completed(0), self.completed(1)]}
        bundle['records'][1]['preference'] = {'status': 'unanswered', 'value': None}
        with self.assertRaises(ValueError): save_submission(self.root, bundle, self.current)
        self.assertFalse((self.root / 'attribute-feedback').exists())
        bundle['records'][1] = self.completed(1)
        self.assertEqual(len(save_submission(self.root, bundle, self.current)), 2)
        bundle['kind'] = 'draft_backup'
        with self.assertRaises(ValueError): save_submission(self.root, bundle, self.current)

    def test_source_retained_and_scope_explicit(self):
        base = [{'id': f'A{i}', 'text': 'Original wording.', 'source': 'Original source', 'scale': 'agreement7'} for i in range(5)]
        actual = feedback_items(base)
        self.assertTrue(all('this attribute' in item['text'] for item in actual))
        self.assertTrue(all(item['source'] == 'Original source' for item in actual))
        self.assertEqual(base[0]['text'], 'Original wording.')
        self.assertEqual(actual[0]['scale'], 'fulfillment7')
        self.assertEqual((actual[0]['left'], actual[0]['right']), ('Not at all', 'Completely'))

    def test_a0_numeric_round_trip_and_invalid_values(self):
        for score in range(1, 8):
            value = self.completed(); value['conditions']['E']['answers']['A0']['value'] = score
            path = Path(save_submission(self.root, value, self.current))
            self.assertEqual(json.loads(path.read_text())['conditions']['E']['answers']['A0']['value'], score)
        for invalid in ('fully_met', 'partly_met', 'not_met', '4', 4.0, True, 0, 8):
            value = self.completed(); value['conditions']['E']['answers']['A0']['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_feedback(value, self.current)

    def test_legacy_categories_stay_versioned_and_do_not_supersede_numeric(self):
        legacy = self.completed(); legacy['questionnaire_version'] = LEGACY_VERSION
        legacy['preference']['value'] = 'S'
        for section in legacy['conditions'].values():
            section['answers']['A0']['value'] = 'partly_met'
        current = {**self.current, 'questionnaire_version': LEGACY_VERSION}
        old = Path(save_submission(self.root, legacy, current))
        old_bytes = old.read_bytes()
        new = json.loads(Path(save_submission(self.root, self.completed(), self.current)).read_text())
        self.assertIsNone(new['supersedes'])
        self.assertEqual(old.read_bytes(), old_bytes)
        with self.assertRaises(ValueError): validate_feedback(legacy, self.current)
        with self.assertRaises(ValueError): validate_feedback(self.completed(), current)
        legacy['conditions']['E']['answers']['A0']['value'] = 4
        with self.assertRaises(ValueError): validate_feedback(legacy, current)

    def test_multi_preference_shape_exclusive_category_and_no_unable(self):
        for preference in ([], ['S', 'S'], ['N', 'S', 'no_preference'], ['unknown'], 'S', None,
                           [True], [{'condition': 'S'}], ['E', 'A', 'N', 'S', 'E']):
            value = self.completed(); value['preference']['value'] = preference
            with self.subTest(preference=preference), self.assertRaises(ValueError):
                validate_feedback(value, self.current)
        value = self.completed(); value['preference'] = {'status': 'unable_to_judge', 'value': None}
        with self.assertRaises(ValueError): validate_feedback(value, self.current)
        value['preference'] = {'status': 'answered', 'value': ['N', 'S']}
        saved = json.loads(Path(save_submission(self.root, value, self.current)).read_text())
        self.assertEqual(saved['preference']['value'], ['N', 'S'])
        value['conditions']['A']['answers']['A0'] = {'status': 'unable_to_judge', 'value': None}
        validate_feedback(value, self.current)

    def test_numeric_single_v2_keeps_a0_and_legacy_preference_shapes(self):
        old_current = {**self.current, 'questionnaire_version': NUMERIC_SINGLE_VERSION}
        old = self.completed(); old['questionnaire_version'] = NUMERIC_SINGLE_VERSION
        for preference in ({'status': 'answered', 'value': 'N'},
                           {'status': 'answered', 'value': 'no_preference'},
                           {'status': 'unable_to_judge', 'value': None}):
            old['preference'] = preference
            self.assertEqual(validate_feedback(old, old_current)['conditions']['E']['answers']['A0']['value'], 5)
        old['preference'] = {'status': 'answered', 'value': ['N', 'S']}
        with self.assertRaises(ValueError): validate_feedback(old, old_current)
        base = [{'id': f'A{i}', 'scale': 'category'} for i in range(5)]
        self.assertEqual(feedback_items(base, NUMERIC_SINGLE_VERSION)[0]['scale'], 'fulfillment7')


if __name__ == '__main__':
    unittest.main()
