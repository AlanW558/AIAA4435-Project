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
        void CheckPanel(bool expanded)
        {
            Assert(flow.ExpandedForFeedback==expanded,"Panel size must follow task vs feedback content.");
            var rect=flow.GetComponentInChildren<Canvas>().GetComponent<RectTransform>();
            var expected=expanded?new Vector2(920,1050):new Vector2(780,780);
            Assert(rect.sizeDelta==expected,"Unexpected study canvas dimensions.");
            var position=flow.transform.position;
            flow.ToggleVisibility();Assert(rect.sizeDelta==new Vector2(250,52),"Hide must leave only Show panel.");
            flow.ToggleVisibility();Assert(rect.sizeDelta==expected && flow.transform.position==position,"Show must restore size and drag anchor.");
        }
        IEnumerator Start()
        {
            panel=GetComponent<TutorPanel>();flow=panel.StudyFlow;comparison=panel.comparison;
            CheckQuestionnaireVersions();
            flow.StartStudy();yield return Wait(()=>!flow.Running&&flow.State!=null,"create run");
            Assert(flow.State["manifest"].Value<string>("preference_questionnaire_version")=="strategy-preference-v2","New runs pin multi-select preference version.");
            Assert(flow.State.Value<string>("collection_kind")=="engineering","Preview must remain engineering.");
            Assert(flow.State["manifest"].Value<string>("attribute_feedback_unit")=="attribute","New runs must use attribute-level feedback.");
            Assert(flow.State["manifest"].Value<string>("attribute_questionnaire_version")=="attribute-summary-feedback-v3","New runs must explicitly pin the numeric outcome questionnaire.");
            for(int n=0;n<32;n++)
            {
                CheckPanel(false);
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
                Assert(flow.GetComponentsInChildren<UnityEngine.UI.Button>().Any(b=>(b.name=="Complete task · next task" || b.name=="Finish attribute · open questionnaire") && b.interactable),"Task completion must become available after unified reveal.");
                if(n==0)
                {
                    comparison.SetSpeechRate(comparison.View.settings.speech_rate<1.2f?1.4f:.7f);
                    yield return Wait(()=>!comparison.Busy&&comparison.State.results_visible&&TutorComparisonClient.Conditions.All(c=>comparison.State.branches.Get(c).status=="ready"),"changed results revealed before completion");
                }
                flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"complete task");Assert(flow.Error.Length==0,flow.Error);
                tasks++;
                var completed=((JObject)flow.State["tasks"]).Properties().Select(p=>p.Value).Count(t=>t["completion_id"]?.Type==JTokenType.String);
                Assert(completed==tasks,"Each completed interaction must receive its own completion receipt.");
                Assert(((JObject)flow.State["questionnaires"]).Count==4*(tasks/8),"Questionnaires must only be created after eight tasks for an attribute.");
                if(tasks%8!=0)
                {
                    CheckPanel(false);Assert(!flow.ReadyToSubmit,"Individual tasks must not open a rating form.");
                }
                else
                {
                    CheckPanel(true);
                    Assert(((JObject)flow.State["questionnaires"]).Properties().All(p=>p.Value.Value<string>("questionnaire_version")=="attribute-summary-feedback-v3"),"New attribute records must keep the numeric questionnaire identity.");
                    var buttons=flow.GetComponentsInChildren<UnityEngine.UI.Button>();
                    for(int score=1;score<=7;score++)Assert(buttons.Count(b=>b.GetComponentInChildren<UnityEngine.UI.Text>()?.text==score.ToString())==5,"All five questions need each numeric score button.");
                    Assert(buttons.Count(b=>b.GetComponentInChildren<UnityEngine.UI.Text>()?.text=="Cannot judge")==5,"Unable to judge remains independent for all five questions.");
                    Assert(!buttons.Any(b=>b.GetComponentInChildren<UnityEngine.UI.Text>()?.text=="Fully met"),"New numeric forms must not show categorical outcome buttons.");
                    foreach(var text in flow.GetComponentsInChildren<UnityEngine.UI.Text>().Where(t=>System.Text.RegularExpressions.Regex.IsMatch(t.text,@"^[1-5]\. ")))
                        Assert(text.preferredHeight<=text.rectTransform.rect.height+1,"Attribute question text must fit without truncation: "+text.text);
                    foreach(string c in TutorComparisonClient.Conditions)
                    {
                        flow.SelectApproach(c);yield return Wait(()=>!comparison.Busy,"select attribute evaluation");
                        for(int i=0;i<5;i++)flow.Choose("A"+i,"answered",new JValue(4));
                    }
                    Assert(flow.ReadyToSubmit,"Twenty answers across four strategies must permit attribute submission.");
                    if(tasks==8)
                    {
                        var reviewCards=TutorTaskManifest.Parse(Resources.Load<TextAsset>("Tutor/StudyTaskSequence").text).modules[0].tasks;
                        foreach(var reviewCard in reviewCards)
                        {
                            flow.ReviewAttributeTask(reviewCard.task_code);yield return Wait(()=>!flow.Running,"review saved task "+reviewCard.DisplayCode);
                            Assert(comparison.State.task_code==reviewCard.task_code && !comparison.CanSubmit && !comparison.CanEdit,"Review may load any frozen result without enabling changes.");
                            Assert(panel.StrategyButtons.All(b=>b.interactable),"Strategy tabs remain available for read-only result review.");
                        }
                        flow.CloseResultReview();Assert(flow.ReadyToSubmit,"Reviewing another task must retain all twenty attribute answers.");
                        flow.RestoreStudy();yield return Wait(()=>!flow.Running,"restore attribute questionnaire drafts");
                        Assert(flow.ReadyToSubmit,"Restoring must retain current attribute answers.");
                    }
                    flow.SubmitAndNext();yield return Wait(()=>!flow.Running,"submit attribute");Assert(flow.Error.Length==0,flow.Error);
                    Assert(((JObject)flow.State["questionnaires"]).Properties().Count(p=>p.Value.Value<string>("record_stage")=="submitted")==4*(tasks/8),"Final questionnaire rows are per attribute and strategy.");
                    CheckPanel(true);
                    var preferenceLabels=flow.GetComponentsInChildren<UnityEngine.UI.Button>().Select(b=>b.GetComponentInChildren<UnityEngine.UI.Text>()?.text).ToArray();
                    Assert(preferenceLabels.Contains("No preference")&&!preferenceLabels.Contains("Unable to compare"),"Preference UI contains only current categories.");
                    foreach(var text in flow.GetComponentsInChildren<UnityEngine.UI.Text>().Where(t=>t.gameObject.activeInHierarchy))Assert(text.preferredHeight<=text.rectTransform.rect.height+1,"Preference text fits: "+text.text);
                    flow.ChoosePreference("selected","E","A","N","S");flow.SubmitPreference();yield return Wait(()=>!flow.Running,"attribute preference");Assert(flow.Error.Length==0,flow.Error);
                }
                if(tasks==32)
                {flow.ChoosePreference("no_clear_preference");flow.SubmitPreference();yield return Wait(()=>!flow.Running,"overall preference");Assert(flow.Error.Length==0,flow.Error);}
                File.WriteAllText(Path.Combine(System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT"),"progress.json"),"{\"tasks\":"+tasks+"}");
            }
            flow.StartNatural();yield return Wait(()=>!flow.Running&&panel.client&&panel.client.Connected,"natural session");CheckPanel(false);flow.ContinueInteraction();yield return null;
            panel.client.SubmitUserUtterance("Natural conversation: explain recall.");yield return Wait(()=>!panel.client.Busy&&!panel.client.HasQueuedAnswer,"natural answer");
            if(panel.client.HasQuestion){panel.client.ChooseOption("c1");yield return Wait(()=>!panel.client.Busy&&!panel.client.HasQueuedAnswer,"natural clarification");}
            flow.CaptureEvaluation();yield return Wait(()=>!flow.Running,"natural questionnaire");Assert(flow.Error.Length==0,flow.Error);
            CheckPanel(true);
            flow.Choose("N0","answered",new JValue("fully_met"));for(int i=1;i<8;i++)flow.Choose("N"+i,"answered",new JValue(5));
            for(int i=1;i<=10;i++)flow.Choose("S"+i,"answered",new JValue(i%2==1?5:1));
            for(int i=1;i<=8;i++)flow.Choose("U"+i,"answered",new JValue(6));
            flow.SubmitAndNext();yield return Wait(()=>!flow.Running,"finish study");Assert(flow.Error.Length==0,flow.Error);
            Assert(flow.State.Value<string>("end_reason")=="normal_completion","Study must end only after final save.");
            Assert(((JObject)flow.State["questionnaires"]).Count==17,"Expected 16 attribute and one natural questionnaire.");
            Assert(((JObject)flow.State["preferences"]).Count==5,"Expected five preferences.");
            Finish(true,"");
        }
        void CheckQuestionnaireVersions()
        {
            var catalog=JObject.Parse(Resources.Load<TextAsset>("Tutor/StudyQuestionnaires").text);
            var current=TutorStudyFlowPanel.AttributeItemsForVersion(catalog,"attribute-summary-feedback-v3");
            var numericSingle=TutorStudyFlowPanel.AttributeItemsForVersion(catalog,"attribute-summary-feedback-v2");
            var legacy=TutorStudyFlowPanel.AttributeItemsForVersion(catalog,"attribute-summary-feedback-v1");
            var perTask=TutorStudyFlowPanel.AttributeItemsForVersion(catalog,"attribute-feedback-v3");
            Assert(current.Length==5 && numericSingle.Length==5 && legacy.Length==5 && perTask.Length==5,"Each saved version needs exactly five attribute items.");
            Assert(current[0].Value<string>("scale")=="fulfillment7" && current[0].Value<string>("left")=="Not at all" && current[0].Value<string>("right")=="Completely","A0 requires its own fulfillment anchors.");
            Assert(numericSingle[0].Value<string>("scale")=="fulfillment7","Saved v2 A0 stays numeric.");
            Assert(TutorStudyFlowPanel.PreferenceSelectionValid("selected",new[]{"E","A","N","S"}),"All four preferences are supported.");
            Assert(!TutorStudyFlowPanel.PreferenceSelectionValid("selected",new[]{"S","S"}),"Duplicate preferences are rejected.");
            Assert(!TutorStudyFlowPanel.PreferenceSelectionValid("unable_to_compare",new string[0]),"Removed option cannot be newly submitted.");
            Assert(TutorStudyFlowPanel.PreferenceSelectionValid("no_clear_preference",new string[0])&&!TutorStudyFlowPanel.PreferenceSelectionValid("no_clear_preference",new[]{"S"}),"No preference is exclusive.");
            Assert(legacy[0].Value<string>("scale")=="category" && perTask[0].Value<string>("scale")=="category","Existing categorical records must render their original scales.");
            Assert(((JArray)catalog["items"]).OfType<JObject>().Single(i=>i.Value<string>("id")=="N0").Value<string>("scale")=="category","Natural N0 must remain categorical.");
            for(int i=1;i<=7;i++)Assert(TutorStudyFlowPanel.UnmetReasonsAllowed(new JObject{["status"]="answered",["value"]=i},"attribute-summary-feedback-v2")== (i<7),"Only unmet numeric goals enable optional reasons.");
            Assert(TutorStudyFlowPanel.UnmetReasonsAllowed(new JObject{["status"]="unable_to_judge",["value"]=JValue.CreateNull()},"attribute-summary-feedback-v2"),"Unable to judge may explain uncertainty.");
            Assert(!TutorStudyFlowPanel.UnmetReasonsAllowed(new JObject{["status"]="unanswered",["value"]=JValue.CreateNull()},"attribute-summary-feedback-v2"),"Unanswered must not enable reasons.");
            Assert(!TutorStudyFlowPanel.UnmetReasonsAllowed(new JObject{["status"]="answered",["value"]="fully_met"},"attribute-summary-feedback-v1"),"Legacy fully met must keep its reason gate.");
            Assert(TutorStudyFlowPanel.UnmetReasonsAllowed(new JObject{["status"]="answered",["value"]="partly_met"},"attribute-summary-feedback-v1"),"Legacy partly met must retain optional reasons.");
            bool rejected=false;try{TutorStudyFlowPanel.AttributeItemsForVersion(catalog,"unknown");}catch(InvalidOperationException){rejected=true;}
            Assert(rejected,"Unknown versions must not silently use the current scale.");
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
