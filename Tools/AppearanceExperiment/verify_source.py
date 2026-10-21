#!/usr/bin/env python3
"""Verify source assets and authored study joins without producing experiment data.

This is a static audit. It does not replace a Unity build, rendered-state smoke,
real API verification, participant sessions, or headset testing.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'Docs/AppearanceExperiment/Study'
STREAM = ROOT / 'Assets/StreamingAssets/AppearanceStudy'
COLORS = {'blue','orange','green','gray','red','purple'}
ACCESSORIES = {'none','hat','glasses'}
PUBLIC_KEYS = {'initial_query','state','visible_history','soft_preferences'}

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))

def valid_state(state):
    scale = state.get('scale')
    return (state.get('jacket_color') in COLORS
            and state.get('accessory') in ACCESSORIES
            and isinstance(scale,(float,int)) and not isinstance(scale,bool)
            and .85-1e-6 <= scale <= 1.15+1e-6
            and abs(round(scale/.05)*.05-scale)<1e-6)

def audit():
    checks=[]
    def check(name,passed,detail):
        checks.append({'check':name,'passed':bool(passed),'detail':detail})

    materialization=read_json(ROOT/'Tools/AppearanceExperiment/local-lfs-materialization.json')
    bad=[]
    for item in materialization['assets']:
        path=ROOT/item['path']
        if not path.is_file():bad.append({'path':item['path'],'error':'missing'});continue
        actual=sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size!=item['size'] or actual!=item['sha256']:
            bad.append({'path':item['path'],'error':'original LFS OID/size mismatch'})
    check('materialized_lfs_asset_integrity',not bad,
          {'files':len(materialization['assets']),'mismatches':bad})
    pointers=[]
    for path in (ROOT/'Assets').rglob('*'):
        if path.is_file() and path.stat().st_size<300:
            if path.read_bytes().startswith(b'version https://git-lfs.github.com/spec/v1'):
                pointers.append(str(path.relative_to(ROOT)))
    check('no_unresolved_asset_lfs_pointers',not pointers,pointers)

    private=read_json(STUDY/'materials/tasks_private.json')
    public=read_json(STREAM/'tasks.json')['tasks']
    private_ids=[t['task_id'] for t in private];public_ids=[t['task_id'] for t in public]
    check('sixteen_unique_matching_tasks',
          len(private_ids)==len(public_ids)==16 and len(set(private_ids))==16
          and set(private_ids)==set(public_ids),{'private':private_ids,'unity':public_ids})
    by_id={t['task_id']:t for t in private}
    mismatches=[]
    for task in public:
        expected=by_id.get(task['task_id'])
        if (not expected or task['model_visible']!=expected['model_visible']
                or set(task['model_visible'])!=PUBLIC_KEYS
                or task.get('participant_goal')!=expected['evaluator_only']['participant_goal_text']
                or 'evaluator_only' in task):
            mismatches.append(task['task_id'])
    check('unity_public_context_and_participant_goal_join',not mismatches,mismatches)
    invalid=[]
    for task in private:
        context=task['model_visible']
        if not all(valid_state(s) for s in [context['state']]+context['visible_history']):
            invalid.append(task['task_id'])
        hidden=task['evaluator_only']
        for field,values in hidden['allowed_values'].items():
            if not values or field not in {'jacket_color','accessory','scale'}:
                invalid.append(task['task_id']);continue
            if not all(valid_state({**context['state'],field:value}) for value in values):
                invalid.append(task['task_id'])
    check('task_initial_history_and_target_states_supported',not invalid,sorted(set(invalid)))

    trials=csv_rows(STREAM/'trial_schedule.csv')
    source=csv_rows(STUDY/'materials/trial_schedule.csv')
    check('unity_schedule_matches_frozen_source',trials==source,{'unity_rows':len(trials),'source_rows':len(source)})
    participant_rows=defaultdict(list)
    for row in trials:participant_rows[row['participant_slot']].append(row)
    schedule_errors=[]
    expected_ids={f'P{i:03d}' for i in range(1,21)}
    if set(participant_rows)!=expected_ids:schedule_errors.append('Participant IDs do not equal P001–P020')
    for participant,rows in participant_rows.items():
        if len(rows)!=16 or len({r['task_id'] for r in rows})!=16:
            schedule_errors.append(participant+': not 16 unique tasks')
        if Counter(r['condition'] for r in rows)!=Counter({'E':4,'A':4,'N':4,'S':4}):
            schedule_errors.append(participant+': condition counts')
        if len({r['trial_id'] for r in rows})!=16:schedule_errors.append(participant+': duplicate trial IDs')
        for block in range(1,5):
            block_rows=[r for r in rows if int(r['block'])==block]
            if ({int(r['within_block']) for r in block_rows}!={1,2,3,4}
                    or len({r['condition'] for r in block_rows})!=1):
                schedule_errors.append(f'{participant}: invalid block {block}')
    assignment=csv_rows(STUDY/'materials/participant_schedule.csv')
    blocks={(r['participant_slot'],r['block']):r for r in assignment}
    for row in trials:
        assigned=blocks.get((row['participant_slot'],row['block']))
        task=by_id.get(row['task_id'])
        if not assigned or not task or assigned['condition']!=row['condition'] or assigned['task_set']!=task['task_set']:
            schedule_errors.append(row['trial_id']+': mismatched block/task-set assignment')
    check('twenty_planned_participants_four_conditions_320_trials',not schedule_errors and len(trials)==320,schedule_errors)

    questionnaire=read_json(STUDY/'survey/questionnaires.json')
    form=next(f for f in questionnaire['forms'] if f['id']=='block')
    ratings=[q for q in form['questions'] if q['type']=='rating']
    expected_fields={'interruption_1to7','control_1to7','effort_1to7','satisfaction_1to7'}
    rating_ok={q['id'] for q in ratings}==expected_fields
    for q in ratings:
        values=[o['value'] for o in q['options']]
        rating_ok=rating_ok and values==[1,2,3,4,5,6,7,'cannot_judge'] and not q['required']
    check('four_separate_optional_rating_items',rating_ok,[q['id'] for q in ratings])

    for name in ['trial_results_EMPTY_TEMPLATE.csv','block_ratings_EMPTY_TEMPLATE.csv']:
        check('empty_planned_template_'+name,len(csv_rows(STUDY/'materials'/name))==0,
              'Header-only templates must not be presented as observed data.')

    return {
        'audit':'appearance-source-v0.1',
        'passed':all(c['passed'] for c in checks),
        'checks':checks,
        'scope':'Static source assets and authored study joins; no synthetic participant records.',
        'not_verified':['Unity compilation','GUI interaction','actual rendered state','DeepSeek decisions','PICO integration','participant data quality']
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'Docs/AppearanceExperiment/Validation/source-checks.json')
    args=parser.parse_args()
    try:report=audit()
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.error(f'Cannot complete source audit: {error}')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(args.out)},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main())
