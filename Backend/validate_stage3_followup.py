#!/usr/bin/env python3
"""One bounded follow-up after a saved Stage 3 task-start restoration failure.

Reconstructs that run's public pre-failure state, not its task IDs or study data.
Shares the original 18-attempt total budget. Never reruns the paid prefix.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from core import APIError
from model import ModelError
from tutor_state import TutorState
from tutor_session import TutorSessions
from tutor_dialogue_log import export_rows
from export_tutor_dialogue import export_file
from validate_stage3_acceptance import Acceptance, BoundedModel, load_environment, RESTORE_RATE, INVALID, AMBIGUOUS


def reconstruct(baseline, target):
    state = TutorState(baseline['settings'])
    events = [(r['id'], 'change', r) for r in target['changes']] + [(r['id'], 'exchange', r) for r in target['conversation']]
    for _, kind, item in sorted(events):
        rev = state.snapshot()['revision']
        if kind == 'change':
            if item['kind'] != 'commit': raise ValueError('This bounded follow-up only reconstructs the saved pre-undo prefix')
            state.commit(item['patch'], expected_revision=rev, source=item['source'], query=item['query'])
        else:
            messages = item['messages']
            state.record_exchange(messages[0]['content'], messages[1]['content'], expected_revision=rev, generation_settings=item['settings'])
    for field in ('settings', 'changes', 'conversation', 'revision'):
        if state.snapshot()[field] != target[field]: raise ValueError('Public prefix reconstruction differs: ' + field)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prior', type=Path)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if not args.live: parser.error('--live is required; uses only the prior run remaining budget')
    prior = json.loads((args.prior / 'report.json').read_text())
    if prior['mode'] != 'live' or prior.get('error') != 'Task-start rate restored without restoring unrelated fields':
        parser.error('Expected the saved initial task-start failure report')
    remaining = 18 - prior['provider_attempts']
    if remaining < 4: parser.error('Fewer than four attempts remain; do not exceed the declared budget')
    baseline = json.loads((args.prior/'01-hidden.json').read_text())['baseline']
    source = json.loads((args.prior/'04-one-answer-and-followup.json').read_text())['branches']['E']['result']['state']
    state = reconstruct(baseline, source)
    root = Path(__file__).resolve().parents[1]
    load_environment(root/'.env')
    model = BoundedModel(limit=remaining)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = root/'StudyData/macos/stage3-acceptance/live-followup'/stamp
    # Reserve remaining attempts once, even if this process is interrupted.
    with (args.prior/'followup-reservation.json').open('x') as stream:
        json.dump({'output':str(output), 'remaining_attempt_limit':remaining},stream)
    run = Acceptance(model, output)
    run.report['scope'] = 'Targeted headless follow-up after a preserved failed live run. Public pre-failure state reconstructed exactly; no task/process resume or new participant evidence. No audio/STT/Unity presentation.'
    run.report['prior_run'] = str(args.prior.resolve())
    run.report['prior_attempts'] = prior['provider_attempts']
    singles = TutorSessions(model, output/'logs')
    v = singles.create({'participant_id':'STAGE3FOLLOWUP','condition':'E','settings':baseline['settings']})
    session = singles.get(v['session_id']); session.state = state
    singles.log(session,'engineering_seeded_state', source_run=str(args.prior.resolve()), snapshot=state.snapshot())
    run.report['seed_session_id'] = v['session_id']
    def change(op, **payload):
        current = singles.view(session)
        return singles.mutate(session.session_id, op, {'request_id':'followup_'+str(current['revision'])+'_'+op, 'expected_revision':current['revision'], **payload})
    try:
        expected = {**source['settings'], 'speech_rate':1.2}
        v = change('request',query=RESTORE_RATE)
        run.check(v['settings'] == expected, 'Real model restores explicit public task-start 1.20 instead of default 1.00')
        (output/'restored-single.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
        v = change('undo',field='speech_rate')
        run.check(v['settings'] == source['settings'], 'Scoped undo restores pre-request rate and preserves other state')
        v = change('request',query=INVALID)
        run.check(v['decision']=='UNRESOLVED' and v['settings']==source['settings'], 'Real unsupported joint request does not partially change Voice')
        (output/'unsupported-single.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
        path = singles.log_dir/(session.session_id+'.jsonl')
        export_file(path,output/'single-dialogue.jsonl')
        run.create('STAGE3-ALTERNATIVES-FOLLOWUP', {'speech_rate':1.2,'tone':'friendly','voice':'voice_a'})
        run.command('start',query=AMBIGUOUS); current=run.settle()
        run.check(current['branches']['S']['status']=='awaiting_clarification','Real Selective requests clarification for competing interpretations')
        run.snapshot('alternatives-hidden')
        current=run.reveal(divergent=True)
        run.check(run.settings('A')!=run.settings('S'),'Different real clarification selections remain independent')
        for c in 'EANS':
            run.check(all(run.settings(c)[f]==run.baseline['settings'][f] for f in ('voice','reply_length','avatar_id','outfit','jacket_color','accessory','scale')), 'Real alternatives preserve non-target fields '+c)
        run.command('close')
        run.snapshot('alternatives-aborted')
        path2=run.app.log_dir/(run.task_id+'.jsonl')
        records=[json.loads(line) for line in path2.read_text().splitlines()]
        reveals=[r for r in records if r['event']=='first_reveal']
        run.check(len(reveals)==1 and reveals[0]['snapshot']==run.first,'Saved reveal is immutable actual revealed snapshot')
        gates=[r for r in records if r['event']=='branch_gate_plan']
        run.check(len(gates)==4 and len({r['shared_id'] for r in gates})==1,'Follow-up four strategies use one shared interpretation')
        export_file(path2,output/'comparison-dialogue.jsonl')
        run.check(model.attempts+prior['provider_attempts']<=18,'Original plus repair stay within 18 provider attempts')
        run.report['passed']=True
    except (AssertionError,APIError,ModelError,TimeoutError,KeyError,IndexError) as exc:
        run.report['passed']=False;run.report['error']=str(exc)
        if run.task_id: run.snapshot('failure-state')
    finally:
        run.app.shutdown()
        run.report['provider_records']=deepcopy(model.records)
        run.report['total_attempts_including_prior']=prior['provider_attempts']+model.attempts
        run.report['usage']={k:sum(r.get('usage',{}).get(k,0) for r in model.records) for k in ('prompt_tokens','completion_tokens','total_tokens')}
        run.save()
    print(json.dumps({'passed':run.report['passed'],'checks':len(run.report['checks']),'provider_attempts':model.attempts,'total_attempts':run.report['total_attempts_including_prior'],'error':run.report.get('error'),'folder':str(output)}),flush=True)
    return 0 if run.report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
