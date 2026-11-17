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
    public sealed class TutorQuestionnaireChecks : MonoBehaviour
    {
        public string Result = "Running";
        readonly List<string> checks = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        TutorStudyPanel study;
        int recovered;
        string folder => Path.GetFullPath("StudyData/validation/questionnaire-20261111");
        void Check(bool value, string name)
        { if (!value) { Result = "FAIL: " + name; Save(); throw new Exception(Result); } checks.Add(name); }
        void Save() { Directory.CreateDirectory(folder); File.WriteAllText(Path.Combine(folder, "unity-checks.txt"), Result + "\n" + string.Join("\n", checks)); }
        IEnumerator Wait(Func<bool> predicate, string name)
        {
            float end = Time.realtimeSinceStartup + 30;
            while (!predicate() && Time.realtimeSinceStartup < end)
            {
                if (!client.Busy && client.UnknownOutcome && client.CanRetry) { recovered++; client.Retry(); }
                yield return null;
            }
            Check(predicate(), name);
        }
        IEnumerator Idle() { yield return null; yield return Wait(() => !client.Busy && !client.UnknownOutcome, "Command acknowledged"); Check(client.Error == "", "No command error: " + client.Error); }
        void Fill(int score = 5)
        {
            study.ChooseCompletion("fully_met");
            foreach (string key in TutorStudyPanel.RatingKeys) study.ChooseRating(key, score);
        }
        IEnumerator Start()
        {
            panel = FindObjectOfType<TutorPanel>(); client = panel.comparison; study = panel.Study;
            client.endpoint = "http://127.0.0.1:8776";
            Check(study && study.transform.parent == panel.transform.parent && !study.transform.IsChildOf(panel.transform), "Independent study surface is a sibling of the system panel");
            var cam = Camera.main.transform;
            var frame=Quaternion.LookRotation(Vector3.ProjectOnPlane(client.avatar.transform.position-cam.position, Vector3.up));
            Vector3 local = Quaternion.Inverse(frame) * (study.transform.position - cam.position);
            Vector3 control = Quaternion.Inverse(frame) * (panel.transform.position - cam.position);
            Check(local.x < 0 && local.z > 0, "Study panel is in front-left of seated desktop view");
            Check(Mathf.Abs(Mathf.Atan2(local.x, local.z)) < Mathf.Abs(Mathf.Atan2(control.x, control.z)), "Study panel is closer to the central view than system panel");
            Check(study.GetComponentsInChildren<Image>().First(x => x.name == "Opaque paper").color.a == 1, "Paper background is opaque");
            Check(!panel.transform.Find("Adaptive Agent Canvas/Task instructions"), "Task instructions removed from system panel");
            Check(study.BeginButton.interactable && !study.NextButton.interactable, "Start enabled, next locked before task");
            study.ToggleVisible(); Check(!study.Visible && study.ToggleButton.gameObject.activeInHierarchy, "Collapsed panel retains reopen handle"); study.ToggleVisible();
            study.BeginButton.onClick.Invoke(); yield return Idle();
            Check(client.State.feedback_version == TutorStudyPanel.Version, "New comparison uses attribute-feedback-v2");
            panel.ConfirmPreparationButton.onClick.Invoke(); yield return Idle();
            client.SubmitUserUtterance("Compare an easier explanation."); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "awaiting_clarification", "Clarification available");
            Check(!client.State.results_visible, "Results remain hidden before clarification");
            study.OpenPage(1); Check(!study.SaveButton.interactable, "Cannot rate hidden results");
            yield return Wait(() => TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing"), "All initial decisions ready");
            foreach (string c in TutorComparisonClient.Conditions)
            {
                if (client.State.branches.Get(c).status != "awaiting_clarification") continue;
                client.Select(c); yield return Idle(); client.ChooseOption("c1"); yield return Idle();
                yield return Wait(() => client.State.branches.Get(c).status != "processing", "Answered branch settled");
            }
            client.Select("A"); yield return Idle();
            yield return Wait(() => client.State.results_visible && client.CanEditBranch, "All results revealed");
            study.OpenPage(1); study.Render();
            Check(JObject.Parse(study.CurrentAnswers)["ratings"].Count() == 0, "Ratings start empty without midpoint defaults");
            study.ChooseCompletion("partly_met"); study.ChooseRating("effort_ease", 0);
            Check(!study.SaveButton.interactable && !study.NextButton.interactable, "Missing ratings block save and next");
            string draft = study.CurrentAnswers; study.ToggleVisible(); study.ToggleVisible(); Check(study.CurrentAnswers == draft, "Hiding retains unfinished answers");
            Fill(); study.ChooseRating("effort_ease", 0); study.SaveButton.onClick.Invoke(); yield return Idle();
            Check(recovered == 1, "Lost feedback acknowledgement recovered using same request");
            Check(client.State.feedback.A.complete && !study.HasUnsavedAnswers, "Saved answers acknowledged without duplicate draft");
            Check(client.FeedbackDraft("A").Value<int>("feedback_revision") == 1, "Feedback retry did not duplicate save");
            study.ChooseRating("control", 2); Check(study.HasUnsavedAnswers && !study.NextButton.interactable, "Edited saved feedback blocks next until resaved");
            study.SaveRating(); yield return Idle();
            study.OpenPage(2);
            byte[] wav = TutorSpeechInput.EncodeWav(new float[8000], 1, 16000);
            int revision = client.Branch.branch_revision;
            study.Speech.RecognizeFixture(wav);
            yield return Wait(() => study.Speech.Transcript.Length > 0 && !study.Speech.Working, "Independent survey transcript returned");
            Check(client.Branch.branch_revision == revision && !study.CurrentAnswers.Contains("clarification helped"), "STT does not mutate dialogue or save unconfirmed text");
            study.Speech.Submit();
            Check(study.CurrentAnswers.Contains("clarification helped") && !study.Speech.HasCapture, "Use text explicitly confirms optional comment");
            study.SaveRating(); yield return Idle();
            foreach (string c in new[] { "E", "N", "S" })
            {
                client.Select(c); yield return Idle(); study.OpenPage(1); Fill(); study.SaveRating(); yield return Idle();
                Check(client.State.feedback.Get(c).complete, "Valid questionnaire saved for " + c);
            }
            Check(study.NextButton.interactable, "All four saved evaluations unlock next");
            client.SetReplyLength(2); yield return Idle();
            yield return Wait(() => client.CanEditBranch, "Updated branch ready");
            Check(!study.NextButton.interactable && !client.State.feedback.S.current, "Updated result invalidates earlier feedback");
            study.SaveRating(); yield return Idle(); Check(study.NextButton.interactable, "Explicit reconfirmation rates updated result");
            study.OpenPage(2); study.Speech.RecognizeFixture(wav); yield return null;
            client.Select("E"); yield return Idle(); yield return new WaitForSeconds(.65f);
            Check(study.Speech.Transcript.Length == 0 && !study.Speech.HasCapture, "Late survey transcript discarded after strategy switch");
            study.OpenPage(1);
            Canvas.ForceUpdateCanvases();
            foreach (var text in study.GetComponentsInChildren<Text>().Where(t => t.gameObject.activeInHierarchy && t.name != "Text" && !string.IsNullOrEmpty(t.text)))
                Check(text.preferredHeight <= text.rectTransform.rect.height + 1, "Text fits: " + text.name);
            Screenshot("questionnaire-panel.png", false); Screenshot("questionnaire-closeup.png", true);
            File.WriteAllText(Path.Combine(folder,"task-id.txt"),client.State.task_id);
            study.NextButton.onClick.Invoke(); yield return Idle();
            yield return Wait(() => client.State.sequence_index == 2, "Next task created only after feedback submission");
            Check(panel.TaskCardOpen && !study.NextButton.interactable && client.State.feedback_version == TutorStudyPanel.Version, "Next task has independent instructions and new-version questionnaire");
            Result = "PASS: " + checks.Count + " checks; " + recovered + " feedback ACK recovery; synthetic STT; no microphone/provider calls";
            Save(); Debug.Log("TUTOR_QUESTIONNAIRE_CHECKS " + Result);
        }
        void Screenshot(string name, bool closeup)
        {
            Directory.CreateDirectory(folder); var c = Camera.main; var position=c.transform.position; var rotation=c.transform.rotation; float fov=c.fieldOfView;
            c.transform.rotation=Quaternion.LookRotation(Vector3.ProjectOnPlane(client.avatar.transform.position-c.transform.position, Vector3.up));
            if(closeup) { c.transform.position=study.transform.position-study.transform.forward*1.15f; c.transform.rotation=study.transform.rotation; c.fieldOfView=52; }
            var old=c.targetTexture;var previous=RenderTexture.active;var rt=new RenderTexture(1800,1400,24);c.targetTexture=rt;c.Render();RenderTexture.active=rt;
            var image=new Texture2D(1800,1400,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1800,1400),0,0);image.Apply();File.WriteAllBytes(Path.Combine(folder,name),image.EncodeToPNG());
            c.targetTexture=old;RenderTexture.active=previous;Destroy(image);rt.Release();Destroy(rt);c.transform.SetPositionAndRotation(position,rotation);c.fieldOfView=fov;
        }
    }
}
#endif
