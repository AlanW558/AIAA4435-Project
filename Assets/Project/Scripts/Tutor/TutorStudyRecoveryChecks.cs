#if UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEditor;

namespace IAI.Tutor
{
    // Explicit automation only: synthetic speech inputs, never starts Microphone.
    public sealed class TutorStudyRecoveryChecks:MonoBehaviour
    {
        TutorPanel panel;TutorStudyFlowPanel flow;TutorComparisonClient comparison;
        string folder,phase;int checks;bool done;
        void Check(bool value,string message){checks++;if(!value)throw new Exception(message);}
        void Awake(){Application.logMessageReceived+=Log;}
        void OnDestroy(){Application.logMessageReceived-=Log;}
        void Log(string text,string trace,LogType type){if(type==LogType.Exception&&!done)Finish(false,text);}
        IEnumerator Wait(Func<bool> ready,string label)
        {
            float until=Time.realtimeSinceStartup+100;
            while(!ready()&&Time.realtimeSinceStartup<until)yield return null;
            Check(ready(),label+" / "+flow.Error+" / "+flow.Data.Error+" / "+comparison.Error);
        }
        IEnumerator Settle(){yield return Wait(()=>!comparison.Busy&&TutorComparisonClient.Conditions.All(c=>!new[]{"processing","idle"}.Contains(comparison.State.branches.Get(c).status)),"settled branches");}
        IEnumerator Reveal()
        {
            yield return Settle();Check(!comparison.State.results_visible,"Clarifications must hide all results.");
            foreach(string c in TutorComparisonClient.Conditions)
            {
                if(comparison.State.branches.Get(c).status!="awaiting_clarification")continue;
                comparison.Select(c);yield return Wait(()=>!comparison.Busy&&comparison.Selected==c,"select branch");
                comparison.ChooseOption("c1");yield return Settle();
            }
            yield return Wait(()=>comparison.State.results_visible,"unified reveal");
        }
        IEnumerator Prepare()
        {
            flow.ContinueInteraction();yield return null;
            yield return Wait(()=>comparison.CanConfirmPreparation,"preparation");comparison.ConfirmPreparation();
            yield return Wait(()=>!comparison.Busy&&!comparison.PreparationPending,"preparation confirmed");
        }
        IEnumerator Audio(string purpose)
        {
            var v=comparison.State;int exchange=purpose=="reply"?comparison.View.conversation.Last().id:0;
            var data=new JObject{["request_id"]=Guid.NewGuid().ToString("N"),["expected_revision"]=v.revision,["condition"]=comparison.Selected,["purpose"]=purpose,["exchange_id"]=exchange};
            using(var r=new UnityWebRequest(comparison.endpoint+"/tutor/comparisons/"+v.task_id+"/audio","POST"))
            {
                r.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(data.ToString()));r.downloadHandler=new DownloadHandlerBuffer();r.SetRequestHeader("Content-Type","application/json");r.timeout=130;
                yield return r.SendWebRequest();Check(r.result==UnityWebRequest.Result.Success,"Cloud TTS: "+purpose+" / HTTP "+r.responseCode);
                var clip=TutorAudioPlayback.DecodeWav(r.downloadHandler.data);Check(clip.samples>0&&clip.channels==1,"Unity must decode provider PCM.");Destroy(clip);
                File.WriteAllBytes(Path.Combine(folder,"tutor-"+purpose+".wav"),r.downloadHandler.data);
            }
        }
        IEnumerator FinishAttribute()
        {
            // The caller has already revealed the first task's results.
            for(int i=0;i<8;i++)
            {
                flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"complete task or open attribute questionnaire");
                Check(flow.Error.Length==0,flow.Error);
                if(flow.ExpandedForFeedback)yield break;
                yield return Prepare();comparison.SubmitUserUtterance("Make the answer brief and explain recall.");yield return Reveal();
            }
            Check(false,"Attribute questionnaire must follow exactly eight completed tasks.");
        }
        IEnumerator FillAll()
        {
            foreach(string c in TutorComparisonClient.Conditions)
            {
                flow.SelectApproach(c);yield return Wait(()=>!comparison.Busy,"select rating");
                for(int i=0;i<5;i++)flow.Choose("A"+i,"answered",new JValue(4));
            }
            Check(flow.ReadyToSubmit,"All ratings should be ready.");
        }
        IEnumerator Start()
        {
            folder=System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT");phase=System.Environment.GetEnvironmentVariable("IAI_STUDY_RECOVERY_PHASE");
            panel=GetComponent<TutorPanel>();flow=panel.StudyFlow;comparison=panel.comparison;panel.seat=null; // Automated transport check does not test physical seating.
            if(phase=="1")
            {
                flow.StartStudy();yield return Wait(()=>!flow.Running&&flow.State!=null,"start");yield return Prepare();
                panel.OpenTab(0); // Same STT component as the microphone, with a labeled synthetic WAV.
                yield return null;
                panel.Speech.RecognizeFixture(File.ReadAllBytes(Path.Combine(folder,"request-synthetic.wav")));
                yield return Wait(()=>!panel.Speech.Working&&panel.Speech.CanSend,"cloud ASR request");
                Check(comparison.State.phase=="awaiting_input","STT must not send before confirmation.");
                File.WriteAllText(Path.Combine(folder,"request-transcript.txt"),panel.Speech.Transcript);
                panel.Speech.Submit();yield return Reveal();
                comparison.Select("S");yield return Wait(()=>!comparison.Busy&&comparison.Selected=="S","select S");
                yield return Audio("reply");
                File.WriteAllText(Path.Combine(folder,"drop-runtime.once"),"settings");
                comparison.SetSpeechRate(comparison.View.settings.speech_rate<1.2f?1.3f:.7f);
                yield return Wait(()=>!comparison.Busy&&comparison.UnknownOutcome,"lost runtime acknowledgement");
                flow.RestoreStudy();yield return Wait(()=>!flow.Running,"runtime receipt synchronization");
                Check(flow.Error.Length==0&&!comparison.UnknownOutcome,"Exact receipt must clear uncertainty without replay.");
                yield return Wait(()=>comparison.State.results_visible&&TutorComparisonClient.Conditions.All(c=>comparison.State.branches.Get(c).status=="ready"),"recovered shared round revealed");
                flow.ContinueInteraction();yield return FinishAttribute();
                flow.Speech.RecognizeFixture(File.ReadAllBytes(Path.Combine(folder,"comment-synthetic.wav")));
                yield return Wait(()=>!flow.Speech.Working&&flow.Speech.CanSend,"cloud survey ASR");
                File.WriteAllText(Path.Combine(folder,"survey-transcript.txt"),flow.Speech.Transcript);flow.Speech.Submit();
                yield return FillAll();
                File.WriteAllText(Path.Combine(folder,"drop-submit.once"),"submit_attribute");flow.SubmitAndNext();
                yield return Wait(()=>!flow.Running,"lost submit acknowledgement");
                Check(flow.Data.Journal.PendingCount==1,"Original questionnaire submission must remain pending.");
                Check(((JObject)flow.State["tasks"]).Count==8,"Client must not open the next attribute without a submission receipt.");
            }
            else
            {
                var original=JObject.Parse(File.ReadAllText(Path.Combine(folder,"phase-1.json"))).Value<string>("study_run_id");
                flow.RestoreStudy();yield return Wait(()=>!flow.Running&&flow.State!=null,"restore saved run");
                Check(flow.Error.Length==0,flow.Error);Check(flow.RunId==original,"Restarts must keep the same run ID.");
                Check(flow.Data.Journal.PendingCount==0,"Exact pending submission receipt should reconcile.");
                Check(((JObject)flow.State["questionnaires"]).Properties().Count(q=>q.Value.Value<string>("record_stage")=="submitted")==4,"Exactly four final records for the first attribute.");
                if(phase=="2")
                {
                    Check(((JObject)flow.State["tasks"]).Count==8,"Recovery must stop at the attribute preference boundary.");
                    flow.ChoosePreference("selected","S");flow.SubmitPreference();yield return Wait(()=>!flow.Running,"first attribute preference");
                    Check(((JObject)flow.State["tasks"]).Count==9,"One acknowledged preference opens just one next task.");
                    yield return Prepare();comparison.SubmitUserUtterance("Make the answer brief and explain recall.");yield return Reveal();
                    yield return FinishAttribute();flow.SelectApproach("S");yield return Wait(()=>!comparison.Busy,"S partial draft");
                    flow.Choose("A0","answered",new JValue(1));flow.Choose("A1","answered",new JValue(2));
                    Check(!flow.ReadyToSubmit,"Partial drafts must block navigation.");
                    if(System.Environment.GetEnvironmentVariable("IAI_STUDY_OFFLINE_FAULT")=="1")
                    {
                        File.WriteAllText(Path.Combine(folder,"disconnect.once"),"before pause request");
                        yield return Wait(()=>File.Exists(Path.Combine(folder,"disconnected.json")),"backend disconnected");
                        flow.PauseResume();yield return Wait(()=>!flow.Running,"offline pause intent");yield return null;
                        Check(flow.Data.Journal.PendingCount==1,"Unsent pause must remain durably queued.");
                        Check(flow.InstructionsOpen&&!comparison.CanSubmit,"Pending synchronization must lock tutor interaction.");
                    }
                }
                else
                {
                    if(System.Environment.GetEnvironmentVariable("IAI_STUDY_OFFLINE_FAULT")=="1")
                    {
                        Check(flow.State.Value<string>("lifecycle")=="paused","Original unsent pause must apply after recovery.");
                        flow.PauseResume();yield return Wait(()=>!flow.Running&&flow.State.Value<string>("lifecycle")=="active","explicit resume");yield return null;
                    }
                    flow.SelectApproach("S");yield return Wait(()=>!comparison.Busy,"restored S draft");
                    var q=((JObject)flow.State["questionnaires"]).Properties().Select(p=>(JObject)p.Value).Single(x=>x.Value<string>("condition")=="S"&&x.Value<string>("record_stage")=="draft");
                    var draft=JObject.Parse(flow.Data.Journal.RestoreLocal("draft:"+q.Value<string>("questionnaire_id")));
                    Check(q.Value<string>("questionnaire_version")=="attribute-summary-feedback-v3" && draft["answers"]["A0"]["value"].Type==JTokenType.Integer && draft["answers"]["A0"].Value<int>("value")==1,"Numeric outcome version and draft survive restart without conversion.");
                    Check(draft["answers"]["A1"].Value<int>("value")==2,"Unsynchronized local rating survives client/backend restart.");
                    Check(q["answers"]["A1"].Value<string>("status")=="unanswered","Local draft was never silently promoted to saved server feedback.");
                    Check(!flow.ReadyToSubmit,"Unanswered items must remain unanswered.");yield return FillAll();
                    flow.SubmitAndNext();yield return Wait(()=>!flow.Running,"second attribute saved");Check(flow.Error.Length==0,flow.Error);
                    flow.ExitStudy();yield return Wait(()=>!flow.Running,"explicit early exit");Check(flow.State.Value<string>("end_reason")=="participant_exit","Early exit must not claim normal completion.");
                }
            }
            Finish(true,"");
        }
        void Finish(bool passed,string error)
        {
            if(done)return;done=true;
            if(folder==null)folder=System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT");
            File.WriteAllText(Path.Combine(folder,"phase-"+phase+".json"),new JObject{["passed"]=passed,["checks"]=checks,["study_run_id"]=flow?.RunId,["error"]=error,["microphone_used"]=false,["heard_audio_verified"]=false}.ToString());
            EditorApplication.Exit(passed?0:1);
        }
    }
}
#endif
