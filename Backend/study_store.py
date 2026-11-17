"""Durable, versioned study acquisition service (engineering/practice only).

One SQLite transaction commits the run snapshot, audit event and idempotent
receipt. This does not replay model calls or turn legacy tutor sessions formal.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

from core import APIError
from study_answers import (ATTRIBUTE_VERSION, NATURAL_VERSION, PREFERENCE_VERSION,
                           validate_answers, extras, completeness, scores)
from tutor_preferences import validate_preference
from tutor_state import validate_settings

CONTRACT = 'study-data-contract-v1'
PROTOCOL = 'study-protocol-v1.7'
DOMAINS = ('speech_rate', 'reply_length', 'tone', 'voice')
CONDITIONS = ('E', 'A', 'N', 'S')
UUID = re.compile(r'[0-9a-f]{32}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def uid(): return uuid.uuid4().hex

def now(): return datetime.now(timezone.utc).isoformat()

def encoded(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()

def require(condition, code, message, status=400):
    if not condition: raise APIError(status, code, message)


def keys(p, required, optional=()):
    require(isinstance(p, dict) and set(required) <= set(p) and not set(p) - set(required) - set(optional),
            'invalid_study_fields', 'Use exactly the documented fields for this operation.')


def bounded(value, limit=200):
    return isinstance(value, str) and 0 < len(value) <= limit


class StudyStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'study.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS participants (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (request_id TEXT PRIMARY KEY, signature TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, payload TEXT NOT NULL);
            ''')
            old = db.execute("SELECT value FROM metadata WHERE key='storage_version'").fetchone()
            require(old is None or old[0] == 'study-sqlite-v1', 'unsupported_storage_version', 'Do not open an unknown database schema.')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('storage_version','study-sqlite-v1')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA foreign_keys=ON')
            yield db
        finally:
            db.close()

    def _load(self, db, run_id):
        require(isinstance(run_id, str) and UUID.fullmatch(run_id), 'invalid_study_run_id', 'Use a registered study run ID.')
        row = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
        require(row is not None, 'study_run_not_found', 'This study run does not exist.', 404)
        return json.loads(row[0])

    def read(self, run_id):
        with self.connect() as db:
            return self._load(db, run_id)

    def client_snapshot(self, run_id):
        # Completed result bodies stay in the authoritative state/export and runtime
        # evidence. Do not copy all prior model responses into every UI refresh.
        state=self.read(run_id)
        for task in state['tasks'].values():
            if task.get('submission_id'):task['evaluation']=None
        for module in state['modules'].values():
            if module.get('submission_id'):module['evaluation']=None
        for q in state['questionnaires'].values():
            if q['record_stage']=='submitted':
                q.pop('evaluation_binding',None);q.pop('evaluation',None)
        return state

    def receipt(self, request_id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM receipts WHERE request_id=?', (request_id,)).fetchone()
            require(row is not None, 'receipt_not_found', 'No committed receipt exists for this request.', 404)
            return json.loads(row[0])

    def snapshot(self, run_id):
        # Same read transaction for state and events, including during live export.
        with self.connect() as db:
            db.execute('BEGIN')
            state = self._load(db, run_id)
            events = [dict(json.loads(r[1]), server_sequence=r[0]) for r in db.execute('SELECT sequence,payload FROM events WHERE run_id=? ORDER BY sequence', (run_id,))]
            db.execute('COMMIT')
        return state, events

    def _before_commit(self, db):
        """Fault-injection seam for tests; production performs no extra work."""

    def command(self, body):
        keys(body, ('request_id', 'operation', 'expected_revision', 'payload_json'), ('study_run_id',))
        rid, op = body['request_id'], body['operation']
        require(isinstance(rid, str) and UUID.fullmatch(rid), 'invalid_request_id', 'Use a stable UUID request ID.')
        require(type(body['expected_revision']) is int and body['expected_revision'] >= 0, 'invalid_revision', 'Use an integer revision.')
        require(bounded(body['payload_json'], 250000) and bounded(op, 40), 'invalid_payload', 'Use a bounded JSON payload.')
        try:
            p = json.loads(body['payload_json'], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            signature = digest(encoded(body))
        except (ValueError, TypeError): raise APIError(400, 'invalid_payload', 'Payload must be finite JSON.') from None
        require(isinstance(p, dict), 'invalid_payload', 'Payload must be an object.')
        run_id = body.get('study_run_id')
        try:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                cached = db.execute('SELECT signature,payload FROM receipts WHERE request_id=?', (rid,)).fetchone()
                if cached:
                    require(cached[0] == signature, 'request_id_conflict', 'This request ID already identifies different content.', 409)
                    db.execute('COMMIT')
                    return dict(json.loads(cached[1]), idempotent_replay=True)
                state = None
                if op in ('register_participant', 'create_run'):
                    require(run_id in (None, '') and body['expected_revision'] == 0, 'invalid_create', 'Creation must not target an existing run.')
                    if op == 'register_participant':
                        keys(p, ('prior_participation',))
                        require(p['prior_participation'] in ('yes', 'no', 'not_reported'), 'invalid_participant', 'Use an explicit prior-participation category.')
                        count = db.execute('SELECT COUNT(*) FROM participants').fetchone()[0]
                        pid = f'P{count + 1:04d}'
                        result = {'participant_id': pid, **p, 'registered_at': now()}
                        db.execute('INSERT INTO participants VALUES (?,?)', (pid, encoded(result)))
                    else:
                        state = self._create_run(db, p)
                        run_id = state['study_run_id']; result = {'study_run_id': run_id}
                else:
                    state = self._load(db, run_id)
                    require(body['expected_revision'] == state['revision'], 'stale_revision', 'Reload the saved study state before editing.', 409)
                    require(state['lifecycle'] != 'ended', 'study_ended', 'This run has ended; existing submissions remain immutable.', 409)
                    require(state['lifecycle'] != 'paused' or op in ('resume', 'end_run', 'connect'), 'study_paused', 'Resume the study before changing its data.', 409)
                    result = self._apply(db, state, op, p)
                    state['revision'] += 1
                event = {'event_id': uid(), 'timestamp_utc': now(), 'request_id': rid,
                         'study_run_id': run_id, 'event': op, 'payload': p, 'result': deepcopy(result)}
                if state is not None:
                    state['updated_at'] = event['timestamp_utc']
                    db.execute('INSERT INTO runs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (run_id, encoded(state)))
                    event.update({k: state[k] for k in ('participant_id', 'collection_kind', 'protocol_version', 'data_contract_version')})
                db.execute('INSERT INTO events(run_id,payload) VALUES (?,?)', (run_id, encoded(event)))
                ack = {'recorded': True, 'request_id': rid, 'study_run_id': run_id,
                       'payload_sha256': digest(body['payload_json']), 'server_saved_at': event['timestamp_utc'],
                       'revision': state['revision'] if state else 0, 'result': result}
                db.execute('INSERT INTO receipts VALUES (?,?,?)', (rid, signature, encoded(ack)))
                self._before_commit(db)
                db.execute('COMMIT')
                return ack
        except sqlite3.Error:
            raise APIError(503, 'study_storage_unavailable', 'Study data were not acknowledged. Retain the local packet and retry the same request ID.') from None

    def _create_run(self, db, p):
        keys(p, ('participant_id', 'collection_kind', 'execution_mode', 'manifest'), ('repeat_of_study_run_id',))
        require(p['collection_kind'] in ('engineering', 'practice'), 'formal_collection_disabled', 'Pilot/formal collection remains disabled until questionnaire and headset acceptance.', 403)
        require(p['execution_mode'] in ('mock', 'live'), 'invalid_mode', 'Use mock or live explicitly.')
        pid = p['participant_id']
        require(isinstance(pid, str), 'invalid_participant', 'Use an anonymous participant identifier.')
        row = db.execute('SELECT payload FROM participants WHERE id=?', (pid,)).fetchone()
        require(row is not None or re.fullmatch(r'(ENG|PRACTICE)-[A-Za-z0-9_-]{1,50}', pid), 'participant_not_registered', 'Register a participant or use an engineering/practice identifier.')
        manifest = p['manifest']
        keys(manifest, ('protocol_version', 'task_manifest_version', 'task_manifest_sha256', 'questionnaire_manifest_sha256', 'app_build_id', 'backend_build_id', 'configuration_sha256', 'tasks'), ('execution_sequence',))
        require(manifest['protocol_version'] == PROTOCOL, 'invalid_protocol', 'Use the frozen study protocol.')
        for k in ('task_manifest_sha256', 'questionnaire_manifest_sha256', 'configuration_sha256'):
            require(isinstance(manifest[k], str) and HASH.fullmatch(manifest[k]), 'invalid_manifest', 'Manifest hashes must be SHA-256 hex values.')
        for k in ('app_build_id', 'backend_build_id', 'task_manifest_version'):
            require(bounded(manifest[k]), 'invalid_manifest', 'Build and material versions must be explicit.')
        tasks = manifest['tasks']
        require(isinstance(tasks, list) and 1 <= len(tasks) <= 32, 'invalid_manifest', 'Register the exact ordered task list (up to 32 for engineering/practice).')
        seen = set()
        for t in tasks:
            keys(t, ('task_code', 'domain', 'scenario'))
            require(bounded(t['task_code'], 80) and t['task_code'] not in seen and t['domain'] in DOMAINS and t['scenario'] in ('C1', 'C2', 'C3', 'C4'), 'invalid_manifest', 'Task codes must be unique and use the four study domains/scenarios.')
            seen.add(t['task_code'])
        previous = p.get('repeat_of_study_run_id')
        if previous:
            require(self._load(db, previous)['participant_id'] == pid, 'identity_mismatch', 'Repeat runs must belong to the same participant.')
        return {'study_id': 'aiaa4435-final-user-study', 'study_run_id': uid(), 'participant_id': pid,
                'prior_participation': json.loads(row[0])['prior_participation'] if row else 'not_reported',
                'data_contract_version': CONTRACT, 'protocol_version': PROTOCOL, 'revision': 0,
                'collection_kind': p['collection_kind'], 'execution_mode': p['execution_mode'],
                'repeat_of_study_run_id': previous, 'manifest': manifest, 'lifecycle': 'active', 'end_reason': None,
                'created_at': now(), 'modules': {}, 'tasks': {}, 'questionnaires': {}, 'preferences': {},
                'connections': [], 'dialogue_event_ids': []}

    def _module(self, s, module_id):
        m = s['modules'].get(module_id)
        require(m is not None, 'module_not_found', 'Use a module from this run.', 404)
        return m

    def _task(self, s, task_id):
        t = s['tasks'].get(task_id)
        require(t is not None, 'task_not_found', 'Use a task from this run.', 404)
        return t

    def _submitted_tasks(self, s, domain=None):
        return [t for t in s['tasks'].values() if t.get('submission_id') and (domain is None or t['domain'] == domain)]

    def _apply(self, db, s, op, p):
        if op == 'launch_runtime':
            require(hasattr(self,'executor'),'executor_unavailable','Study execution is not connected.',503)
            return self.executor.launch(db,s,p)
        if op in ('capture_evaluation','finish_natural'):
            require(hasattr(self,'executor'),'executor_unavailable','Study execution is not connected.',503)
            keys(p, ('module_instance_id',) if op=='finish_natural' else ('task_id',))
            payload=self.executor.evaluate(s,p,natural=op=='finish_natural')
            return self._apply(db,s,'freeze_natural' if op=='finish_natural' else 'bind_evaluation',payload)
        if op == 'open_module':
            keys(p, ('module_type', 'domain'), ('initial_state',))
            natural = p['module_type'] == 'natural_selective'
            require(natural and p['domain'] is None or p['module_type'] == 'attribute_comparison' and p['domain'] in DOMAINS, 'invalid_module', 'Use one of the four domains or the independent natural module.')
            require(not any(m['module_type'] == p['module_type'] and m['domain'] == p['domain'] for m in s['modules'].values()), 'duplicate_module', 'This module already exists; restore it instead.', 409)
            if natural:
                require('comparison_overall' in s['preferences'], 'preference_required', 'Finish the comparison preference before natural simulation.', 409)
                validate_settings(p.get('initial_state'))
            else: require(not any(m['module_type'] == 'natural_selective' for m in s['modules'].values()), 'comparison_closed', 'Do not return to comparison after natural simulation.', 409)
            mid = uid()
            s['modules'][mid] = {'module_instance_id': mid, **p, 'order': len(s['modules']) + 1, 'session_id': uid() if natural else None,
                                 'evaluation': None, 'evaluation_revision': 0, 'frozen': False}
            return deepcopy(s['modules'][mid])
        if op == 'open_task':
            keys(p, ('module_instance_id', 'task_code'))
            m = self._module(s, p['module_instance_id'])
            expected = next((t for t in s['manifest']['tasks'] if t['task_code'] == p['task_code']), None)
            require(expected is not None and m['module_type'] == 'attribute_comparison' and m['domain'] == expected['domain'], 'task_mismatch', 'Task must belong to this registered module.')
            require(not any(t['task_code'] == p['task_code'] for t in s['tasks'].values()), 'duplicate_task', 'Restore the existing task instead.', 409)
            require(len(s['tasks']) == len(self._submitted_tasks(s)), 'task_pending', 'Submit the preceding task before opening another.', 409)
            require(s['manifest']['tasks'][len(s['tasks'])]['task_code'] == p['task_code'], 'task_order', 'Use the registered task order.')
            tid = uid(); s['tasks'][tid] = {'task_id': tid, **expected, 'module_instance_id': p['module_instance_id'], 'evaluation_revision': 0, 'evaluation': None, 'submission_id': None}
            return {'task_id': tid}
        if op == 'bind_evaluation':
            keys(p, ('task_id', 'branches', 'first_reveal_id'))
            t = self._task(s, p['task_id'])
            require(t['submission_id'] is None, 'already_submitted', 'Submitted evaluations are immutable.', 409)
            require(isinstance(p['branches'], dict) and set(p['branches']) == set(CONDITIONS) and bounded(p['first_reveal_id']), 'invalid_evaluation', 'Bind all four branch results to the reveal.')
            for b in p['branches'].values():
                keys(b, ('branch_revision', 'state_revision', 'status', 'result'))
                require(all(type(b[k]) is int and b[k] >= 0 for k in ('branch_revision', 'state_revision')) and b['status'] in ('ready', 'stopped') and isinstance(b['result'], dict), 'invalid_evaluation', 'Only resolved/stopped result snapshots may be evaluated.')
            if t['evaluation'] is not None:
                require(t['evaluation']['first_reveal_id'] == p['first_reveal_id'], 'reveal_mismatch', 'First reveal cannot change.')
                for c, b in p['branches'].items():
                    old = t['evaluation']['branches'][c]
                    require(b == old or b['branch_revision'] > old['branch_revision'], 'revision_content_conflict', 'Changed results require a new branch revision.', 409)
                    require(b['branch_revision'] >= old['branch_revision'] and b['state_revision'] >= old['state_revision'], 'stale_evaluation', 'Cannot bind older branch state.', 409)
            t['evaluation_revision'] += 1; t['evaluation'] = deepcopy(p)
            for q in s['questionnaires'].values():
                if q.get('task_id') == t['task_id'] and q.get('evaluation_binding') != p['branches'][q['condition']]:
                    q['evaluation_status'] = 'stale'
            for c in CONDITIONS:
                if not any(q.get('task_id')==t['task_id'] and q['condition']==c for q in s['questionnaires'].values()):
                    qid=uid(); s['questionnaires'][qid]={'questionnaire_id':qid,'target_id':t['task_id'],'task_id':t['task_id'],
                        'module_instance_id':t['module_instance_id'],'session_id':None,'condition':c,'questionnaire_version':ATTRIBUTE_VERSION,
                        'answer_schema_version':'study-answer-v1','feedback_revision':0,'record_stage':'draft','completeness':'partial',
                        'evaluation_status':'stale','evaluation_revision':t['evaluation_revision'],'answers':validate_answers(ATTRIBUTE_VERSION,{}),
                        'extras':{'reasons':[],'comment':'','comment_confirmed':False}}
            return {'evaluation_revision': t['evaluation_revision']}
        if op == 'freeze_natural':
            keys(p, ('module_instance_id', 'final_state', 'pending_requests', 'end_reason'))
            m = self._module(s, p['module_instance_id'])
            require(m['module_type'] == 'natural_selective' and not m['frozen'], 'invalid_natural_state', 'Freeze an active natural module once.', 409)
            require(type(p['pending_requests']) is int and p['pending_requests'] == 0 and isinstance(p['final_state'], dict) and p['end_reason'] in ('participant_finished', 'time_limit', 'researcher_stop'), 'pending_requests', 'Resolve or explicitly stop pending requests before freezing.')
            ids = [r[0] for r in db.execute("SELECT payload FROM events WHERE run_id=? ORDER BY sequence", (s['study_run_id'],))]
            dialogue = [e for e in map(json.loads, ids) if (e['event'] == 'dialogue' and e['payload']['module_instance_id'] == p['module_instance_id']) or (e['event']=='runtime_audit' and e['target_id']==p['module_instance_id'] and any(x.get('text') for x in e['record'].get('dialogue_entries',[])))]
            require(bool(dialogue), 'no_natural_interaction', 'Do not create a natural evaluation without a recorded interaction.')
            m.update(frozen=True, evaluation_revision=m['evaluation_revision'] + 1,
                     evaluation={**p, 'evaluation_event_start': dialogue[0].get('result',{}).get('dialogue_event_id',dialogue[0]['event_id']), 'evaluation_event_end': dialogue[-1].get('result',{}).get('dialogue_event_id',dialogue[-1]['event_id'])})
            qid=uid(); s['questionnaires'][qid]={'questionnaire_id':qid,'target_id':m['module_instance_id'],'task_id':None,
                'module_instance_id':m['module_instance_id'],'session_id':m['session_id'],'condition':'S','questionnaire_version':NATURAL_VERSION,
                'answer_schema_version':'study-answer-v1','feedback_revision':0,'record_stage':'draft','completeness':'partial',
                'evaluation_status':'stale','evaluation_revision':m['evaluation_revision'],'answers':validate_answers(NATURAL_VERSION,{}),
                'extras':{'reasons':[],'comment':'','comment_confirmed':False}}
            return {'session_id': m['session_id'], 'evaluation_revision': m['evaluation_revision']}
        if op == 'save_feedback':
            keys(p, ('module_instance_id', 'task_id', 'condition', 'evaluation_revision', 'answers', 'questionnaire_version'), ('extras',))
            m = self._module(s, p['module_instance_id']); natural = m['module_type'] == 'natural_selective'
            version = NATURAL_VERSION if natural else ATTRIBUTE_VERSION
            require(p['questionnaire_version'] == version, 'questionnaire_version_mismatch', 'Do not relabel legacy answers.')
            t = m if natural else self._task(s, p['task_id'])
            require((natural and p['task_id'] is None and p['condition'] == 'S' and m['frozen']) or (not natural and p['condition'] in CONDITIONS and t['module_instance_id'] == p['module_instance_id']), 'feedback_scope_mismatch', 'Feedback must reference this module and condition.')
            require(t.get('submission_id') is None and t['evaluation'] is not None and type(p['evaluation_revision']) is int and p['evaluation_revision'] == t['evaluation_revision'], 'stale_evaluation', 'Rate the current unsubmitted evaluation.', 409)
            target = m['module_instance_id'] if natural else t['task_id']
            q = next((q for q in s['questionnaires'].values() if q['target_id'] == target and q['condition'] == p['condition']), None)
            if hasattr(self,'executor'):self.executor.assert_current(s,t)
            answers = validate_answers(version, p['answers'])
            extra = extras(p.get('extras', {}), answers, natural=natural,
                           later_interaction=bool(not natural and t['evaluation_revision'] > 1))
            if q is None:
                q = {'questionnaire_id': uid(), 'target_id': target, 'module_instance_id': p['module_instance_id'],
                     'task_id': p['task_id'], 'session_id': m['session_id'], 'condition': p['condition'],
                     'questionnaire_version': version, 'answer_schema_version': 'study-answer-v1', 'feedback_revision': 0}
                s['questionnaires'][q['questionnaire_id']] = q
            q.update(answers=answers, extras=extra, evaluation_revision=p['evaluation_revision'], evaluation_status='current',
                     evaluation_binding=deepcopy(t['evaluation'] if natural else t['evaluation']['branches'][p['condition']]),
                     feedback_revision=q['feedback_revision'] + 1, record_stage='draft', completeness=completeness(answers))
            return {'questionnaire_id': q['questionnaire_id'], 'feedback_revision': q['feedback_revision']}
        if op in ('submit_task', 'submit_natural'):
            natural = op == 'submit_natural'; key = 'module_instance_id' if natural else 'task_id'
            keys(p, (key, 'evaluation_revision'))
            t = self._module(s, p[key]) if natural else self._task(s, p[key])
            require(not natural or t['module_type'] == 'natural_selective' and t['frozen'], 'invalid_natural_state', 'Natural evaluation must be frozen.')
            require(t.get('submission_id') is None, 'already_submitted', 'Use the original request ID to recover its receipt.', 409)
            require(type(p['evaluation_revision']) is int and p['evaluation_revision'] == t['evaluation_revision'] and t['evaluation'] is not None, 'stale_evaluation', 'Submit the current evaluation.', 409)
            if hasattr(self,'executor'):self.executor.assert_current(s,t)
            qs = [q for q in s['questionnaires'].values() if q['target_id'] == p[key]]
            require({q['condition'] for q in qs} == ({'S'} if natural else set(CONDITIONS)), 'feedback_required', 'Every required strategy needs a questionnaire.')
            for q in qs:
                require(q['evaluation_status'] == 'current' and q['evaluation_binding'] == (t['evaluation'] if natural else t['evaluation']['branches'][q['condition']]), 'stale_feedback', 'Reconfirm changed evaluations.', 409)
                validate_answers(q['questionnaire_version'], q['answers'], final=True)
            submission_id = uid()
            for q in qs:
                q.update(record_stage='submitted', submission_id=submission_id, submitted_at=now(), evaluation=deepcopy(t['evaluation']))
                if natural: q['scores'] = scores(q['answers'])
            t['submission_id'] = submission_id
            return {'submission_id': submission_id, 'questionnaire_ids': [q['questionnaire_id'] for q in qs]}
        if op == 'preference':
            keys(p, ('scope', 'domain', 'answers'))
            scope, domain = p['scope'], p['domain']
            require(scope == 'attribute' and domain in DOMAINS or scope == 'comparison_overall' and domain is None, 'invalid_scope', 'Use an attribute or comparison overall preference.')
            key = domain if scope == 'attribute' else scope
            require(key not in s['preferences'], 'already_submitted', 'Preference is immutable; retry with the same request ID.', 409)
            planned = [t for t in s['manifest']['tasks'] if domain is None or t['domain'] == domain]
            tasks = self._submitted_tasks(s, domain)
            require(planned and len(tasks) == len(planned), 'tasks_incomplete', 'Submit the evaluated tasks before choosing preference.', 409)
            if domain is None:
                require(all(d in s['preferences'] for d in {t['domain'] for t in planned}), 'preferences_incomplete', 'Save every attribute preference first.', 409)
            answers = validate_preference(p['answers'])
            pref = {'preference_id': uid(), 'submission_id': uid(), 'record_stage': 'submitted', 'questionnaire_version': PREFERENCE_VERSION,
                    'scope': scope, 'domain': domain, 'answers': answers, 'submitted_at': now(),
                    'task_submissions': [{'task_id': t['task_id'], 'submission_id': t['submission_id']} for t in tasks]}
            s['preferences'][key] = pref
            return {'preference_id': pref['preference_id'], 'submission_id': pref['submission_id']}
        if op == 'dialogue':
            keys(p, ('module_instance_id', 'task_id', 'condition', 'speaker', 'kind', 'text', 'input_source', 'client_time_utc', 'client_sequence'), ('question_id', 'exchange_id', 'source_event_id'))
            m = self._module(s, p['module_instance_id'])
            require(not m['frozen'], 'evaluation_frozen', 'Do not append dialogue to a frozen evaluation.', 409)
            if m['module_type'] == 'natural_selective':
                require(p['task_id'] is None and p['condition'] == 'S', 'dialogue_scope', 'Use the independent S session.')
            else:
                t = self._task(s, p['task_id'])
                require(t['module_instance_id'] == p['module_instance_id'] and t['submission_id'] is None and p['condition'] in (*CONDITIONS, None), 'dialogue_scope', 'Dialogue must reference the active task.')
            require(p['speaker'] in ('participant', 'tutor') and p['kind'] in ('request', 'clarification', 'answer', 'repair', 'setting_message'), 'dialogue_kind', 'Use an explicit dialogue role and kind.')
            require(isinstance(p['text'], str) and 1 <= len(p['text']) <= 16000 and p['input_source'] in ('stt_submitted', 'option', 'model', 'controller'), 'dialogue_text', 'Save only submitted text and its origin; no audio or ASR hypotheses.')
            require((p['speaker'] == 'participant') == (p['input_source'] in ('stt_submitted', 'option')), 'dialogue_origin', 'Speaker and input origin disagree.')
            require(type(p['client_sequence']) is int and p['client_sequence'] >= 0 and bounded(p['client_time_utc'], 60), 'invalid_client_metadata', 'Preserve client event sequence and time.')
            for k in ('question_id', 'exchange_id', 'source_event_id'):
                require(k not in p or bounded(p[k]), 'invalid_reference', 'Reference IDs must be bounded text.')
            eid = uid(); s['dialogue_event_ids'].append(eid)
            return {'dialogue_event_id': eid, 'session_id': m['session_id'], 'status': 'generated_not_presentation' if p['input_source'] == 'model' else 'submitted_text'}
        if op in ('pause', 'resume', 'end_run', 'connect'):
            if op == 'end_run':
                keys(p, ('end_reason',))
                require(p['end_reason'] in ('normal_completion', 'participant_exit', 'technical_abort', 'researcher_stop'), 'invalid_end_reason', 'Use an explicit end reason.')
                if p['end_reason'] == 'normal_completion':
                    require(len(self._submitted_tasks(s)) == len(s['manifest']['tasks']) and 'comparison_overall' in s['preferences'] and any(m.get('submission_id') for m in s['modules'].values() if m['module_type'] == 'natural_selective'), 'study_incomplete', 'Required submissions are missing.', 409)
                s.update(lifecycle='ended', end_reason=p['end_reason'], ended_at=now())
            elif op == 'connect':
                keys(p, ('connection_id',))
                require(isinstance(p['connection_id'], str) and UUID.fullmatch(p['connection_id']), 'invalid_connection', 'Use a connection UUID, never a new study ID for recovery.')
                s['connections'].append({'connection_id': p['connection_id'], 'connected_at': now()})
            else:
                keys(p, ())
                require(s['lifecycle'] == ('active' if op == 'pause' else 'paused'), 'invalid_lifecycle', 'Pause/resume must match the current state.', 409)
                s['lifecycle'] = 'paused' if op == 'pause' else 'active'
            return {'lifecycle': s['lifecycle'], 'end_reason': s['end_reason']}
        raise APIError(404, 'study_operation_not_found', 'Unknown study operation.')
