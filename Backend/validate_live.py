#!/usr/bin/env python3
"""Bounded real-provider engineering check, never participant data or renderer proof.
Run only against an intentionally started live backend. Uses at most six attempts
observed in its own debug-session JSONL, stopping if failures exhaust the budget.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8765')
    parser.add_argument('--log-dir',default=str(ROOT/'StudyData/logs'))
    parser.add_argument('--output',default=str(ROOT/'Docs/AppearanceExperiment/engineering_backend_validation.json'))
    args=parser.parse_args()
    def call(route,data=None):
        req=urllib.request.Request(args.base_url+route,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=100) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    def mutation(view,operation,**fields):
        return call('/sessions/'+view['session_id']+'/'+operation,{'request_id':uuid.uuid4().hex,'expected_revision':view['state']['revision'],**fields})
    _,health=call('/health')
    if health.get('mode')!='live':raise RuntimeError('This check requires an explicitly started live backend.')
    tasks=json.loads((ROOT/'Assets/StreamingAssets/AppearanceStudy/tasks.json').read_text())['tasks']
    by_id={task['task_id']:task for task in tasks}
    output={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'engineering debug only; no participants and no renderer/VR validation','health':health,'provider_attempt_budget':6,'public_task_resets':[],'cases':[]}
    _,view=call('/sessions',{'participant_id':'ENGINEERING_BACKEND_CONTEXTS','phase':'debug','condition':'S'})
    for task in tasks:
        context=task['model_visible']
        status,view=mutation(view,'reset',state=context['state'],history=context['visible_history'],soft_preferences=context['soft_preferences'],task_id=task['task_id'])
        output['public_task_resets'].append({'task_id':task['task_id'],'status':status,'passed':status==200,'state':view.get('state')})
        if status!=200:raise RuntimeError('A public reset failed; see returned backend error.')
    budget_used=0
    for condition,task_id,label,minimum in [('E','A_T1','clear_execute',1),('A','A_T1','clear_confirm',1),('N','A_T1','clear_native',2),('S','A_T4','historical_reference',1),('S','B_T4','soft_preference',1)]:
        if budget_used+minimum>6:
            output['cases'].append({'label':label,'status':'skipped_budget_exhausted'});continue
        _,view=call('/sessions',{'participant_id':'ENGINEERING_BACKEND_'+condition+'_'+task_id,'phase':'debug','condition':condition})
        context=by_id[task_id]['model_visible']
        _,view=mutation(view,'reset',state=context['state'],history=context['visible_history'],soft_preferences=context['soft_preferences'],task_id=task_id)
        before=dict(view['state'])
        status,view=mutation(view,'request',query=context['initial_query'])
        record={'label':label,'condition':condition,'task_id':task_id,'session_id':view['session_id'],'request_http_status':status,'initial_decision':view['decision'],'state_after_request':view['state']}
        log=Path(args.log_dir)/'debug'/(view['session_id']+'.jsonl')
        events=[json.loads(line) for line in log.read_text().splitlines()]
        record['model_calls']=[{k:v for k,v in event.items() if k in ('role','attempt','status','requested_model','response_model','usage','duration_seconds','http_status','error','system_prompt_sha256')} for event in events if event['event']=='model_call']
        record['proposal']=next((event['proposal'] for event in events if event['event']=='proposal'),None)
        record['gate']=next(({key:event[key] for key in ('decision','reason','question')} for event in events if event['event']=='gate_decision'),None)
        budget_used+=len(record['model_calls'])
        if status==200 and view['decision']=='ASK':
            candidate=record['proposal']['default_id']
            answer_status,view=mutation(view,'answer',option_id=candidate,free_text='')
            record['answer_http_status']=answer_status
            record['state_after_answer']=view['state']
        changed=[field for field in ('jacket_color','accessory','scale') if view['state'][field]!=before[field]]
        if status==200 and changed:
            previous=dict(view['state']);field=changed[0]
            undo_status,view=mutation(view,'undo',field=field)
            record['undo']={'field':field,'http_status':undo_status,'restored_field':view['state'][field]==before[field],'preserved_other_fields':all(view['state'][f]==previous[f] for f in ('jacket_color','accessory','scale') if f!=field),'state':view['state']}
        finish_status,view=mutation(view,'finish')
        record['finish_http_status']=finish_status
        record['passed_transport_and_state']=status==200 and record.get('answer_http_status',200)==200 and finish_status==200 and record.get('undo',{}).get('restored_field',True) and record.get('undo',{}).get('preserved_other_fields',True)
        output['cases'].append(record)
        print(json.dumps({'case':label,'initial_decision':record['initial_decision'],'gate':record['gate']['reason'] if record['gate'] else None,'provider_attempts_so_far':budget_used,'passed':record['passed_transport_and_state']},ensure_ascii=False),flush=True)
    output['provider_attempts']=budget_used
    output['all_requested_cases_completed']=len([case for case in output['cases'] if case.get('passed_transport_and_state')])==5
    output['all_16_public_contexts_reset']=len(output['public_task_resets'])==16 and all(item['passed'] for item in output['public_task_resets'])
    output['limits']=['Backend API/state verification only; no renderer or headset verification.','R1/R2 proposal observations are model-dependent and are preserved even if a rule does not trigger.','No participant data, formal efficacy results or calibration claims are implied.']
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(path),'attempts':budget_used,'completed':output['all_requested_cases_completed'],'public_contexts':len(output['public_task_resets'])},ensure_ascii=False))

if __name__=='__main__':main()
