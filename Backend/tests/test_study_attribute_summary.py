"""Attribute summaries collect 20 answers after task completion, without inventing task ratings."""
import csv
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from server import Server
from study_answers import (ATTRIBUTE_SUMMARY_VERSION, LEGACY_ATTRIBUTE_SUMMARY_VERSION,
                           NUMERIC_SINGLE_ATTRIBUTE_SUMMARY_VERSION, NUMERIC_ATTRIBUTE_SUMMARY_VERSIONS,
                           ATTRIBUTE_VERSION, NATURAL_VERSION, validate_answers, extras)
from tutor_preferences import VERSION as PREFERENCE_VERSION, LEGACY_VERSION as LEGACY_PREFERENCE_VERSION
from study_store import StudyStore, require
from export_study_data import export_run
from test_study_store import Fixture, manifest, answers as legacy_answers
import test_study_flow as flow_tests
from test_tutor_generation import GenerationFixture


def answers(version=ATTRIBUTE_SUMMARY_VERSION):
    result = legacy_answers()
    if version in NUMERIC_ATTRIBUTE_SUMMARY_VERSIONS:
        result['A0']['value'] = 1
    return result


class FixtureExecution:
    """Deterministic authoritative result source, never calls a provider."""
    def __init__(self): self.results = {}
    def evaluate(self, state, payload): return deepcopy(self.results[payload['task_id']])
    def assert_current(self, state, target):
        tasks = [state['tasks'][tid] for tid in target['evaluation']['tasks']] if 'module_type' in target and target['module_type'] == 'attribute_comparison' else []
        for task in tasks:
            require(task['evaluation'] == self.results[task['task_id']], 'stale_evaluation', 'Fixture result changed.', 409)


class SummaryFixture(Fixture):
    def __init__(self, folder, full=True, store=None, version=ATTRIBUTE_SUMMARY_VERSION, preference_version=PREFERENCE_VERSION):
        self.store = store or StudyStore(folder); self.run = None
        spec = manifest(full)
        spec['attribute_feedback_unit'] = 'attribute'
        if version is not None: spec['attribute_questionnaire_version'] = version
        if preference_version is not None: spec['preference_questionnaire_version'] = preference_version
        self.send('create_run', {'participant_id': 'ENG-summary', 'collection_kind': 'engineering', 'execution_mode': 'mock', 'manifest': spec})
        if store is None: self.store.executor = FixtureExecution()

    def task(self, mid, task_code=None, finish=True):
        code = task_code or next(t['task_code'] for t in self.state['manifest']['tasks'] if not any(x['task_code'] == t['task_code'] for x in self.state['tasks'].values()))
        tid = self.send('open_task', {'module_instance_id': mid, 'task_code': code})['task_id']
        self.store.executor.results[tid] = {'task_id': tid, 'first_reveal_id': 'reveal-' + tid,
            'branches': {c: {'branch_revision': 2, 'state_revision': 1, 'status': 'ready',
                            'result': {'message': 'Recorded fixture ' + c}} for c in 'EANS'}}
        if finish: self.send('finish_task', {'task_id': tid})
        return tid

    def summary(self, mid, condition='E', data=None, **extra):
        version = self.store.attribute_questionnaire_version(self.state)
        return self.send('save_feedback', {'module_instance_id': mid, 'task_id': None, 'condition': condition,
            'evaluation_revision': self.state['modules'][mid]['evaluation_revision'],
            'questionnaire_version': version, 'answers': data if data is not None else answers(version), **extra})

    def submit_summary(self, mid):
        return self.send('submit_attribute', {'module_instance_id': mid, 'evaluation_revision': self.state['modules'][mid]['evaluation_revision']})

    def finish_attributes(self):
        for domain in dict.fromkeys(t['domain'] for t in self.state['manifest']['tasks']):
            mid = self.module(domain)
            for task in [t for t in self.state['manifest']['tasks'] if t['domain'] == domain]: self.task(mid, task['task_code'])
            for c in 'EANS': self.summary(mid, c)
            self.submit_summary(mid); self.pref(domain)
        self.pref(None)


class SummaryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.f = SummaryFixture(self.root / 'data')
    def tearDown(self): self.tmp.cleanup()

    def finish_domain(self):
        mid = self.f.module()
        for task in self.f.state['manifest']['tasks'][:8]: self.f.task(mid, task['task_code'])
        return mid

    def test_no_task_questionnaires_or_fake_submissions_and_atomic_freeze(self):
        mid = self.f.module()
        for spec in self.f.state['manifest']['tasks'][:7]: self.f.task(mid, spec['task_code'])
        self.assertEqual(self.f.state['questionnaires'], {})
        self.assertFalse(self.f.state['modules'][mid]['frozen'])
        tid = self.f.task(mid, finish=False)
        packet = self.f.packet('finish_task', {'task_id': tid})
        with patch.object(self.f.store, '_before_commit', side_effect=sqlite3.OperationalError()):
            with self.assertRaises(APIError): self.f.store.command(packet)
        self.assertIsNone(self.f.state['tasks'][tid]['completion_id'])
        self.assertEqual(self.f.state['questionnaires'], {})
        ack = self.f.store.command(packet)
        self.assertTrue(ack['result']['attribute_ready_for_feedback'])
        restarted = StudyStore(self.root / 'data')
        self.assertEqual(restarted.command(packet)['result'], ack['result'])
        state = self.f.state; module = state['modules'][mid]
        self.assertTrue(module['frozen']); self.assertEqual(len(module['evaluation']['tasks']), 8)
        self.assertEqual(len(module['evaluation']['task_completions']), 8)
        self.assertEqual([t['task_code'] for t in module['evaluation']['task_completions']],
                         [t['task_code'] for t in state['manifest']['tasks'][:8]])
        self.assertTrue(all(t['completion_id'] and t['frozen'] and t['submission_id'] is None for t in state['tasks'].values()))
        self.assertEqual(len(state['questionnaires']), 4)
        for q in state['questionnaires'].values():
            self.assertEqual(q['questionnaire_version'], ATTRIBUTE_SUMMARY_VERSION)
            self.assertIsNone(q['task_id']); self.assertEqual(q['target_id'], mid)
            self.assertTrue(all(a['status'] == 'unanswered' for a in q['answers'].values()))
        with self.assertRaises(APIError): self.f.bind(tid)
        with self.assertRaises(APIError): self.f.submit(tid)

    def test_summary_and_preference_gate_next_attribute(self):
        mid = self.finish_domain()
        for operation in (lambda: self.f.pref(), lambda: self.f.module('reply_length'), lambda: self.f.submit_summary(mid)):
            with self.assertRaises(APIError): operation()
        for c in 'EAN': self.f.summary(mid, c)
        self.f.summary(mid, 'S', {'A0': {'status': 'answered', 'value': 7}})
        with self.assertRaises(APIError): self.f.submit_summary(mid)
        self.f.summary(mid, 'S'); self.f.submit_summary(mid)
        with self.assertRaises(APIError): self.f.module('reply_length')
        self.f.pref(); self.f.module('reply_length')
        pref = self.f.state['preferences']['speech_rate']
        self.assertEqual(pref['task_submissions'], [])
        self.assertEqual(len(pref['task_completions']), 8)
        self.assertEqual(pref['attribute_submissions'][0]['submission_id'], self.f.state['modules'][mid]['submission_id'])

    def test_wrong_scope_version_and_changed_results_are_rejected(self):
        mid = self.finish_domain(); tid = next(iter(self.f.state['tasks']))
        for patch_value in ({'task_id': tid}, {'questionnaire_version': ATTRIBUTE_VERSION}, {'evaluation_revision': 0}):
            payload = {'module_instance_id': mid, 'task_id': None, 'condition': 'E', 'evaluation_revision': 1,
                       'questionnaire_version': ATTRIBUTE_SUMMARY_VERSION, 'answers': answers(), **patch_value}
            with self.assertRaises(APIError): self.f.send('save_feedback', payload)
        for c in 'EANS': self.f.summary(mid, c)
        self.f.store.executor.results[tid]['branches']['S']['branch_revision'] += 1
        with self.assertRaises(APIError) as err: self.f.summary(mid, 'S')
        self.assertEqual(err.exception.code, 'stale_evaluation')
        with self.assertRaises(APIError): self.f.submit_summary(mid)

    def test_partial_summary_export_never_counts_finished_tasks_as_rated(self):
        mid = self.finish_domain()
        self.f.summary(mid, 'S', {'A0': {'status': 'unable_to_judge', 'value': None}})
        self.f.send('pause', {}); self.f.send('resume', {})
        out = export_run(self.f.store, self.f.run, self.root / 'partial')
        self.assertEqual(out['counts']['attribute_feedback'], 0)
        incomplete = [json.loads(line) for line in (self.root / 'partial/incomplete_records.jsonl').read_text().splitlines()]
        self.assertEqual(sum(r['kind'] == 'questionnaire_draft' for r in incomplete), 4)
        self.assertFalse(any(r['kind'] in ('unsubmitted_task', 'unfinished_task') for r in incomplete))
        self.assertTrue(any(r['kind'] == 'attribute_feedback_not_submitted' and r['domain'] == 'speech_rate' for r in incomplete))

    def test_full_run_exports_16_attribute_rows_26_natural_items_and_five_preferences(self):
        self.f.finish_attributes()
        mid = self.f.natural(); self.f.feedback(mid, None)
        self.f.send('submit_natural', {'module_instance_id': mid, 'evaluation_revision': 1})
        self.f.send('end_run', {'end_reason': 'normal_completion'})
        out = export_run(self.f.store, self.f.run, self.root / 'complete')
        self.assertEqual([out['counts'][k] for k in ('attribute_feedback', 'natural_feedback', 'preferences', 'incomplete_records')], [16, 1, 5, 0])
        self.assertEqual(out['export_schema_version'], 'study-export-v2')
        with (self.root / 'complete/attribute_feedback.csv').open(encoding='utf-8-sig') as stream: rows = list(csv.DictReader(stream))
        self.assertEqual({r['domain'] for r in rows}, {'speech_rate', 'reply_length', 'tone', 'voice'})
        for row in rows:
            self.assertEqual(row['collection_unit'], 'attribute'); self.assertEqual(row['task_id'], '')
            self.assertEqual(len(json.loads(row['task_completions'])), 8)
            self.assertEqual(len(json.loads(row['evaluation'])['tasks']), 8)
            self.assertEqual(row['A0_value'], '1')
            self.assertEqual(row['questionnaire_version'], ATTRIBUTE_SUMMARY_VERSION)
        natural_q = next(q for q in self.f.state['questionnaires'].values() if q['questionnaire_version'] == NATURAL_VERSION)
        self.assertEqual(len(natural_q['answers']), 26)

    def test_summary_submit_atomic_and_replayed_after_restart(self):
        mid = self.finish_domain()
        for c in 'EANS': self.f.summary(mid, c)
        packet = self.f.packet('submit_attribute', {'module_instance_id': mid, 'evaluation_revision': 1})
        with patch.object(self.f.store, '_before_commit', side_effect=sqlite3.OperationalError()):
            with self.assertRaises(APIError): self.f.store.command(packet)
        self.assertTrue(all(q['record_stage'] == 'draft' for q in self.f.state['questionnaires'].values()))
        ack = self.f.store.command(packet)
        restarted = StudyStore(self.root / 'data')
        self.assertEqual(restarted.command(packet)['result'], ack['result'])
        self.assertEqual(len({q['submission_id'] for q in self.f.state['questionnaires'].values()}), 1)
        slim = self.f.store.client_snapshot(self.f.run)
        self.assertTrue(all(t['evaluation'] is None for t in slim['tasks'].values()))
        self.assertTrue(all(t['evaluation'] is not None for t in self.f.state['tasks'].values()))

    def test_reconciliation_accepts_submitted_summary_draft_with_module_basis(self):
        from study_reconcile import reconcile
        from study_store import digest, encoded
        mid = self.finish_domain()
        for c in 'EANS': self.f.summary(mid, c)
        packet = self.f.packet('submit_attribute', {'module_instance_id': mid, 'evaluation_revision': 1})
        self.f.store.command(packet)
        q = next(iter(self.f.state['questionnaires'].values()))
        draft = {'answers': q['answers'], 'extras': q['extras'], 'evaluation_basis': f"{mid}:{q['condition']}:1"}
        root = self.root / 'journal'; root.mkdir()
        for n, (kind, scope, payload) in enumerate((('command', self.f.run, packet), ('draft', 'draft:' + q['questionnaire_id'], draft)), 1):
            body = encoded(payload)
            item = {'sequence': n, 'kind': kind, 'scope': scope, 'request_id': packet['request_id'], 'payload': body, 'sha256': digest(body)}
            (root / f'{n:020d}.json').write_text(encoded(item))
        report = reconcile(self.f.store, self.f.run, self.f.state['revision'], root)
        self.assertEqual(report['status'], 'provided_copy_reconciled')
        self.assertEqual(report['local_drafts_to_review'], [])

    def test_numeric_a0_range_and_missingness_are_versioned(self):
        for n in range(1, 8):
            result = answers(); result['A0']['value'] = n
            self.assertEqual(validate_answers(ATTRIBUTE_SUMMARY_VERSION, result, final=True)['A0']['value'], n)
        for value in (0, 8, True, False, 4.5, '4', 'fully_met', 'partly_met', 'not_met', None):
            with self.subTest(value=value):
                result = answers(); result['A0']['value'] = value
                with self.assertRaises(APIError): validate_answers(ATTRIBUTE_SUMMARY_VERSION, result, final=True)
        result = answers(); result['A0'] = {'status': 'unable_to_judge', 'value': None}
        self.assertEqual(validate_answers(ATTRIBUTE_SUMMARY_VERSION, result, final=True)['A0'], result['A0'])
        with self.assertRaises(APIError): validate_answers(ATTRIBUTE_SUMMARY_VERSION, {}, final=True)
        for version in (ATTRIBUTE_VERSION, LEGACY_ATTRIBUTE_SUMMARY_VERSION):
            self.assertEqual(validate_answers(version, legacy_answers(), final=True)['A0']['value'], 'not_met')
            with self.assertRaises(APIError): validate_answers(version, answers(), final=True)
        # The independent natural questionnaire keeps its categorical completion item.
        self.assertEqual(validate_answers(NATURAL_VERSION, legacy_answers(True), final=True)['N0']['value'], 'partly_met')

    def test_numeric_endpoint_gates_unmet_reasons_without_converting_answers(self):
        mid = self.finish_domain()
        reasons = {'reasons': ['target_mismatch'], 'comment': '', 'comment_confirmed': False}
        data = answers(); data['A0']['value'] = 7
        before = self.f.state
        with self.assertRaises(APIError): self.f.summary(mid, data=data, extras=reasons)
        self.assertEqual(self.f.state, before)
        for n in range(1, 7):
            data['A0']['value'] = n
            self.f.summary(mid, data=data, extras=reasons)
            q = next(q for q in self.f.state['questionnaires'].values() if q['condition'] == 'E')
            self.assertEqual(q['answers']['A0']['value'], n)
            self.assertEqual(q['extras']['reasons'], ['target_mismatch'])
        data['A0'] = {'status': 'unable_to_judge', 'value': None}
        self.f.summary(mid, data=data, extras=reasons)
        data['A0'] = {'status': 'answered', 'value': 7}
        self.f.summary(mid, data=data)
        q = next(q for q in self.f.state['questionnaires'].values() if q['condition'] == 'E')
        self.assertEqual(q['answers']['A0']['value'], 7)
        self.assertEqual(q['extras']['reasons'], [])

    def test_legacy_summary_resume_and_export_preserve_categorical_answers(self):
        # Old manifests had no selector, including runs that had not reached feedback yet.
        for version in (None, LEGACY_ATTRIBUTE_SUMMARY_VERSION):
            with self.subTest(version=version):
                folder = self.root / ('legacy-implicit' if version is None else 'legacy-explicit')
                f = SummaryFixture(folder, full=False, version=version)
                mid = f.module()
                f.store = StudyStore(folder); f.store.executor = FixtureExecution()
                f.task(mid)
                for c in 'EANS': f.summary(mid, c)
                old = f.state
                with self.assertRaises(APIError):
                    f.summary(mid, data=answers(), questionnaire_version=ATTRIBUTE_SUMMARY_VERSION)
                self.assertEqual(f.state, old)
                f.submit_summary(mid)
                f.store = StudyStore(folder)
                export_run(f.store, f.run, folder / 'export')
                with (folder / 'export/attribute_feedback.csv').open(encoding='utf-8-sig') as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), 4)
                for row in rows:
                    self.assertEqual(row['collection_unit'], 'attribute')
                    self.assertEqual(row['questionnaire_version'], LEGACY_ATTRIBUTE_SUMMARY_VERSION)
                    self.assertEqual(row['A0_value'], 'not_met')
                    self.assertEqual(len(json.loads(row['task_completions'])), 1)
                self.assertEqual(f.state['manifest'], old['manifest'])

    def test_invalid_or_task_scope_summary_selector_is_rejected(self):
        for version, unit in (('attribute-summary-feedback-v99', 'attribute'), (ATTRIBUTE_VERSION, 'attribute'),
                              (ATTRIBUTE_SUMMARY_VERSION, 'task')):
            spec = manifest(); spec.update(attribute_feedback_unit=unit, attribute_questionnaire_version=version)
            payload = {'participant_id': 'ENG-version', 'collection_kind': 'engineering', 'execution_mode': 'mock', 'manifest': spec}
            body = {'request_id': __import__('uuid').uuid4().hex, 'operation': 'create_run', 'expected_revision': 0,
                    'payload_json': json.dumps(payload)}
            with self.assertRaises(APIError) as error: self.f.store.command(body)
            self.assertEqual(error.exception.code, 'invalid_manifest')

    def test_v2_summary_numeric_a0_is_not_reinterpreted_as_category(self):
        version = NUMERIC_SINGLE_ATTRIBUTE_SUMMARY_VERSION
        for n in (1, 4, 7):
            result = answers(version); result['A0']['value'] = n
            self.assertEqual(validate_answers(version, result, final=True)['A0']['value'], n)
        with self.assertRaises(APIError): validate_answers(version, legacy_answers(), final=True)
        reasons = {'reasons': ['target_mismatch']}
        result = answers(version); result['A0']['value'] = 7
        with self.assertRaises(APIError): extras(reasons, result, version=version)
        result['A0']['value'] = 4
        self.assertEqual(extras(reasons, result, version=version)['reasons'], ['target_mismatch'])
        folder = self.root / 'numeric-v2'
        f = SummaryFixture(folder, full=False, version=version, preference_version=LEGACY_PREFERENCE_VERSION)
        mid = f.module(); f.task(mid)
        f.store = StudyStore(folder)
        for c in 'EANS': f.summary(mid, c)
        f.submit_summary(mid)
        export_run(f.store, f.run, folder / 'export')
        with (folder / 'export/attribute_feedback.csv').open(encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({r['questionnaire_version'] for r in rows}, {version})
        self.assertEqual({r['A0_value'] for r in rows}, {'1'})

    def test_preference_v2_all_four_survives_restart_retry_and_export(self):
        mid = self.finish_domain()
        for c in 'EANS': self.f.summary(mid, c)
        self.f.submit_summary(mid)
        answer = {'choice_kind':'selected','selected_conditions':list('SNAE')}
        packet = self.f.packet('preference', {'scope':'attribute','domain':'speech_rate','answers':answer})
        ack = self.f.store.command(packet)
        restarted = StudyStore(self.root / 'data')
        replay = restarted.command(packet)
        self.assertTrue(replay['idempotent_replay']); self.assertEqual(replay['result'], ack['result'])
        pref = restarted.read(self.f.run)['preferences']['speech_rate']
        self.assertEqual(pref['questionnaire_version'], PREFERENCE_VERSION)
        self.assertEqual(pref['answers']['selected_conditions'], list('EANS'))
        out = self.root / 'preference-export'
        export_run(restarted, self.f.run, out)
        with (out / 'preferences.csv').open(encoding='utf-8-sig') as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['questionnaire_version'], PREFERENCE_VERSION)
        self.assertEqual(json.loads(row['answers'])['selected_conditions'], list('EANS'))

    def test_v2_preference_rejects_removed_or_mixed_categories(self):
        mid = self.finish_domain()
        for c in 'EANS': self.f.summary(mid, c)
        self.f.submit_summary(mid)
        before = self.f.state
        for kind, selected in [('unable_to_compare',[]), ('none_acceptable',[]), ('no_clear_preference',['S']), ('selected',[]), ('selected',['S','S'])]:
            with self.subTest(kind=kind, selected=selected):
                with self.assertRaises(APIError):
                    self.f.send('preference', {'scope':'attribute','domain':'speech_rate','answers':{'choice_kind':kind,'selected_conditions':selected}})
                self.assertEqual(self.f.state, before)
        self.f.send('preference', {'scope':'attribute','domain':'speech_rate','answers':{'choice_kind':'no_clear_preference','selected_conditions':[]}})
        self.assertEqual(self.f.state['preferences']['speech_rate']['answers']['selected_conditions'], [])

    def test_legacy_preference_selector_omission_restores_and_exports_without_relabelling(self):
        for version in (None, LEGACY_PREFERENCE_VERSION):
            folder = self.root / ('old-pref-implicit' if version is None else 'old-pref-explicit')
            f = SummaryFixture(folder, full=False, version=NUMERIC_SINGLE_ATTRIBUTE_SUMMARY_VERSION, preference_version=version)
            mid = f.module(); f.task(mid)
            for c in 'EANS': f.summary(mid, c)
            f.submit_summary(mid)
            manifest_before = deepcopy(f.state['manifest'])
            f.store = StudyStore(folder)
            with self.assertRaises(APIError):
                f.send('preference', {'scope':'attribute','domain':'speech_rate','answers':{'choice_kind':'selected','selected_conditions':list('EANS')}})
            f.send('preference', {'scope':'attribute','domain':'speech_rate','answers':{'choice_kind':'unable_to_compare','selected_conditions':[]}})
            pref = f.state['preferences']['speech_rate']
            self.assertEqual(pref['questionnaire_version'], LEGACY_PREFERENCE_VERSION)
            self.assertEqual(f.state['manifest'], manifest_before)
            f.store = StudyStore(folder)
            export_run(f.store, f.run, folder / 'export')
            with (folder / 'export/preferences.csv').open(encoding='utf-8-sig') as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row['questionnaire_version'], LEGACY_PREFERENCE_VERSION)
            self.assertEqual(json.loads(row['answers'])['choice_kind'], 'unable_to_compare')

    def test_unknown_preference_selector_is_rejected(self):
        spec = manifest(); spec['preference_questionnaire_version'] = 'strategy-preference-v99'
        packet = {'request_id': __import__('uuid').uuid4().hex, 'operation':'create_run', 'expected_revision':0,
                  'payload_json':json.dumps({'participant_id':'ENG-versions','collection_kind':'engineering','execution_mode':'mock','manifest':spec})}
        with self.assertRaises(APIError): self.f.store.command(packet)


class SummaryRuntime(unittest.TestCase):
    view = flow_tests.Flow.view; action = flow_tests.Flow.action; settle = flow_tests.Flow.settle; revealed = flow_tests.Flow.revealed
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.model = GenerationFixture()
        self.server = Server(('127.0.0.1', 0), Experiment(self.model, self.tmp.name))
        self.f = SummaryFixture(Path(self.tmp.name) / 'study', full=False, store=self.server.study)
        self.mid = self.f.module()
        self.tid = self.f.send('open_task', {'module_instance_id': self.mid, 'task_code': self.f.state['manifest']['tasks'][0]['task_code']})['task_id']
        self.rid = self.f.send('launch_runtime', {'target_id': self.tid})['runtime_id']
    def tearDown(self): self.server.server_close(); self.tmp.cleanup()

    def test_linked_runtime_finish_restore_and_summary_stale_guard(self):
        with self.assertRaises(APIError): self.f.send('finish_task', {'task_id': self.tid})
        self.revealed()
        self.f.send('finish_task', {'task_id': self.tid})
        with self.assertRaises(APIError): self.action('settings', 'S', patch={'tone': 'friendly'})
        self.action('select', condition='A')
        self.assertEqual(self.view()['selected_condition'], 'A')
        with self.assertRaises(APIError): self.f.send('launch_runtime', {'target_id': self.mid})
        self.server.server_close()
        self.server = Server(('127.0.0.1', 0), Experiment(self.model, self.tmp.name)); self.f.store = self.server.study
        for c in 'EANS': self.f.summary(self.mid, c)
        self.f.submit_summary(self.mid); self.f.pref()
        self.assertEqual(len(self.f.state['questionnaires']), 4)
        self.assertIsNone(self.f.state['tasks'][self.tid]['submission_id'])

    def test_runtime_tampering_invalidates_summary_before_save(self):
        self.revealed(); self.f.send('finish_task', {'task_id': self.tid})
        # Bypass the public frozen guard to emulate incompatible external state.
        view = self.view()
        self.server.comparisons.mutate(self.rid, 'select', {'request_id': 'fixture-select', 'expected_revision': view['revision'], 'condition': 'A'})
        # A view-only selection is harmless and must not invalidate result bindings.
        self.f.summary(self.mid, 'E')
        from study_store import uid
        view = self.view()
        self.server.comparisons.mutate(self.rid, 'settings', {'request_id': uid(), 'expected_branch_revision': view['branches']['S']['branch_revision'], 'patch': {'tone': 'friendly'}}, condition='S')
        self.settle()
        with self.assertRaises(APIError): self.f.summary(self.mid, 'S')

    def test_http_finish_receipt_survives_unavailable_runtime(self):
        from study_store import encoded
        self.revealed()
        packet = self.f.packet('finish_task', {'task_id': self.tid})
        ack = self.f.store.command(packet)
        self.server.study_flow.blocked.add(self.rid)
        thread = threading.Thread(target=self.server.serve_forever); thread.start()
        try:
            client = HTTPConnection(*self.server.server_address)
            client.request('POST', '/study/commands', encoded(packet), {'Content-Type': 'application/json'})
            response = client.getresponse(); result = json.loads(response.read()); client.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(result['result'], ack['result'])
            self.assertTrue(result['idempotent_replay'])
        finally:
            self.server.shutdown(); thread.join()


if __name__ == '__main__': unittest.main()
