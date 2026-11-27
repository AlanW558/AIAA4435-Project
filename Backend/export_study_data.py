"""Export new-contract study records, keeping drafts and final answers separate.

Example: python Backend/export_study_data.py --data-dir StudyData/logs/study \
  --run RUN_ID --destination StudyData/exports/NEW_DIRECTORY
Never interprets legacy debug logs as new questionnaire submissions.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from study_answers import ATTRIBUTE_IDS, NATURAL_IDS, NATURAL_VERSION, ATTRIBUTE_SUMMARY_VERSIONS
from study_store import StudyStore, encoded, now
from study_reconcile import reconcile
from tutor_dialogue_log import export_rows

META = ('participant_id', 'study_run_id', 'collection_kind', 'protocol_version', 'data_contract_version')


def safe_cell(value):
    if isinstance(value, (list, dict)): value = encoded(value)
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + value
    return value


def csv_file(path, rows, fields):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='raise')
        writer.writeheader()
        for row in rows: writer.writerow({k: safe_cell(v) for k, v in row.items()})


def json_file(path, value):
    with path.open('x', encoding='utf-8') as f: f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def jsonl_file(path, rows):
    with path.open('x', encoding='utf-8') as f:
        for row in rows: f.write(encoded(row) + '\n')


def export_run(store, run_id, destination, local_journal=None):
    state, events = store.snapshot(run_id)
    reconciliation = reconcile(store, run_id, state['revision'], local_journal, state) if local_journal else None
    destination = Path(destination)
    # Validate and derive everything before opening a new export directory.
    meta = {k: state[k] for k in META}
    attribute, natural, prefs, incomplete, dialogue = [], [], [], [], []
    common = list(META) + ['module_instance_id', 'task_id', 'task_code', 'domain', 'scenario', 'condition', 'session_id',
                          'collection_unit', 'task_completions',
                          'questionnaire_id', 'questionnaire_version', 'answer_schema_version', 'submission_id',
                          'submitted_at', 'evaluation_revision', 'feedback_revision', 'record_stage', 'completeness', 'extras', 'evaluation']
    score_fields = ['scoring_version'] + [f'{name}_{k}' for name in ('sus', 'ueq_pragmatic', 'ueq_hedonic') for k in ('value', 'n_answered', 'score_status')]
    af = common + [f'{i}_{k}' for i in ATTRIBUTE_IDS for k in ('value', 'status', 'reason')]
    nf = common + [f'{i}_{k}' for i in NATURAL_IDS for k in ('value', 'status', 'reason')] + score_fields
    for q in state['questionnaires'].values():
        if q['record_stage'] != 'submitted':
            incomplete.append({**meta, 'kind': 'questionnaire_draft', **q}); continue
        row = {**meta, **{k: q.get(k) for k in common if k not in META}}
        row['collection_unit'] = 'natural_session' if q['questionnaire_version'] == NATURAL_VERSION else 'attribute' if q['questionnaire_version'] in ATTRIBUTE_SUMMARY_VERSIONS else 'task'
        if q['task_id']:
            task = state['tasks'][q['task_id']]
            row.update({k: task[k] for k in ('task_code', 'domain', 'scenario')})
        elif q['questionnaire_version'] in ATTRIBUTE_SUMMARY_VERSIONS:
            row['domain'] = state['modules'][q['module_instance_id']]['domain']
            row['task_completions'] = q['evaluation']['task_completions']
        for item, answer in q['answers'].items():
            for k in ('value', 'status', 'reason'): row[f'{item}_{k}'] = answer.get(k)
        if q['questionnaire_version'] == NATURAL_VERSION:
            row['scoring_version'] = q['scores']['scoring_version']
            row.update({f'{name}_{k}': q['scores'][name][k] for name in ('sus', 'ueq_pragmatic', 'ueq_hedonic') for k in ('value', 'n_answered', 'score_status')})
            natural.append(row)
        else: attribute.append(row)
    for p in state['preferences'].values(): prefs.append({**meta, **p})
    with store.connect() as db:
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='study_runtimes'").fetchone():
            for rid,kind,target,snapshot,inflight in db.execute('SELECT id,kind,target_id,snapshot,inflight FROM study_runtimes WHERE run_id=?',(run_id,)):
                if inflight or json.loads(snapshot).get('processing'):
                    incomplete.append({**meta,'kind':'runtime_needs_reconciliation','runtime_id':rid,'target_id':target,'runtime_kind':kind,'pending_operation':json.loads(inflight) if inflight else None})
    for task in state['tasks'].values():
        if store.attribute_summary(state):
            if not task.get('completion_id'): incomplete.append({**meta, 'kind': 'unfinished_task', **task})
        elif not task['submission_id']: incomplete.append({**meta, 'kind': 'unsubmitted_task', **task})
    if store.attribute_summary(state):
        for domain in dict.fromkeys(t['domain'] for t in state['manifest']['tasks']):
            module = next((m for m in state['modules'].values() if m['module_type'] == 'attribute_comparison' and m['domain'] == domain), None)
            if module is None or not module.get('submission_id'):
                incomplete.append({**meta, 'kind': 'attribute_feedback_not_submitted', 'domain': domain,
                                   'module_instance_id': module['module_instance_id'] if module else None})
            if domain not in state['preferences']:
                incomplete.append({**meta, 'kind': 'attribute_preference_not_submitted', 'domain': domain})
    if state['end_reason'] != 'normal_completion':
        incomplete.append({**meta, 'kind': 'unfinished_run', 'lifecycle': state['lifecycle'], 'end_reason': state['end_reason']})
    for task in state['manifest']['tasks']:
        if not any(t['task_code'] == task['task_code'] for t in state['tasks'].values()):
            incomplete.append({**meta, 'kind': 'task_not_started', **task})
    if not any(m.get('submission_id') for m in state['modules'].values() if m['module_type'] == 'natural_selective'):
        incomplete.append({**meta, 'kind': 'natural_feedback_not_submitted'})
    for event in events:
        if event['event'] == 'dialogue':
            dialogue.append({**meta, 'audit_event_id': event['event_id'], 'request_id': event['request_id'],
                             'server_sequence': event['server_sequence'], 'server_received_at': event['timestamp_utc'],
                             **event['payload'], **event['result']})
    runtime_events=[e for e in events if e['event']=='runtime_audit']
    projected=export_rows([(i,e['record']) for i,e in enumerate(runtime_events)])
    for row in projected:
        source=runtime_events[row['source_line']]
        dialogue.append({**row,**meta,'audit_event_id':source['event_id'],'study_target_id':source['target_id'],'runtime_id':source['runtime_id']})
    pref_fields = list(META) + ['preference_id', 'submission_id', 'record_stage', 'questionnaire_version', 'scope', 'domain', 'answers', 'submitted_at', 'task_submissions', 'task_completions', 'attribute_submissions']
    destination.mkdir(parents=True, exist_ok=False)
    json_file(destination / 'session.json', state)
    csv_file(destination / 'attribute_feedback.csv', attribute, af)
    csv_file(destination / 'natural_feedback.csv', natural, nf)
    csv_file(destination / 'preferences.csv', prefs, pref_fields)
    jsonl_file(destination / 'dialogue.jsonl', dialogue)
    jsonl_file(destination / 'events.jsonl', events)
    jsonl_file(destination / 'incomplete_records.jsonl', incomplete)
    counts = {'attribute_feedback': len(attribute), 'natural_feedback': len(natural), 'preferences': len(prefs),
              'dialogue': len(dialogue), 'events': len(events), 'incomplete_records': len(incomplete)}
    if reconciliation is not None: json_file(destination / 'local_reconciliation.json', reconciliation)
    manifest = {'export_schema_version': 'study-export-v2' if store.attribute_summary(state) else 'study-export-v1',
                'attribute_feedback_unit': state['manifest'].get('attribute_feedback_unit', 'task'),
                **meta, 'generated_at': now(), 'source': str(store.path.resolve()),
                'source_revision': state['revision'], 'counts': counts,
                'backend_record_status': 'complete' if state['end_reason'] == 'normal_completion' else 'partial',
                'synchronization_status': 'unknown_client_pending', 'export_status': 'unreconciled',
                'note': 'Backend snapshot is consistent. Headset-local pending/conflicting packets must be reconciled separately; no unknown client data are assumed synchronized.',
                'files': {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in sorted(destination.iterdir())}}
    if reconciliation is not None:
        manifest['synchronization_status'] = reconciliation['status']
        if reconciliation['status'] == 'provided_copy_reconciled': manifest['export_status'] = manifest['backend_record_status']
        manifest['note'] = reconciliation['scope']
    json_file(destination / 'export_manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run'); group.add_argument('--all', action='store_true')
    parser.add_argument('--destination', required=True)
    parser.add_argument('--local-journal', help='Optional frozen Unity journal copy; verified against durable receipts')
    args = parser.parse_args()
    if not (Path(args.data_dir) / 'study.sqlite3').is_file(): parser.error('Existing study.sqlite3 required; refusing to create an empty source.')
    store = StudyStore(args.data_dir)
    if args.run:
        result = export_run(store, args.run, args.destination, args.local_journal)
        print(json.dumps({'destination': str(Path(args.destination).resolve()), 'counts': result['counts'], 'status': result['export_status']}))
    else:
        dest = Path(args.destination); dest.mkdir(parents=True, exist_ok=False)
        with store.connect() as db: ids = [r[0] for r in db.execute('SELECT id FROM runs ORDER BY id')]
        runs = []
        for run_id in ids:
            state = store.read(run_id)
            target = dest / state['collection_kind'] / state['participant_id'] / run_id
            result = export_run(store, run_id, target, args.local_journal)
            runs.append({'study_run_id': run_id, 'path': str(target.relative_to(dest)), 'counts': result['counts']})
        json_file(dest / 'batch_manifest.json', {'generated_at': now(), 'runs': runs, 'atomicity': 'Each run has its own consistent snapshot; this is not a single cross-run time snapshot.'})
        print(json.dumps({'destination': str(dest.resolve()), 'runs': len(runs)}))


if __name__ == '__main__': main()
