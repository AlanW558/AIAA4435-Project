#!/usr/bin/env python3
"""Read-only acceptance checks for a complete generated-reply auxiliary batch.

No providers, Batch constructor, browser profile, ratings, or experiment writes.
The optional JSON report must be outside the batch being inspected.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

from attribute_feedback import VERSION, SUPPORTED_VERSIONS, validate_feedback
from report import collect, checkpoint, digest, inside, rebase_audio_urls
from workbook import parse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Backend'))
from speech import validate_wav

CONDITIONS = ('E', 'A', 'N', 'S')
DOMAINS = ('speech_rate', 'reply_length', 'tone', 'voice')


def check(condition, message):
    if not condition: raise ValueError(message)


def inspect_wav(raw):
    validate_wav(raw)
    with wave.open(io.BytesIO(raw)) as audio:
        count, rate = audio.getnframes(), audio.getframerate()
        pcm = audio.readframes(count)
        check(any(pcm), 'WAV contains only zero-valued PCM samples.')
        return {'frames': count, 'sample_rate': rate, 'duration_seconds': count / rate,
                'channels': audio.getnchannels(), 'sample_width_bytes': audio.getsampwidth()}


def blank_page_state(document, data, node=None):
    """Run the exported page's own draft logic against empty isolated storage."""
    scripts = re.findall(r'<script>\s*(.*?)</script>', document, re.S)
    check(len(scripts) == 1, 'HTML must contain one questionnaire application script.')
    script, changed = re.subn(r'\nrender\(\);\s*$', '', scripts[0])
    check(changed == 1, 'Cannot isolate questionnaire initialization from page rendering.')
    node = node or shutil.which('node') or str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
    runner = r'''const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));const memory=new Map(),reads=[];
const context=vm.createContext({document:{getElementById:id=>id==='report-data'?{textContent:JSON.stringify(input.data)}:{addEventListener(){}}},localStorage:{getItem:key=>{reads.push(key);return memory.get(key)||null;},setItem:(key,value)=>memory.set(key,value)}});
vm.runInContext(input.script,context,{timeout:5000});
const state=vm.runInContext('({drafts:publishedAttributes.map(getDraft),completed:publishedAttributes.map(completion),valid:publishedAttributes.map(g=>draftValid(g,getDraft(g)))})',context,{timeout:5000});
process.stdout.write(JSON.stringify({...state,storage_reads:reads,storage_writes:memory.size}));'''
    result = subprocess.run([node, '-e', runner], input=json.dumps({'data': data, 'script': script}),
                            capture_output=True, text=True, timeout=15)
    check(result.returncode == 0, 'Isolated questionnaire JavaScript validation failed.')
    value = json.loads(result.stdout)
    check(len(value['drafts']) == 4 and value['completed'] == [0] * 4 and all(value['valid']), 'Questionnaire is not initially empty and valid.')
    check(value['storage_writes'] == 0, 'Initialization unexpectedly wrote questionnaire answers.')
    total_answers = 0
    for draft in value['drafts']:
        validate_feedback(draft, data, final=False)
        check(draft['preference'] == {'status': 'unanswered', 'value': None}, 'A strategy preference was prefilled.')
        for section in draft['conditions'].values():
            check(all(answer == {'status': 'unanswered', 'value': None} for answer in section['answers'].values()), 'A questionnaire rating was prefilled.')
            total_answers += len(section['answers'])
    check(total_answers == 80, 'Expected 80 empty strategy answers plus four empty preferences.')
    check(all(key.startswith('tutor-text-attribute-feedback-v1:' + data['batch_id'] + ':') for key in value['storage_reads']), 'Page reads a different batch or legacy task rating cache.')
    return {'strategy_answers_unanswered': total_answers, 'preferences_unanswered': 4,
            'total_required_responses': total_answers + 4, 'isolated_storage': True}


def verify(directory, *, html=None, workbook=None, node=None, allow_technical_failures=False,
           request_source='assistant_revised_user_authorized',
           clarification_source='assistant_authored_user_authorized'):
    directory = Path(directory).resolve()
    check(directory.is_dir(), 'Existing batch directory required.')
    html = Path(html).resolve() if html else directory / 'REVIEW_AND_QUESTIONNAIRE.html'
    workbook = Path(workbook).resolve() if workbook else directory / 'TASK_REQUESTS.md'
    watched = {}

    def read(path):
        path = Path(path).resolve(); raw = path.read_bytes()
        watched[path] = digest(raw)
        return raw

    metadata = json.loads(read(directory / 'batch.json'))
    check(metadata.get('response_mode') == 'generated_reply' and metadata.get('questionnaire_version') in SUPPORTED_VERSIONS
          and metadata.get('collection_unit') == 'attribute', 'Not a generated-reply attribute-summary batch.')
    check(metadata.get('formal_study_submission') is False and metadata.get('collection_kind') == 'engineering', 'Auxiliary provenance is missing.')
    read(directory / 'catalog.json'); read(workbook)
    rows = parse(workbook)
    check(len(rows) == 32 and all(row['request'].strip() for row in rows.values()), 'All 32 requests must be filled.')
    check(all(not row['clarification'].strip() for row in rows.values()), 'Unprocessed clarification text remains in the worksheet.')
    document = read(html).decode('utf-8')
    embedded = re.findall(r'<script id="report-data" type="application/json">(.*?)</script>', document, re.S)
    check(len(embedded) == 1, 'HTML must embed exactly one report dataset.')
    html_data = json.loads(embedded[0])
    data = rebase_audio_urls(collect(directory, html_data.get('questionnaire_version')), directory, html.parent)
    check(len(data['tasks']) == 32 and all(task['status'] == 'published' for task in data['tasks']), 'All 32 current task releases must be published.')
    scenarios = Counter((task['domain'], task['scenario']) for task in data['tasks'])
    check(scenarios == Counter({(domain, f'C{i}'): 2 for domain in DOMAINS for i in range(1, 5)}), 'Each attribute scenario must have exactly two tasks.')
    for domain, prefix in zip(DOMAINS, ('R', 'L', 'T', 'V')):
        check([t['display_code'] for t in data['tasks'] if t['domain'] == domain]
              == [f'{prefix}{scenario}-{number}' for scenario in range(1, 5) for number in (1, 2)],
              f'{domain}: participant-visible task numbers are not contiguous 1/2.')
    check([g['domain'] for g in data['attributes']] == list(DOMAINS)
          and all(g['status'] == 'published' and len(g['task_codes']) == len(g['task_releases']) == 8 for g in data['attributes']), 'Each of four attributes needs eight current task releases.')
    check(data['baseline_audio_count'] == data['listening_material_count'] == 0, 'New release contains fixed sample/reference audio.')
    if not allow_technical_failures:
        check(data['technical_failure_count'] == 0 and data['audio_count'] == 128, 'Expected 128 strategy replies without technical failures.')
    check(data['audio_count'] + data['technical_failure_count'] == 128, 'Strategy coverage does not total 128.')
    clarification_counts = Counter(); request_origins = Counter(); clarification_origins = Counter()
    audio = []; failures = []
    for task in data['tasks']:
        code = task['task_code']; cp = directory / 'tasks' / code / 'checkpoint.json'
        read(cp); record = checkpoint(cp, code)
        check(not record.get('pending') and not record['runtime'].get('processing'), f'{code}: unresolved checkpoint.')
        release = json.loads(read(inside(directory, record['published_release']['directory']) / 'result.json'))
        check(record['request'] == release['request'] == rows[code]['request'], f'{code}: request text differs across worksheet and result.')
        starts = [op for op in record['operations'] if op['operation'] == 'start']
        check(len(starts) == 1 and starts[0]['body']['query'] == record['request'], f'{code}: initial request evidence mismatch.')
        check(starts[0].get('input_source') == request_source, f'{code}: request provenance mismatch.')
        request_origins[starts[0]['input_source']] += 1
        check(set(task['conditions']) == set(CONDITIONS), f'{code}: missing strategy card.')
        for c in CONDITIONS:
            check(not release['view']['branches'][c].get('question'), f'{code}/{c}: unresolved clarification question.')
            ops = [op for op in record['operations'] if op['operation'] == 'answer' and op['condition'] == c]
            annotation = release['clarifications'][c]
            check(annotation['count'] == len(ops) and annotation['occurred'] == bool(ops), f'{code}/{c}: clarification count mismatch.')
            ids = [op['body']['question_id'] for op in ops]
            check(len(ids) == len(set(ids)), f'{code}/{c}: duplicate clarification answer evidence.')
            check([turn['question_id'] for turn in annotation['turns']] == ids, f'{code}/{c}: clarification IDs differ from recorded operations.')
            for op, turn in zip(ops, annotation['turns']):
                origin = record['answers'][op['body']['question_id']]
                question = op.get('question') or origin.get('question')
                check(isinstance(question, dict) and turn['question'] == question['text'], f'{code}/{c}: question text mismatch.')
                check(isinstance(turn['answer'], str) and turn['answer'].strip()
                      and turn['answer'] == op['body']['response'].get('text') == origin.get('text'), f'{code}/{c}: clarification reply mismatch.')
                check(turn['source'] == origin.get('input_source') == op.get('input_source') == clarification_source, f'{code}/{c}: clarification provenance mismatch.')
                clarification_origins[turn['source']] += 1
            clarification_counts[c] += len(ops)
            entry = release['audio'][c]
            if entry is None:
                failures.append({'task_code': code, 'condition': c, **release['technical_failures'][c]}); continue
            raw = read(inside(directory, entry['file']))
            check(digest(raw) == entry['sha256'] and len(raw) == entry['bytes'], f'{code}/{c}: audio bytes differ from metadata.')
            sidecar = json.loads(read(inside(directory, entry['file']).with_suffix('.json')))
            check(sidecar == entry, f'{code}/{c}: audio sidecar mismatch.')
            properties = inspect_wav(raw)
            audio.append({'task_code': code, 'condition': c, 'sha256': entry['sha256'], **properties})
    check({k: v for k, v in html_data.items() if k != 'generated_at'} == {k: v for k, v in data.items() if k != 'generated_at'}, 'HTML dataset is stale or differs from the validated releases.')
    blank = blank_page_state(document, data, node)
    check(not list((directory / 'attribute-feedback').glob('**/*.json')) and not list((directory / 'feedback').glob('*.json')), 'Feedback already exists; this check expects a new, unanswered release.')
    for path, checksum in watched.items():
        check(digest(path.read_bytes()) == checksum, 'An input file changed during read-only validation; retry once publication is stable.')
    durations = [item['duration_seconds'] for item in audio]
    return {'schema': 'tutor-text-release-qa-v1', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'status': 'passed', 'batch_id': metadata['batch_id'], 'directory': str(directory),
            'questionnaire_version': data['questionnaire_version'],
            'provider_calls': 0, 'batch_writes': 0, 'tasks': 32, 'attributes': 4,
            'strategy_audio_files': len(audio), 'technical_failures': failures,
            'request_provenance': dict(request_origins), 'clarification_provenance': dict(clarification_origins),
            'clarification_turns_by_strategy': dict(clarification_counts), 'blank_questionnaire': blank,
            'audio_duration_seconds': {'min': min(durations) if durations else None, 'max': max(durations) if durations else None, 'total': sum(durations)},
            'html_sha256': watched[html], 'checked_file_count': len(watched),
            'limitation': 'Structural, provenance and PCM checks only; this does not judge perceived voice quality or task success, and does not inspect real browser-local participant drafts.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--html', type=Path); parser.add_argument('--workbook', type=Path)
    parser.add_argument('--node'); parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-technical-failures', action='store_true')
    args = parser.parse_args()
    if args.output:
        check(not args.output.resolve().is_relative_to(args.directory.resolve()), 'QA output must stay outside the inspected batch.')
    result = verify(args.directory, html=args.html, workbook=args.workbook, node=args.node,
                    allow_technical_failures=args.allow_technical_failures)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output: output.write(payload)
    print(payload, end='')


if __name__ == '__main__': main()
