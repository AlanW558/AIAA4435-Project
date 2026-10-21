#!/usr/bin/env python3
"""Export actual appearance JSONL evidence into the preserved study CSV schema.

Default: live/formal only. Missing renderer/timing/probe/build evidence stays blank.
Use --phase debug explicitly for engineering traces; never call them participant data.
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO/'Docs/AppearanceExperiment/Study'
FIELDS = ('jacket_color','accessory','scale')
COLUMNS = ('participant_id','phase','trial_id','condition','task_id','block',
    'stable_goal_success','first_commit_success','collateral_change','policy_questions',
    'repair_count','undo_count','unresolved','timeout','technical_failure','candidate_coverage',
    'elapsed_ms','service_wait_ms','probe_ms','observed_build_sha256')
ANALYSIS_REQUIRED = ('stable_goal_success','first_commit_success','collateral_change',
                     'policy_questions','repair_count','undo_count','elapsed_ms')


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def appearance(value):
    if not isinstance(value,dict) or not all(k in value for k in FIELDS):
        return None
    if not isinstance(value['jacket_color'],str) or not isinstance(value['accessory'],str) or not number(value['scale']):
        return None
    return {k:value[k] for k in FIELDS}


def equal(a,b):
    return a==b if not number(a) or not number(b) else abs(a-b)<1e-6


def same_state(a,b):
    return a is not None and b is not None and all(equal(a[k],b[k]) for k in FIELDS)


def goal_pass(state,task):
    """Evaluator-only target comparison; private targets never enter model inputs."""
    if state is None or task is None:
        return None
    hidden=task['evaluator_only'];initial=appearance(task['model_visible']['state'])
    return (all(any(equal(state[field],v) for v in values) for field,values in hidden['allowed_values'].items())
            and all(equal(state[field],initial[field]) for field in hidden['preserve_fields']))


def union_ms(intervals):
    if not intervals:return 0.0
    spans=sorted(intervals);total=0.0;left,right=spans[0]
    for a,b in spans[1:]:
        if a>right:total+=right-left;left,right=a,b
        else:right=max(right,b)
    return total+right-left


def load_logs(root):
    files=[root] if root.is_file() else sorted(root.rglob('*.jsonl'))
    if not files:raise ValueError('No JSONL logs found. Empty directories are not observed study data.')
    records=[];digests=set();sources=[]
    for path in files:
        raw=path.read_bytes();sources.append({'path':str(path.resolve()),'sha256':sha256(raw).hexdigest()})
        for line_number,line in enumerate(raw.decode('utf-8').splitlines(),1):
            if not line.strip():continue
            try:record=json.loads(line)
            except ValueError:raise ValueError(f'{path}:{line_number}: invalid JSON; preserve and repair the log explicitly.') from None
            if not isinstance(record,dict) or any(k not in record for k in ('event','session_id','trial_id','participant_id','phase','condition','mode')):
                raise ValueError(f'{path}:{line_number}: missing backend event envelope.')
            digest=sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if digest in digests:
                raise ValueError(f'Duplicate event at {path}:{line_number}; avoid importing the same log twice.')
            digests.add(digest)
            record['_source']={'path':str(path.resolve()),'line':line_number}
            records.append(record)
    return records,sources


def assess_trial(events,task,schedule):
    first=events[0];issues=[];sources={};n=len(events)
    by=lambda name:[(i,e) for i,e in enumerate(events) if e['event']==name]
    markers=[(i,e.get('payload',{})) for i,e in enumerate(events) if e['event'] in ('client_marker','client_client_marker')]
    row={key:'' for key in COLUMNS}
    row.update({k:first.get(k,'') for k in ('participant_id','phase','trial_id','condition','task_id')})
    participant=row['participant_id'];condition=row['condition'];task_id=row['task_id']
    match=schedule.get((participant,condition))
    if row['phase']=='formal':
        if not match:issues.append('No unique participant/condition in the frozen schedule.')
        else:
            row['block']=match['block'];sources['block']='frozen participant_schedule.csv'
            if task is None or task.get('task_set')!=match['task_set']:
                issues.append('Actual task does not match the frozen condition/task-set assignment.')
    marker_blocks={m['block'] for _,m in markers if type(m.get('block')) is int}
    if len(marker_blocks)>1:issues.append('Conflicting block indices in client markers.')
    elif marker_blocks:
        marker_block=next(iter(marker_blocks))
        if row['block']!='' and row['block']!=marker_block:issues.append('Client block index disagrees with the frozen schedule.')
        elif row['block']=='':row['block']=marker_block;sources['block']='client_marker'
    if task is None:issues.append('No evaluator-only task definition: goal-dependent metrics are missing.')
    resets=by('trial_reset')
    if task is not None and resets and not same_state(appearance(resets[0][1].get('state')),appearance(task['model_visible']['state'])):
        issues.append('Actual reset state differs from the task initial state.')
    completions=[(i,m) for i,m in markers if m.get('kind')=='completion']
    study_ids={m['study_session_id'] for _,m in markers if isinstance(m.get('study_session_id'),str)}
    if len(study_ids)>1:issues.append('Conflicting participant-wide study_session_id values.')
    completed=by('trial_finished');finish=completed[-1] if completed else None
    if not finish:issues.append('No trial_finished event; this observed trial is incomplete.')
    if len(completions)>1:issues.append('Multiple completion markers; earliest marker is used for elapsed time.')
    if completions:
        completion=completions[0][1]
        if number(completion.get('elapsed_seconds')) and completion['elapsed_seconds']>=0:
            row['elapsed_ms']=round(completion['elapsed_seconds']*1000,3);sources['elapsed_ms']='Unity completion marker: monotonic request-to-completion duration'
        reason=completion.get('value')
        if reason in ('participant_done','timeout') or (row['phase']=='debug' and reason=='engineering_done'):
            row['timeout']=int(reason=='timeout')
            sources['timeout']='Explicit engineering completion reason (debug only)' if reason=='engineering_done' else 'client completion reason'
    if row['elapsed_ms']=='':
        starts=[(i,e) for i,e in by('user_request') if e.get('initial') is True]
        if starts and finish:
            a,b=starts[0][1],finish[1]
            if a.get('run_id') and a.get('run_id')==b.get('run_id') and number(a.get('monotonic_ms')) and number(b.get('monotonic_ms')) and b['monotonic_ms']>=a['monotonic_ms']:
                # This excludes client network/presentation latency and may include probes.
                # Preserve it as a diagnostic, not the participant end-to-end metric.
                sources['backend_request_to_finish_ms']=round(b['monotonic_ms']-a['monotonic_ms'],3)
        issues.append('Missing client elapsed_seconds: end-to-end elapsed_ms left blank; wall clocks are not subtracted.')
    if row['timeout']=='':issues.append('Missing explicit completion reason: timeout left blank.')
    row['policy_questions']=sum(e.get('decision')=='ASK' for _,e in by('gate_decision'))
    sources['policy_questions']='Derived count of backend initial ASK decisions; not independently verified UI exposure.'
    row['repair_count']=sum(e.get('initial') is False for _,e in by('user_request'))+len(by('undo'))
    row['undo_count']=len(by('undo'));sources['repair_count']='Accepted repair user_request events plus accepted undo events'
    if finish and finish[1].get('repair_count')!=row['repair_count']:
        issues.append('trial_finished repair_count disagrees with event-derived count.')
    technical_events=by('operation_error')+by('client_error')+by('client_client_error')
    model_errors=[e for _,e in by('model_call') if e.get('status')=='error']
    render_events=by('client_render_ack');probe_events=by('client_probe')
    renderer_mismatch=any(e.get('payload',{}).get('server_computed_match') is False for _,e in render_events+probe_events)
    row['technical_failure']=int(bool(technical_events or model_errors or renderer_mismatch))
    sources['technical_failure']='Any logged operation/client/model-call error or renderer-state mismatch, including recovered API retries.'
    decisions=[e.get('decision') for _,e in by('operation_completed') if e.get('operation') not in ('reset','finish')]
    if decisions:
        row['unresolved']=int(decisions[-1] in ('UNRESOLVED','ASK')) if decisions[-1] in ('ACT','UNRESOLVED','ASK') else ''
        sources['unresolved']='Last accepted request/answer/undo decision before finish; initial unresolved repaired later is not final unresolved.'
    repairs=[i for i,e in enumerate(events) if e['event']=='undo' or (e['event']=='user_request' and e.get('initial') is False)]
    first_repair=min(repairs,default=n)
    commits=by('commit');changes=commits+by('undo');changes.sort(key=lambda x:x[0])
    pre_repair_commits=[(i,e) for i,e in commits if i<first_repair]
    if not pre_repair_commits:
        if finish:row['first_commit_success']=0;sources['first_commit_success']='No commit before repair/end; protocol defines no first commit as failure.'
    else:
        commit_i,commit=pre_repair_commits[0]
        next_change=min((i for i,_ in changes if i>commit_i),default=n)
        ack=next((e.get('payload',{}) for i,e in render_events if commit_i<i<next_change and e.get('payload',{}).get('revision')==commit.get('revision')),None)
        if ack and task is not None:
            passed=goal_pass(appearance(ack.get('state')),task)
            if passed is not None:
                row['first_commit_success']=int(passed and ack.get('server_computed_match') is True)
                sources['first_commit_success']='First pre-repair commit plus matching-revision renderer acknowledgement, evaluated against private target.'
        if row['first_commit_success']=='':issues.append('First commit lacks sufficient renderer evidence; first_commit_success left blank.')
    last_change=max((i for i,_ in changes),default=-1)
    terminal_state=appearance(finish[1].get('state')) if finish else None
    final_acks=[e.get('payload',{}) for i,e in render_events if i>last_change]
    final_ack=final_acks[-1] if final_acks else None
    probes={}
    for i,e in probe_events:
        payload=e.get('payload',{});index=payload.get('probe_index')
        if i>last_change and type(index) is int and index in (1,2,3):
            if index in probes:issues.append(f'Duplicate probe index {index}; latest actual observation retained.')
            probes[index]=payload
    if finish and task is not None and final_ack and set(probes)=={1,2,3}:
        observations=[final_ack,*[probes[k] for k in (1,2,3)]]
        valid=all(appearance(p.get('state')) is not None and type(p.get('server_computed_match')) is bool for p in observations)
        if valid:
            row['stable_goal_success']=int(all(p['server_computed_match'] and goal_pass(appearance(p['state']),task) and same_state(appearance(p['state']),terminal_state) for p in observations))
            sources['stable_goal_success']='Final renderer acknowledgement and three distinct post-change probes, all compared to actual terminal state and private target.'
    if row['stable_goal_success']=='':issues.append('Stable success requires end-state renderer acknowledgement plus three actual probes; absent evidence remains missing.')
    if set(probes)=={1,2,3} and all(number(p.get('duration_ms')) and p['duration_ms']>=0 for p in probes.values()):
        row['probe_ms']=round(sum(p['duration_ms'] for p in probes.values()),3);sources['probe_ms']='Sum of three individually measured probe durations (not wall-clock gaps).'
    else:issues.append('Individual measured probe durations missing; probe_ms left blank.')
    if task is not None:
        initial=appearance(task['model_visible']['state']);preserved=task['evaluator_only']['preserve_fields']
        actual_states=[appearance(e.get('payload',{}).get('state')) for _,e in render_events+probe_events]
        actual_states=[s for s in actual_states if s is not None]
        any_collateral=any(any(not equal(s[f],initial[f]) for f in preserved) for s in actual_states)
        every_change_acknowledged=all(any(j>i and e.get('payload',{}).get('revision')==change.get('revision') for j,e in render_events) for i,change in changes)
        if any_collateral:row['collateral_change']=1
        elif actual_states and every_change_acknowledged:row['collateral_change']=0
        else:issues.append('Cannot exclude transient collateral changes without renderer acknowledgements for all changes.')
        sources['collateral_change']='Observed renderer/probe states; 0 only if all committed/undone revisions have renderer evidence.'
    proposals=by('proposal')
    if proposals and task is not None:
        proposal=proposals[0][1].get('proposal',{});public_state=appearance(proposals[0][1].get('public_context',{}).get('state'))
        candidates=proposal.get('candidates')
        if public_state is not None and isinstance(candidates,list):
            row['candidate_coverage']=int(any(isinstance(c,dict) and isinstance(c.get('patch'),dict) and goal_pass(appearance({**public_state,**c['patch']}),task) for c in candidates))
            sources['candidate_coverage']='Evaluator-only coverage of first shared proposal outcomes, not observed human success.'
    calls=[e for _,e in by('model_call')]
    if not calls:row['service_wait_ms']=0;sources['service_wait_ms']='No model-call events recorded in this trial.'
    elif all(number(e.get('started_monotonic_ms')) and number(e.get('duration_seconds')) and e['duration_seconds']>=0 and e.get('run_id') for e in calls) and len({e['run_id'] for e in calls})==1:
        row['service_wait_ms']=round(union_ms([(e['started_monotonic_ms'],e['started_monotonic_ms']+1000*e['duration_seconds']) for e in calls]),3)
        sources['service_wait_ms']='Union of actual model-attempt intervals on one backend run clock; includes retries.'
    else:issues.append('Model-attempt monotonic intervals missing; service_wait_ms left blank.')
    build_ids=set()
    for _,m in markers:
        value=m.get('observed_build_sha256',m.get('client_build'))
        if isinstance(value,str) and re.fullmatch(r'[0-9a-fA-F]{64}',value):build_ids.add(value.lower())
    if len(build_ids)==1:row['observed_build_sha256']=next(iter(build_ids))
    elif len(build_ids)>1:issues.append('Conflicting measured build SHA-256 values.')
    else:issues.append('No actual build SHA-256 in client markers; build identifier left blank.')
    quality={'participant_id':participant,'trial_id':row['trial_id'],'backend_session_id':first['session_id'],'study_session_id':next(iter(study_ids)) if len(study_ids)==1 else None,'task_id':task_id,'phase':row['phase'],'condition':condition,'event_count':len(events),'missing_fields':[key for key,value in row.items() if value==''],'issues':issues,'metric_sources':sources,'source_events':[e['_source'] for e in events]}
    return row,quality


def export(logs,out_dir,phase,tasks_path,schedule_path):
    records,sources=load_logs(logs)
    tasks={t['task_id']:t for t in json.loads(tasks_path.read_text(encoding='utf-8'))}
    schedule={}
    with schedule_path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            key=(r['participant_slot'],r['condition'])
            if key in schedule:raise ValueError('Frozen schedule has duplicate participant/condition.')
            schedule[key]={'block':int(r['block']),'task_set':r['task_set']}
    groups=defaultdict(list);excluded=defaultdict(int)
    for r in records:
        if r['phase']!=phase:excluded['other_phase_events']+=1;continue
        if phase!='debug' and r['mode']!='live':excluded['non_live_events']+=1;continue
        groups[(r['session_id'],r['trial_id'])].append(r)
    rows=[];quality=[]
    for events in groups.values():
        if not any(e['event']=='user_request' and e.get('initial') is True for e in events):
            excluded['trials_without_initial_request']+=1;continue
        identities={(e['participant_id'],e['condition'],e['phase'],e.get('task_id')) for e in events}
        if len(identities)!=1:raise ValueError('Trial envelope changes participant/condition/phase/task within a trial.')
        row,detail=assess_trial(events,tasks.get(events[0].get('task_id')),schedule)
        rows.append(row);quality.append(detail)
    if not rows:raise ValueError(f'No observed {phase} trials with an initial request. Debug/mock runs are not formal participants.')
    rows.sort(key=lambda r:(r['participant_id'],str(r['block']),r['task_id'],r['trial_id']))
    observed_keys=[(r['participant_id'],r['task_id']) for r in rows]
    duplicates=len(observed_keys)!=len(set(observed_keys))
    out_dir.mkdir(parents=True,exist_ok=True)
    prefix='engineering_debug_' if phase=='debug' else ('pilot_' if phase=='pilot' else '')
    csv_path=out_dir/(prefix+'trial_results.csv');report_path=out_dir/(prefix+'export_report.json')
    if csv_path.exists() or report_path.exists():raise ValueError('Output files already exist; choose a new directory to preserve prior exports.')
    counts=defaultdict(lambda:defaultdict(int))
    for row in rows:counts[row['participant_id']][row['condition']]+=1
    complete_participants=all(set(c)=={'E','A','N','S'} and all(n==4 for n in c.values()) for c in counts.values())
    metrics_complete=all(all(row[k]!='' for k in ANALYSIS_REQUIRED) for row in rows)
    report={
        'exporter_version':'appearance-evidence-export-v0.1',
        'phase':phase,
        'evidence_class':'engineering_debug_not_participant_results' if phase=='debug' else 'observed_live_trials_requiring_quality_review',
        'trial_rows':len(rows),
        'participants_seen':len(counts),
        'excluded':dict(excluded),
        'duplicate_participant_task_requires_adjudication':duplicates,
        'analysis_required_fields_missing':sum(any(r[k]=='' for k in ANALYSIS_REQUIRED) for r in rows),
        'all_participants_have_four_trials_per_condition':complete_participants,
        'analysis_ready':phase=='formal' and len(counts)>=2 and not duplicates and metrics_complete and complete_participants and not any(q['issues'] for q in quality),
        'minimum_two_complete_participants_required_for_interval_analysis':True,
        'source_log_files':sources,
        'tasks_sha256':sha256(tasks_path.read_bytes()).hexdigest(),
        'schedule_sha256':sha256(schedule_path.read_bytes()).hexdigest(),
        'trials':quality,
        'limits':[
            'JSON state alone never proves displayed appearance.',
            'Missing fields remain empty; this exporter does not impute success or synthesize participant results.',
            'policy_questions counts backend ASK decisions; UI presentation requires additional exposure instrumentation.',
            'A complete four-condition participant and frozen study checks are still required before paired analysis.',
            'Private targets are used locally for offline evaluation only.'
        ]
    }
    with csv_path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS);writer.writeheader();writer.writerows(rows)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report,csv_path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--logs',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    p.add_argument('--phase',choices=('formal','pilot','debug'),default='formal')
    p.add_argument('--tasks',type=Path,default=STUDY/'materials/tasks_private.json')
    p.add_argument('--schedule',type=Path,default=STUDY/'materials/participant_schedule.csv')
    args=p.parse_args()
    try:report,path=export(args.logs,args.out_dir,args.phase,args.tasks,args.schedule)
    except (OSError,ValueError,KeyError,TypeError) as exc:p.error(str(exc))
    print(json.dumps({'csv':str(path),'phase':args.phase,'trial_rows':report['trial_rows'],'analysis_ready':report['analysis_ready'],'rows_missing_required_metrics':report['analysis_required_fields_missing']},ensure_ascii=False))


if __name__=='__main__':main()
