"""Synthetic-data tests; never call APIs or alter participant results."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

EXPERIMENTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENTS / 'scripts'))
from data_contract import aggregate, atomic_json, build_participant, import_participant, read


class DataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = read(EXPERIMENTS / 'runs/text-check-v4/review-data.json')
        cls.source = read(EXPERIMENTS / 'results/participant_001.json')['source_export']
        cls.amendments = read(EXPERIMENTS / 'results/amendments/P001-tone-preference.json')

    def participant(self, pid='P001', source=None, amendments=None):
        return build_participant(json.dumps(source or self.source).encode(), pid, pid, self.review, amendments)

    def test_idempotent_import_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = json.dumps(self.source).encode()
            source = root / 'download.json'
            source.write_bytes(raw)
            review = root / 'review.json'
            atomic_json(review, self.review)
            args = (source, 'P001', 'Participant 1', review, root / 'results')
            target, created = import_participant(*args)
            self.assertTrue(created)
            first = target.read_bytes()
            self.assertFalse(import_participant(*args)[1])
            self.assertEqual(target.read_bytes(), first)
            saved = read(target)
            self.assertEqual((target.parent / saved['source']['filename']).read_bytes(), raw)
            changed = deepcopy(self.source)
            changed['records'][0]['conditions']['S']['answers']['A0']['value'] = 1
            source.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                import_participant(*args)
            self.assertEqual(target.read_bytes(), first)

    def test_multiselect_amendment_preserves_all_ratings(self):
        raw = self.participant()
        changed = self.participant(amendments=self.amendments)
        self.assertEqual(raw['ratings'], changed['ratings'])
        self.assertEqual(raw['source_export'], changed['source_export'])
        rows = aggregate([changed])['cohorts'][0]['preference_summary']
        tone = next(r for r in rows if r['domain'] == 'tone')
        self.assertEqual(tone['votes'], {'E': 0, 'A': 0, 'N': 1, 'S': 1, 'no_preference': 0})
        self.assertEqual(tone['n_answered'], 1)

    def test_import_same_export_under_another_id_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'download.json'
            source.write_text(json.dumps(self.source))
            review = root / 'review.json'
            atomic_json(review, self.review)
            output = root / 'results'
            import_participant(source, 'P001', 'Participant 1', review, output)
            with self.assertRaisesRegex(ValueError, 'already registered as P001'):
                import_participant(source, 'P002', 'Participant 2', review, output)
            self.assertFalse((output / 'participant_002.json').exists())
            independent = deepcopy(self.source)
            independent['exported_at'] = '2026-11-28T10:00:00.000Z'
            source.write_text(json.dumps(independent))
            self.assertTrue(import_participant(source, 'P002', 'Participant 2', review, output)[1])

    def test_aggregate_duplicate_export_rejected_but_equal_independent_answers_allowed(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate source export'):
            aggregate([self.participant('P001'), self.participant('P002')])
        independent = deepcopy(self.source)
        independent['exported_at'] = '2026-11-28T10:00:00.000Z'
        result = aggregate([self.participant('P001'), self.participant('P002', independent)])
        self.assertEqual(result['n_unique_participants'], 2)
        self.assertEqual(result['cohorts'][0]['n_participants'], 2)

    def test_unable_not_automatically_amended(self):
        participant = self.participant('P002')
        tone = next(p for p in participant['preferences'] if p['domain'] == 'tone')
        self.assertEqual(tone['status'], 'unable_to_judge')
        self.assertEqual(tone['choices'], [])

    def test_missing_scores_and_multiple_people(self):
        second = deepcopy(self.source)
        second['records'][0]['conditions']['S']['answers']['A0'] = {'status': 'unable_to_judge', 'value': None}
        result = aggregate([self.participant(), self.participant('P002', second)])
        self.assertEqual(result['n_unique_participants'], 2)
        cohort = result['cohorts'][0]
        self.assertEqual(cohort['n_participants'], 2)
        cell = next(r for r in cohort['rating_summary'] if (r['domain'], r['condition'], r['item_id']) == ('speech_rate', 'S', 'A0'))
        self.assertEqual(cell['n_valid'], 1)
        self.assertEqual(cell['n_total'], 2)
        self.assertEqual(cell['missing_by_status'], {'unable_to_judge': 1})
        self.assertEqual(cell['mean'], self.source['records'][0]['conditions']['S']['answers']['A0']['value'])

    def test_partial_attribute_submission_is_not_complete(self):
        source = deepcopy(self.source)
        source['records'] = source['records'][:1]
        participant = self.participant(source=source)
        self.assertEqual(participant['completion_status'], 'partial_attributes')
        self.assertEqual(sum(r['status'] == 'not_submitted' for r in participant['ratings']), 60)

    def test_v3_multiselect_and_exclusive_no_preference(self):
        source = deepcopy(self.source)
        source['questionnaire_version'] = 'attribute-summary-feedback-v3'
        for record in source['records']:
            record['questionnaire_version'] = source['questionnaire_version']
            record['preference'] = {'status': 'answered', 'value': ['N', 'S']}
        p = self.participant('P002', source)
        self.assertEqual(p['preferences'][0]['choices'], ['N', 'S'])
        source['records'][0]['preference']['value'] = ['no_preference', 'S']
        with self.assertRaises(ValueError):
            self.participant('P002', source)

    def test_versions_are_separate_cohorts_not_pooled(self):
        source = deepcopy(self.source)
        source['questionnaire_version'] = 'attribute-summary-feedback-v3'
        for record in source['records']:
            record['questionnaire_version'] = source['questionnaire_version']
            record['preference'] = {'status': 'answered', 'value': ['S']}
        result = aggregate([self.participant(), self.participant('P002', source)])
        self.assertEqual(len(result['cohorts']), 2)
        self.assertEqual([c['n_participants'] for c in result['cohorts']], [1, 1])

    def test_duplicate_id_and_tampered_normalized_score_rejected(self):
        p = self.participant()
        with self.assertRaisesRegex(ValueError, 'Duplicate participant'):
            aggregate([p, deepcopy(p)])
        p['ratings'][0]['value'] = 1
        with self.assertRaisesRegex(ValueError, 'differs from source'):
            aggregate([p])

    def test_stale_release_and_wrong_amendment_rejected(self):
        source = deepcopy(self.source)
        source['records'][0]['task_releases']['R1-1'] = 'old'
        with self.assertRaises(ValueError):
            self.participant(source=source)
        amendments = deepcopy(self.amendments)
        amendments[0]['previous'] = {'status': 'answered', 'value': 'S'}
        with self.assertRaisesRegex(ValueError, 'previous value'):
            self.participant(amendments=amendments)


if __name__ == '__main__':
    unittest.main()
