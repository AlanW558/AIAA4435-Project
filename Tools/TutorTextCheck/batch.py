#!/usr/bin/env python3
"""Auxiliary text checks using the unchanged tutor engine; no STT or VR edits.

Independent task checkpoints deliberately do not pretend to be formal StudyStore
submissions. Supplied text retains its provenance, including explicitly authorized
assistant-authored clarifications; the runner never invents answers itself.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Backend'))
from core import APIError
from model import DeepSeekModel
from speech import SpeechConfig, SpeechService, validate_wav
from study_answers import ATTRIBUTE_VERSION, validate_answers, extras as validate_extras
from study_runtime import comparison_dump, comparison_load
from tutor_audio import TutorAudio
from tutor_comparison_service import TutorComparisons
from tutor_feedback import ATTRIBUTE_VERSION as INTERNAL_EXECUTION_VERSION
from tutor_study_materials import CATALOG, TASKS, DIGEST, VERSION
from workbook import parse, replace_fields
from attribute_feedback import VERSION as SUMMARY_VERSION, SUPPORTED_VERSIONS as SUMMARY_VERSIONS

DEFAULT_DIR = ROOT / 'StudyData/text-check-v3'
CODES = list(TASKS)
CONDITIONS = 'EANS'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('xb') as stream:
        os.chmod(temporary, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_json(path, value):
    atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def plan():
    return {'version': 'attribute-sequence-v2', 'purpose': 'study_preview',
            'materials_version': VERSION, 'catalog_sha256': DIGEST,
            'modules': [{'domain': m['direction'], 'tasks': [
                {'task_code': t['task_code'], 'scenario': t['scenario']} for t in m['tasks']
            ]} for m in CATALOG['modules']]}


class NoCalls:
    mode, model = 'read_only', 'not_loaded'

    def __getattr__(self, name):
        raise AttributeError(name)


class Batch:
    def __init__(self, directory, model=None, speech=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.model, self.speech = model or NoCalls(), speech
        meta = self.directory / 'batch.json'
        if meta.exists():
            self.meta = json.loads(meta.read_text())
            if self.meta['catalog_sha256'] != DIGEST:
                raise ValueError('Task catalog changed. Preserve this batch and use a new directory.')
        else:
            self.meta = {'schema': 'tutor-text-check-v1', 'batch_id': uuid.uuid4().hex,
                         'created_at': now(), 'collection_kind': 'engineering',
                         'input_source': 'user_supplied_text', 'catalog_sha256': DIGEST,
                         'questionnaire_version': SUMMARY_VERSION, 'collection_unit': 'attribute',
                         'response_mode': 'generated_reply', 'formal_study_submission': False}
            save_json(meta, self.meta)
        snapshot = self.directory / 'catalog.json'
        if not snapshot.exists():
            atomic(snapshot, (ROOT / 'Assets/Project/Resources/Tutor/StudyTaskSequence.json').read_bytes())
        if sha(snapshot.read_bytes()) != self.meta['catalog_sha256']:
            raise ValueError('Frozen task catalog does not match this batch.')
        profiles = {}
        if model is not None:
            profiles['model_profile'] = {k: getattr(model, k, None) for k in ('mode', 'model', 'base_url', 'timeout', 'max_attempts')}
        if speech is not None:
            config = getattr(speech, 'config', None)
            profiles['tts_profile'] = {
                'model': getattr(config, 'tts_model', 'fixture'),
                'base_url': getattr(config, 'base_url', 'fixture'),
                'voice_catalog_sha256': sha((ROOT / 'Backend/tutor_voice_catalog.py').read_bytes())}
        for name, profile in profiles.items():
            if name in self.meta and self.meta[name] != profile:
                raise ValueError(f'{name} changed. Keep the original configuration or use a new batch.')
            self.meta[name] = profile
        if profiles:
            save_json(meta, self.meta)
        if model is None and 'model_profile' in self.meta:
            self.model.mode = self.meta['model_profile']['mode']
            self.model.model = self.meta['model_profile']['model']
        self.service = TutorComparisons(self.model, self.directory / 'logs', max_workers=4)
        self.service.audio_available = True
        self.audio_service = TutorAudio(None, self.service, speech)
        self.records = {}

    def close(self):
        self.service.shutdown()

    def path(self, code):
        if code not in TASKS:
            raise ValueError('Unknown task code.')
        return self.directory / 'tasks' / code / 'checkpoint.json'

    def save(self, record):
        payload = encoded(record)
        save_json(self.path(record['task_code']), {'sha256': sha(payload), 'payload': record})

    def load(self, code, create=False):
        if code in self.records:
            return self.records[code]
        path = self.path(code)
        if path.exists():
            envelope = json.loads(path.read_text())
            record = envelope['payload']
            if sha(encoded(record)) != envelope['sha256'] or record['task_code'] != code:
                raise ValueError('Checkpoint checksum or task identity mismatch.')
            if record['runtime']['processing']:
                raise ValueError(f'{code}: interrupted processing; do not automatically replay it.')
            rt = comparison_load(self.service, record['runtime'])
            self.service.tasks[rt.comparison.task_id] = rt
        elif create:
            domain, task = TASKS[code]
            view = self.service.create({
                'request_id': uuid.uuid4().hex, 'participant_id': 'ENG-text-check',
                'task_code': code, 'domain': domain, 'scenario': task['scenario'],
                'require_preparation': True, 'feedback_version': INTERNAL_EXECUTION_VERSION,
                'sequence': plan()}, lineage=(self.meta['batch_id'], CODES.index(code) + 1, None))
            record = {'task_code': code, 'request': None, 'runtime_id': view['task_id'],
                      'runtime': comparison_dump(self.service.get(view['task_id'])),
                      'pending': None, 'operations': [], 'answers': {}, 'worksheet': {},
                      'audio_files': {}, 'feedback': {}}
            self.save(record)
        else:
            return None
        self.records[code] = record
        return record

    def view(self, record):
        return self.service.view(self.service.get(record['runtime_id']))

    def guard(self, record):
        if record['pending']:
            raise ValueError(f"{record['task_code']}: an operation is unresolved; inspect its checkpoint, do not replay.")

    def mutate(self, record, operation, branch=None, *, input_source='user_supplied_text', **fields):
        self.guard(record)
        view = self.view(record)
        body = {'request_id': uuid.uuid4().hex, **fields}
        body['expected_branch_revision' if branch else 'expected_revision'] = (
            view['branches'][branch]['branch_revision'] if branch else view['revision'])
        pending = {'operation': operation, 'condition': branch, 'body': body, 'started_at': now(),
                   'input_source': input_source}
        if operation == 'answer':
            pending['question'] = deepcopy(view['branches'][branch].get('question'))
        record['pending'] = pending
        self.save(record)
        try:
            self.service.mutate(record['runtime_id'], operation, body, branch)
            deadline = time.monotonic() + 300
            while any(b['status'] == 'processing' for b in self.view(record)['branches'].values()):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Operation did not settle; original input is retained and replay is blocked.')
                time.sleep(.05)
            record['runtime'] = comparison_dump(self.service.get(record['runtime_id']))
            if record['runtime']['processing']:
                raise RuntimeError('Runtime is still processing.')
        except Exception:
            # Keep the pre-operation checkpoint and original pending packet.
            # Even an exception may follow a provider call; do not guess/retry.
            raise
        record['operations'].append({**pending, 'settled_at': now()})
        if operation == 'start':
            record['request'] = fields['query']
        if operation == 'answer':
            record['answers'][fields['question_id']] = {
                'condition': branch, 'text': fields['response'].get('text'),
                'question': pending.get('question'), 'input_source': input_source}
        record['pending'] = None
        self.save(record)
        return self.view(record)

    @staticmethod
    def questions(view):
        return {c: b['question'] for c, b in view['branches'].items() if b.get('question')}

    @staticmethod
    def answers_from_text(text, questions):
        if not text.strip():
            return {}
        markers = list(re.finditer(r'(?m)^([EANS]):[ \t]?', text))
        if not markers:
            if len(questions) != 1:
                raise ValueError('Use separate A: / N: / S: lines when more than one strategy asks.')
            return {next(iter(questions)): text}
        if text[:markers[0].start()].strip():
            raise ValueError('Put each clarification under its strategy label.')
        result = {}
        for i, marker in enumerate(markers):
            c = marker.group(1)
            if c in result or c not in questions:
                raise ValueError('Duplicate strategy or reply to a strategy without a recorded question.')
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            answer = text[marker.end():end].rstrip('\r\n')
            if answer.strip():
                result[c] = answer
        return result

    def process(self, workbook, limit=4, clarification_source='user_supplied_text', request_source='user_supplied_text'):
        if clarification_source not in ('user_supplied_text', 'assistant_authored_user_authorized'):
            raise ValueError('Unknown clarification provenance.')
        if request_source not in ('user_supplied_text', 'assistant_revised_user_authorized'):
            raise ValueError('Unknown request provenance.')
        rows = parse(workbook)
        # Validate every existing request before making any calls.
        for code, fields in rows.items():
            record = self.load(code)
            if record and record['request'] is not None and fields['request'] != record['request']:
                raise ValueError(f'{code}: an already submitted Request changed. Keep it or start a new batch.')
            if record:
                self.guard(record)
        processed = []
        for code, fields in rows.items():
            if len(processed) >= limit:
                break
            if not fields['request'].strip():
                continue
            record = self.load(code, create=True)
            if record['request'] is None:
                if fields['clarification'].strip():
                    raise ValueError(f'{code}: no question has been issued yet; leave Clarification empty.')
                if not self.view(record)['preparation_confirmed']:
                    self.mutate(record, 'confirm_preparation')
                self.mutate(record, 'start', input_source=request_source, query=fields['request'])
                processed.append(code)
            else:
                binding = record.get('worksheet', {})
                if fields['clarification'].strip():
                    if not binding or sha(fields['clarify']) != binding.get('clarify_sha256'):
                        raise ValueError(f'{code}: Clarify was changed or not issued by this batch.')
                    answers = self.answers_from_text(fields['clarification'], binding['questions'])
                    changed = False
                    for c, text in answers.items():
                        question = binding['questions'][c]
                        qid = question['question_id']
                        if qid in record['answers']:
                            if record['answers'][qid]['text'] != text:
                                raise ValueError(f'{code}/{c}: an already submitted clarification changed.')
                            continue
                        current = self.questions(self.view(record)).get(c)
                        if not current or current['question_id'] != qid:
                            raise ValueError(f'{code}/{c}: stale clarification; refresh the worksheet.')
                        self.mutate(record, 'answer', c, input_source=clarification_source,
                                    question_id=qid, response={'text': text})
                        changed = True
                    if changed:
                        processed.append(code)
        self.sync(workbook)
        return {'processed': processed, 'results_published': False, 'status': self.status(workbook)}

    def sync(self, workbook):
        path = Path(workbook)
        original = path.read_bytes()
        rows = parse(path)
        replacements = {}
        bindings = {}
        for code, fields in rows.items():
            record = self.load(code)
            if not record:
                continue
            self.guard(record)
            if record['request'] is not None and fields['request'] != record['request']:
                raise ValueError(f'{code}: Request changed after submission.')
            old = record.get('worksheet', {})
            if fields['clarification'].strip():
                if not old or sha(fields['clarify']) != old.get('clarify_sha256'):
                    raise ValueError(f'{code}: edited/unbound Clarify field; preserve it for review.')
                answered = self.answers_from_text(fields['clarification'], old['questions'])
                consumed = all(record['answers'].get(old['questions'][c]['question_id'], {}).get('text') == text for c, text in answered.items())
                if not consumed:
                    continue  # Do not erase unsubmitted user text.
                replacements[(code, 'clarification')] = ''
            questions = self.questions(self.view(record))
            lines = []
            for c in CONDITIONS:
                if c not in questions:
                    continue
                q = questions[c]
                lines.append(f"{c}: {q['text']}")
                lines.extend(f"  - {o['label']}" for o in q['options'])
            if not lines and record['request'] is not None:
                lines = ['No clarification is currently pending. Results remain withheld until batch release.']
            rendered = '\n'.join(lines)
            replacements[(code, 'clarify')] = rendered
            bindings[code] = {'questions': questions, 'clarify_sha256': sha(rendered)}
        updated = replace_fields(original.decode('utf-8'), replacements).encode('utf-8')
        if path.read_bytes() != original:
            raise ValueError('Worksheet changed during processing. No user edits were overwritten; run sync again.')
        if updated != original:
            backup = self.directory / 'worksheet-history' / (now().replace(':', '-') + '-' + uuid.uuid4().hex + '.md')
            atomic(backup, original)
            atomic(path, updated)
        for code, binding in bindings.items():
            self.records[code]['worksheet'] = binding
            self.save(self.records[code])

    def status(self, workbook):
        result = {}
        for code, fields in parse(workbook).items():
            record = self.load(code)
            if record and record['pending']:
                status = 'interrupted_do_not_replay'
            elif record and record['request'] is not None and fields['request'] != record['request']:
                status = 'request_changed'
            elif not fields['request'].strip():
                status = 'request_blank'
            elif not record or record['request'] is None:
                status = 'request_not_processed'
            elif self.questions(self.view(record)):
                status = 'clarification_required'
            elif self.view(record)['results_visible']:
                status = 'ready_withheld'
            else:
                status = 'unresolved'
            result[code] = status
        return result

    def release_guard(self, workbook):
        statuses = self.status(workbook)
        active = [code for code, status in statuses.items() if status != 'request_blank']
        if not active or any(statuses[c] != 'ready_withheld' for c in active):
            raise ValueError('Resolve all nonblank requests and clarifications before releasing results.')
        # Do not release while a new clarification has been typed but not consumed.
        if any(fields['clarification'].strip() for fields in parse(workbook).values()):
            raise ValueError('Process or clear pending clarification text before release.')
        return active

    def followup(self, workbook, text, codes):
        active = self.release_guard(workbook)
        if not text.strip() or not set(codes) <= set(active):
            raise ValueError('Provide explicit follow-up text and ready task codes.')
        for code in codes:
            record = self.load(code)
            failures = record.get('technical_failures', {})
            if failures:
                # A failed adjustment is not repaired by silently giving its
                # baseline a new answer. Probe only the valid result branches.
                for condition in CONDITIONS:
                    if condition not in failures:
                        self.mutate(record, 'request', condition, input_source='standardized_evaluation_probe', query=text)
            else:
                self.mutate(record, 'round_request', input_source='standardized_evaluation_probe', query=text)
        self.sync(workbook)

    def retry(self, workbook, code, condition=None):
        record = self.load(code)
        if record is None:
            raise ValueError('This task has not started.')
        self.guard(record)
        view = self.view(record)
        if condition is None:
            if view['shared_preparation']['status'] != 'failed':
                raise ValueError('No known failed shared interpretation to retry.')
            self.mutate(record, 'retry_shared', expected_attempt=view['shared_preparation']['attempt'])
        else:
            if view['branches'][condition]['status'] != 'failed':
                raise ValueError('Only a known failed branch can be explicitly retried.')
            self.mutate(record, 'retry', condition)
        self.sync(workbook)

    def stop_failed(self, workbook, code):
        record = self.load(code)
        if record is None:
            raise ValueError('Task not found.')
        self.guard(record)
        view = self.view(record)
        failed = {c: b for c, b in view['branches'].items() if b['status'] == 'failed'}
        if not failed:
            raise ValueError('No known failed branches to record.')
        snapshot = self.directory / 'failures' / code / (uuid.uuid4().hex + '.json')
        save_json(snapshot, {'view': view, 'runtime': record['runtime'], 'recorded_at': now()})
        for condition, branch in failed.items():
            record.setdefault('technical_failures', {})[condition] = {
                'error_code': branch.get('error_code'), 'recorded_at': now(),
                'evidence': str(snapshot.relative_to(self.directory)),
                'status': 'no_valid_result', 'audio_generated': False,
                'message': 'No valid result was produced after retry. No output audio is available for this branch.'}
            self.save(record)
            self.mutate(record, 'stop', condition)
        self.sync(workbook)

    def render_audio(self, record, condition, purpose='sample', exchange_id=0):
        self.guard(record)
        if not self.speech:
            raise ValueError('TTS is not configured for this command.')
        view = self.view(record)
        if view['selected_condition'] != condition:
            self.mutate(record, 'select', condition=condition)
        view = self.view(record)
        target = {'request_id': uuid.uuid4().hex, 'expected_revision': view['revision'],
                  'condition': condition, 'purpose': purpose, 'exchange_id': exchange_id}
        _, text, settings = self.audio_service.resolve('comparisons', record['runtime_id'], target)
        identity = {'runtime_id': record['runtime_id'], 'condition': condition, 'purpose': purpose,
                    'exchange_id': exchange_id, 'text': text, 'settings': settings,
                    'branch_revision': view['branches'][condition]['branch_revision'],
                    'latest_reveal_id': (view.get('latest_reveal') or {}).get('reveal_id'),
                    'tts_profile': self.meta.get('tts_profile')}
        key = sha(encoded(identity))
        if key in record['audio_files']:
            entry = record['audio_files'][key]
            path = self.directory / entry['file']
            if sha(path.read_bytes()) != entry['sha256']:
                raise ValueError('Saved audio is missing or changed; do not silently regenerate it.')
            return entry
        relative = f"audio/{record['task_code']}/{condition}-{purpose}-{key[:16]}.wav"
        pending = {'operation': 'tts', 'identity': identity, 'file': relative, 'started_at': now()}
        record['pending'] = pending
        self.save(record)
        audio = self.audio_service.synthesize('comparisons', record['runtime_id'], target)
        validate_wav(audio)
        atomic(self.directory / relative, audio)
        entry = {**identity, 'file': relative, 'sha256': sha(audio), 'bytes': len(audio),
                 'created_at': now(), 'playback': 'not_observed',
                 'tts_model': getattr(getattr(self.speech, 'config', None), 'tts_model', 'fixture')}
        save_json((self.directory / relative).with_suffix('.json'), entry)
        record['audio_files'][key] = entry
        record['runtime'] = comparison_dump(self.service.get(record['runtime_id']))
        record['operations'].append({**pending, 'settled_at': now()})
        record['pending'] = None
        self.save(record)
        return entry

    def materials(self, codes):
        result = {}
        for code in codes:
            record = self.load(code, create=True)
            result[code] = [self.render_audio(record, self.view(record)['selected_condition'], 'material', i)
                            for i in range(1, len(TASKS[code][1]['materials']) + 1)]
        save_json(self.directory / 'materials.json', result)
        return result

    def render_baseline(self, record):
        """Synthesize the supplied starting material, never a strategy result."""
        self.guard(record)
        if not self.speech:
            raise ValueError('TTS is not configured.')
        from tutor_voice_catalog import SAMPLE_TEXT
        view = self.view(record)
        if not view['results_visible']:
            raise ValueError('Publish starting references together with settled strategy results.')
        baseline = view['baseline']
        text = SAMPLE_TEXT
        if TASKS[record['task_code']][0] in ('reply_length', 'tone'):
            text = '\n\n'.join(m['content'] for m in baseline['conversation'][-1]['messages'] if m['role'] == 'assistant')
        identity = {'runtime_id': record['runtime_id'], 'purpose': 'baseline', 'text': text,
                    'settings': baseline['settings'], 'tts_profile': self.meta.get('tts_profile'),
                    'source': 'supplied_starting_material'}
        key = sha(encoded(identity))
        if key in record['audio_files']:
            entry = record['audio_files'][key]
            if sha((self.directory / entry['file']).read_bytes()) != entry['sha256']:
                raise ValueError('Saved baseline audio checksum mismatch.')
            return entry
        relative = f"audio/{record['task_code']}/baseline-{key[:16]}.wav"
        pending = {'operation': 'tts_baseline', 'identity': identity, 'file': relative, 'started_at': now()}
        record['pending'] = pending
        self.save(record)
        rendered = self.speech.synthesize(text, baseline['settings'])
        audio = rendered['audio']
        validate_wav(audio)
        atomic(self.directory / relative, audio)
        entry = {**identity, 'file': relative, 'sha256': sha(audio), 'bytes': len(audio),
                 'created_at': now(), 'playback': 'not_observed',
                 'tts_model': getattr(getattr(self.speech, 'config', None), 'tts_model', 'fixture')}
        save_json((self.directory / relative).with_suffix('.json'), entry)
        record['audio_files'][key] = entry
        record['operations'].append({**pending, 'settled_at': now()})
        record['pending'] = None
        self.save(record)
        return entry

    @staticmethod
    def clarification_details(record):
        details = {}
        for condition in CONDITIONS:
            turns = []
            current = {a['question_id']: a for a in record['runtime']['task']['_branches'][condition]['answers']}
            for operation in record['operations']:
                if operation['operation'] != 'answer' or operation['condition'] != condition:
                    continue
                qid = operation['body']['question_id']
                origin = record['answers'].get(qid, {})
                question = operation.get('question') or origin.get('question') or current.get(qid, {}).get('question')
                response = operation['body']['response']
                turns.append({'question_id': qid, 'question': question['text'] if question else 'Question text unavailable in this legacy record.',
                              'answer': response.get('text'), 'option_id': response.get('option_id'),
                              'source': origin.get('input_source', operation.get('input_source', 'unknown')),
                              'answered_at': operation.get('settled_at')})
            details[condition] = {'occurred': bool(turns), 'count': len(turns), 'turns': turns}
        return details

    def publish(self, workbook, codes=None):
        active = self.release_guard(workbook)
        codes = active if codes is None else codes
        if not set(codes) <= set(active):
            raise ValueError('Only ready tasks may be published.')
        published = {}
        for code in codes:
            record = self.load(code)
            view = self.view(record)
            domain = TASKS[code][0]
            purposes = {}
            for c in CONDITIONS:
                if c in record.get('technical_failures', {}):
                    if view['branches'][c]['status'] != 'stopped':
                        raise ValueError('Technical-failure annotation must match a stopped branch.')
                    continue
                snapshot = view['branches'][c]['result']['state']
                previous = {e['id'] for e in view['baseline']['conversation']}
                actual = [e for e in snapshot['conversation'] if e['id'] not in previous]
                if not actual:
                    raise ValueError(f'{code}/{c}: no new model-generated reply; fixed samples cannot substitute for a response.')
                purposes[c] = ('reply', actual[-1]['id'])
            entries = {c: self.render_audio(record, c, *purposes[c]) if c in purposes else None for c in CONDITIONS}
            view = self.view(record)
            release = {'task_code': code, 'batch_id': self.meta['batch_id'], 'request': record['request'],
                       'clarification_answers': record['answers'], 'view': view, 'audio': entries,
                       'response_mode': 'generated_reply', 'collection_unit': 'attribute',
                       'clarifications': self.clarification_details(record),
                       'technical_failures': record.get('technical_failures', {}),
                       'followup_questions': [{'text': op['body']['query'], 'condition': op['condition'],
                                               'source': op.get('input_source', 'unknown')}
                                              for op in record['operations'] if op['operation'] in ('request', 'round_request')],
                       'questionnaire_version': self.meta.get('questionnaire_version') if self.meta.get('questionnaire_version') in SUMMARY_VERSIONS else SUMMARY_VERSION}
            release_id = sha(encoded({c: {'branch_revision': b['branch_revision'], 'result': b['result']} for c, b in view['branches'].items()}))
            release['release_id'] = release_id
            output = self.directory / 'results' / code / release_id
            output.mkdir(parents=True, exist_ok=True)
            if not (output / 'result.json').exists():
                save_json(output / 'result.json', release)
                lines = [f'# {code} — four-strategy results', '',
                         'User request:', '', '> ' + record['request'].replace('\n', '\n> '), '']
                for c in CONDITIONS:
                    entry = entries[c]
                    clarification = release['clarifications'][c]
                    lines.extend([f'## {c}', '', f"Clarification: {'Yes' if clarification['occurred'] else 'No'} ({clarification['count']})", ''])
                    for turn in clarification['turns']:
                        lines.extend(['Question: ' + turn['question'], '',
                                      'Reply: ' + (turn['answer'] or str(turn['option_id'])), '',
                                      'Reply source: ' + turn['source'], ''])
                    if entry is None:
                        lines.extend(['Technical failure: no valid result; no output audio was generated.', ''])
                        continue
                    lines.extend(['Synthesized text:', '',
                                  '> ' + entry['text'].replace('\n', '\n> '), '',
                                  f"[Play / download audio](<{(self.directory / entry['file']).resolve()}>)", ''])
                lines.extend(['Feedback is collected once per attribute after all eight tasks (four strategies × five answers plus one preference).', '',
                              'Generated audio is not evidence of playback or task success.', ''])
                atomic(output / 'result.md', '\n'.join(lines).encode())
            record['published_release'] = {'release_id': release_id, 'directory': str(output.relative_to(self.directory))}
            self.save(record)
            published[code] = str(output / 'result.json')
        return published

    def save_feedback(self, file):
        data = json.loads(Path(file).read_text())
        if data.get('collection_unit') == 'attribute' or data.get('schema') == 'tutor-text-attribute-feedback-bundle-v1':
            raise ValueError('Use attribute-feedback --file for attribute-level records; the feedback command preserves legacy task ratings.')
        record = self.load(data['task_code'])
        self.guard(record)
        release = record.get('published_release', {})
        published = json.loads((self.directory / release['directory'] / 'result.json').read_text())
        if published.get('questionnaire_version') != ATTRIBUTE_VERSION:
            raise ValueError('This release uses attribute questionnaires; use attribute-feedback after all eight tasks.')
        view = self.view(record)
        current = sha(encoded({c: {'branch_revision': b['branch_revision'], 'result': b['result']} for c, b in view['branches'].items()}))
        if not view['results_visible'] or data['release_id'] != release.get('release_id') or current != data['release_id']:
            raise ValueError('Feedback does not refer to the current published results.')
        if data['questionnaire_version'] != ATTRIBUTE_VERSION or set(data['conditions']) != set(CONDITIONS):
            raise ValueError('Use the unchanged five-item questionnaire for all four strategies.')
        saved = deepcopy(data)
        for c, item in saved['conditions'].items():
            item['answers'] = validate_answers(ATTRIBUTE_VERSION, item['answers'], final=True)
            later = len(view['branches'][c]['result']['state']['conversation']) > len(view['first_reveal']['branches'][c]['state']['conversation'])
            item['extras'] = validate_extras(item.get('extras', {}), item['answers'], later_interaction=later)
        key = sha(encoded(saved))
        destination = self.directory / 'feedback' / (key + '.json')
        if destination.exists():
            return str(destination)
        previous = record['feedback'].get(data['release_id'])
        saved.update(saved_at=now(), collection_kind='engineering', input_source='user_supplied_text',
                     formal_study_submission=False, submission_id=key,
                     supersedes=previous, answers_sha256=key)
        save_json(destination, saved)
        record['feedback'][data['release_id']] = key
        self.save(record)
        return str(destination)

    def save_attribute_feedback(self, file):
        from attribute_feedback import save_submission
        from report import collect
        data = json.loads(Path(file).read_text())
        return save_submission(self.directory, data, collect(self.directory, questionnaire_version=data.get('questionnaire_version')))


@contextmanager
def locked(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)
    with (Path(directory) / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=DEFAULT_DIR)
    p.add_argument('--workbook', type=Path, default=DEFAULT_DIR / 'TASK_REQUESTS.md')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status'); sub.add_parser('sync')
    run = sub.add_parser('process'); run.add_argument('--limit', type=int, default=4)
    run.add_argument('--clarification-source', choices=('user_supplied_text', 'assistant_authored_user_authorized'), default='user_supplied_text')
    run.add_argument('--request-source', choices=('user_supplied_text', 'assistant_revised_user_authorized'), default='user_supplied_text')
    follow = sub.add_parser('followup'); follow.add_argument('--text-file', type=Path, required=True); follow.add_argument('--codes', nargs='+', choices=CODES, required=True)
    materials = sub.add_parser('materials'); materials.add_argument('--codes', nargs='+', choices=CODES, default=[c for c in CODES if c.startswith('V')])
    publish = sub.add_parser('publish'); publish.add_argument('--codes', nargs='+', choices=CODES)
    feedback = sub.add_parser('feedback'); feedback.add_argument('--file', type=Path, required=True)
    attribute_feedback = sub.add_parser('attribute-feedback'); attribute_feedback.add_argument('--file', type=Path, required=True)
    retry = sub.add_parser('retry'); retry.add_argument('--task', choices=CODES, required=True); retry.add_argument('--condition', choices=list(CONDITIONS))
    retry.add_argument('--capture-diagnostics', action='store_true', help='Archive the unchanged model JSON/context for a known failed retry; never repairs it.')
    stopped = sub.add_parser('stop-failed'); stopped.add_argument('--task', choices=CODES, required=True)
    args = p.parse_args()
    if args.command == 'process' and not 1 <= args.limit <= 32:
        p.error('--limit must be between 1 and 32.')
    with locked(args.directory):
        model = DeepSeekModel(os.environ.get('DEEPSEEK_MODEL', ''), timeout=45, max_attempts=1) if args.command in ('process', 'followup', 'retry') else None
        if args.command == 'retry' and args.capture_diagnostics:
            original_call = model._call
            def capture_call(role, system, context):
                raw, records = original_call(role, system, context)
                save_json(args.directory / 'diagnostics' / args.task / (uuid.uuid4().hex + '.json'),
                          {'role': role, 'context': context, 'response': raw, 'records': records,
                           'system_prompt_sha256': sha(system), 'modified_response': False})
                return raw, records
            model._call = capture_call
        speech = SpeechService(SpeechConfig.from_env()) if args.command in ('publish', 'materials') else None
        batch = Batch(args.directory, model, speech)
        try:
            if args.command == 'process': result = batch.process(args.workbook, args.limit, args.clarification_source, args.request_source)
            elif args.command == 'status': result = batch.status(args.workbook)
            elif args.command == 'sync': batch.sync(args.workbook); result = {'synced': True}
            elif args.command == 'followup': batch.followup(args.workbook, args.text_file.read_text(), args.codes); result = {'processed': args.codes, 'results_published': False}
            elif args.command == 'materials': result = batch.materials(args.codes)
            elif args.command == 'publish': result = batch.publish(args.workbook, args.codes)
            elif args.command == 'retry': batch.retry(args.workbook, args.task, args.condition); result = {'retried': args.task, 'results_published': False}
            elif args.command == 'stop-failed': batch.stop_failed(args.workbook, args.task); result = {'recorded_technical_failure': args.task, 'results_published': False}
            elif args.command == 'attribute-feedback': result = batch.save_attribute_feedback(args.file)
            else: result = batch.save_feedback(args.file)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            batch.close()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, APIError, OSError, RuntimeError, TimeoutError) as error:
        # Never print model/provider raw responses or configured credentials.
        message = error.code if isinstance(error, APIError) else str(error)
        print(json.dumps({'error': type(error).__name__, 'message': message}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
