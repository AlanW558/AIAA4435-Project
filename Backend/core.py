"""Versioned appearance sessions, shared interpretation, gates, undo and JSONL audit log."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import re
import threading
import time
import uuid

from model import CAPABILITIES, ModelError, stable_json, sha

FIELDS = ("jacket_color", "accessory", "scale")
INITIAL = {"jacket_color":"blue","accessory":"none","scale":1.0}
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
MAX_REPAIRS = 2
TRIAL_LIMIT_SECONDS = 120
POLICY_VERSION = "appearance-backend-v0.1"

class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, view: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.view = status, code, message, view or {}
    def body(self):
        return {**self.view,"error":self.code,"message":self.message,"decision":"ERROR"}

def fail(code, message, status=400):
    raise APIError(status, code, message)

def text_value(value, name, max_length=2000, empty=False):
    if not isinstance(value,str) or len(value)>max_length or (not empty and not value.strip()):
        fail("invalid_"+name, f"{name} must be a {'possibly empty ' if empty else 'nonempty '}string of at most {max_length} characters.")
    return value.strip()

def patch_valid(value, full=False):
    if full and isinstance(value,dict) and "revision" in value:
        value={k:v for k,v in value.items() if k!="revision"}
    if not isinstance(value,dict) or set(value)-set(FIELDS) or (full and set(value)!=set(FIELDS)):
        fail("invalid_state", "Only jacket_color, accessory and scale are supported; a full state requires all three.")
    result = dict(value)
    for name in ("jacket_color","accessory"):
        if name in result and result[name] not in CAPABILITIES[name]:
            fail("invalid_state", f"Unsupported {name} value.")
    if "scale" in result:
        number = result["scale"]
        if isinstance(number,bool) or not isinstance(number,(float,int)) or not math.isfinite(number):
            fail("invalid_state", "Scale must be a finite number on the 0.85–1.15 grid with 0.05 increments.")
        # Unity serializes float32 values (e.g. 1.0499999523162842). Accept only
        # small representation error around a valid grid value, then canonicalize.
        nearest=round(number*20)/20
        if nearest<.85 or nearest>1.15 or abs(number-nearest)>1e-5:
            fail("invalid_state", "Scale must be on the 0.85–1.15 grid with 0.05 increments.")
        result["scale"] = round(nearest,2)
    return result

def public_history(value):
    if not isinstance(value,list) or len(value)>30:
        fail("invalid_history", "history must be a list with at most 30 public items.")
    output=[]
    for item in value:
        if isinstance(item,dict) and set(item).issubset(set(FIELDS)|{"revision"}) and all(f in item for f in FIELDS):
            item={"state":patch_valid(item,full=True)}
        if not isinstance(item,dict) or set(item)-{"query","state","before","after","patch"}:
            fail("invalid_history", "History accepts only public query/state/before/after/patch fields, not task goals or labels.")
        cleaned={}
        for key in ("state","before","after","patch"):
            if key in item:
                cleaned[key]=patch_valid(item[key],full=(key!="patch"))
        if "query" in item:
            cleaned["query"]=text_value(item["query"],"history_query",500)
        output.append(cleaned)
    return output

def public_preferences(value):
    if not isinstance(value,list) or len(value)>10:
        fail("invalid_preferences", "soft_preferences must be a list with at most 10 public items.")
    output=[]
    for item in value:
        if isinstance(item,str):
            output.append({"text":text_value(item,"preference_text",500)})
            continue
        if not isinstance(item,dict) or set(item)-{"field","value","text"} or item.get("field") not in FIELDS or "value" not in item:
            fail("invalid_preferences", "Each soft preference needs field/value and optional public text.")
        pref={"field":item["field"],"value":patch_valid({item["field"]:item["value"]})[item["field"]]}
        if "text" in item:
            pref["text"]=text_value(item["text"],"preference_text",500)
        output.append(pref)
    return output

def normalize_proposal(raw, state):
    """Deduplicate by observable result, retain default mapping, fail closed on invalid output."""
    try:
        if not isinstance(raw,dict) or type(raw.get("supported")) is not bool:
            raise ValueError()
        items=raw.get("candidates")
        if not isinstance(items,list) or len(items)>3:
            raise ValueError()
        if not raw["supported"]:
            if items:
                raise ValueError()
            return {"supported":False,"reason":str(raw.get("reason","Unsupported request"))[:500],"candidates":[],"default_id":"","unresolved_references":[],"possible_soft_preference_overrides":[],"explicit_override":False}
        if not items:
            raise ValueError()
        candidates, remap, outcomes, ids = [], {}, {}, set()
        for item in items:
            if not isinstance(item,dict) or not isinstance(item.get("id"),str) or not IDENTIFIER.fullmatch(item["id"]) or item["id"] in ids or item["id"] in ("other","cancel"):
                raise ValueError()
            ids.add(item["id"])
            patch=patch_valid(item.get("patch"))
            patch={k:v for k,v in patch.items() if state[k]!=v}
            outcome=stable_json({**state,**patch})
            if outcome in outcomes:
                remap[item["id"]]=outcomes[outcome]
                continue
            evidence=item.get("evidence","")
            if not isinstance(evidence,str):
                raise ValueError()
            candidates.append({"id":item["id"],"patch":patch,"evidence":evidence[:1000]})
            outcomes[outcome]=item["id"]
            remap[item["id"]]=item["id"]
        default_id=remap[raw["default_id"]]
        result={"supported":True,"reason":str(raw.get("reason",""))[:500],"candidates":candidates,"default_id":default_id}
        for key in ("unresolved_references","possible_soft_preference_overrides"):
            val=raw.get(key,[])
            if not isinstance(val,list) or len(val)>10 or any(not isinstance(x,str) or len(x)>1000 for x in val):
                raise ValueError()
            result[key]=val
        if type(raw.get("explicit_override",False)) is not bool:
            raise ValueError()
        result["explicit_override"]=raw.get("explicit_override",False)
        return result
    except (ValueError,KeyError,TypeError,APIError):
        raise ModelError("The model returned an invalid appearance proposal; no edit was applied.") from None

LABELS={"blue":"蓝色","orange":"橙色","green":"绿色","gray":"灰色","red":"红色","purple":"紫色","none":"无配饰","hat":"帽子","glasses":"眼镜"}
def patch_label(patch):
    labels=[]
    if "jacket_color" in patch: labels.append("外衣改为"+LABELS[patch["jacket_color"]])
    if "accessory" in patch: labels.append("配饰改为"+LABELS[patch["accessory"]])
    if "scale" in patch: labels.append("比例改为"+f'{patch["scale"]:.2f}')
    return "；".join(labels) if labels else "保持当前外形"

def common_question(proposal, context):
    options=[{"id":c["id"],"label":patch_label(c["patch"])} for c in proposal["candidates"]]
    seed=sha({"query":context["query"],"state":context["state"],"history":context["history"]})
    options.sort(key=lambda option:sha({"seed":seed,"label":option["label"]}))
    question="你希望进行哪项修改？" if len(options)>1 else "请确认是否执行这项修改："
    return {"text":question,"options":options+[{"id":"other","label":"其他／都不是（请补充）"},{"id":"cancel","label":"取消，保持当前外形"}]}

def selective_gate(proposal, state, preferences):
    candidates=proposal["candidates"]
    if not proposal["supported"]:
        return "UNRESOLVED","COMMON_UNSUPPORTED"
    if proposal["unresolved_references"]:
        return ("ASK","R1_REFERENCE") if len(candidates)>1 else ("UNRESOLVED","R1_NO_DISCRIMINATING_OPTIONS")
    may_override=any(p.get("field") in c["patch"] and c["patch"][p["field"]]!=p["value"] for p in preferences if "field" in p for c in candidates) or any("field" not in p and p.get("text") for p in preferences)
    if may_override and proposal["possible_soft_preference_overrides"] and not proposal["explicit_override"]:
        return "ASK","R2_SOFT_PREFERENCE"
    default=next(c for c in candidates if c["id"]==proposal["default_id"])
    all_fields=set().union(*(set(c["patch"]) for c in candidates))
    scales=[c["patch"].get("scale",state["scale"]) for c in candidates]
    if all_fields=={"scale"} and abs(default["patch"].get("scale",state["scale"])-state["scale"])<=.0500001 and max(scales)-min(scales)<=.0500001:
        return "ACT","SMALL_REVERSIBLE_STEP"
    if len(candidates)>1:
        outcomes=[{**state,**c["patch"]} for c in candidates]
        different_fields=len({tuple(sorted(c["patch"])) for c in candidates})>1
        categorical_difference=any(len({out[field] for out in outcomes})>1 for field in ("jacket_color","accessory"))
        if different_fields or categorical_difference or max(scales)-min(scales)>=.0999999:
            return "ASK","R3_MATERIAL_DIVERGENCE"
    return "ACT","NO_TRIGGER"

@dataclass
class Session:
    session_id: str
    participant_id: str
    condition: str
    phase: str
    state: dict = field(default_factory=lambda:{"revision":0,**INITIAL})
    history: list = field(default_factory=list)
    preferences: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    pending: dict | None = None
    idempotency: dict = field(default_factory=dict)
    task_id: str = "unassigned"
    trial_id: str = field(default_factory=lambda:uuid.uuid4().hex)
    requests: int = 0
    repairs: int = 0
    initial_clarifications: int = 0
    finished: bool = False
    commits: int = 0
    trial_started_monotonic: float | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    last: dict = field(default_factory=lambda:{"decision":"READY","message":"会话已就绪。"})

class Experiment:
    def __init__(self, model, log_dir):
        self.model=model
        self.log_dir=Path(log_dir)
        self.log_dir.mkdir(parents=True,exist_ok=True)
        self.run_id=uuid.uuid4().hex
        self.sessions={}
        self.lock=threading.Lock()

    def log(self,session,event,**payload):
        record={"timestamp_utc":datetime.now(timezone.utc).isoformat(),"monotonic_ms":time.monotonic()*1000,"run_id":self.run_id,"event":event,"session_id":session.session_id,"participant_id":session.participant_id,"condition":session.condition,"phase":session.phase,"task_id":session.task_id,"trial_id":session.trial_id,"revision":session.state["revision"],"mode":self.model.mode,"policy_version":POLICY_VERSION,**payload}
        directory=self.log_dir/session.phase
        directory.mkdir(exist_ok=True)
        with (directory/(session.session_id+".jsonl")).open("a",encoding="utf-8") as stream:
            stream.write(stable_json(record)+"\n")

    def view(self,s):
        result={"session_id":s.session_id,"state":deepcopy(s.state),"condition":s.condition,"phase":s.phase,"task_id":s.task_id,"trial_id":s.trial_id,"mode":self.model.mode,"repairs_used":s.repairs,"max_repairs":MAX_REPAIRS,"finished":s.finished,**deepcopy(s.last)}
        if s.pending:
            result["question"]=deepcopy(s.pending["question"])
        return result

    def get(self,sid):
        with self.lock: s=self.sessions.get(sid)
        if not s: fail("session_not_found","Session does not exist on this server.",404)
        return s

    def create(self,data):
        if not isinstance(data,dict) or set(data)-{"participant_id","condition","phase"}:
            fail("invalid_session","Only participant_id, condition and phase are accepted.")
        pid=text_value(data.get("participant_id"),"participant_id",48)
        if not IDENTIFIER.fullmatch(pid): fail("invalid_participant_id","Use a pseudonymous ASCII participant code, not a name or contact address.")
        condition,phase=data.get("condition"),data.get("phase","debug")
        if condition not in ("E","A","N","S") or phase not in ("debug","pilot","formal"):
            fail("invalid_session","condition must be E/A/N/S and phase debug/pilot/formal.")
        if self.model.mode=="mock" and phase!="debug": fail("mock_phase_forbidden","Mock mode only permits debug sessions; pilot/formal require live mode.")
        s=Session(uuid.uuid4().hex,pid,condition,phase)
        with self.lock: self.sessions[s.session_id]=s
        self.log(s,"session_created",state=s.state,requested_model=self.model.model)
        return self.view(s)

    def context(self,s,query):
        return {"query":query,"state":{f:s.state[f] for f in FIELDS},"history":deepcopy(s.history[-30:]),"soft_preferences":deepcopy(s.preferences),"capabilities":CAPABILITIES}

    def proposal(self,s,context):
        try:
            raw,records=self.model.propose(context)
        except ModelError as exc:
            for record in exc.records: self.log(s,"model_call",**record)
            raise
        for record in records: self.log(s,"model_call",**record)
        proposal=normalize_proposal(raw,context["state"])
        self.log(s,"proposal",public_context=context,proposal=proposal,proposal_sha256=sha(proposal))
        return proposal

    def ensure_trial_time(self,s):
        if s.trial_started_monotonic is not None and time.monotonic()-s.trial_started_monotonic>=TRIAL_LIMIT_SECONDS:
            s.pending=None
            s.last={"decision":"UNRESOLVED","message":"已达到本试次 120 秒上限；未执行迟到的修改。"}
            raise APIError(408,"trial_timeout",s.last["message"],self.view(s))

    def apply(self,s,patch,source,query=""):
        self.ensure_trial_time(s)
        before={f:s.state[f] for f in FIELDS}
        patch=patch_valid(patch)
        changed={k:v for k,v in patch.items() if before[k]!=v}
        s.state.update(changed)
        after={f:s.state[f] for f in FIELDS}
        if changed: s.changes.append({"before":before,"after":after,"remaining_fields":list(changed)})
        s.history.append({"query":query or source,"before":before,"after":after,"patch":changed})
        self.log(s,"commit",source=source,before=before,patch=changed,after=after,first_commit=s.commits==0)
        s.commits+=1
        s.last={"decision":"ACT","message":patch_label(changed)+"。"}
        s.pending=None

    def mutate(self,sid,operation,data):
        s=self.get(sid)
        if not isinstance(data,dict): fail("invalid_json","Expected a JSON object.")
        with s.lock:
            request_id=text_value(data.get("request_id"),"request_id",80)
            if not IDENTIFIER.fullmatch(request_id): fail("invalid_request_id","request_id must contain only ASCII letters, digits, underscore or hyphen.")
            signature=sha({"operation":operation,"data":data})
            if request_id in s.idempotency:
                previous=s.idempotency[request_id]
                if previous["signature"]!=signature: raise APIError(409,"request_id_conflict","This request_id was already used for different content.",self.view(s))
                result=deepcopy(previous["body"])
                if s.state["revision"]>result.get("state",{}).get("revision",-1):
                    result={**self.view(s),"idempotent_replay":True,"original_decision":previous["body"]["decision"]}
                if previous["status"]!=200: raise APIError(previous["status"],previous["body"]["error"],previous["body"]["message"],result)
                return result
            expected=data.get("expected_revision")
            if type(expected) is not int or expected!=s.state["revision"]:
                raise APIError(409,"stale_revision","State or pending question changed. Refresh the session before retrying.",self.view(s))
            if s.finished and operation!="reset": raise APIError(409,"trial_finished","Reset the next task before issuing another mutation.",self.view(s))
            started=time.monotonic()
            try:
                self._dispatch(s,operation,data)
                result=self.view(s)
                s.idempotency[request_id]={"signature":signature,"status":200,"body":deepcopy(result)}
                self.log(s,"operation_completed",operation=operation,request_id=request_id,expected_revision=expected,decision=result["decision"],duration_seconds=time.monotonic()-started,state=s.state)
                return result
            except ModelError as exc:
                s.pending=None
                s.last={"decision":"ERROR","message":str(exc)}
                error=APIError(502,"model_error",str(exc),self.view(s))
                s.idempotency[request_id]={"signature":signature,"status":502,"body":error.body()}
                self.log(s,"operation_error",operation=operation,request_id=request_id,error="model_error",duration_seconds=time.monotonic()-started)
                raise error
            except APIError as exc:
                exc.view=self.view(s)
                self.log(s,"operation_rejected",operation=operation,request_id=request_id,error=exc.code)
                raise

    def bump(self,s):
        s.state["revision"]+=1
        s.pending=None

    def _dispatch(self,s,op,data):
        allowed={"request":{"query"},"answer":{"option_id","free_text"},"undo":{"field"},"reset":{"state","history","soft_preferences","task_id"},"finish":set()}
        if op not in allowed: fail("endpoint_not_found","Unknown operation.",404)
        if set(data)-allowed[op]-{"request_id","expected_revision"}: fail("unexpected_fields","Request contains unsupported fields. Private goal/task category fields are never accepted.")
        if op=="reset":
            state=patch_valid(data.get("state"),full=True)
            history=public_history(data.get("history",[]))
            prefs=public_preferences(data.get("soft_preferences",[]))
            task=text_value(data.get("task_id","unassigned"),"task_id",80)
            if not IDENTIFIER.fullmatch(task): fail("invalid_task_id","Use an ASCII task code.")
            self.bump(s)
            s.state.update(state)
            s.history,s.preferences,s.task_id=history,prefs,task
            s.changes=[]
            s.requests=s.repairs=s.initial_clarifications=s.commits=0
            s.finished=False
            s.trial_started_monotonic=None
            s.trial_id=uuid.uuid4().hex
            s.last={"decision":"READY","message":"任务状态已重置。"}
            self.log(s,"trial_reset",state=s.state,public_history=s.history,soft_preferences=s.preferences)
            return
        if op=="finish":
            self.bump(s)
            s.finished=True
            s.last={"decision":"FINISHED","message":"当前任务已结束。"}
            self.log(s,"trial_finished",state=s.state,repair_count=s.repairs,initial_clarifications=s.initial_clarifications)
            return
        self.ensure_trial_time(s)
        if op=="undo":
            target=data.get("field","all")
            if target not in (*FIELDS,"all"): fail("invalid_undo_field","field must be all, jacket_color, accessory or scale.")
            if s.repairs>=MAX_REPAIRS: fail("repair_limit","The shared limit of two repair/undo actions has been reached.",409)
            selected=next((entry for entry in reversed(s.changes) if entry["remaining_fields"] and (target=="all" or target in entry["remaining_fields"])),None)
            if not selected: fail("nothing_to_undo","No eligible appearance change remains for this field.",409)
            fields=list(selected["remaining_fields"]) if target=="all" else [target]
            before={f:s.state[f] for f in FIELDS}
            patch={f:selected["before"][f] for f in fields}
            self.bump(s)
            s.repairs+=1
            s.state.update(patch)
            for name in fields: selected["remaining_fields"].remove(name)
            after={f:s.state[f] for f in FIELDS}
            s.history.append({"query":"undo "+target,"before":before,"after":after,"patch":patch})
            s.last={"decision":"ACT","message":"已撤销最近的"+("修改。" if target=="all" else target+"修改。")}
            self.log(s,"undo",field=target,before=before,patch=patch,after=after)
            return
        if op=="answer":
            if not s.pending: fail("no_pending_question","There is no active clarification question.",409)
            pending=deepcopy(s.pending)
            option=text_value(data.get("option_id"),"option_id",80)
            free=text_value(data.get("free_text",""),"free_text",2000,empty=True)
            ids={c["id"] for c in pending["proposal"]["candidates"]}
            if option not in ids|{"other","cancel"}: fail("invalid_option","Choose a current option, other, or cancel.")
            if option=="other" and not free: fail("free_text_required","Please describe the desired change or choose cancel.")
            self.bump(s)
            self.log(s,"clarification_answer",option_id=option,free_text=free)
            if option=="cancel":
                s.last={"decision":"UNRESOLVED","message":"已取消，外形保持不变。"}
                return
            if option in ids:
                candidate=next(c for c in pending["proposal"]["candidates"] if c["id"]==option)
                self.apply(s,candidate["patch"],"clarification_option",pending["query"])
                return
            query=pending["query"]+"\n用户补充（以此补充为准）："+free
            proposal=self.proposal(s,self.context(s,query))
            self.resolve_without_question(s,proposal,query,"clarification_free_text")
            return
        query=text_value(data.get("query"),"query")
        initial=s.requests==0
        if not initial and s.repairs>=MAX_REPAIRS: fail("repair_limit","The shared limit of two repair/undo actions has been reached.",409)
        self.bump(s)
        if initial:
            s.trial_started_monotonic=time.monotonic()
        s.requests+=1
        if not initial: s.repairs+=1
        self.log(s,"user_request",query=query,initial=initial)
        context=self.context(s,query)
        proposal=self.proposal(s,context)
        if not initial:
            self.resolve_without_question(s,proposal,query,"repair")
            return
        question=common_question(proposal,context) if proposal["supported"] else None
        if not proposal["supported"]:
            decision,reason="UNRESOLVED","COMMON_UNSUPPORTED"
        elif s.condition=="E": decision,reason="ACT","ALWAYS_EXECUTE"
        elif s.condition=="A": decision,reason="ASK","ALWAYS_ASK"
        elif s.condition=="S": decision,reason=selective_gate(proposal,context["state"],s.preferences)
        else:
            try:
                native,records=self.model.decide({**context,"proposal":proposal,"question":question})
            except ModelError as exc:
                for record in exc.records: self.log(s,"model_call",**record)
                raise
            for record in records: self.log(s,"model_call",**record)
            decision=native.get("decision")
            if decision not in ("ACT","ASK","UNRESOLVED") or not isinstance(native.get("reason",""),str):
                raise ModelError("The native gate returned an invalid decision; no edit was applied.")
            reason=native.get("reason","")[:1000]
        self.ensure_trial_time(s)
        self.log(s,"gate_decision",decision=decision,reason=reason,proposal_sha256=sha(proposal),question=question if decision=="ASK" else None)
        if decision=="ACT":
            patch=next(c["patch"] for c in proposal["candidates"] if c["id"]==proposal["default_id"])
            self.apply(s,patch,"initial",query)
        elif decision=="ASK":
            s.initial_clarifications+=1
            s.pending={"proposal":proposal,"question":question,"query":query}
            s.last={"decision":"ASK","message":"请补充一个信息后再执行。"}
        else: s.last={"decision":"UNRESOLVED","message":"当前请求无法确定可执行的修改，请补充或取消。"}

    def resolve_without_question(self,s,proposal,query,source):
        decision,reason=selective_gate(proposal,{f:s.state[f] for f in FIELDS},s.preferences)
        # Same repair resolver for every condition; no second policy clarification.
        # Multiple materially different interpretations remain unresolved rather than guessing.
        self.log(s,"shared_repair_resolution",decision=decision,reason=reason,source=source)
        if decision=="ACT":
            patch=next(c["patch"] for c in proposal["candidates"] if c["id"]==proposal["default_id"])
            self.apply(s,patch,source,query)
        else:
            s.last={"decision":"UNRESOLVED","message":"补充后仍有多种解释或不支持的修改；未改变外形。本试次不再自动提问。"}

    def event(self,sid,data):
        s=self.get(sid)
        with s.lock:
            if not isinstance(data,dict) or set(data)-{"event","payload"}: fail("invalid_event","Expected event and payload only.")
            event=data.get("event")
            payload=data.get("payload",{})
            if event not in ("render_ack","probe","client_error","trial_rating","client_marker") or not isinstance(payload,dict): fail("invalid_event","Unsupported event or payload.")
            if len(stable_json(payload))>12000: fail("event_too_large","Event payload is too large.",413)
            if event in ("render_ack","probe"):
                if set(payload)-{"revision","state","probe_index","screenshot","duration_ms","matched","message","trial_id","task_id","block","within_block","timing","kind","value","elapsed_seconds","client_build","study_session_id","build_sha256"}: fail("invalid_render_event","Render/probe payload contains unsupported fields.")
                if type(payload.get("revision")) is not int or payload["revision"]!=s.state["revision"]: raise APIError(409,"stale_render_ack","Renderer acknowledged an old revision.",self.view(s))
                actual=patch_valid(payload.get("state"),full=True)
                payload=deepcopy(payload)
                payload["server_computed_match"]=actual=={f:s.state[f] for f in FIELDS}
            self.log(s,event if event.startswith("client_") else "client_"+event,payload=payload)
            return {**self.view(s),"event_saved":True}
