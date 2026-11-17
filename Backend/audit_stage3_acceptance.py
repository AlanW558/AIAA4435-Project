#!/usr/bin/env python3
"""Read saved Stage 3 initial/follow-up evidence without model calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
from tutor_dialogue_log import export_rows
from export_tutor_dialogue import export_file


def audit(initial, followup):
    reports = [json.loads((f/'report.json').read_text()) for f in (initial,followup)]
    checks, canonical, files = {}, [], []
    for label, folder, report in zip(('initial','followup'),(initial,followup),reports):
        run_calls=[]
        for path in sorted((folder/'logs').glob('*/*/*.jsonl')):
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            events=lambda name:[r for r in rows if r['event']==name]
            source=path.relative_to(folder).as_posix()
            if path.parent.parent.name=='comparisons':
                starts,finishes=events('provider_started'),events('provider_finished')
                checks[label+'/'+source+'/paired_calls']=Counter(r['call_id'] for r in starts)==Counter(r['call_id'] for r in finishes)
                run_calls.extend(c for r in finishes for c in r['model_calls'])
                reveals=events('first_reveal')
                checks[label+'/'+source+'/one_reveal']=len(reveals)==1
                gates=events('branch_gate_plan')
                shared=events('shared_prepared')
                checks[label+'/'+source+'/shared_input']=len(shared)==1 and len(gates)==4 and {g['shared_id'] for g in gates}=={shared[0]['prepared']['shared_id']}
                if reveals:
                    before=rows[:rows.index(reveals[0])]
                    latest={c:next(r for r in reversed(before) if r['event']=='branch_checkpoint' and r['condition']==c) for c in 'EANS'}
                    checks[label+'/'+source+'/barrier']=all(r['result']['question'] is None and all(j['status']=='completed' for j in r['result']['generation_jobs']) for r in latest.values())
                    checks[label+'/'+source+'/reveal_matches_checkpoint']=all(all(reveals[0]['snapshot']['branches'][c]['state'][k]==latest[c]['result'][k] for k in ('settings','changes','conversation')) for c in 'EANS')
            else:
                run_calls.extend(r['record'] for r in events('model_call'))
            evidence=list(export_rows(enumerate(rows,1)))
            checks[label+'/'+source+'/no_false_unity_presentation']=not any(r['kind']=='panel_presented' for r in evidence)
            answers=[r for r in evidence if r['kind']=='answer']
            checkpoints=[r for r in evidence if r['kind']=='checkpoint']
            checks[label+'/'+source+'/answers_have_commit_evidence']=all(any(c['scope']==a['scope'] and any(j['job_id']==a['job_id'] and j['text_sha256']==a['text_sha256'] for j in c.get('completed_answers',[])) for c in checkpoints) for a in answers)
            feedback=events('feedback_saved')
            checks[label+'/'+source+'/feedback_versions_exist']=all(any(r['event']=='branch_checkpoint' and r['condition']==f['condition'] and r['result']['state_revision']==f['draft']['state_revision'] for r in rows[:rows.index(f)]) for f in feedback)
            export=folder/(path.stem+'-audit-dialogue.jsonl')
            if not export.exists():export_file(path,export)
            files.append({'source':str(path),'export':str(export),'dialogue_entries':len(evidence),'synthetic_feedback_events':len(feedback)})
        checks[label+'/canonical_attempts']=len(run_calls)==report['provider_attempts']==len(report['provider_records'])
        canonical.extend(run_calls)
    checks['total_budget']=sum(r['provider_attempts'] for r in reports)==len(canonical)<=18
    checks['provider_status']=all(c['status']=='ok' for c in canonical)
    ids=[c['response_id'] for c in canonical if c.get('response_id')]
    checks['provider_responses_not_double_counted']=len(ids)==len(set(ids))==len(canonical)
    checks['original_failure_preserved']=reports[0]['passed'] is False and reports[0].get('error')=='Task-start rate restored without restoring unrelated fields'
    checks['targeted_followup_passed']=reports[1]['passed'] is True
    restored=json.loads((followup/'restored-single.json').read_text())
    checks['corrected_task_start']=restored['settings']['speech_rate']==restored['task_start_settings']['speech_rate']==1.2
    result={'scope':'Engineering evidence consistency only; initial live sequence FAILED and targeted follow-up passed. Not a full clean real-model rerun or semantic-quality score.',
            'checks':checks,'passed':all(checks.values()),'provider_attempts':len(canonical),
            'usage':{k:sum(c.get('usage',{}).get(k,0) for c in canonical) for k in ('prompt_tokens','completion_tokens','total_tokens')},
            'files':files,'response_models':sorted({c['response_model'] for c in canonical})}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('initial',type=Path);parser.add_argument('followup',type=Path)
    args=parser.parse_args();result=audit(args.initial,args.followup)
    (args.followup/'combined-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'provider_attempts':result['provider_attempts'],'usage':result['usage'],'failed_checks':[k for k,v in result['checks'].items() if not v]}))
    raise SystemExit(0 if result['passed'] else 1)
