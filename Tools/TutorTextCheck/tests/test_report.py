"""Offline report evidence boundaries and browser-export schema checks."""
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report import collect, generate, canonical, digest, release_identity, PAGE, ROOT
from attribute_feedback import VERSION, LEGACY_VERSION, NUMERIC_SINGLE_VERSION, blank_feedback, validate_feedback

NODE = shutil.which('node') or '/Users/alanwong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'batch.json').write_text(json.dumps({'batch_id': 'fixture-batch',
            'catalog_sha256': digest((ROOT / 'Assets/Project/Resources/Tutor/StudyTaskSequence.json').read_bytes())}))
        self.path = self.root / 'tasks/R1-1/checkpoint.json'
        self.path.parent.mkdir(parents=True)
        self.branches = {}
        runtime = {}
        for c in 'EANS':
            state = {'revision': 1, 'settings': {'speech_rate': .9}, 'conversation': []}
            b = {'branch_id': 'branch-' + c, 'branch_revision': 1, 'status': 'ready',
                 'outcome': 'act', 'message': 'Fixture output', 'state': state}
            self.branches[c] = {'branch_revision': 1, 'result': b}
            runtime[c] = {'branch_id': b['branch_id'], 'revision': 1, 'status': 'ready',
                          'outcome': b['outcome'], 'message': b['message'], 'state': state, 'answers': []}
        rid = release_identity(self.branches)
        self.release_dir = self.root / 'results/R1-1' / rid
        self.release_dir.mkdir(parents=True)
        self.record = {'task_code': 'R1-1', 'runtime_id': 'fixture-runtime', 'pending': None,
                       'runtime': {'processing': False, 'task': {'_latest_reveal': {'reveal_id': 'reveal'}, '_branches': runtime}},
                       'published_release': {'directory': str(self.release_dir.relative_to(self.root)), 'release_id': rid},
                       'operations': [], 'answers': {}}
        audio = {}
        for c in 'EANS':
            f = self.root / 'audio' / f'{c}.wav'
            f.parent.mkdir(exist_ok=True)
            f.write_bytes(b'fixture audio bytes')
            audio[c] = {'condition': c, 'runtime_id': 'fixture-runtime', 'file': f'audio/{c}.wav',
                        'sha256': digest(f.read_bytes()), 'text': 'Hello from a fixture.', 'purpose': 'sample'}
        clarification = {c: {'occurred': False, 'count': 0, 'turns': []} for c in 'EANS'}
        clarification['A'] = {'occurred': True, 'count': 1, 'turns': [
            {'question_id': 'q-a', 'question': 'Did you mean the default speed?', 'answer': 'Yes, the default speed.',
             'source': 'assistant_authored_user_authorized'}]}
        self.release = {'task_code': 'R1-1', 'batch_id': 'fixture-batch', 'request': 'Set the speed.',
                        'release_id': rid, 'view': {'results_visible': True, 'branches': self.branches},
                        'audio': audio, 'clarifications': clarification, 'questionnaire_version': 'attribute-feedback-v3'}
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps({'payload': self.record, 'sha256': digest(canonical(self.record))}))
        (self.release_dir / 'result.json').write_text(json.dumps(self.release))

    def generated_release(self):
        self.release.update(response_mode='generated_reply', collection_unit='attribute', questionnaire_version=VERSION)
        self.release['view'].update(baseline={'conversation': []}, latest_reveal={'reveal_id': 'new-reveal'})
        for c in 'EANS':
            state = self.branches[c]['result']['state']
            exchange = {'id': 1, 'settings': deepcopy(state['settings']),
                        'messages': [{'role': 'user', 'content': 'Make that change.'},
                                     {'role': 'assistant', 'content': 'Actual model reply ' + c}]}
            state['conversation'] = [exchange]
            self.release['audio'][c].update(purpose='reply', branch_revision=1, exchange_id=1,
                text=exchange['messages'][-1]['content'], settings=deepcopy(exchange['settings']), latest_reveal_id='new-reveal')
        rid = release_identity(self.branches)
        self.release['release_id'] = self.record['published_release']['release_id'] = rid
        self.write()

    def test_generated_reply_audio_is_bound_to_its_exact_frozen_exchange(self):
        self.generated_release()
        data = collect(self.root)
        self.assertEqual(data['audio_count'], 4)
        self.assertTrue(all(card['purpose'] == 'reply' for card in data['tasks'][0]['conditions'].values()))
        original = deepcopy(self.release['audio']['A'])
        for changed in ({'purpose': 'sample'}, {'branch_revision': 0}, {'exchange_id': 0},
                        {'text': 'An unrelated reply.'}, {'settings': {'speech_rate': 1.2}},
                        {'latest_reveal_id': 'old-reveal'}):
            with self.subTest(changed=changed):
                self.release['audio']['A'] = {**original, **changed}; self.write()
                with self.assertRaisesRegex(ValueError, 'generated reply audio'):
                    collect(self.root)
        self.release['audio']['A'] = original

    def test_v2_questionnaire_can_rate_v1_audio_without_rewriting_results(self):
        self.generated_release()
        self.release['questionnaire_version'] = LEGACY_VERSION; self.write()
        before = (self.release_dir / 'result.json').read_bytes()
        data = collect(self.root)
        self.assertEqual(data['questionnaire_version'], VERSION)
        self.assertEqual(data['source_questionnaire_version'], LEGACY_VERSION)
        self.assertEqual(data['items'][0]['scale'], 'fulfillment7')
        self.assertEqual(collect(self.root, LEGACY_VERSION)['items'][0]['scale'], 'category')
        self.assertEqual((self.release_dir / 'result.json').read_bytes(), before)

    def test_generated_release_cannot_relabel_baseline_or_old_summary_version(self):
        self.generated_release()
        self.release['view']['baseline']['conversation'] = deepcopy(self.branches['A']['result']['state']['conversation'])
        self.write()
        with self.assertRaisesRegex(ValueError, 'new conversation exchange'): collect(self.root)
        self.release['view']['baseline']['conversation'] = []
        self.release['questionnaire_version'] = 'attribute-feedback-v3'; self.write()
        with self.assertRaisesRegex(ValueError, 'attribute-summary contract'): collect(self.root)
        self.release['questionnaire_version'] = VERSION
        for field, value in (('baseline_audio', deepcopy(self.release['audio']['E'])),
                             ('listening_materials', [{'label': 'Old sample', 'audio': self.release['audio']['E']}])):
            self.release[field] = value; self.write()
            with self.assertRaisesRegex(ValueError, 'fixed baseline or reference'): collect(self.root)
            del self.release[field]

    def test_new_batch_cannot_hide_generated_mode_but_legacy_samples_stay_readable(self):
        legacy = collect(self.root)
        self.assertEqual(legacy['tasks'][0]['conditions']['A']['purpose'], 'sample')
        metadata = json.loads((self.root / 'batch.json').read_text())
        metadata['response_mode'] = 'generated_reply'
        (self.root / 'batch.json').write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, 'attribute-summary contract'): collect(self.root)
        self.generated_release()
        self.assertEqual(collect(self.root)['audio_count'], 4)

    def publish_attribute(self):
        """Use isolated fixture evidence for all eight tasks, never real results."""
        first = collect(self.root)['attributes'][0]
        for code in first['task_codes'][1:]:
            record, release = deepcopy(self.record), deepcopy(self.release)
            record['task_code'] = release['task_code'] = code
            relative = f"results/{code}/{release['release_id']}"
            record['published_release']['directory'] = relative
            folder = self.root / relative
            folder.mkdir(parents=True)
            (folder / 'result.json').write_text(json.dumps(release))
            path = self.root / 'tasks' / code / 'checkpoint.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'payload': record, 'sha256': digest(canonical(record))}))
        return collect(self.root)

    def browser_logic(self, data, expression):
        script = re.search(r'<script>\s*(.*?)</script>', PAGE, re.S).group(1)
        script = re.sub(r'\nrender\(\);\s*$', '', script)
        runner = r'''const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const memory=new Map([['tutor-text-feedback-v3:fixture-batch:R1-1:old','DO NOT MIGRATE']]);
const reads=[];
const ctx=vm.createContext({document:{getElementById:id=>id==='report-data'?{textContent:JSON.stringify(input.data)}:{addEventListener(){}}},localStorage:{getItem:k=>{reads.push(k);return memory.get(k)||null;},setItem:(k,v)=>memory.set(k,v)},memory,reads});
vm.runInContext(input.script,ctx);process.stdout.write(JSON.stringify(vm.runInContext(input.expression,ctx)));'''
        completed = subprocess.run([NODE, '-e', runner], input=json.dumps({'data': data, 'script': script, 'expression': expression}), text=True, capture_output=True, check=True)
        return json.loads(completed.stdout)

    def test_only_published_task_has_audio_and_questionnaire(self):
        data = collect(self.root)
        self.assertEqual(len(data['tasks']), 32)
        task = data['tasks'][0]
        self.assertEqual(task['status'], 'published')
        self.assertEqual(set(task['conditions']), set('EANS'))
        self.assertEqual(task['conditions']['A']['clarification']['status'], 'yes')
        self.assertEqual(task['conditions']['E']['clarification']['status'], 'no')
        self.assertEqual(task['conditions']['A']['clarification']['turns'][0]['answer'], 'Yes, the default speed.')
        self.assertEqual([i['id'] for i in data['items']], ['A0', 'A1', 'A2', 'A3', 'A4'])
        self.assertTrue(all('conditions' not in t for t in data['tasks'][1:]))
        self.assertEqual(data['questionnaire_version'], VERSION)
        self.assertEqual(data['source_questionnaire_version'], 'attribute-feedback-v3')
        self.assertEqual(task['questionnaire_version'], 'attribute-feedback-v3')
        self.assertEqual(len(data['attributes']), 4)
        self.assertTrue(all(len(g['task_codes']) == 8 and g['status'] == 'pending' for g in data['attributes']))
        base = json.loads((ROOT / 'Assets/Project/Resources/Tutor/StudyQuestionnaires.json').read_text())
        for item in data['items']:
            original = next(i for i in base['legacy_attribute_items'] if i['id'] == item['id'])
            self.assertEqual(item['source'], original['source'])
            self.assertNotEqual(item['text'], original['text'])
            self.assertIn('attribute', item['text'])

    def test_attribute_requires_all_eight_current_published_releases(self):
        data = self.publish_attribute()
        group = data['attributes'][0]
        self.assertEqual(group['status'], 'published')
        self.assertEqual(len(group['task_releases']), 8)
        self.assertEqual(group['audio_count'], 32)
        previous = group['release_set_id']
        self.record['pending'] = {'operation': 'answer'}
        self.write()
        group = collect(self.root)['attributes'][0]
        self.assertEqual(group['status'], 'pending')
        self.assertNotEqual(group['release_set_id'], previous)
        self.assertEqual(len(group['task_releases']), 7)

    def test_frozen_catalog_preserves_archived_task_spec_and_display_identity(self):
        catalog = json.loads((ROOT / 'Assets/Project/Resources/Tutor/StudyTaskSequence.json').read_text())
        spec = catalog['modules'][0]['tasks'][0]
        spec['display_code'] = 'DISPLAY-1'
        spec['instructions'] = 'Frozen task wording for this batch.'
        raw = json.dumps(catalog).encode()
        (self.root / 'catalog.json').write_bytes(raw)
        metadata = json.loads((self.root / 'batch.json').read_text())
        metadata['catalog_sha256'] = digest(raw)
        (self.root / 'batch.json').write_text(json.dumps(metadata))
        fake_project = self.root / 'project-with-no-global-catalog'
        source = Path('Assets/Project/Resources/Tutor/StudyQuestionnaires.json')
        (fake_project / source).parent.mkdir(parents=True)
        (fake_project / source).write_bytes((ROOT / source).read_bytes())
        with patch('report.ROOT', fake_project):
            data = collect(self.root)
        task = data['tasks'][0]
        self.assertEqual(task['task_code'], 'R1-1')
        self.assertEqual(task['display_code'], 'DISPLAY-1')
        self.assertEqual(task['goal'], 'Frozen task wording for this batch.')
        self.assertIn('R1-1', data['attributes'][0]['task_releases'])
        self.assertNotIn('DISPLAY-1', data['attributes'][0]['task_releases'])
        (self.root / 'catalog.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'catalog'):
            collect(self.root)

    def test_baseline_and_reference_audio_are_validated_and_counted_separately(self):
        baseline = deepcopy(self.release['audio']['E'])
        baseline['purpose'] = 'baseline'
        reference = deepcopy(self.release['audio']['N'])
        reference['purpose'] = 'reference'
        self.release['baseline_audio'] = baseline
        self.release['listening_materials'] = [{'label': 'Previously heard voice', 'audio': reference},
                                             {'label': 'Target voice', 'audio': reference}]
        self.write()
        data = collect(self.root)
        task = data['tasks'][0]
        self.assertEqual(task['baseline_audio']['audio_url'], 'audio/E.wav')
        self.assertEqual(task['baseline_audio']['purpose'], 'baseline')
        self.assertEqual([m['label'] for m in task['listening_materials']], ['Previously heard voice', 'Target voice'])
        self.assertEqual(data['audio_count'], 4)
        self.assertEqual(data['baseline_audio_count'], 1)
        self.assertEqual(data['listening_material_count'], 2)

    def test_comparison_audio_rejects_wrong_runtime_hash_or_path(self):
        for kind in ('baseline', 'reference'):
            for problem in ('runtime', 'checksum', 'path', 'metadata'):
                with self.subTest(kind=kind, problem=problem):
                    audio = deepcopy(self.release['audio']['E'])
                    expected = 'metadata'
                    if problem == 'runtime': audio['runtime_id'] = 'other-runtime'
                    elif problem == 'checksum': audio['sha256'] = '0' * 64; expected = 'checksum'
                    elif problem == 'path': audio['file'] = '../outside.wav'; expected = 'paths'
                    else: audio['text'] = None
                    self.release.pop('baseline_audio', None)
                    self.release.pop('listening_materials', None)
                    if kind == 'baseline': self.release['baseline_audio'] = audio
                    else: self.release['listening_materials'] = [{'label': 'Reference', 'audio': audio}]
                    self.write()
                    with self.assertRaisesRegex(ValueError, expected):
                        collect(self.root)

    def test_comparison_materials_are_optional_and_never_leak_pending_results(self):
        task = collect(self.root)['tasks'][0]
        self.assertIsNone(task['baseline_audio'])
        self.assertEqual(task['listening_materials'], [])
        self.release['baseline_audio'] = deepcopy(self.release['audio']['E'])
        self.release['listening_materials'] = [{'label': 'Target voice', 'audio': deepcopy(self.release['audio']['A'])}]
        self.record['pending'] = {'operation': 'answer'}
        self.write()
        data = collect(self.root)
        self.assertNotIn('baseline_audio', data['tasks'][0])
        self.assertNotIn('listening_materials', data['tasks'][0])
        self.assertEqual(data['baseline_audio_count'], 0)
        self.assertEqual(data['listening_material_count'], 0)

    def test_unresolved_and_unchanged_results_retain_audio_and_actual_settings(self):
        self.release['view']['baseline'] = {'settings': {'speech_rate': .9}}
        self.branches['N']['result']['outcome'] = 'unresolved'
        self.branches['N']['result']['message'] = 'The request remains unresolved.'
        self.record['runtime']['task']['_branches']['N']['outcome'] = 'unresolved'
        self.record['runtime']['task']['_branches']['N']['message'] = 'The request remains unresolved.'
        self.branches['A']['result']['state']['settings']['speech_rate'] = .7
        rid = release_identity(self.branches)
        self.release['release_id'] = self.record['published_release']['release_id'] = rid
        self.write()
        data = collect(self.root)
        cards = data['tasks'][0]['conditions']
        self.assertEqual(data['audio_count'], 4)
        self.assertEqual(data['technical_failure_count'], 0)
        self.assertTrue(cards['N']['audio_url'])
        self.assertEqual(cards['N']['result']['outcome'], 'unresolved')
        self.assertEqual(cards['N']['result']['message'], 'The request remains unresolved.')
        self.assertEqual(cards['N']['result']['setting_changes'], [])
        self.assertEqual(cards['E']['result']['settings'], {'speech_rate': .9})
        self.assertEqual(cards['A']['result']['setting_changes'], [{'field': 'speech_rate', 'before': .9, 'after': .7}])
        self.assertNotIn('success', cards['A']['result'])
        if Path(NODE).exists():
            labels = self.browser_logic(data, "Object.fromEntries(CONDITIONS.map(c=>[c,resultLabel(DATA.tasks[0].conditions[c].result)]))")
            self.assertEqual(labels['N'], 'Unresolved')
            self.assertEqual(labels['E'], 'No setting change')
            self.assertEqual(labels['A'], 'Settings changed')

    def test_pending_and_stale_results_are_hidden(self):
        for mode in ('pending', 'stale', 'unrevealed'):
            with self.subTest(mode=mode):
                old = deepcopy(self.record)
                if mode == 'pending': self.record['pending'] = {'operation': 'answer'}
                elif mode == 'stale': self.record['runtime']['task']['_branches']['S']['revision'] = 2
                else: self.record['runtime']['task']['_latest_reveal'] = None
                self.write()
                task = collect(self.root)['tasks'][0]
                self.assertEqual(task['status'], 'pending')
                self.assertNotIn('conditions', task)
                self.assertNotIn('request', task)
                self.record = old

    def test_corrupt_checkpoint_refused(self):
        data = json.loads(self.path.read_text())
        data['payload']['pending'] = True
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            collect(self.root)

    def test_corrupt_audio_and_traversal_refused(self):
        (self.root / 'audio/A.wav').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'audio checksum'):
            collect(self.root)
        self.release['audio']['E']['file'] = '../other.wav'
        self.write()
        with self.assertRaisesRegex(ValueError, 'paths'):
            collect(self.root)

    def test_changed_publication_identity_refused(self):
        self.release['view']['branches']['A']['result']['message'] = 'tampered'
        self.write()
        with self.assertRaisesRegex(ValueError, 'branch checksum'):
            collect(self.root)

    def test_material_and_questionnaire_version_mismatches_refused(self):
        self.release['questionnaire_version'] = 'attribute-feedback-v2'
        self.write()
        with self.assertRaisesRegex(ValueError, 'questionnaire version'):
            collect(self.root)
        (self.root / 'batch.json').write_text(json.dumps({'batch_id': 'fixture-batch', 'catalog_sha256': '0'*64}))
        with self.assertRaisesRegex(ValueError, 'catalog'):
            collect(self.root)

    def test_followup_probe_retains_source_and_original_request(self):
        probe = 'How can active recall help me study?'
        self.release['followup_questions'] = [
            {'text': probe, 'condition': c, 'source': 'standardized_evaluation_probe'} for c in 'EANS']
        self.write()
        task = collect(self.root)['tasks'][0]
        self.assertEqual(task['request'], 'Set the speed.')
        self.assertEqual(len(task['followup_questions']), 4)
        self.assertEqual({q['text'] for q in task['followup_questions']}, {probe})
        self.assertTrue(all(q['source'] == 'standardized_evaluation_probe' for q in task['followup_questions']))
        self.assertIn('new Set(followups.map(q=>q.text))', PAGE)
        self.assertIn('not a spontaneous user request', PAGE)

    def test_legacy_missing_clarification_is_unknown_not_no(self):
        del self.release['clarifications']
        self.write()
        task = collect(self.root)['tasks'][0]
        self.assertTrue(all(v['clarification']['status'] == 'unknown' for v in task['conditions'].values()))

    def test_explicit_stopped_failure_keeps_other_audio_and_clarification(self):
        self.release['audio']['A'] = None
        self.release['technical_failures'] = {'A': {'error_code': 'invalid_result'}}
        self.branches['A']['result']['status'] = 'stopped'
        self.record['runtime']['task']['_branches']['A']['status'] = 'stopped'
        rid = release_identity(self.branches)
        self.release['release_id'] = rid
        self.record['published_release']['release_id'] = rid
        self.write()
        data = collect(self.root)
        task = data['tasks'][0]
        self.assertEqual(task['status'], 'published')
        self.assertIsNone(task['conditions']['A']['audio_url'])
        self.assertEqual(task['conditions']['A']['technical_failure']['error_code'], 'invalid_result')
        self.assertEqual(task['conditions']['A']['clarification']['status'], 'yes')
        self.assertEqual(task['conditions']['A']['clarification']['turns'][0]['answer'], 'Yes, the default speed.')
        self.assertTrue(all(task['conditions'][c]['audio_url'] for c in 'ENS'))
        self.assertEqual(data['audio_count'], 3)
        self.assertEqual(data['technical_failure_count'], 1)
        self.assertNotIn('answers', task['conditions']['A'])

    def test_missing_audio_without_stopped_failure_evidence_is_rejected(self):
        self.release['audio']['A'] = None
        self.write()
        with self.assertRaisesRegex(ValueError, 'stopped branch'):
            collect(self.root)
        self.release['technical_failures'] = {'A': {'error_code': 'invalid_result'}}
        self.write()
        with self.assertRaisesRegex(ValueError, 'stopped branch'):
            collect(self.root)

    def test_legacy_answer_links_question_and_author_source(self):
        del self.release['clarifications']
        self.record['runtime']['task']['_branches']['A']['answers'] = [
            {'question_id': 'old', 'question': {'text': 'Which speed?'}, 'response': {'text': 'Default.'}}]
        self.record['operations'] = [{'operation': 'answer', 'condition': 'A', 'body': {'question_id': 'old', 'response': {'text': 'Default.'}}}]
        self.record['answers']['old'] = {'text': 'Default.', 'input_source': 'assistant_authored_user_authorized'}
        self.write()
        turn = collect(self.root)['tasks'][0]['conditions']['A']['clarification']['turns'][0]
        self.assertEqual(turn['question'], 'Which speed?')
        self.assertEqual(turn['source'], 'assistant_authored_user_authorized')

    def test_clarification_count_must_match_evidence(self):
        self.release['clarifications']['A']['count'] = 0
        self.write()
        with self.assertRaisesRegex(ValueError, 'count'):
            collect(self.root)

    def test_html_embedded_data_cannot_close_script(self):
        hostile = '</script><script>alert("xss")</script>&<img src=x onerror=alert(1)>'
        self.release['request'] = hostile
        self.release['clarifications']['A']['turns'][0]['question'] = hostile
        self.write()
        result = generate(self.root)
        self.assertEqual(result['published_tasks'], 1)
        text = Path(result['file']).read_text()
        self.assertNotIn(hostile, text)
        embedded = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', text, re.S).group(1)
        self.assertEqual(json.loads(embedded)['tasks'][0]['request'], hostile)
        self.assertNotIn('innerHTML', text)
        self.assertNotIn('fetch(', text)

    def test_browser_feedback_has_no_default_scores_and_matches_schema(self):
        self.assertIn("{status:'unanswered',value:null}", PAGE)
        self.assertIn("questionnaire_version:DATA.questionnaire_version", PAGE)
        self.assertIn("{status:'unable_to_judge',value:null}", PAGE)
        self.assertIn("extras:{reasons:[],comment:'',comment_confirmed:false}", PAGE)
        self.assertIn('localStorage.setItem', PAGE)
        self.assertIn('Download all drafts (backup)', PAGE)
        self.assertIn('This does not submit data to a server.', PAGE)
        self.assertNotIn('tutor-text-feedback-v3:', PAGE)
        self.assertNotIn('download-task', PAGE)
        self.assertIn('Download completed attributes', PAGE)
        self.assertIn('Listening only: no questionnaire is required for this task.', PAGE)
        self.assertIn('Starting sample', PAGE)
        self.assertIn('This is not an output produced by any of the four strategies.', PAGE)
        self.assertIn("g.task_codes.map(taskLabel).join(', ')", PAGE)
        self.assertNotIn("el('h2',t.task_code)", PAGE)
        self.assertNotIn('`${t.task_code} ${c} output audio`', PAGE)

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_javascript_uses_display_codes_without_changing_export_identity(self):
        data = self.publish_attribute()
        for index, task in enumerate(data['tasks']):
            task['display_code'] = f'SHOWN-{index+1}'
        result = self.browser_logic(data, "({label:taskLabel('R1-1'),scope:DATA.attributes[0].task_codes.map(taskLabel),draft:blank(DATA.attributes[0])})")
        self.assertEqual(result['label'], 'SHOWN-1')
        self.assertEqual(result['scope'], [f'SHOWN-{i}' for i in range(1, 9)])
        self.assertIn('R1-1', result['draft']['task_releases'])
        self.assertNotIn('SHOWN-1', result['draft']['task_releases'])

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_javascript_blank_draft_matches_python_and_never_reads_old_task_storage(self):
        data = self.publish_attribute()
        result = self.browser_logic(data, "({draft:getDraft(DATA.attributes[0]),reads,old:memory.get('tutor-text-feedback-v3:fixture-batch:R1-1:old'),count:completion(DATA.attributes[0])})")
        self.assertEqual(result['draft'], blank_feedback(data['batch_id'], data['attributes'][0]))
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['old'], 'DO NOT MIGRATE')
        self.assertTrue(result['reads'])
        self.assertTrue(all(k.startswith('tutor-text-attribute-feedback-v1:') for k in result['reads']))
        self.assertTrue(all(data['attributes'][0]['release_set_id'] in k for k in result['reads']))
        validate_feedback(result['draft'], data, final=False)

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_javascript_twenty_answers_requires_preference_and_exports_new_bundle(self):
        data = self.publish_attribute()
        result = self.browser_logic(data, r'''(()=>{const g=DATA.attributes[0],d=getDraft(g);
for(const c of CONDITIONS)for(const id of IDS)d.conditions[c].answers[id]={status:'unable_to_judge',value:null};
const withoutPreference=completion(g);d.preference={status:'answered',value:['no_preference']};
d.conditions.E.extras.comment='Fixture comment';d.conditions.E.extras.comment_confirmed=true;
return {withoutPreference,complete:completion(g),draft:d,valid:draftValid(g,d),bundle:bundle('completed_attributes',[g])};})()''')
        self.assertEqual(result['withoutPreference'], 20)
        self.assertEqual(result['complete'], 21)
        self.assertTrue(result['valid'])
        validate_feedback(result['draft'], data)
        self.assertEqual(set(result['bundle']), {'schema', 'batch_id', 'questionnaire_version', 'kind', 'exported_at', 'records'})
        self.assertEqual(result['bundle']['schema'], 'tutor-text-attribute-feedback-bundle-v1')
        self.assertEqual(result['bundle']['kind'], 'completed_attributes')
        self.assertEqual(result['bundle']['records'], [result['draft']])
        for preference in (['E'], ['N', 'S'], ['E', 'A', 'N', 'S'], ['no_preference']):
            with self.subTest(preference=preference):
                draft = deepcopy(result['draft'])
                draft['preference'] = {'status': 'answered', 'value': preference}
                validate_feedback(draft, data)

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_javascript_rejects_wrong_scope_extra_keys_and_invalid_comment(self):
        data = self.publish_attribute()
        result = self.browser_logic(data, r'''(()=>{const g=DATA.attributes[0];const checks=[];
let d=blank(g);d.task_code='R1-1';checks.push(draftValid(g,d));
d=blank(g);d.questionnaire_version='attribute-feedback-v3';checks.push(draftValid(g,d));
d=blank(g);d.task_releases['R1-1']='old';checks.push(draftValid(g,d));
d=blank(g);d.conditions.E.extras.comment='Not confirmed';checks.push(draftValid(g,d));
d=blank(g);d.preference={status:'answered',value:'invalid'};checks.push(draftValid(g,d));
return checks;})()''')
        self.assertEqual(result, [False] * 5)

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_javascript_a0_is_numeric_and_old_drafts_have_distinct_keys(self):
        data = self.publish_attribute()
        result = self.browser_logic(data, r'''(()=>{const g=DATA.attributes[0];return {key:key(g),scores:[1,2,3,4,5,6,7].map(value=>answerValid('A0',{status:'answered',value},true)),invalid:['partly_met','4',true,0,8].map(value=>answerValid('A0',{status:'answered',value},true)),unable:answerValid('A0',{status:'unable_to_judge',value:null},true)};})()''')
        self.assertTrue(result['key'].endswith(':' + VERSION))
        self.assertEqual(result['scores'], [True] * 7)
        self.assertEqual(result['invalid'], [False] * 5)
        self.assertTrue(result['unable'])

    @unittest.skipUnless(Path(NODE).exists(), 'Node is needed for offline JavaScript contract checks')
    def test_multi_preference_toggle_restore_and_legacy_v2_are_distinct(self):
        data = self.publish_attribute()
        result = self.browser_logic(data, r'''(()=>{
let p={status:'unanswered',value:null};const steps=[];
for(const c of CONDITIONS){p=nextPreference(p,c,true);steps.push(p);}
p=nextPreference(p,'no_preference',true);steps.push(p);
p=nextPreference(p,'N',true);p=nextPreference(p,'S',true);steps.push(p);
const g=DATA.attributes[0],d=blank(g);d.preference=p;memory.set(key(g),JSON.stringify(d));
const restored=getDraft(g);const exported=bundle('draft_backup',[g]);
p=nextPreference(p,'N',false);p=nextPreference(p,'S',false);steps.push(p);
return {steps,restored:restored.preference,exported:exported.records[0].preference,
invalid:[['N','N'],['N','no_preference'],[],['unknown'],'S'].map(value=>preferenceValid({status:'answered',value},true)),
unable:preferenceValid({status:'unable_to_judge',value:null},true)};})()''')
        self.assertEqual(result['steps'][3]['value'], list('EANS'))
        self.assertEqual(result['steps'][4]['value'], ['no_preference'])
        self.assertEqual(result['restored'], {'status': 'answered', 'value': ['N', 'S']})
        self.assertEqual(result['exported'], result['restored'])
        self.assertEqual(result['steps'][-1], {'status': 'unanswered', 'value': None})
        self.assertEqual(result['invalid'], [False]*5)
        self.assertFalse(result['unable'])
        old=collect(self.root, NUMERIC_SINGLE_VERSION)
        legacy=self.browser_logic(old,"({key:key(DATA.attributes[0]),numeric:answerValid('A0',{status:'answered',value:5},true),scalar:preferenceValid({status:'answered',value:'S'},true),unable:preferenceValid({status:'unable_to_judge',value:null},true),array:preferenceValid({status:'answered',value:['S']},true)})")
        self.assertTrue(legacy['key'].endswith(':'+NUMERIC_SINGLE_VERSION))
        self.assertTrue(legacy['numeric'] and legacy['scalar'] and legacy['unable'])
        self.assertFalse(legacy['array'])

    def test_explicit_version_and_relocated_page_preserve_frozen_source(self):
        self.generated_release(); self.release['questionnaire_version']=NUMERIC_SINGLE_VERSION; self.write()
        old_page=self.root/'REVIEW_AND_QUESTIONNAIRE.html'; old_page.write_text('ARCHIVED PAGE')
        source_before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        output=self.root/'new-page'/'review.html'; output.parent.mkdir()
        result=generate(self.root,output,VERSION)
        embedded=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',output.read_text(),re.S).group(1))
        self.assertEqual(result['questionnaire_version'],VERSION)
        self.assertEqual(embedded['source_questionnaire_version'],NUMERIC_SINGLE_VERSION)
        self.assertEqual(embedded['tasks'][0]['conditions']['S']['audio_url'],'../audio/S.wav')
        self.assertEqual(embedded['items'][0]['scale'],'fulfillment7')
        for path,raw in source_before.items(): self.assertEqual(path.read_bytes(),raw)


if __name__ == '__main__':
    unittest.main()
