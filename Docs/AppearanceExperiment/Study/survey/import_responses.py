"""Validate actual local-questionnaire responses and join the frozen schedule.

This does not create or simulate answers. Duplicate revisions require explicit
researcher adjudication; skipped/cannot-judge ratings remain empty in CSV.
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RATINGS = ('interruption_1to7','control_1to7','effort_1to7','satisfaction_1to7')
ID_RE = re.compile(r'^(P00[1-9]|P01[0-9]|P020|PILOT0[12])$')
SESSION_RE = re.compile(r'^[A-Za-z0-9_-]{3,80}$')


def validate_record(record, spec):
    if not isinstance(record,dict):
        raise ValueError('A response must be one JSON object.')
    if record.get('schema_version') != spec['schema_version']:
        raise ValueError('Unknown questionnaire version; do not silently pool versions.')
    forms = {f['id']: f for f in spec['forms']}
    fid = record.get('form_id')
    if fid not in forms:
        raise ValueError('Unknown form_id.')
    pid = record.get('participant_id','')
    if not isinstance(pid,str) or not ID_RE.fullmatch(pid):
        raise ValueError('Invalid participant_id.')
    if not isinstance(record.get('session_id'),str) or not SESSION_RE.fullmatch(record['session_id']):
        raise ValueError('Invalid session_id.')
    expected_phase = 'pilot' if pid.startswith('PILOT') else 'formal'
    if record.get('phase') != expected_phase:
        raise ValueError('Participant ID and pilot/formal phase disagree.')
    block = record.get('block')
    if fid == 'block' and (type(block) is not int or block not in range(1,5)):
        raise ValueError('Block responses must identify block 1–4.')
    if fid != 'block' and block is not None:
        raise ValueError('Only block responses may set block.')
    try:
        timestamp = datetime.fromisoformat(record['recorded_at_utc'].replace('Z','+00:00'))
    except (KeyError,ValueError,AttributeError):
        raise ValueError('Missing or invalid recorded_at_utc.') from None
    if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds()!=0:
        raise ValueError('recorded_at_utc must include the UTC timezone.')
    if type(record.get('page_elapsed_ms')) is not int or record['page_elapsed_ms'] < 0:
        raise ValueError('page_elapsed_ms must be a nonnegative integer.')
    questions = {q['id']:q for q in forms[fid]['questions']}
    answers = record.get('answers',{})
    statuses = record.get('answer_status',{})
    if set(answers) != set(questions) or set(statuses) != set(questions):
        raise ValueError('Answer fields do not match this questionnaire version.')
    for key,q in questions.items():
        value,status = answers[key],statuses[key]
        hidden=bool(q.get('show_if') and answers.get(q['show_if']['field'])!=q['show_if']['equals'])
        if hidden:
            if value is not None or status!='not_shown':
                raise ValueError(f'{key}: hidden fields must be null/not_shown.')
            continue
        expected='skipped' if value is None else ('cannot_judge' if value=='cannot_judge' else 'answered')
        if status != expected:
            raise ValueError(f'{key}: status and value disagree.')
        if q['required'] and value is None:
            raise ValueError(f'{key}: required answer missing.')
        if value is None:
            continue
        if q.get('options'):
            if value not in [o['value'] for o in q['options']]:
                raise ValueError(f'{key}: unknown option.')
            if q['type']=='rating' and value!='cannot_judge' and type(value) is not int:
                raise ValueError(f'{key}: ratings must be integer 1–7 or cannot_judge.')
        elif not isinstance(value,str) or len(value)>q.get('max_length',1000):
            raise ValueError(f'{key}: invalid text answer.')
    if fid=='pre' and answers.get('consent')!='agree':
        raise ValueError('Declined-consent responses should not be stored as study responses.')
    return record


def import_records(input_dir,schedule_path,out_dir):
    spec=json.loads((ROOT/'questionnaires.json').read_text(encoding='utf-8'))
    sources=sorted(input_dir.glob('*.json'))
    if not sources:
        raise ValueError('No actual JSON response files found. Empty folders are not data.')
    records=[];identities=set();participant_sessions={};session_participants={}
    for path in sources:
        try:
            record=validate_record(json.loads(path.read_text(encoding='utf-8')),spec)
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError(f'{path.name}: {exc}') from None
        pid,sid=record['participant_id'],record['session_id']
        identity=(sid,record['form_id'],record['block'])
        if identity in identities:
            raise ValueError(f'Duplicate response/revision for {identity}; explicitly retain the intended revision before importing.')
        identities.add(identity)
        if pid in participant_sessions and participant_sessions[pid]!=sid:
            raise ValueError(f'{pid} has multiple sessions; adjudicate resumed/repeated sessions before pooling.')
        if sid in session_participants and session_participants[sid]!=pid:
            raise ValueError(f'{sid} was used for multiple participants.')
        participant_sessions[pid]=sid;session_participants[sid]=pid
        records.append(record)
    consent_sessions={r['session_id'] for r in records if r['form_id']=='pre' and r['answers']['consent']=='agree'}
    if set(session_participants)-consent_sessions:
        raise ValueError('Pre-session consent record is missing for one or more sessions; collect the corresponding file before importing.')
    with schedule_path.open(newline='',encoding='utf-8-sig') as f:
        schedule={}
        for row in csv.DictReader(f):
            key=(row['participant_slot'],int(row['block']))
            if key in schedule:
                raise ValueError('Duplicate participant/block in schedule.')
            if row['condition'] not in ('E','A','N','S'):
                raise ValueError('Unknown condition in frozen schedule.')
            schedule[key]=row['condition']
    rows=[];missing=Counter();by_participant=defaultdict(list)
    for record in records:
        if record['form_id']!='block':
            continue
        pid,block=record['participant_id'],record['block']
        condition=schedule.get((pid,block),'')
        if record['phase']=='formal' and not condition:
            raise ValueError(f'No frozen schedule entry for {pid}, block {block}.')
        row=dict(participant_id=pid,phase=record['phase'],block=block,condition=condition)
        for key in RATINGS:
            value=record['answers'][key]
            row[key]=value if type(value) is int else ''
            if row[key]=='':missing[f'{key}:{record["answer_status"][key]}']+=1
        rows.append(row);by_participant[pid].append(block)
    participants={pid:{'session_id':sid,'phase':'pilot' if pid.startswith('PILOT') else 'formal','blocks_present':sorted(by_participant[pid]),'missing_blocks':sorted(set(range(1,5))-set(by_participant[pid])),'has_exit':any(r['participant_id']==pid and r['form_id']=='exit' for r in records)} for pid,sid in participant_sessions.items()}
    report={'schema_version':spec['schema_version'],'source':'actual_local_questionnaire_files','response_files':len(records),'participants':participants,'block_rows':len(rows),'missing_ratings_by_reason':dict(missing),'notes':['No questionnaire responses were generated by this importer.','Pilot condition is blank because the formal schedule does not specify pilot assignments.','cannot_judge and skipped are blank in the CSV; original distinctions remain in response_records.json.','Questionnaire scores remain separate single items; do not compute an overall UX score.']}
    out_dir.mkdir(parents=True,exist_ok=True)
    outputs=[out_dir/'block_ratings.csv',out_dir/'response_records.json',out_dir/'response_import_report.json']
    if any(p.exists() for p in outputs):
        raise ValueError('Output already exists. Choose a new output directory to preserve prior analysis.')
    fields=['participant_id','phase','block','condition',*RATINGS]
    with outputs[0].open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(sorted(rows,key=lambda r:(r['participant_id'],r['block'])))
    outputs[1].write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    outputs[2].write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--schedule',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args()
    try:report=import_records(args.input_dir,args.schedule,args.out_dir)
    except (ValueError,OSError,json.JSONDecodeError) as exc:parser.error(str(exc))
    print(f'Imported {report["response_files"]} actual files and {report["block_rows"]} block ratings. No response content printed.')


if __name__=='__main__':main()
