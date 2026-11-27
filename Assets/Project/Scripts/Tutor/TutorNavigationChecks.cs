#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace IAI.Tutor
{
    public sealed class TutorNavigationChecks : MonoBehaviour
    {
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        int recoveries;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-navigation-unity"));
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllLines(Path.Combine(Folder, "checks.txt"), passed.Concat(new[] { Result })); }
        void Check(bool ok, string message)
        { if (!ok) { Result = "FAIL: " + message; Save(); throw new Exception(Result); } passed.Add(message); }
        IEnumerator Wait(Func<bool> predicate, string message)
        {
            float end = Time.realtimeSinceStartup + 30;
            while (!predicate() && Time.realtimeSinceStartup < end)
            {
                if (!client.Busy && client.UnknownOutcome && client.CanRetry) { recoveries++; client.Retry(); }
                yield return null;
            }
            Check(predicate(), message);
        }
        IEnumerator Idle()
        {
            yield return null;
            yield return Wait(() => !client.Busy && !client.UnknownOutcome, "Command acknowledged or recovered");
            Check(client.Error == "", "No command error");
        }
        void Invalid(string json, string label)
        { bool rejected = false; try { TutorTaskManifest.Parse(json); } catch (ArgumentException) { rejected = true; } Check(rejected, label); }
        IEnumerator Reveal()
        {
            panel.ConfirmPreparationButton.onClick.Invoke(); yield return Idle();
            Check(!panel.TaskCardOpen && client.CanSubmit, "Prepared task accepts participant speech");
            client.SubmitUserUtterance("Compare an easier explanation."); yield return Idle();
            foreach (var condition in new[] { "A", "S" })
            {
                yield return Wait(() => TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing" && client.State.branches.Get(c).status != "idle"), "Branches settle before selection");
                if (client.State.branches.Get(condition).status != "awaiting_clarification") continue;
                client.Select(condition); yield return Idle();
                string question = client.View.question.question_id;
                panel.TaskDetailsButton.onClick.Invoke();
                Check(panel.TaskCardOpen && !client.CanSubmit && !panel.Speech.CanRecord && !panel.Playback.Active, "Task details suspend input and playback during clarification");
                panel.BeginTaskButton.onClick.Invoke();
                Check(!panel.TaskCardOpen && client.View.question.question_id == question, "Closing task card preserves captured clarification");
                client.ChooseOption("c1"); yield return Idle();
            }
            yield return Wait(() => client.State.results_visible && client.CanEditBranch, "Four results revealed together");
        }
        IEnumerator Rate(string condition)
        {
            client.Select(condition); yield return Idle();
            // Explicit engineering fixture only; never inserted by navigation UI.
            client.SaveFeedback("{\"completion\":\"fully_met\",\"ratings\":{\"effort_ease\":4,\"control\":4,\"clarification_appropriateness\":4,\"satisfaction\":4}}");
            yield return Idle();
        }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            client.endpoint = "http://127.0.0.1:8775";
            string json = Resources.Load<TextAsset>("Tutor/PracticeTaskSequence").text;
            var manifest = TutorTaskManifest.Parse(json);
            Check(manifest.modules[0].tasks.Length == 2, "Two explicitly practice-only tasks loaded");
            var wire = JsonUtility.ToJson(TutorTaskNavigation.PublicTask(manifest.modules[0], manifest.modules[0].tasks[0]));
            Check(!wire.Contains("instructions") && !wire.Contains("title") && !wire.Contains("active recall"), "Task transport excludes participant instructions");
            Invalid(json.Replace("practice", "formal"), "Unapproved formal manifest rejected");
            Invalid(json.Replace("PRACTICE-L2", "PRACTICE-L1"), "Duplicate task identifiers rejected");
            Invalid(json.Replace("\"C2\"", "\"C9\""), "Invalid scenario rejected");
            foreach (string direction in new[] { "speech_rate", "reply_length", "tone", "voice" })
                Check(TutorTaskManifest.Parse(JsonUtility.ToJson(new TutorTaskManifest { version = manifest.version, purpose = manifest.purpose, modules = new[] { new TutorTaskModule { direction = direction, title = "Fixture", tasks = manifest.modules[0].tasks } } })).modules[0].direction == direction, "Direction supported: " + direction);
            panel.Render();
            Check(panel.TaskCardOpen && panel.BeginTaskButton.interactable && !panel.NextTaskButton.interactable, "Initial task instructions precede session creation");
            panel.BeginTaskButton.onClick.Invoke(); yield return Idle();
            Check(client.Connected && client.State.task_code == "PRACTICE-L1" && client.PreparationPending && !panel.TaskCardOpen, "First task opens shared preparation after create replay");
            Check(string.IsNullOrEmpty(client.State.initial_query), "Task goal is not automatically sent as participant speech");
            Check(panel.Navigation.Progress.Contains("1/2"), "Progress begins at first task");
            string first = client.State.task_id;
            panel.Navigation.Next(); Check(client.State.task_id == first && !client.Busy, "Next cannot skip missing results or feedback");
            panel.TaskDetailsButton.onClick.Invoke();
            Check(!client.CanPrepare && !panel.ConfirmControlsButton.interactable, "Task details block hidden preparation controls");
            panel.BeginTaskButton.onClick.Invoke();
            yield return Reveal();
            Check(!panel.NextTaskButton.interactable, "Unrated results cannot advance");
            foreach (var condition in new[] { "E", "A", "N" }) yield return Rate(condition);
            Check(!panel.NextTaskButton.interactable, "Three feedback drafts cannot substitute for four");
            yield return Rate("S");
            Check(panel.NextTaskButton.interactable, "Four current feedback drafts unlock Next");
            client.SetTone(1); yield return Idle();
            Check(!panel.NextTaskButton.interactable, "Changed result invalidates navigation eligibility");
            yield return Rate("S");
            panel.NextTaskButton.onClick.Invoke();
            yield return Wait(() => client.State.task_code == "PRACTICE-L2" && !client.Busy && !client.UnknownOutcome, "Submit and next recover lost acknowledgements");
            Check(client.State.previous_task_id == first && client.State.sequence_index == 2 && panel.Navigation.Progress.Contains("2/2"), "Progress follows acknowledged successor identity");
            Check(panel.TaskCardOpen && !client.CanSubmit && !client.CanPrepare, "Next task shows instructions before preparation");
            Check(string.IsNullOrEmpty(client.State.initial_query) && client.State.baseline.conversation.Length == 0, "No dialogue copied into new task");
            panel.BeginTaskButton.onClick.Invoke();
            Check(client.CanPrepare && !client.State.preparation_confirmed, "New task requires fresh preparation confirmation");
            yield return Reveal();
            foreach (var condition in TutorComparisonClient.Conditions) yield return Rate(condition);
            panel.NextTaskButton.onClick.Invoke();
            yield return Wait(() => client.State.lifecycle == "submitted" && !client.Busy && !client.UnknownOutcome, "Last task feedback submitted");
            Check(panel.Navigation.AwaitingPreference && panel.TaskCardOpen && !panel.NextTaskButton.interactable && !panel.BeginTaskButton.interactable, "Section stops for preference feedback without inventing an answer");
            Check(client.State.sequence_index == 2 && string.IsNullOrEmpty(client.State.next_task_id), "No extra task created at section boundary");
            Check(recoveries >= 5, "Lost create/start/answer/submit/next responses recovered");
            Check(panel.Navigation.Error == "", "Sequence identity remains verified");
            Result = "PASS: " + passed.Count + " task navigation checks; " + recoveries + " lost acknowledgements recovered"; Save(); Debug.Log(Result);
        }
    }
}
#endif
