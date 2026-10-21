"""The optional avatar demo must not widen the frozen study contract."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capabilities import AVATAR_DEFAULTS, DEMO_PROFILE, STUDY_PROFILE
from core import APIError, Experiment, normalize_proposal, patch_valid, selective_gate
from model import DeepSeekModel, DEMO_PROPOSER_PROMPT, MockModel, ModelError, PROPOSER_PROMPT
import test_backend
from test_backend import FixtureModel, raw


class AvatarDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.model=FixtureModel()
        self.app=Experiment(self.model,self.temp.name)
        self.i=0

    def tearDown(self):
        self.temp.cleanup()

    def create(self,profile="avatar-demo-v1",condition="S",phase="debug"):
        return self.app.create({"participant_id":"ENGINEERING","condition":condition,
                                "phase":phase,"capability_profile":profile})

    def mutate(self,view,op,**fields):
        self.i+=1
        return self.app.mutate(view["session_id"],op,{
            "request_id":f"r{self.i}","expected_revision":view["state"]["revision"],**fields})

    def state(self,view):
        return {key:value for key,value in view["state"].items() if key!="revision"}

    def reset(self,view,avatar="liang",**fields):
        return self.mutate(view,"reset",state={**AVATAR_DEFAULTS[avatar],**fields})

    def test_default_study_contract_and_demo_default_are_separate(self):
        study=self.app.create({"participant_id":"ENGINEERING","condition":"S","phase":"debug"})
        self.assertEqual(self.state(study),STUDY_PROFILE.initial)
        self.assertEqual((study["capability_profile"],study["max_repairs"],study["trial_limit_seconds"]),
                         ("study-v1",2,120))
        demo=self.create()
        self.assertEqual(self.state(demo),AVATAR_DEFAULTS["liang"])
        self.assertEqual((demo["capability_profile"],demo["max_repairs"],demo["trial_limit_seconds"]),
                         ("avatar-demo-v1",12,600))
        for value in ({"avatar_id":"liang"},{"outfit":"sport"},{"jacket_color":"yellow"}):
            with self.subTest(value=value),self.assertRaises(APIError):
                patch_valid(value)

    def test_demo_rejected_in_pilot_formal_and_unknown_profiles_fail(self):
        for phase in ("pilot","formal"):
            with self.subTest(phase=phase),self.assertRaises(APIError) as caught:
                self.create(phase=phase)
            self.assertEqual(caught.exception.code,"demo_phase_forbidden")
        for value in ("",None,"avatar-demo-v2",[],{}):
            with self.subTest(profile=value),self.assertRaises(APIError) as caught:
                self.create(profile=value)
            self.assertEqual(caught.exception.code,"invalid_capability_profile")

    def test_reset_history_and_preferences_use_full_demo_contract(self):
        v=self.create()
        with self.assertRaises(APIError):
            self.mutate(v,"reset",state=STUDY_PROFILE.initial)
        with self.assertRaises(APIError):
            self.mutate(v,"reset",state=AVATAR_DEFAULTS["liang"],history=[STUDY_PROFILE.initial])
        v=self.mutate(v,"reset",state=AVATAR_DEFAULTS["liang"],
                      history=[AVATAR_DEFAULTS["nailong"]],
                      soft_preferences=[{"field":"outfit","value":"suit"}])
        context=self.app.context(self.app.get(v["session_id"]),"改成红色")
        self.assertEqual(context["capability_profile"],"avatar-demo-v1")
        self.assertEqual(context["history"][0]["state"],AVATAR_DEFAULTS["nailong"])
        self.assertEqual(set(context["state"]),set(DEMO_PROFILE.fields))
        self.assertEqual(context["capabilities"],DEMO_PROFILE.capabilities)
        for private in ("ENGINEERING","participant_id","condition","trial_id","revision"):
            self.assertNotIn(private,json.dumps(context))

    def test_replacement_defaults_are_atomic_and_undo_restores_all_fields(self):
        before={**AVATAR_DEFAULTS["liang"],"outfit":"sport","jacket_color":"purple",
                "accessory":"hat","scale":1.1}
        v=self.mutate(self.create(),"reset",state=before)
        self.model.raw=raw([{"avatar_id":"nailong"}])
        v=self.mutate(v,"request",query="把整个形象换成奶龙")
        self.assertEqual(v["decision"],"ACT")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["nailong"])
        self.assertEqual(len(self.app.get(v["session_id"]).changes),1)
        v=self.mutate(v,"undo",field="all")
        self.assertEqual(self.state(v),before)

    def test_explicit_preservation_overrides_replacement_defaults(self):
        v=self.reset(self.create(),jacket_color="purple",accessory="glasses",scale=1.1)
        self.model.raw=raw([{"avatar_id":"nailong","jacket_color":"purple",
                            "accessory":"glasses","scale":1.1}])
        v=self.mutate(v,"request",query="换成奶蛙，但保留颜色、眼镜和大小")
        self.assertEqual(self.state(v),{**AVATAR_DEFAULTS["nailong"],
                                       "jacket_color":"purple","accessory":"glasses","scale":1.1})

    def test_replacing_same_avatar_still_applies_replacement_defaults(self):
        v=self.reset(self.create(),avatar="nailong",jacket_color="red",scale=1.1)
        self.model.raw=raw([{"avatar_id":"nailong"}])
        v=self.mutate(v,"request",query="全部替换成默认奶龙")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["nailong"])

    def test_plain_color_cannot_change_avatar_even_if_model_proposes_it(self):
        v=self.create()
        self.model.raw=raw([{"avatar_id":"nailong"}])
        with self.assertRaises(APIError) as caught:
            self.mutate(v,"request",query="把颜色改成黄色")
        self.assertEqual(caught.exception.code,"model_error")
        self.assertEqual(self.state(self.app.view(self.app.get(v["session_id"]))),AVATAR_DEFAULTS["liang"])
        self.assertEqual(self.app.get(v["session_id"]).commits,0)

    def test_outfit_ambiguity_and_later_demo_request_use_selective_clarification(self):
        v=self.mutate(self.create(),"request",query="改成橙色")
        self.model.raw=raw([{"outfit":"sport"},{"outfit":"none"}])
        v=self.mutate(v,"request",query="换件衣服")
        self.assertEqual(v["decision"],"ASK")
        self.assertEqual(v["state"]["outfit"],"suit")
        labels=[item["label"] for item in v["question"]["options"]]
        self.assertIn("服装改为运动装",labels)
        v=self.mutate(v,"answer",option_id="c1")
        self.assertEqual(v["state"]["outfit"],"sport")
        v=self.mutate(v,"undo",field="outfit")
        self.assertEqual((v["state"]["outfit"],v["state"]["jacket_color"]),("suit","orange"))

    def test_character_ambiguity_cancel_and_clarification_cannot_mutate_early(self):
        self.model.raw=raw([{"avatar_id":"liang"},{"avatar_id":"nailong"}])
        v=self.mutate(self.create(),"request",query="换个角色")
        self.assertEqual(v["decision"],"ASK")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["liang"])
        old=deepcopy(v)
        v=self.mutate(v,"answer",option_id="cancel")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["liang"])
        with self.assertRaises(APIError) as caught:
            self.mutate(old,"answer",option_id="c2")
        self.assertEqual(caught.exception.code,"stale_revision")

    def test_invalid_outfit_or_partial_undo_never_changes_other_fields(self):
        self.model.raw=raw([{"avatar_id":"nailong","outfit":"suit"}])
        v=self.create()
        with self.assertRaises(APIError) as caught:
            self.mutate(v,"request",query="换成穿西装的奶龙")
        self.assertEqual(caught.exception.code,"model_error")
        v=self.app.view(self.app.get(v["session_id"]))
        self.model.raw=raw([{"avatar_id":"nailong"}])
        v=self.mutate(v,"request",query="换成奶龙")
        before=deepcopy(v)
        with self.assertRaises(APIError) as caught:
            self.mutate(v,"undo",field="outfit")
        self.assertEqual(caught.exception.code,"invalid_undo_combination")
        after=self.app.view(self.app.get(v["session_id"]))
        self.assertEqual(after["state"],before["state"])
        self.assertEqual(after["repairs_used"],before["repairs_used"])
        v=self.mutate(after,"undo",field="all")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["liang"])

    def test_whole_and_partial_undo_are_idempotent_and_preserve_later_edits(self):
        self.model.raw=raw([{"avatar_id":"nailong"}])
        v=self.mutate(self.create(),"request",query="全部换掉")
        self.model.raw=raw([{"jacket_color":"green"}])
        v=self.mutate(v,"request",query="颜色改成绿色")
        partial={"request_id":"undo-avatar","expected_revision":v["state"]["revision"],"field":"avatar_id"}
        v=self.app.mutate(v["session_id"],"undo",partial)
        self.assertEqual((v["state"]["avatar_id"],v["state"]["outfit"],v["state"]["jacket_color"]),
                         ("liang","none","green"))
        replay=self.app.mutate(v["session_id"],"undo",partial)
        self.assertEqual(replay,v)
        whole={"request_id":"undo-whole","expected_revision":v["state"]["revision"],"field":"all"}
        v=self.app.mutate(v["session_id"],"undo",whole)
        self.assertEqual(v["state"]["jacket_color"],"yellow")
        replay=self.app.mutate(v["session_id"],"undo",whole)
        self.assertEqual(replay,v)
        old_replay=self.app.mutate(v["session_id"],"undo",partial)
        self.assertEqual(old_replay["state"],v["state"])
        self.assertTrue(old_replay["idempotent_replay"])
        v=self.mutate(v,"undo",field="all")
        self.assertEqual(self.state(v),AVATAR_DEFAULTS["liang"])

    def test_demo_repairs_and_duration_do_not_expand_formal_limits(self):
        v=self.create()
        for i in range(13):
            self.model.raw=raw([{"jacket_color":"orange" if i%2==0 else "blue"}])
            v=self.mutate(v,"request",query="换颜色")
        self.assertEqual(v["repairs_used"],12)
        with self.assertRaises(APIError) as caught:
            self.mutate(v,"request",query="再改颜色")
        self.assertEqual(caught.exception.code,"repair_limit")
        v=self.create()
        session=self.app.get(v["session_id"])
        session.trial_started_monotonic=time.monotonic()-121
        self.app.ensure_trial_time(session)
        session.trial_started_monotonic=time.monotonic()-601
        with self.assertRaises(APIError) as caught:
            self.app.ensure_trial_time(session)
        self.assertEqual(caught.exception.code,"trial_timeout")
        study=self.create(profile="study-v1")
        self.assertEqual((study["max_repairs"],study["trial_limit_seconds"]),(2,120))

    def test_render_ack_requires_all_five_fields_and_compares_identity_outfit(self):
        v=self.create()
        for actual in (STUDY_PROFILE.initial,{**AVATAR_DEFAULTS["nailong"],"outfit":"sport"}):
            with self.subTest(actual=actual),self.assertRaises(APIError):
                self.app.event(v["session_id"],{"event":"render_ack","payload":{"revision":0,"state":actual}})
        for actual in (AVATAR_DEFAULTS["liang"],{**AVATAR_DEFAULTS["liang"],"outfit":"sport"},AVATAR_DEFAULTS["nailong"]):
            self.app.event(v["session_id"],{"event":"render_ack","payload":{"revision":0,"state":actual}})
        lines=(Path(self.temp.name)/"debug"/(v["session_id"]+".jsonl")).read_text().splitlines()
        matches=[json.loads(line)["payload"]["server_computed_match"] for line in lines if json.loads(line)["event"]=="client_render_ack"]
        self.assertEqual(matches,[True,False,False])

    def test_demo_scale_and_unknown_fields_still_fail_closed(self):
        for bad in ({"scale":1.2},{"scale":.97},{"scale":True},{"hair_color":"pink"}):
            with self.subTest(bad=bad),self.assertRaises(ModelError):
                normalize_proposal(raw([bad]),dict(AVATAR_DEFAULTS["liang"]),DEMO_PROFILE,"换个形象")


class DemoMockAndPromptTests(unittest.TestCase):
    def interpret(self,query,state=None):
        state=state or AVATAR_DEFAULTS["liang"]
        context={"query":query,"state":dict(state),"history":[],"soft_preferences":[],
                 "capabilities":DEMO_PROFILE.capabilities,"capability_profile":"avatar-demo-v1"}
        proposal,_=MockModel().propose(context)
        normalized=normalize_proposal(proposal,context["state"],DEMO_PROFILE,query)
        return normalized,{**state,**normalized["candidates"][0]["patch"]} if normalized["supported"] else dict(state)

    def test_all_nailong_aliases_and_whole_replacement_have_one_default_outcome(self):
        for query in ("换成奶龙","换成奶蛙","换成奶娃","全部替换","全部换掉","整个换掉","全都换掉","replace everything"):
            with self.subTest(query=query):
                proposal,state=self.interpret(query)
                self.assertEqual(len(proposal["candidates"]),1)
                self.assertEqual(state,AVATAR_DEFAULTS["nailong"])

    def test_mock_outfit_color_size_and_preservation_do_not_revert_identity(self):
        _,state=self.interpret("换成运动装，颜色改成红色，比例1.10")
        self.assertEqual(state,{**AVATAR_DEFAULTS["liang"],"outfit":"sport","jacket_color":"red","scale":1.1})
        _,state=self.interpret("换成奶娃，但保留颜色、眼镜和大小",state)
        self.assertEqual(state,{**AVATAR_DEFAULTS["nailong"],"jacket_color":"red","accessory":"glasses","scale":1.1})
        _,state=self.interpret("颜色改成绿色",state)
        self.assertEqual((state["avatar_id"],state["outfit"],state["jacket_color"]),("nailong","none","green"))

    def test_mock_invalid_combination_unresolved(self):
        proposal,state=self.interpret("换成穿西装的奶龙")
        self.assertFalse(proposal["supported"])
        self.assertEqual(state,AVATAR_DEFAULTS["liang"])

    def test_clear_replacement_authorizes_default_changes_over_soft_preferences(self):
        context={"query":"全部换掉","state":dict(AVATAR_DEFAULTS["liang"]),"history":[],
                 "soft_preferences":[{"field":"accessory","value":"glasses"}],
                 "capabilities":DEMO_PROFILE.capabilities,"capability_profile":"avatar-demo-v1"}
        proposal,_=MockModel().propose(context)
        proposal=normalize_proposal(proposal,context["state"],DEMO_PROFILE,context["query"])
        self.assertEqual(selective_gate(proposal,context["state"],context["soft_preferences"],DEMO_PROFILE)[0],"ACT")

    def test_deepseek_prompt_is_selected_by_public_capability_profile(self):
        with patch.dict(os.environ,{"DEEPSEEK_API_KEY":"unit-test-not-a-credential"}):
            model=DeepSeekModel("test-model")
        with patch.object(model,"_call",return_value=({},[])) as call:
            model.propose({"query":"颜色","state":STUDY_PROFILE.initial})
            self.assertEqual(call.call_args.args[1],PROPOSER_PROMPT)
            model.propose({"query":"换成奶龙","state":AVATAR_DEFAULTS["liang"],"capability_profile":"avatar-demo-v1"})
            self.assertEqual(call.call_args.args[1],DEMO_PROPOSER_PROMPT)
            self.assertIn("outfit=suit",call.call_args.args[1])
            self.assertIn("奶蛙",call.call_args.args[1])


class DemoHTTPTests(unittest.TestCase):
    setUp=test_backend.HTTPTests.setUp
    tearDown=test_backend.HTTPTests.tearDown
    req=test_backend.HTTPTests.req

    def test_demo_http_edit_clarify_undo_and_strict_observation(self):
        code,v=self.req("/sessions",{"participant_id":"ENGINEERING","condition":"S","phase":"debug",
                                     "capability_profile":"avatar-demo-v1"})
        self.assertEqual(code,200)
        route=f"/sessions/{v['session_id']}"
        def mutate(op,**values):
            nonlocal v
            code,v=self.req(route+"/"+op,{"request_id":"http"+str(v["state"]["revision"]),
                "expected_revision":v["state"]["revision"],**values})
            self.assertEqual(code,200)
            return v
        mutate("request",query="换成运动装，颜色改成紫色，比例1.1")
        self.assertEqual((v["state"]["avatar_id"],v["state"]["outfit"]),("liang","sport"))
        mutate("request",query="换个风格")
        self.assertEqual(v["decision"],"ASK")
        mutate("answer",option_id="cancel")
        mutate("request",query="全部替换")
        self.assertEqual({k:v["state"][k] for k in DEMO_PROFILE.fields},AVATAR_DEFAULTS["nailong"])
        code,ack=self.req(route+"/events",{"event":"render_ack","payload":{
            "revision":v["state"]["revision"],"state":v["state"]}})
        self.assertEqual(code,200)
        self.assertTrue(ack["event_saved"])
        mutate("undo",field="all")
        self.assertEqual((v["state"]["avatar_id"],v["state"]["outfit"],v["state"]["jacket_color"]),
                         ("liang","sport","purple"))


if __name__=="__main__":
    unittest.main()
