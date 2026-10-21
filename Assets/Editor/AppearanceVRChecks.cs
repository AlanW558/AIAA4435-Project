using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using IAI.Appearance;
using UnityEngine;

// Deterministic checks of the actual runtime classes. No provider calls or participant records.
public static class AppearanceVRChecks
{
    [Serializable] sealed class Report {public bool passed;public List<string> checks=new List<string>();}
    static void Check(Report r,bool condition,string name){if(!condition)throw new Exception("Appearance check failed: "+name);r.checks.Add(name);}
    static void Reject(Report r,Action action,string name)
    {
        bool rejected=false;try{action();}catch(ArgumentException){rejected=true;}
        Check(r,rejected,name);
    }
    static void Field(object obj,string name,object value)=>obj.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(obj,value);

    public static void Run()
    {
        var r=new Report();
        var cfg=new AppearanceSessionConfig{schema_version="appearance-session-v1",participant_id="DEBUGPICO",phase="debug",study_session_id="debug_checks",condition="S"};
        cfg.Validate();r.checks.Add("Valid debug identity accepted");
        cfg.participant_id="P001";Reject(r,cfg.Validate,"Phase/participant mismatch rejected");
        cfg.phase="formal";cfg.assigned=true;Reject(r,cfg.Validate,"Formal condition override rejected");
        cfg.condition="";cfg.Validate();r.checks.Add("Valid assigned formal identity accepted");
        cfg.task_id="A1";Reject(r,cfg.Validate,"Formal task override rejected");cfg.task_id="";
        cfg.assigned=false;Reject(r,cfg.Validate,"Formal unassigned launch rejected");cfg.assigned=true;
        cfg.participant_id="P001\n";Reject(r,cfg.Validate,"Trailing newline identity rejected");cfg.participant_id="P001";
        cfg.study_session_id="a\nb";Reject(r,cfg.Validate,"Multiline session ID rejected");cfg.study_session_id="formal_checks";
        cfg.expected_build_sha256="pretend-build";Reject(r,cfg.Validate,"Invalid fingerprint rejected");cfg.expected_build_sha256="";

        var tasks=JsonUtility.FromJson<TaskList>(File.ReadAllText("Assets/StreamingAssets/AppearanceStudy/tasks.json")).tasks;
        string csv=File.ReadAllText("Assets/StreamingAssets/AppearanceStudy/trial_schedule.csv");
        for(int p=1;p<=20;p++)
        {
            var rows=AppearanceSchedule.Parse(csv,"P"+p.ToString("000"),tasks);
            for(int i=0;i<16;i++)
            {
                var expected=i==15?ScheduleStep.Complete:(i+1)%4==0?ScheduleStep.Pause:ScheduleStep.Advance;
                if(AppearanceSchedule.Next(rows,i)!=expected)throw new Exception("Schedule transition mismatch.");
            }
        }
        r.checks.Add("All 20 schedules: 16 unique trials, four conditions, three block pauses, terminal completion");
        Reject(r,()=>AppearanceSchedule.Parse(csv,"P999",tasks),"Missing participant schedule rejected");
        Reject(r,()=>AppearanceSchedule.Parse(csv,"P001",Array.Empty<StudyTask>()),"Missing task assets rejected");
        var rows1=AppearanceSchedule.Parse(csv,"P001",tasks);
        string first="P001,"+rows1[0].trialId+","+rows1[0].block+","+rows1[0].withinBlock+","+rows1[0].condition+","+rows1[0].taskId;
        Reject(r,()=>AppearanceSchedule.Parse(csv+"\n"+first,"P001",tasks),"Duplicate schedule row rejected");

        var go=new GameObject("Appearance runtime checks");
        try
        {
            var c=go.AddComponent<AppearanceExperimentClient>();c.view=new SessionView{session_id="checks",state=new AppearanceState()};
            Field(c,"initialized",true);Field(c,"controlledTask",true);Field(c,"trialActive",true);Field(c,"trialStarted",true);
            c.query="Fixed first request";
            Check(r,!c.CanEditQuery&&!c.CanFinish&&!c.RequestSubmit("Changed request")&&c.query=="Fixed first request","First rejected/pending controlled request stays locked and cannot finish");
            Field(c,"initialSent",true);Check(r,c.CanEditQuery,"Accepted first request permits repairs");
            Field(c,"faulted",true);Field(c,"finished",true);Field(c,"awaitingBlock",true);
            Check(r,!c.RequestSubmit("repair")&&!c.RequestAnswer("c1")&&!c.RequestUndo("all")&&!c.RequestFinish()&&!c.RequestNext()&&!c.RequestResume(),"Fault blocks every participant/researcher mutation");
            var validate=typeof(AppearanceExperimentClient).GetMethod("ValidView",BindingFlags.Static|BindingFlags.NonPublic);
            Check(r,!(bool)validate.Invoke(null,new object[]{new SessionView()}),"Empty HTTP snapshot rejected");
            Check(r,!(bool)validate.Invoke(null,new object[]{new SessionView{session_id="checks",decision="ACT",state=new AppearanceState{scale=float.NaN}}}),"Nonfinite renderer state rejected");
            Check(r,!(bool)validate.Invoke(null,new object[]{new SessionView{session_id="checks",decision="ASK",state=new AppearanceState()}}),"Question without options rejected");
            var a=go.AddComponent<AppearanceAvatar>();a.Create();c.avatar=a;int count=go.GetComponentsInChildren<Renderer>(true).Length;
            a.Apply(new AppearanceState{jacket_color="purple",accessory="glasses",scale=1.1f});a.Create();a.SetInteraction("ask");
            Check(r,count<100&&count==go.GetComponentsInChildren<Renderer>(true).Length,"Avatar creation idempotent and below mobile renderer budget");
            Check(r,a.ObservedColor=="purple"&&a.ObservedAccessory=="glasses"&&Mathf.Abs(a.ObservedScale-1.1f)<.0001f,"Actual renderer observations survive Create and interaction feedback");
            var reject=typeof(AppearanceExperimentClient).GetMethod("ApplyRequestFailure",BindingFlags.Instance|BindingFlags.NonPublic);
            Field(c,"faulted",false);Field(c,"finished",false);Field(c,"awaitingBlock",false);Field(c,"initialSent",false);
            reject.Invoke(c,new object[]{502L,new SessionView{session_id="checks",decision="ERROR",error="model_error",state=new AppearanceState{revision=1}}});
            Check(r,c.Faulted&&!c.CanOperate&&!c.CanFinish,"Provider failure stops the trial before a retry could bypass the initial gate");
            Field(c,"faulted",false);Field(c,"initialSent",true);
            var pending=new Question{text="Which color?",options=new[]{new Choice{id="c1",label="Orange"},new Choice{id="cancel",label="Cancel"}}};
            reject.Invoke(c,new object[]{409L,new SessionView{session_id="checks",decision="ERROR",error="nothing_to_undo",state=new AppearanceState{revision=1},question=pending}});
            Check(r,!c.Faulted&&c.IsQuestion&&c.view.state.revision==1&&!c.RequestSubmit("Bypass question"),"Rejected undo preserves the authoritative pending clarification");
        }
        finally{UnityEngine.Object.DestroyImmediate(go);}
        r.passed=true;Directory.CreateDirectory("Builds/Pico");File.WriteAllText("Builds/Pico/runtime-checks.json",JsonUtility.ToJson(r,true));
        Debug.Log("APPEARANCE_RUNTIME_CHECKS "+r.checks.Count+" passed");
    }
}
