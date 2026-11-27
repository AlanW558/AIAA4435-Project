#!/usr/bin/env python3
"""Opt-in, bounded live interpretation/gate regression; no TTS or study writes.

Uses frozen public baselines and requests, never private task goals or ratings.
Each invocation requires a NEW output directory. A crash leaves pending evidence;
there is deliberately no resume, retry, fallback account, or overwrite command.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Backend'))
from core import APIError
from model import DeepSeekModel, ModelError
from tutor_interpretation import TutorInterpreter, build_context, INTERPRETER_VERSION
from tutor_policy import POLICY_VERSION, evaluate_gate, common_question
from verify_live_tutor_voice import literals

CALL_LIMIT = 15
DEFAULT_BATCH = ROOT / 'StudyData/text-check-v3'


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def error_record(error):
    result = {'type': type(error).__name__}
    if isinstance(error, APIError): result['code'] = error.code
    # Never stringify exceptions: provider/configuration errors may contain secrets.
    if isinstance(error, ModelError): result['provider_records'] = error.records
    return result


class AuditModel(DeepSeekModel):
    def __init__(self, name, output):
        super().__init__(name, timeout=45, max_attempts=1)
        self.fallback_key = ''
        self.output, self.calls, self.active_case = output, [], ''

    def _call(self, role, system, context):
        if role not in ('tutor_interpreter', 'tutor_clarification'):
            raise ModelError('Only interpretation and clarification calls are allowed.')
        if len(self.calls) >= CALL_LIMIT:
            raise ModelError('engineering_call_budget_reached')
        number = len(self.calls) + 1
        item = {'number': number, 'case': self.active_case, 'role': role,
                'status': 'pending', 'started_utc': now(),
                'public_context': deepcopy(context),
                'system_prompt_sha256': digest(system.encode()),
                'model': self.model, 'max_attempts': 1}
        path = self.output / f'call-{number:02}.json'
        if path.exists(): raise RuntimeError('Refusing to replace an earlier call record.')
        save(path, item)  # Durable pending marker BEFORE any network action.
        self.calls.append(item)
        started = time.monotonic()
        try:
            raw, records = super()._call(role, system, deepcopy(context))
        except Exception as error:
            item.update(status='failed_no_retry', finished_utc=now(),
                        seconds=round(time.monotonic() - started, 3), error=error_record(error))
            save(path, item)
            raise
        # If this write fails, the on-disk record intentionally remains pending.
        item.update(status='response_received', finished_utc=now(),
                    seconds=round(time.monotonic() - started, 3),
                    raw_response=deepcopy(raw), provider_records=deepcopy(records))
        save(path, item)
        return raw, records


def load_cases(batch):
    records = {}
    hashes = {}
    for path in sorted((batch / 'tasks').glob('*/checkpoint.json')):
        raw = path.read_bytes(); envelope = json.loads(raw)
        payload = envelope['payload']
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
        if digest(encoded) != envelope['sha256']:
            raise ValueError('Frozen checkpoint checksum mismatch.')
        records[payload['task_code']] = payload
        hashes[str(path.relative_to(batch))] = digest(raw)
    if len(records) != 32: raise ValueError('The frozen 32-task batch is required.')
    for name in ('batch.json', 'catalog.json'):
        hashes[name] = digest((batch / name).read_bytes())

    cases = []
    def add(label, code, expected, patch=None, query=None):
        record = records[code]
        cases.append({'label': label, 'source_task_code': code,
                      'query': query or record['request'],
                      'snapshot': deepcopy(record['runtime']['task']['_baseline']),
                      'preferences': deepcopy(record['runtime']['task']['_preferences']),
                      'expectation': expected, 'expected_patch': patch})
    add('actual-clarity-keep-details', 'R3-2', 'ask')
    add('actual-understanding-not-reassurance', 'L3-2', 'ask_or_grounded_direct', {'reply_length': 'detailed'})
    add('actual-less-intimidating', 'T3-1', 'ask')
    add('heldout-clarity', 'R3-2', 'ask', query='Could you make this easier to take in without losing any of the information?')
    add('heldout-comfort', 'T3-1', 'ask', query="I'd like our conversation to feel more comfortable.")
    add('clear-default-rate', 'R1-1', 'act_exact', {'speech_rate': .8})
    add('clear-current-relative-rate', 'R1-2', 'act_exact', {'speech_rate': .9})
    add('clear-key-point-only', 'L1-1', 'act_exact', {'reply_length': 'brief'})
    add('clear-friendly-tone', 'T1-1', 'act_exact', {'tone': 'friendly'})
    add('clear-male-voice-1', 'V1-1', 'act_exact', {'voice': 'voice_d'})
    add('clear-preserve-other-fields', 'L1-1', 'act_exact', {'reply_length': 'brief'},
        'Give me only the key point; keep the current speaking speed, tone and voice unchanged.')
    add('clear-idempotent-rate', 'R1-1', 'act_exact', {},
        'Set the speech rate to one point two times the default speed, and keep every other setting unchanged.')
    record = records['R3-2']
    answer = next(op for op in record['operations'] if op['operation'] == 'answer' and op['condition'] == 'A')
    original = record['runtime']['shared']['shared']['result']['interpretation']
    bound = {'label': 'actual-bound-answer-extra-rate',
             'query': answer['body']['response']['text'],
             'snapshot': deepcopy(record['runtime']['task']['_baseline']),
             'preferences': deepcopy(record['runtime']['task']['_preferences']),
             'pending': deepcopy(answer['question']), 'scope': original['scope'],
             'preserved_fields': original.get('preserved_fields', [])}
    return cases, bound, hashes


def evaluate_case(case, interpreter, model):
    model.active_case = case['label']
    result = interpreter.interpret(case['query'], case['snapshot'], preferences=case['preferences'])
    interpreted = result['interpretation']
    context = build_context(case['query'], case['snapshot'], preferences=case['preferences'])
    question = common_question(case['query'], interpreted, context['settings']) if interpreted.get('proposal') and interpreted['proposal']['supported'] else None
    gate = evaluate_gate(model, 'S', context, interpreted, question)
    proposal = interpreted.get('proposal')
    supported = bool(proposal and proposal['supported'])
    default = next((c for c in proposal['candidates'] if c['id'] == proposal['default_id']), None) if supported else None
    actual = {**context['settings'], **default['patch']} if default else None
    checks = {'supported_request': supported, 'no_extra_learning_question': not interpreted['conversation_query']}
    if case['label'] in ('actual-clarity-keep-details', 'heldout-clarity'):
        checks['all_candidates_preserve_requested_information'] = bool(supported and
            'reply_length' in interpreted.get('preserved_fields', []) and
            all(c['patch'].get('reply_length', context['settings']['reply_length']) == context['settings']['reply_length']
                for c in proposal['candidates']))
    if case['label'] in ('actual-less-intimidating', 'heldout-comfort'):
        checks['no_ungrounded_voice_identity_for_comfort'] = bool(supported and
            all(c['patch'].get('voice', context['settings']['voice']) == context['settings']['voice']
                for c in proposal['candidates']))
    expected = case['expectation']
    if expected == 'ask': checks['selective_asks'] = gate['decision'] == 'ASK'
    else:
        exact = actual == {**context['settings'], **case['expected_patch']}
        if expected == 'act_exact':
            checks.update(selective_acts=gate['decision'] == 'ACT', exact_effect_preserves_other_fields=exact)
        else:
            checks['asks_or_resolves_explanatory_support'] = gate['decision'] == 'ASK' or (gate['decision'] == 'ACT' and exact)
    return {'label': case['label'], 'expectation': expected, 'interpretation': result,
            'question': question, 'gate': gate, 'default_effective_settings': actual,
            'checks': checks, 'passed': all(checks.values())}


def evaluate_bound(bound, interpreter, model):
    model.active_case = bound['label']
    routed = interpreter.interpret(bound['query'], bound['snapshot'], preferences=bound['preferences'],
                                   pending=bound['pending'], answering_pending_question=True)
    result = {'label': bound['label'], 'interpretation': routed}
    interpretation = routed['interpretation']
    checks = {'routes_full_answer_to_resolver': interpretation['kind'] == 'clarification'
              and interpretation['clarification'] == {'option_id': 'other', 'free_text': bound['query']}}
    # Diagnose resolver independently even if the routing check fails; never commit.
    model.active_case = bound['label'] + '-resolve'
    resolved = interpreter.resolve_answer(bound['query'], bound['snapshot'],
        preferences=bound['preferences'], pending=bound['pending'], scope=bound['scope'],
        preserved_fields=bound['preserved_fields'])
    value = resolved['interpretation']; proposal = value.get('proposal')
    ready = bool(value['kind'] in ('tailoring', 'mixed') and proposal and proposal['supported']
                 and len(proposal['candidates']) == 1 and not proposal['unresolved_references']
                 and not proposal.get('ambiguities') and value['scope'] == bound['scope'])
    actual = {**bound['snapshot']['settings'], **proposal['candidates'][0]['patch']} if ready else None
    checks.update(resolved_single_supported_change=ready,
                  rate_point_eight_detail_and_other_settings_preserved=actual == {**bound['snapshot']['settings'], 'speech_rate': .8})
    result.update(resolution=resolved, checks=checks, effective_settings=actual,
                  resolver_is_independent_probe=not checks['routes_full_answer_to_resolver'], passed=all(checks.values()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--batch', type=Path, default=DEFAULT_BATCH)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', help='Explicit subset of initial case labels; each gets one fresh call.')
    parser.add_argument('--skip-bound', action='store_true', help='Exclude the two-call historical bound-answer regression.')
    args = parser.parse_args()
    if not args.live: parser.error('--live is required; this verifier spends bounded API quota')
    batch, output = args.batch.resolve(), args.output.resolve()
    if output == batch or batch in output.parents:
        parser.error('Output must be outside the original batch.')
    cases, bound, source_hashes = load_cases(batch)
    if args.cases:
        if len(set(args.cases)) != len(args.cases) or set(args.cases) - {c['label'] for c in cases}:
            parser.error('Use distinct known initial case labels.')
        cases = [case for case in cases if case['label'] in args.cases]
    active = cases + ([] if args.skip_bound else [bound])
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'selective-ambiguity-live-regression-v1', 'started_utc': now(),
              'acceptance_revision': 2,
              'kind': 'engineering_regression_not_participant_data', 'provider_mode': 'live',
              'limits': {'text_calls': CALL_LIMIT, 'planned_calls': len(cases) + (0 if args.skip_bound else 2), 'tts_calls': 0},
              'automatic_retries': 0, 'fallback_account': False,
              'interpreter_version': INTERPRETER_VERSION, 'policy_version': POLICY_VERSION,
              'source_hashes': source_hashes, 'checks': [], 'original_batch_unchanged': False,
              'code_hashes': {name: digest((ROOT / name).read_bytes()) for name in
                  ['Backend/tutor_interpretation.py', 'Backend/tutor_policy.py', 'Backend/tutor_session.py',
                   'Backend/tutor_capabilities.py', 'Backend/model.py',
                   'Tools/AppearanceExperiment/verify_selective_ambiguity.py']},
              'limitations': ['One bounded run per request; no reliability estimate, TTS or perceived quality test.',
                              'No questionnaire answers, private goals or task identifiers enter provider payloads.']}
    save(output / 'run.json', report)
    save(output / 'local-case-plan.json', {'initial': cases, 'bound_answer': bound})
    model = None
    try:
        config = literals(args.env_file)
        for key in ('DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL'):
            if config.get(key): os.environ[key] = config[key]
        teacher = Path.home() / '.config/aiaa4435/deepseek-teacher.key'
        if teacher.is_file(): os.environ['DEEPSEEK_API_KEY'] = teacher.read_text().strip()
        os.environ.pop('DEEPSEEK_FALLBACK_API_KEY', None)
        model = AuditModel(config.get('DEEPSEEK_MODEL', os.environ.get('DEEPSEEK_MODEL', '')), output)
        interpreter = TutorInterpreter(model)
        report['model'] = model.model
        for case in active:
            try:
                result = evaluate_bound(case, interpreter, model) if case is bound else evaluate_case(case, interpreter, model)
            except (ModelError, APIError, ValueError) as error:
                result = {'label': case['label'], 'passed': False, 'error': error_record(error)}
            save(output / (case['label'] + '.json'), result)
            report['checks'].append({'label': case['label'], 'passed': result['passed'],
                                     'checks': result.get('checks', {}), 'error': result.get('error')})
            save(output / 'run.json', report)
            print(json.dumps({'case': case['label'], 'passed': result['passed']}), flush=True)
    except Exception as error:
        report['execution_error'] = error_record(error)
    finally:
        report['original_batch_unchanged'] = all((batch / name).is_file() and digest((batch / name).read_bytes()) == checksum for name, checksum in source_hashes.items())
        report.update(finished_utc=now(), text_call_count=len(model.calls) if model else 0,
                      calls=[{'number': c['number'], 'case': c['case'], 'role': c['role'], 'status': c['status']} for c in model.calls] if model else [])
        report['passed'] = bool(len(report['checks']) == len(active) and all(c['passed'] for c in report['checks'])
                                and report['original_batch_unchanged'] and not report.get('execution_error'))
        save(output / 'run.json', report)
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']),
                          'text_calls': report['text_call_count'], 'output': str(output)}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
