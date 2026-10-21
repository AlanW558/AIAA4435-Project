"""Analyze real trial CSVs with participant-level paired bootstrap intervals.

No simulated results are generated. Empty templates and duplicate trials fail.
This script implements the objective summary; block ratings and interviews are
analyzed separately as specified in protocol.md.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import json
import random
import statistics

CONDITIONS = ('E','A','N','S')
METRICS = ('stable_goal_success','first_commit_success','collateral_change',
           'policy_questions','repair_count','undo_count','elapsed_ms')
BINARY = {'stable_goal_success','first_commit_success','collateral_change'}


def percentile(xs, q):
    xs=sorted(xs);pos=(len(xs)-1)*q;i=int(pos);f=pos-i
    return xs[i]*(1-f)+xs[min(i+1,len(xs)-1)]*f


def paired_interval(values, rng, samples):
    n=len(values)
    boots=[statistics.mean(rng.choices(values,k=n)) for _ in range(samples)]
    return dict(n_participants=n,mean_difference=statistics.mean(values),
                ci95=[percentile(boots,.025),percentile(boots,.975)])


def analyze(rows, samples=10000):
    rows=[r for r in rows if r.get('phase')=='formal']
    if not rows:
        raise ValueError('No formal observed trials. Empty templates are not data.')
    ids=[(r['participant_id'],r['trial_id']) for r in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate participant/trial IDs; do not count retries as new trials.')
    by=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if r['condition'] not in CONDITIONS:
            raise ValueError('Unknown condition')
        numbers={}
        for m in METRICS:
            try:
                v=float(r[m])
            except (KeyError,ValueError):
                raise ValueError(f'Missing/invalid {m} in {r["trial_id"]}; adjudicate explicitly before analysis.') from None
            if not (0 <= v < float('inf')) or (m in BINARY and v not in (0,1)):
                raise ValueError(f'Invalid {m}: {v}')
            numbers[m]=v
        if not 1<=int(r['block'])<=4:
            raise ValueError('Block outside 1..4')
        by[r['participant_id']][r['condition']].append((r,numbers))
    complete=[];incomplete=[]
    for pid, conditions in by.items():
        cards=[r['task_id'] for c in conditions.values() for r,_ in c]
        good=(set(conditions)==set(CONDITIONS) and all(len(conditions[c])==4 for c in CONDITIONS)
              and len(set(cards))==16)
        (complete if good else incomplete).append(pid)
    if len(complete)<2:
        raise ValueError('Fewer than two complete formal participants; do not generate bootstrap effects.')
    values={p:{c:{m:statistics.mean(x[m] for _,x in by[p][c]) for m in METRICS}
               for c in CONDITIONS} for p in complete}
    conditions={c:{m:statistics.mean(values[p][c][m] for p in complete) for m in METRICS} for c in CONDITIONS}
    rng=random.Random(20261018)
    comparisons={}
    for name,a,b,metrics in [
        ('primary_S_minus_N','S','N',['stable_goal_success']),
        ('secondary_S_minus_A','S','A',['policy_questions']),
        ('secondary_S_minus_E','S','E',['first_commit_success']),
        ('descriptive_S_minus_N','S','N',['first_commit_success','policy_questions','repair_count','elapsed_ms'])]:
        comparisons[name]={m:paired_interval([values[p][a][m]-values[p][b][m] for p in complete],rng,samples) for m in metrics}
    return dict(source='observed_formal_trials_only',formal_participants_seen=len(by),
                complete_participants=len(complete),incomplete_participant_ids=sorted(incomplete),
                formal_trials_seen=len(rows),complete_case_trials=16*len(complete),bootstrap_samples=samples,
                resampling_unit='participant paired contrasts, after aggregating four trials per condition',
                metric_units={'binary':'proportion; multiply differences by 100 for percentage points',
                              'counts':'per-trial mean','elapsed_ms':'milliseconds per trial'},
                condition_means=conditions,paired_comparisons=comparisons,
                limitations=['Exploratory intervals; no power or equivalence claim.',
                             'Incomplete participants are listed; inspect missingness and add available-data sensitivity analysis.',
                             'Block ratings, task-type effects, order/item sensitivity and interviews require separate analysis.',
                             'Input metrics must be computed from actual renderer/log evidence, not fabricated or model-judged alone.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--trials',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);args=p.parse_args()
    if args.out.resolve()==args.trials.resolve():
        p.error('Output cannot overwrite the source trials.')
    with args.trials.open(newline='',encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    try:
        report=analyze(rows)
    except ValueError as e:
        p.error(str(e))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'Analyzed {report["complete_participants"]} complete participants; {report["formal_trials_seen"]} observed formal trials.')


if __name__=='__main__':
    main()
