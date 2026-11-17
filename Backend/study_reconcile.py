"""Read-only reconciliation of a Unity immutable journal copy with server receipts."""
import json
from pathlib import Path
from core import APIError
from study_store import digest, encoded


def reconcile(store, run_id, source_revision, directory, state=None):
    root = Path(directory)
    if not root.is_dir(): raise ValueError('Local journal directory does not exist.')
    if list(root.glob('*.tmp')): raise ValueError('Unfinished journal writes must be recovered on the client before export.')
    sequence = 0; commands = {}; local_receipts = {}; file_hashes = {}; drafts = {}; rejections = {}
    for file in sorted(root.glob('*.json')):
        raw = file.read_text(encoding='utf-8'); item = json.loads(raw)
        if type(item.get('sequence')) is not int or item['sequence'] <= sequence or file.name != f"{item['sequence']:020d}.json":
            raise ValueError('Invalid journal sequence or file identity.')
        sequence = item['sequence']
        if not isinstance(item.get('payload'), str) or item.get('sha256') != digest(item['payload']):
            raise ValueError('Journal payload checksum mismatch.')
        file_hashes[file.name] = digest(raw)
        if item['kind'] == 'command':
            packet = json.loads(item['payload']); rid = item['request_id']
            if packet.get('request_id') != rid or rid in commands: raise ValueError('Duplicate or mismatched command identity.')
            commands[rid] = packet
        elif item['kind'] == 'receipt':
            receipt = json.loads(item['payload']); rid = item['request_id']
            if rid not in commands or rid in local_receipts or receipt.get('recorded') is not True or receipt.get('request_id') != rid or receipt.get('payload_sha256') != digest(commands[rid]['payload_json']):
                raise ValueError('Invalid local acknowledgement.')
            local_receipts[rid] = receipt
        elif item['kind'] == 'rejection':
            if item['request_id'] not in commands:raise ValueError('Unknown rejected command.')
            rejection=json.loads(item['payload'])
            if not rejection.get('error'):raise ValueError('Invalid rejection evidence.')
            rejections[item['request_id']]=rejection
        elif item['kind'] == 'draft':
            drafts[item.get('scope', '')] = item
        elif item['kind'] != 'snapshot':
            raise ValueError('Unknown local journal record.')
    matched, pending, recovered, conflicts = [], [], [], []
    for rid, packet in commands.items():
        try: ack = store.receipt(rid)
        except APIError as e:
            if e.code != 'receipt_not_found': raise
            if packet.get('study_run_id') in (None, '', run_id) and rid not in rejections: pending.append(rid)
            if packet.get('study_run_id') in (None, '', run_id) and rid in rejections and rejections[rid].get('error')=='request_id_conflict':conflicts.append(rid)
            continue
        if ack.get('study_run_id') != run_id:
            if packet.get('study_run_id') == run_id: conflicts.append(rid)
            continue
        # A matching payload alone is insufficient: operation/revision/run must match too.
        with store.connect() as db:
            signature = db.execute('SELECT signature FROM receipts WHERE request_id=?', (rid,)).fetchone()[0]
        if signature != digest(encoded(packet)) or ack['revision'] > source_revision:
            conflicts.append(rid); continue
        local = local_receipts.get(rid)
        if local and any(local.get(k) != ack.get(k) for k in ('request_id', 'study_run_id', 'payload_sha256', 'revision')):
            conflicts.append(rid); continue
        matched.append(rid)
        if local is None: recovered.append(rid)
    draft_review = []
    state = state or store.read(run_id)
    with store.connect() as db:
        other_questionnaires={qid for row in db.execute('SELECT id,payload FROM runs WHERE id!=?',(run_id,)) for qid in json.loads(row[1])['questionnaires']}
    for scope, item in drafts.items():
        if scope.removeprefix('draft:') in other_questionnaires:continue
        if scope.startswith(('preference:','exit:')) and scope.split(':')[1]!=run_id:continue
        if scope.startswith('runtime-ack:'):
            if 'runtime:'+scope.removeprefix('runtime-ack:') in drafts:continue
        if scope.startswith('runtime:'):
            packet=json.loads(item['payload'])
            if packet.get('study_run_id')!=run_id:continue
            key=packet['runtime_id']+':'+packet['body']['request_id']
            with store.connect() as db:
                table=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_receipts'").fetchone()
                receipt=db.execute('SELECT signature FROM runtime_receipts WHERE key=?',(key,)).fetchone() if table else None
            if receipt and receipt[0]==digest(encoded({'op':packet['operation'],'data':packet['body']})):continue
            draft_review.append({'scope':scope,'sequence':item['sequence'],'payload_json':item['payload']});continue
        if scope.startswith('preference:'+run_id+':'):
            preference=state['preferences'].get(scope.split(':')[-1])
            local=json.loads(item['payload'])
            if preference:
                saved=preference['answers']
                if {**local,'selected_conditions':sorted(local.get('selected_conditions',[]))}=={**saved,'selected_conditions':sorted(saved.get('selected_conditions',[]))}:continue
        if scope=='exit:'+run_id and state['lifecycle']=='ended':continue
        q = state['questionnaires'].get(scope.removeprefix('draft:'))
        try: draft = json.loads(item['payload'])
        except ValueError: draft = None
        basis=None
        if q is not None and q.get('evaluation_binding'):
            b=q['evaluation_binding']
            basis=f"{q['target_id']}:{q['condition']}:"+(str(q['evaluation_revision']) if q['task_id'] is None else f"{b['branch_revision']}:{b['state_revision']}")
        represented = (q is not None and isinstance(draft, dict) and set(draft) <= {'answers', 'extras', 'evaluation_basis'}
                       and ('evaluation_basis' not in draft or draft['evaluation_basis']==basis)
                       and draft.get('answers') == q['answers'] and q['record_stage'] == 'submitted'
                       and draft.get('extras', {'reasons': [], 'comment': '', 'comment_confirmed': False}) == q['extras'])
        if not represented:
            draft_review.append({'scope': scope, 'sequence': item['sequence'], 'payload_json': item['payload']})
    # An empty/unrelated journal cannot certify this run's client state.
    status = 'provided_copy_reconciled' if matched and not pending and not conflicts and not draft_review else 'unreconciled'
    return {'status': status, 'scope': 'Only the supplied frozen journal copy; not a live headset inspection.',
            'local_drafts_to_review': draft_review, 'journal_files': file_hashes, 'last_sequence': sequence, 'matched_requests': matched,
            'rejected_requests': [rid for rid in rejections if commands[rid].get('study_run_id') in (None, '', run_id)],
            'pending_requests': pending, 'conflicting_requests': conflicts, 'server_receipts_missing_locally': recovered}
