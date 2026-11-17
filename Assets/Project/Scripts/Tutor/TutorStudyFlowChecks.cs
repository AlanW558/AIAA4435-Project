#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEditor;

namespace IAI.Tutor
{
    public sealed class TutorStudyFlowChecks:MonoBehaviour
    {
        TutorPanel panel;TutorStudyFlowPanel flow;TutorComparisonClient comparison;
        int tasks,checks;bool finished;
        void Assert(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
        void Awake(){Application.logMessageReceived+=ErrorLog;}
        void OnDestroy(){Application.logMessageReceived-=ErrorLog;}
        void ErrorLog(string text,string trace,LogType type){if(type==LogType.Exception && !finished)Finish(false,text);}
        IEnumerator Wait(Func<bool> ready,string label)
        {
            float until=Time.realtimeSinceStartup+45;
            while(!ready()&&Time.realtimeSinceStartup<until)yield return null;
            Assert(ready(),"Timeout: "+label+" / "+flow.Error+" / "+flow.Data.Error+" / "+comparison.Error);
        }
        IEnumerator Start()
        {
            panel=GetComponent<TutorPanel>();flow=panel.StudyFlow;comparison=panel.comparison;
            flow.StartStudy();yield return Wait(()=>!flow.Running&&flow.State!=null,"create run");
            Assert(flow.State.Value<string>("collection_kind")=="engineering","Preview must remain engineering.");
            for(int n=0;n<32;n++)
            {
                flow.ContinueInteraction();yield return null;
                yield return Wait(()=>comparison.CanConfirmPreparation,"preparation");comparison.ConfirmPreparation();
                yield return Wait(()=>!comparison.Busy&&!comparison.PreparationPending,"confirm baseline");
                comparison.SubmitUserUtterance("Make the answer brief and explain recall.");
                yield return Wait(()=>!comparison.Busy&&TutorComparisonClient.Conditions.All(c=>comparison.State.branches.Get(c).status!="processing"&&comparison.State.branches.Get(c).status!="idle"),"initial response");
                Assert(!comparison.State.results_visible,"Clarification barrier must hide initial results.");
                foreach(string c in TutorComparisonClient.Conditions)
                {
                    if(comparison.State.branches.Get(c).status!="awaiting_clarification")continue;
                    comparison.Select(c);yield return Wait(()=>!comparison.Busy&&comparison.Selected==c,"select clarification");
                    comparison.ChooseOption("c1");yield return Wait(()=>!comparison.Busy&&comparison.State.branches.Get(c).status!="processing","clarification response");
                }
                yield return Wait(()=>comparison.State.results_visible,"unified reveal");
                Assert(flow.GetComponentsInChildren<UnityEngine.UI.Button>().Any(b=>b.name=="Open questionnaire" && b.interactable),"Questionnaire button must update when results are revealed.");
                flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"capture evaluation");Assert(flow.Error.Length==0,flow.Error);
                foreach(string c in TutorComparisonClient.Conditions)
                {
                    flow.SelectApproach(c);yield return Wait(()=>!comparison.Busy,"select evaluation");
                    flow.Choose("A0","answered",new JValue("partly_met"));
                    for(int i=1;i<5;i++)flow.Choose("A"+i,"answered",new JValue(4));
                }
                Assert(flow.ReadyToSubmit,"Five answers for each strategy must permit submission.");
                if(n==0)
                {
                    comparison.SetSpeechRate(comparison.View.settings.speech_rate<1.2f?1.3f:.7f);
                    yield return Wait(()=>!comparison.Busy,"change evaluated result");
                    flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"refresh changed result");
                    Assert(!flow.ReadyToSubmit,"A changed result must invalidate its old local answers.");
                    flow.Choose("A0","answered",new JValue("partly_met"));for(int i=1;i<5;i++)flow.Choose("A"+i,"answered",new JValue(4));
                    Assert(flow.ReadyToSubmit,"Unchanged strategy answers should remain usable.");
                    flow.RestoreStudy();yield return Wait(()=>!flow.Running,"restore questionnaire drafts");
                    Assert(flow.ReadyToSubmit,"Restoring must retain current local answers.");
                }
                flow.SubmitAndNext();yield return Wait(()=>!flow.Running,"submit and next");Assert(flow.Error.Length==0,flow.Error);
                tasks++;
                if(tasks%8==0)
                {
                    flow.ChoosePreference("selected","S");flow.SubmitPreference();yield return Wait(()=>!flow.Running,"attribute preference");Assert(flow.Error.Length==0,flow.Error);
                }
                if(tasks==32)
                {flow.ChoosePreference("no_clear_preference");flow.SubmitPreference();yield return Wait(()=>!flow.Running,"overall preference");Assert(flow.Error.Length==0,flow.Error);}
                File.WriteAllText(Path.Combine(System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT"),"progress.json"),"{\"tasks\":"+tasks+"}");
            }
            flow.StartNatural();yield return Wait(()=>!flow.Running&&panel.client&&panel.client.Connected,"natural session");flow.ContinueInteraction();yield return null;
            panel.client.SubmitUserUtterance("Natural conversation: explain recall.");yield return Wait(()=>!panel.client.Busy&&!panel.client.HasQueuedAnswer,"natural answer");
            if(panel.client.HasQuestion){panel.client.ChooseOption("c1");yield return Wait(()=>!panel.client.Busy&&!panel.client.HasQueuedAnswer,"natural clarification");}
            flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"natural questionnaire");Assert(flow.Error.Length==0,flow.Error);
            flow.Choose("N0","answered",new JValue("fully_met"));for(int i=1;i<8;i++)flow.Choose("N"+i,"answered",new JValue(5));
            for(int i=1;i<=10;i++)flow.Choose("S"+i,"answered",new JValue(i%2==1?5:1));
            for(int i=1;i<=8;i++)flow.Choose("U"+i,"answered",new JValue(6));
            flow.SubmitAndNext();yield return Wait(()=>!flow.Running,"finish study");Assert(flow.Error.Length==0,flow.Error);
            Assert(flow.State.Value<string>("end_reason")=="normal_completion","Study must end only after final save.");
            Assert(((JObject)flow.State["questionnaires"]).Count==129,"Expected 128 attribute and one natural questionnaire.");
            Assert(((JObject)flow.State["preferences"]).Count==5,"Expected five preferences.");
            Finish(true,"");
        }
        void Finish(bool success,string error)
        {
            if(finished)return;finished=true;
            var result=new JObject{["passed"]=success,["checks"]=checks,["tasks"]=tasks,["study_run_id"]=flow?.RunId,["error"]=error,["headset_tested"]=false,["provider_calls"]=0};
            File.WriteAllText(Path.Combine(System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT"),"unity-flow.json"),result.ToString());
            EditorApplication.Exit(success?0:1);
        }
    }
}
#endif
