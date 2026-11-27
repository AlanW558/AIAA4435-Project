#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace IAI.Tutor
{
    public sealed class TutorPreferenceChecks : MonoBehaviour
    {
        public string Result = "Running";
        readonly List<string> checks = new List<string>();
        TutorComparisonClient client; TutorPanel panel; TutorStudyPanel study;
        int recovered; readonly List<string> taskIds=new List<string>();
        string folder => Path.GetFullPath("StudyData/validation/preferences-20261111");
        void Check(bool value,string name) { if(!value){Result="FAIL: "+name;Save();throw new Exception(Result);}checks.Add(name); }
        void Save(){Directory.CreateDirectory(folder);File.WriteAllText(Path.Combine(folder,"unity-checks.txt"),Result+"\n"+string.Join("\n",checks));}
        IEnumerator Wait(Func<bool> predicate,string name)
        {
            float end=Time.realtimeSinceStartup+35;
            while(!predicate() && Time.realtimeSinceStartup<end){if(!client.Busy && client.UnknownOutcome && client.CanRetry){recovered++;client.Retry();}yield return null;}
            Check(predicate(),name);
        }
        IEnumerator Idle(){yield return null;yield return Wait(()=>!client.Busy&&!client.UnknownOutcome,"Command acknowledged");Check(client.Error=="","No command error: "+client.Error);}
        IEnumerator RunTask()
        {
            if(panel.BeginTaskButton.interactable){panel.BeginTaskButton.onClick.Invoke();yield return Idle();}
            Check(client.PreparationPending,"New task has independent preparation");
            panel.ConfirmPreparationButton.onClick.Invoke();yield return Idle();
            client.SubmitUserUtterance("Compare an easier explanation.");yield return Idle();
            yield return Wait(()=>TutorComparisonClient.Conditions.All(c=>client.State.branches.Get(c).status!="processing"),"Initial decisions settled");
            foreach(string c in TutorComparisonClient.Conditions)
            {
                if(client.State.branches.Get(c).status!="awaiting_clarification")continue;
                client.Select(c);yield return Idle();client.ChooseOption("c1");yield return Idle();
                yield return Wait(()=>client.State.branches.Get(c).status!="processing","Clarification branch settled");
            }
            yield return Wait(()=>client.State.results_visible,"Results revealed");
            study.OpenPage(1);
            foreach(string c in TutorComparisonClient.Conditions)
            {
                client.Select(c);yield return Idle();study.ChooseCompletion("fully_met");
                foreach(string key in TutorStudyPanel.RatingKeys)study.ChooseRating(key,5);
                study.SaveRating();yield return Idle();
            }
            Check(study.NextButton.interactable,"Four current feedback records unlock task submission");
            taskIds.Add(client.State.task_id);study.NextButton.onClick.Invoke();yield return Idle();
        }
        IEnumerator Start()
        {
            panel=FindObjectOfType<TutorPanel>();client=panel.comparison;study=panel.Study;
            client.endpoint="http://127.0.0.1:8777";
            var manifest=TutorTaskManifest.Parse(Resources.Load<TextAsset>("Tutor/PracticeTaskSequence").text);
            Check(manifest.modules.Length==4 && manifest.modules.All(m=>m.tasks.Length==2),"Eight tasks explicitly marked practice across four attributes");
            var wire=JsonUtility.ToJson(TutorTaskNavigation.PublicSequence(manifest));
            Check(!wire.Contains("instructions")&&!wire.Contains("title"),"Sequence registration excludes private task instructions");
            for(int module=0;module<4;module++)
            {
                for(int task=0;task<2;task++)
                {
                    yield return RunTask();
                    if(task==0){yield return Wait(()=>client.State.sequence.module_task_index==1,"Within-module transition acknowledged");Check(!study.PreferenceMode,"No preference inserted between tasks");}
                }
                yield return Wait(()=>study.PreferenceMode && study.PreferenceScope=="attribute","Attribute preference appears after final task submission");
                Check(!study.SaveButton.interactable&&!study.NextButton.interactable,"Missing preference blocks continuation with no default");
                Check(((JArray)JObject.Parse(study.CurrentPreferenceAnswers)["selected_conditions"]).Count==0,"New attribute starts with no preference selections");
                if(module==0)
                {
                    study.ChoosePreferenceStrategy("E");study.ChoosePreferenceStrategy("S");study.ChoosePreferenceStrategy("N");
                    Check(study.PreferenceStrategyButtons[1].interactable,"Fourth strategy remains selectable");
                    study.ChoosePreferenceStrategy("A");Check(((JArray)JObject.Parse(study.CurrentPreferenceAnswers)["selected_conditions"]).Count==4,"All four strategies can be preferred");
                    study.ChoosePreferenceCategory("no_clear_preference");Check(((JArray)JObject.Parse(study.CurrentPreferenceAnswers)["selected_conditions"]).Count==0,"Special category clears strategy selections");
                    study.ChoosePreferenceStrategy("E");study.ChoosePreferenceStrategy("S");
                    var draft=study.CurrentPreferenceAnswers;study.ToggleVisible();study.ToggleVisible();Check(draft==study.CurrentPreferenceAnswers,"Hiding preserves preference draft");
                    study.PauseButton.onClick.Invoke();yield return Idle();Check(client.State.sequence.preference_paused&&!study.SaveButton.interactable,"Pause prevents preference submission");
                    study.PauseButton.onClick.Invoke();yield return Idle();Check(study.CurrentPreferenceAnswers==draft,"Resume preserves preference draft");
                    var wav=TutorSpeechInput.EncodeWav(new float[8000],1,16000);study.Speech.RecognizeFixture(wav);
                    yield return Wait(()=>study.Speech.Transcript.Length>0&&!study.Speech.Working,"Independent preference STT returns text");
                    Check(!study.CurrentPreferenceAnswers.Contains("useful control"),"Preference STT not saved without confirmation");
                    study.Speech.Submit();Check(study.CurrentPreferenceAnswers.Contains("useful control"),"Confirmed spoken reason enters preference only");
                    Screenshot("attribute-preference.png");
                }
                else if(module==1)study.ChoosePreferenceCategory("no_clear_preference");
                else if(module==2){study.ChoosePreferenceStrategy("N");study.ChoosePreferenceStrategy("S");}
                else study.ChoosePreferenceStrategy("N");
                study.SaveButton.onClick.Invoke();yield return Idle();
                Check(client.State.sequence.attribute_saved,"Attribute preference acknowledged once");
                if(module<3)
                {
                    Check(study.NextButton.interactable && !study.SaveButton.interactable,"Saved preference unlocks next attribute only");
                    int next=module+1;study.NextButton.onClick.Invoke();yield return Idle();
                    yield return Wait(()=>client.State.sequence.module_index==next,"Cross-module transition verified");
                    Check(client.State.sequence_index==2*(module+1)+1 && panel.TaskCardOpen,"Global task index and next instructions match");
                    Check(client.State.baseline.conversation.Length==0,"No preceding dialogue leaks into next module");
                }
            }
            Check(study.PreferenceScope=="comparison_overall"&&!study.SaveButton.interactable,"Overall preference follows four independently saved attribute preferences");
            Check(!JObject.Parse(study.CurrentPreferenceAnswers).ContainsKey("choice_kind"),"Overall preference is not copied or inferred");
            study.ChoosePreferenceCategory("no_clear_preference");
            Canvas.ForceUpdateCanvases();
            foreach(var text in study.GetComponentsInChildren<Text>().Where(t=>t.gameObject.activeInHierarchy && t.name!="Text" && !string.IsNullOrEmpty(t.text)))
                Check(text.preferredHeight<=text.rectTransform.rect.height+1,"Visible text fits: "+text.name);
            Screenshot("overall-preference.png");
            study.SaveButton.onClick.Invoke();yield return Idle();
            Check(panel.Navigation.ComparisonComplete && client.State.sequence.overall_saved,"Overall preference saved before natural activity");
            Check(!study.NextButton.interactable&&!study.SaveButton.interactable,"Final handoff cannot create a fifth comparison module or duplicate preference");
            Check(recovered==3,"Lost attribute, cross-module and overall ACKs recovered");
            Check(taskIds.Count==8&&taskIds.Distinct().Count()==8,"Eight distinct practice tasks, no duplicates");
            Directory.CreateDirectory(folder);File.WriteAllLines(Path.Combine(folder,"task-ids.txt"),taskIds);Screenshot("comparison-complete.png");
            Result="PASS: "+checks.Count+" checks; "+recovered+" ACK recoveries; 8 practice tasks; no provider/microphone calls";Save();Debug.Log("TUTOR_PREFERENCE_CHECKS "+Result);
        }
        void Screenshot(string name)
        {
            Directory.CreateDirectory(folder);var c=Camera.main;var position=c.transform.position;var rotation=c.transform.rotation;float fov=c.fieldOfView;
            c.transform.position=study.transform.position-study.transform.forward*1.15f;c.transform.rotation=study.transform.rotation;c.fieldOfView=52;
            var old=c.targetTexture;var previous=RenderTexture.active;var rt=new RenderTexture(1800,1400,24);c.targetTexture=rt;c.Render();RenderTexture.active=rt;
            var image=new Texture2D(1800,1400,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1800,1400),0,0);image.Apply();File.WriteAllBytes(Path.Combine(folder,name),image.EncodeToPNG());
            c.targetTexture=old;RenderTexture.active=previous;Destroy(image);rt.Release();Destroy(rt);c.transform.SetPositionAndRotation(position,rotation);c.fieldOfView=fov;
        }
    }
}
#endif
