"""Explicit JSON checkpoints for enrolled tutor runtimes; never replay provider work."""
from copy import deepcopy
from dataclasses import fields
import time
from tutor_state import TutorState
from tutor_session import TutorSession
from tutor_comparison import TutorComparison, _Branch, WorkTicket
from tutor_comparison_service import _Runtime, _BranchRuntime, _Engine, _AuditedModel
from tutor_shared_request import _Memo


def state_load(data):
    s = TutorState(data['settings'])
    s._task_start_settings = deepcopy(data['task_start_settings']); s._revision = data['revision']
    s._changes = deepcopy(data['changes']); s._conversation = deepcopy(data['conversation'])
    return s


def session_dump(s):
    return {f.name: s.state.snapshot() if f.name == 'state' else deepcopy(getattr(s, f.name)) for f in fields(s) if f.name != 'lock'}


def session_load(data):
    return TutorSession(**{**deepcopy(data), 'state': state_load(data['state'])})


def memo_dump(m):
    with m.lock: return deepcopy({'result':m.result,'error':m.error,'attempts':m.attempts})


def memo_load(data):
    m=_Memo()
    for k,v in data.items():setattr(m,k,deepcopy(v))
    return m


def comparison_dump(rt):
    with rt.lock:
        task=rt.comparison
        base={k:deepcopy(v) for k,v in vars(task).items() if k not in ('_lock','_branches','_baseline','_shared_initial')}
        base['_baseline']=task._baseline.snapshot()
        base['_branches']={c:{f.name:b.state.snapshot() if f.name=='state' else deepcopy(getattr(b,f.name)) for f in fields(b)} for c,b in task._branches.items()}
        runtime={f.name:deepcopy(getattr(rt,f.name)) for f in fields(rt) if f.name not in ('comparison','branches','lock','audit_lock','shared','engine')}
        branches={c:{f.name:session_dump(b.session) if f.name=='session' else vars(b.ticket).copy() if f.name=='ticket' and b.ticket else deepcopy(getattr(b,f.name)) for f in fields(b)} for c,b in rt.branches.items()}
        processing=rt.shared_status=='processing' or any(b.status=='processing' for b in task._branches.values())
        shared=None if processing or rt.shared is None else {'shared':memo_dump(rt.shared._shared),'gates':{c:memo_dump(m) for c,m in rt.shared._gates.items()}}
        return {'schema':'enrolled-runtime-v1','kind':'comparisons','task':base,'runtime':runtime,'branches':branches,'shared':shared,'processing':processing,
                'elapsed':time.monotonic()-rt.started_at}


def comparison_load(service, data):
    d=data['task'];task=TutorComparison(task_code=d['task_code'],domain=d['domain'],scenario=d['scenario'])
    for k,v in d.items():
        if k=='_baseline':task._baseline=state_load(v)
        elif k=='_branches':task._branches={c:_Branch(**{**deepcopy(b),'state':state_load(b['state'])}) for c,b in v.items()}
        else:setattr(task,k,deepcopy(v))
    if '_latest_reveal' not in d:
        task._latest_reveal=deepcopy(task._first_reveal)
        task._round_index=1 if task._query else 0
        task._round_query=task._query
    rt=_Runtime(task,**deepcopy(data['runtime']))
    rt.started_at=time.monotonic()-data['elapsed']
    if rt.paused_at is not None:rt.paused_at=time.monotonic()
    if rt.ended_at is not None:rt.ended_at=time.monotonic()
    writer=lambda event,**payload:service._log(rt,event,**payload)
    rt.engine=_Engine(_AuditedModel(service.model,writer),writer);rt.engine.audio_available=service.audio_available
    for c,b in data['branches'].items():
        rt.branches[c]=_BranchRuntime(**{**deepcopy(b),'session':session_load(b['session']),'ticket':WorkTicket(**b['ticket']) if b['ticket'] else None})
    if data['shared']:
        rt.shared=task.shared_initial(rt.engine.model)
        rt.shared._shared=memo_load(data['shared']['shared'])
        rt.shared._gates={c:memo_load(m) for c,m in data['shared']['gates'].items()}
    return rt
