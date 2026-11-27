#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;
namespace IAI.Tutor
{
    public sealed class TutorStudyMaterialsChecks : MonoBehaviour
    {
        public string Result = "Running";
        readonly List<string> checks = new List<string>();
        readonly List<string> ids = new List<string>();
        TutorPanel panel; TutorComparisonClient client; TutorStudyPanel study;
        string folder => Path.GetFullPath("StudyData/validation/study-materials-20261111");
        void Check(bool ok, string name) { if (!ok) { Result="FAIL: "+name; Save(); throw new Exception(Result); } checks.Add(name); }
        void Save() { Directory.CreateDirectory(folder); File.WriteAllText(Path.Combine(folder,"unity-checks.txt"),Result+"\n"+string.Join("\n",checks)); }
        IEnumerator Wait(Func<bool> fn,string name)
        { float end=Time.realtimeSinceStartup+35; while(!fn()&&Time.realtimeSinceStartup<end)yield return null;Check(fn(),name); }
        IEnumerator Idle() { yield return null;yield return Wait(()=>!client.Busy&&!client.UnknownOutcome,"Command acknowledged");Check(client.Error=="","No command error: "+client.Error); }
        IEnumerator Start()
        {
            panel=FindObjectOfType<TutorPanel>();client=panel.comparison;study=panel.Study;
            client.endpoint="http://127.0.0.1:8778";panel.LoadStudyPreview(true);
            var manifest=TutorTaskManifest.Parse(Resources.Load<TextAsset>("Tutor/StudyTaskSequence").text);
            Check(manifest.modules.Length==4&&manifest.modules.All(m=>m.tasks.Length==8),"32 tasks in four modules");
            var wire=JsonUtility.ToJson(TutorTaskNavigation.PublicSequence(manifest));
            Check(wire.Contains("catalog_sha256")&&!wire.Contains("instructions")&&!wire.Contains("public_start")&&!wire.Contains("materials\""),"Only version/hash and task metadata transported");
            int global=0;
            foreach(var module in manifest.modules)
            {
                foreach(var task in module.tasks)
                {
                    if(panel.BeginTaskButton.interactable){panel.BeginTaskButton.onClick.Invoke();yield return Idle();}
                    global++;Check(client.State.task_code==task.task_code&&client.State.sequence_index==global,"Correct registered task: "+task.task_code);
                    Check(client.State.preparation_locked&&client.PreparationPending&&!client.CanPrepare,"Fixed baseline; no preparation edits");
                    Check(!panel.RateSlider.interactable&&!panel.LengthSlider.interactable&&panel.VoiceButtons.All(b=>!b.interactable)&&panel.ToneButtons.All(b=>!b.interactable),"All controls disabled during study preparation");
                    Check(panel.ConfirmPreparationButton.interactable,"Can confirm a locked baseline");
                    Check(client.State.baseline.conversation.Length>0&&string.IsNullOrEmpty(client.State.initial_query),"Stored starting state does not send an automatic participant request");
                    Check(task.ParticipantInstructions.Contains("Task goal\n") && task.ParticipantInstructions.Contains("Keep unchanged\n") && task.ParticipantInstructions.Contains("Request example\n") && !task.ParticipantInstructions.Contains("Supplied Starting Context"), "Task card contains the three approved sections");
                    Check(!study.GetComponentsInChildren<Button>(true).Any(b=>b.name.StartsWith("Play") || b.name.Contains("sample")), "No fixed material playback buttons");
                    Check(task.DisplayCode.EndsWith("-"+(Array.IndexOf(module.tasks.Where(t=>t.scenario==task.scenario).ToArray(),task)+1)), "Consecutive participant-facing task numbers");
                    if(task.task_code=="R1-2"){study.OpenPage(0);yield return null;Screenshot("relative-rate-task.png");study.BeginButton.onClick.Invoke();yield return Idle();}
                    panel.ConfirmPreparationButton.onClick.Invoke();yield return Idle();Check(client.State.preparation_confirmed,"Baseline confirmed before recording");
                    client.SubmitUserUtterance("Compare an easier explanation.");yield return Idle();
                    yield return Wait(()=>TutorComparisonClient.Conditions.All(c=>client.State.branches.Get(c).status!="processing"),"Strategies settled before clarifications");
                    Check(!client.State.results_visible&&!panel.Playback.Active,"Clarification barrier hides results without fixed sample playback");
                    foreach(string c in TutorComparisonClient.Conditions)
                    {
                        if(client.State.branches.Get(c).status!="awaiting_clarification")continue;
                        client.Select(c);yield return Idle();client.ChooseOption("c1");yield return Idle();
                        yield return Wait(()=>client.State.branches.Get(c).status!="processing","Clarification settled");
                    }
                    yield return Wait(()=>client.State.results_visible,"All results revealed together");study.OpenPage(1);
                    foreach(string c in TutorComparisonClient.Conditions)
                    {
                        client.Select(c);yield return Idle();study.ChooseCompletion("fully_met");foreach(string k in TutorStudyPanel.RatingKeys)study.ChooseRating(k,5);
                        study.SaveRating();yield return Idle();
                    }
                    ids.Add(client.State.task_id);Check(study.NextButton.interactable,"Task feedback complete");study.NextButton.onClick.Invoke();yield return Idle();
                    if(task!=module.tasks.Last())yield return Wait(()=>panel.Navigation.Task.task_code!=task.task_code,"Next registered task loaded");
                }
                yield return Wait(()=>study.PreferenceMode,"Attribute preference appears after eight tasks");
                study.ChoosePreferenceCategory("no_clear_preference");study.SaveButton.onClick.Invoke();yield return Idle();
                Check(client.State.sequence.attribute_saved,"Attribute preference saved");
                if(module!=manifest.modules.Last())
                { var old=client.State.task_id;study.NextButton.onClick.Invoke();yield return Idle();yield return Wait(()=>client.State.task_id!=old,"Next module loaded"); }
            }
            Check(study.PreferenceScope=="comparison_overall","Overall preference follows all 32 tasks");
            study.ChoosePreferenceCategory("no_clear_preference");study.SaveButton.onClick.Invoke();yield return Idle();
            Check(panel.Navigation.ComparisonComplete&&!study.NextButton.interactable,"Natural module handoff; no fifth comparison module");
            Check(ids.Distinct().Count()==32,"32 distinct tasks completed");
            File.WriteAllLines(Path.Combine(folder,"task-ids.txt"),ids);
            Result="PASS: "+checks.Count+" checks; 32 study-preview tasks, 5 preferences; no fixed sample audio or provider/microphone calls";Save();Debug.Log("TUTOR_STUDY_MATERIALS_CHECKS "+Result);
        }
        void Screenshot(string name)
        {
            Directory.CreateDirectory(folder);Canvas.ForceUpdateCanvases();
            foreach(var text in study.GetComponentsInChildren<Text>().Where(t=>t.gameObject.activeInHierarchy&&t.name!="Text"&&!string.IsNullOrEmpty(t.text)))
                Check(text.preferredHeight<=text.rectTransform.rect.height+1,"Text fits: "+text.name);
            var c=Camera.main;var pos=c.transform.position;var rot=c.transform.rotation;float fov=c.fieldOfView;
            c.transform.position=study.transform.position-study.transform.forward*1.15f;c.transform.rotation=study.transform.rotation;c.fieldOfView=52;
            var old=c.targetTexture;var prev=RenderTexture.active;var rt=new RenderTexture(1800,1400,24);c.targetTexture=rt;c.Render();RenderTexture.active=rt;
            var img=new Texture2D(1800,1400,TextureFormat.RGB24,false);img.ReadPixels(new Rect(0,0,1800,1400),0,0);img.Apply();File.WriteAllBytes(Path.Combine(folder,name),img.EncodeToPNG());
            c.targetTexture=old;RenderTexture.active=prev;Destroy(img);rt.Release();Destroy(rt);c.transform.SetPositionAndRotation(pos,rot);c.fieldOfView=fov;
        }
    }
}
#endif
