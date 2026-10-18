import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Experiment, APIError, INITIAL, normalize_proposal, selective_gate, patch_valid
from model import MockModel, ModelError, DeepSeekModel
from server import Server


def raw(patches, **flags):
    return {"supported":True,"reason":"test","candidates":[{"id":f"c{i+1}","patch":p,"evidence":"test"} for i,p in enumerate(patches)],"default_id":"c1","unresolved_references":[],"possible_soft_preference_overrides":[],"explicit_override":False,**flags}

class FixtureModel:
    mode="live"
    model="test-double-no-paid-calls"
    def __init__(self, proposal=None, native="ACT"):
        self.raw=proposal or raw([{"jacket_color":"orange"}])
        self.native=native
        self.contexts=[]
        self.calls=[]
    def propose(self,context):
        self.contexts.append(deepcopy(context));self.calls.append("propose")
        return deepcopy(self.raw),[]
    def decide(self,context):
        self.contexts.append(deepcopy(context));self.calls.append("native")
        return {"decision":self.native,"reason":"fixture"},[]

class PolicyTests(unittest.TestCase):
    def gate(self,patches,state=None,prefs=None,**flags):
        state=state or dict(INITIAL)
        return selective_gate(normalize_proposal(raw(patches,**flags),state),state,prefs or [])
    def test_clear_large_change_acts(self):
        self.assertEqual(self.gate([{"scale":1.15}])[0],"ACT")
    def test_small_step_acts(self):
        self.assertEqual(self.gate([{"scale":1.05},{"scale":1.1}]),("ACT","SMALL_REVERSIBLE_STEP"))
    def test_material_scale_and_cross_field_differences_ask(self):
        self.assertEqual(self.gate([{"scale":.9},{"scale":1.1}])[0],"ASK")
        self.assertEqual(self.gate([{"accessory":"hat"},{"jacket_color":"orange"}])[1],"R3_MATERIAL_DIVERGENCE")
    def test_duplicate_patches_do_not_invent_ambiguity(self):
        p=normalize_proposal(raw([{"jacket_color":"orange"},{"jacket_color":"orange","scale":1.0}],default_id="c2"),dict(INITIAL))
        self.assertEqual(len(p["candidates"]),1)
        self.assertEqual(p["default_id"],"c1")
        self.assertEqual(selective_gate(p,dict(INITIAL),[])[0],"ACT")
    def test_reference_beats_small_step_but_unique_reference_does_not_ask(self):
        self.assertEqual(self.gate([{"scale":1.05},{"scale":1.1}],unresolved_references=["previous could mean two things"])[1],"R1_REFERENCE")
        self.assertEqual(self.gate([{"scale":1.05}])[0],"ACT")
        self.assertEqual(self.gate([{"scale":1.05}],unresolved_references=["no actual alternatives"])[0],"UNRESOLVED")
    def test_soft_preference_and_explicit_override_counterexample(self):
        prefs=[{"field":"accessory","value":"hat"}]
        self.assertEqual(self.gate([{"accessory":"glasses"}],prefs=prefs,possible_soft_preference_overrides=["usual hat"])[1],"R2_SOFT_PREFERENCE")
        self.assertEqual(self.gate([{"accessory":"glasses"}],prefs=prefs,possible_soft_preference_overrides=["usual hat"],explicit_override=True)[0],"ACT")
        self.assertEqual(self.gate([{"accessory":"glasses"}],possible_soft_preference_overrides=["invented"])[0],"ACT")
    def test_float32_grid_values_are_canonicalized(self):
        import struct
        for i in range(17,24):
            target=i/20
            expanded=struct.unpack("f",struct.pack("f",target))[0]
            self.assertEqual(patch_valid({"scale":expanded})["scale"],round(target,2))
        self.assertEqual(patch_valid({"scale":1.0499999523162842})["scale"],1.05)
    def test_off_grid_and_nonfinite_scale_values_remain_invalid(self):
        for value in (1.051,.97,.849,1.151,float("nan"),float("inf"),float("-inf"),True):
            with self.subTest(value=value),self.assertRaises(APIError):patch_valid({"scale":value})

    def test_malformed_proposal_fails_closed(self):
        for patches in ([{"scale":1.07}],[{"eye_color":"blue"}],[{"scale":True}]):
            with self.assertRaises(ModelError): normalize_proposal(raw(patches),dict(INITIAL))

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.model=FixtureModel()
        self.app=Experiment(self.model,self.temp.name)
        self.i=0
    def tearDown(self): self.temp.cleanup()
    def create(self,condition="S"):
        return self.app.create({"participant_id":"ENGINEERING","condition":condition,"phase":"debug"})
    def mutate(self,view,op,**fields):
        self.i+=1
        return self.app.mutate(view["session_id"],op,{"request_id":f"r{self.i}","expected_revision":view["state"]["revision"],**fields})
    def logs(self,view):
        p=Path(self.temp.name)/"debug"/(view["session_id"]+".jsonl")
        return [json.loads(line) for line in p.read_text().splitlines()]
    def test_four_gates_share_proposer_and_question(self):
        self.model.raw=raw([{"jacket_color":"orange"},{"accessory":"hat"}]);self.model.native="ASK"
        outputs=[]
        for c in "EANS": outputs.append(self.mutate(self.create(c),"request",query="换个风格"))
        self.assertEqual([o["decision"] for o in outputs],["ACT","ASK","ASK","ASK"])
        self.assertEqual(outputs[1]["question"],outputs[2]["question"])
        self.assertEqual(outputs[2]["question"],outputs[3]["question"])
        proposer_contexts=[c for c in self.model.contexts if "proposal" not in c]
        self.assertTrue(all(c==proposer_contexts[0] for c in proposer_contexts))
        self.assertEqual(self.model.calls.count("native"),1)
    def test_state_isolation_and_partial_undo_preserves_newer_field(self):
        v=self.mutate(self.create("E"),"request",query="orange")
        self.model.raw=raw([{"accessory":"glasses"}])
        v=self.mutate(v,"request",query="glasses")
        v=self.mutate(v,"undo",field="jacket_color")
        self.assertEqual(v["state"]["jacket_color"],"blue")
        self.assertEqual(v["state"]["accessory"],"glasses")
        self.assertEqual(self.create()["state"],{"revision":0,**INITIAL})
        commits=[e for e in self.logs(v) if e["event"]=="commit"]
        self.assertEqual([e["first_commit"] for e in commits],[True,False])
    def test_idempotent_success_and_conflicting_id(self):
        v=self.create("E");d={"request_id":"once","expected_revision":0,"query":"orange"}
        a=self.app.mutate(v["session_id"],"request",d)
        b=self.app.mutate(v["session_id"],"request",d)
        self.assertEqual(a,b);self.assertEqual(len(self.model.calls),1)
        with self.assertRaises(APIError) as exc:self.app.mutate(v["session_id"],"request",{**d,"query":"different"})
        self.assertEqual(exc.exception.code,"request_id_conflict")
    def test_old_idempotent_replay_returns_current_renderer_state(self):
        v=self.create("E");data={"request_id":"once","expected_revision":0,"query":"orange"}
        v=self.app.mutate(v["session_id"],"request",data)
        v=self.mutate(v,"reset",state={**INITIAL,"jacket_color":"purple"})
        replay=self.app.mutate(v["session_id"],"request",data)
        self.assertEqual(replay["state"],v["state"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(len(self.model.calls),1)

    def test_old_answer_cannot_overwrite_new_reset_or_question(self):
        v=self.mutate(self.create("A"),"request",query="orange");old=deepcopy(v)
        self.assertEqual(v["state"]["revision"],1)
        v=self.mutate(v,"reset",state={**INITIAL,"jacket_color":"green"},task_id="NEXT")
        with self.assertRaises(APIError) as exc:self.mutate(old,"answer",option_id="c1")
        self.assertEqual(exc.exception.code,"stale_revision")
        self.assertEqual(self.app.get(v["session_id"]).state["jacket_color"],"green")
    def test_cancel_none_of_options_and_one_clarification_limit(self):
        v=self.mutate(self.create("A"),"request",query="orange")
        v=self.mutate(v,"answer",option_id="cancel")
        self.assertEqual(v["decision"],"UNRESOLVED");self.assertEqual(v["state"]["jacket_color"],"blue")
        v=self.mutate(v,"request",query="orange")
        self.assertEqual(v["decision"],"ACT")
        w=self.mutate(self.create("A"),"request",query="orange")
        self.model.raw=raw([{"jacket_color":"green"}])
        w=self.mutate(w,"answer",option_id="other",free_text="green instead")
        self.assertEqual(w["decision"],"ACT");self.assertEqual(w["state"]["jacket_color"],"green")
        self.assertEqual(self.app.get(w["session_id"]).initial_clarifications,1)
    def test_private_goals_rejected_and_public_context_omits_identifiers(self):
        v=self.create()
        with self.assertRaises(APIError):self.mutate(v,"request",query="orange",evaluator_only={"goal":"orange"})
        v=self.mutate(v,"reset",state={"revision":0,**INITIAL},task_id="SECRET_LABEL",history=[dict(INITIAL)],soft_preferences=["通常保留帽子。"])
        v=self.mutate(v,"request",query="orange")
        context=self.model.contexts[-1]
        self.assertNotIn("SECRET_LABEL",json.dumps(context))
        self.assertNotIn("ENGINEERING",json.dumps(context))
        self.assertNotIn("condition",context)
        self.assertNotIn("revision",context["state"])
    def test_unsupported_preserves_state_for_every_condition(self):
        self.model.raw={"supported":False,"reason":"unsupported","candidates":[],"default_id":""}
        for condition in "EANS":
            v=self.mutate(self.create(condition),"request",query="change weather")
            self.assertEqual(v["decision"],"UNRESOLVED")
            self.assertEqual({k:v["state"][k] for k in INITIAL},INITIAL)
        self.assertNotIn("native",self.model.calls)
    def test_model_failure_does_not_silently_mock_or_repeat_billing(self):
        def broken(context): self.model.calls.append("failed");raise ModelError("Provider failed",[{"status":"error"}])
        self.model.propose=broken;v=self.create()
        data={"request_id":"failed","expected_revision":0,"query":"orange"}
        for _ in range(2):
            with self.assertRaises(APIError) as exc:self.app.mutate(v["session_id"],"request",data)
            self.assertEqual(exc.exception.status,502)
        self.assertEqual(self.model.calls,["failed"])
        self.assertEqual(self.app.get(v["session_id"]).state["jacket_color"],"blue")
    def test_concurrent_same_revision_only_one_commits(self):
        v=self.create("E")
        def call(i):
            try:return self.app.mutate(v["session_id"],"request",{"request_id":f"parallel{i}","expected_revision":0,"query":"orange"})["decision"]
            except APIError as exc:return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(call,range(2)))
        self.assertCountEqual(results,["ACT","stale_revision"])
    def test_events_validate_actual_state_without_mutation(self):
        v=self.mutate(self.create(),"request",query="orange")
        r=self.app.event(v["session_id"],{"event":"render_ack","payload":{"revision":1,"state":dict(INITIAL)}})
        self.assertEqual(r["state"],v["state"])
        self.assertFalse(self.logs(v)[-1]["payload"]["server_computed_match"])
        with self.assertRaises(APIError):self.app.event(v["session_id"],{"event":"probe","payload":{"revision":0,"state":dict(INITIAL)}})
    def test_trial_deadline_rejects_late_edit_and_allows_finish(self):
        import time
        v=self.mutate(self.create("E"),"request",query="orange")
        session=self.app.get(v["session_id"])
        session.trial_started_monotonic=time.monotonic()-121
        with self.assertRaises(APIError) as exc:self.mutate(v,"request",query="green")
        self.assertEqual(exc.exception.code,"trial_timeout")
        self.assertEqual(session.state["jacket_color"],"orange")
        v=self.mutate(v,"finish")
        self.assertTrue(v["finished"])
    def test_provider_result_arriving_after_deadline_cannot_commit(self):
        import time
        v=self.create("E")
        def late(context):
            self.app.get(v["session_id"]).trial_started_monotonic=time.monotonic()-121
            return raw([{"jacket_color":"orange"}]),[]
        self.model.propose=late
        with self.assertRaises(APIError) as exc:self.mutate(v,"request",query="orange")
        self.assertEqual(exc.exception.code,"trial_timeout")
        self.assertEqual(self.app.get(v["session_id"]).state["jacket_color"],"blue")

    def test_finish_requires_next_reset_and_mock_cannot_collect_formal(self):
        v=self.mutate(self.create(),"finish")
        with self.assertRaises(APIError):self.mutate(v,"request",query="orange")
        v=self.mutate(v,"reset",state=INITIAL)
        self.assertFalse(v["finished"])
        with self.assertRaises(APIError):Experiment(MockModel(),self.temp.name).create({"participant_id":"P001","condition":"E","phase":"formal"})

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=Server(("127.0.0.1",0),Experiment(MockModel(),self.temp.name))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_address[1]}"
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def req(self,path,data=None):
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(request) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    def test_health_full_roundtrip_and_structured_errors(self):
        code,health=self.req("/health");self.assertEqual(code,200);self.assertEqual(health["mode"],"mock")
        _,v=self.req("/sessions",{"participant_id":"ENGINEERING","condition":"A"})
        sid=v["session_id"]
        _,v=self.req(f"/sessions/{sid}/request",{"request_id":"r1","expected_revision":0,"query":"orange"})
        self.assertEqual(v["decision"],"ASK")
        _,v=self.req(f"/sessions/{sid}/answer",{"request_id":"r2","expected_revision":1,"option_id":"c1"})
        self.assertEqual(v["state"]["jacket_color"],"orange")
        _,v=self.req(f"/sessions/{sid}/undo",{"request_id":"r3","expected_revision":2,"field":"all"})
        self.assertEqual(v["state"]["jacket_color"],"blue")
        code,v=self.req(f"/sessions/{sid}/request",{"request_id":"r4","expected_revision":0,"query":"blue"})
        self.assertEqual(code,409);self.assertEqual(v["error"],"stale_revision")
        self.assertEqual(self.req("/nope")[0],404)

if __name__=="__main__":unittest.main()
