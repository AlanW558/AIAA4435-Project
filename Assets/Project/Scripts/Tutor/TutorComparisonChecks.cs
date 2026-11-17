#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;

namespace IAI.Tutor
{
    /// <summary>Play-mode HTTP and rendered-panel acceptance, explicit fixture only.</summary>
    public sealed class TutorComparisonChecks : MonoBehaviour
    {
        TutorComparisonClient client;
        TutorPanel panel;
        readonly List<string> passed = new List<string>();
        public string Result { get; private set; } = "running";
        string Folder => Path.Combine(Application.dataPath, "../StudyData/macos/tutor-comparison-unity");
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            Check(client && panel && client.endpoint == "http://127.0.0.1:8768", "Explicit comparison fixture endpoint");
            client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.feedbackVersion = "task-feedback-q1-q7-v1"; client.Connect(); yield return Idle();
            Check(client.UnknownOutcome && client.CanRetry && !client.Connected, "Lost create response retains a retryable create ID");
            client.Retry(); yield return Idle();
            Check(client.Connected && !client.UnknownOutcome && client.State.mode == "mock", "Exact create replay recovers comparison");
            Check(panel.StrategyButtons.Length == 4 && panel.DisplayedLength == "Balanced", "Four strategy buttons and shared baseline rendered");
            panel.DebugInput.text = "Compare an easier explanation."; panel.SendButton.onClick.Invoke(); yield return Idle();
            Check(client.UnknownOutcome && !panel.SendButton.interactable, "Lost start response blocks duplicate user submission");
            client.Retry(); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification" && client.State.branches.E.status == "waiting", "Initial branches settled");
            Hidden("E completed while A and S still ask");
            Check(!panel.LengthSlider.interactable && !panel.UndoButton.interactable && !client.CanSubmit, "Initial barrier disables controls, undo and E follow-ups");
            client.SetReplyLength(2); client.SubmitUserUtterance("Why does it help?");
            Check(!client.Busy && client.View.settings.reply_length == "balanced", "Direct public entry points also enforce barrier");
            panel.OpenTab(1); yield return new WaitForSeconds(.2f); Capture("01-baseline-controls"); panel.OpenTab(2);
            Check(!panel.DisplayedHistory.Contains("REPLY LENGTH"), "History does not leak hidden commits");
            yield return Select("A"); panel.OpenTab(0);
            Check(client.HasQuestion && panel.OptionButtons.Length >= 4, "A clarification is independently selectable");
            string question = client.View.question.question_id;
            panel.PauseButton.onClick.Invoke(); yield return Idle();
            Check(client.Paused && !client.HasQuestion && !client.CanEdit && !panel.SendButton.interactable && panel.CloseButton.interactable, "Pause blocks interaction but permits exit without feedback");
            yield return new WaitForSeconds(.2f); Capture("06-paused");
            panel.PauseButton.onClick.Invoke(); yield return Idle();
            Check(!client.Paused && client.View.question.question_id == question, "Resume preserves original unanswered clarification");
            yield return new WaitForSeconds(.2f); Capture("02-clarification");
            panel.OptionButtons.First(b => b.name == "Option c2").onClick.Invoke(); yield return Idle();
            Check(client.UnknownOutcome, "Lost answer response retains original branch and question");
            client.RefreshState(); yield return new WaitForSeconds(.8f);
            Check(client.UnknownOutcome && client.CanRetry, "Polling does not erase uncertain mutation");
            client.Retry(); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "waiting", "A answer completed");
            Hidden("A completed but S is still asking");
            yield return Select("S");
            panel.DebugInput.text = "Yes, use the first option."; panel.SendButton.onClick.Invoke(); yield return Idle();
            yield return Wait(() => client.State.results_visible, "All four results revealed together");
            Check(!client.HasQuestion && panel.DisplayedLength == "Brief" && panel.DisplayedConversation.Contains("Active recall means"), "STT-compatible text entry resolves S and reveals actual answer");
            Check(!panel.DisplayedConversation.Contains("For example"), "S Brief answer omits optional components");
            string reveal = client.State.first_reveal.reveal_id;
            yield return Select("A");
            Check(panel.DisplayedLength == "Detailed" && panel.DisplayedConversation.Contains("For example"), "A independently shows Detailed answer after reveal");
            Capture("03-revealed-conversation");
            yield return Select("E"); panel.OpenTab(1);
            panel.LengthSlider.GetComponent<TutorLengthCommit>().OnPointerDown(new PointerEventData(EventSystem.current));
            panel.LengthSlider.value = 2;
            yield return new WaitForSeconds(1.2f);
            Check(panel.LengthSlider.value == 2 && panel.DisplayedLength.Contains("release to apply") && client.View.settings.reply_length == "brief", "Background polling preserves an uncommitted slider drag");
            panel.LengthSlider.GetComponent<TutorLengthCommit>().OnPointerUp(new PointerEventData(EventSystem.current)); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready" && panel.DisplayedLength == "Detailed", "E control repair completes");
            Check(client.State.branches.S.result.state.settings.reply_length == "brief", "E repair does not change S");
            Capture("04-revealed-controls"); panel.OpenTab(2);
            panel.UndoButton.onClick.Invoke(); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready" && panel.DisplayedLength == "Brief", "E undo completes");
            Check(panel.DisplayedHistory.Contains("UNDO") && client.State.first_reveal.reveal_id == reveal, "Undo history updates while first reveal ID stays fixed");
            Capture("05-history");
            panel.OpenTab(0); int exchanges = client.View.conversation.Length;
            client.SubmitUserUtterance("Test a recoverable generation failure."); yield return Idle();
            yield return Wait(() => client.Branch.status == "failed", "Generation failure becomes visible");
            Check(client.CanRetry && client.View.conversation.Length == exchanges && panel.StopButton.interactable, "Failed generation offers retry or explicit stop without fake reply");
            panel.RetryButton.onClick.Invoke(); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready" && client.View.conversation.Length == exchanges + 1, "Retry completes one new exchange");
            yield return Select("A"); client.SubmitUserUtterance("Make the explanation easier."); yield return Idle();
            yield return Wait(() => client.HasQuestion, "Post-reveal clarification shown");
            panel.StopButton.onClick.Invoke(); yield return Idle();
            Check(client.Branch.result.outcome == "incomplete" && !client.HasQuestion, "Explicit stop records incomplete");
            Check(!client.State.can_submit, "Missing feedback prevents submission");
            string rating = "{\"completion\":\"unable_to_judge\",\"ratings\":{\"q2\":4,\"q3\":\"unable_to_judge\",\"q4\":5,\"q5\":2,\"q6\":4,\"q7\":6}}";
            foreach (string c in TutorComparisonClient.Conditions)
            {
                if (client.Selected != c) yield return Select(c);
                client.SaveFeedback(rating); yield return Idle();
                Check(client.State.feedback.Get(c).current && client.State.feedback.Get(c).complete, "Current structured feedback saved for " + c);
            }
            Check(client.State.can_submit, "All four current Q1–Q7 drafts enable submission");
            yield return Select("E"); client.SetReplyLength(2); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready", "Post-feedback repair completes");
            Check(!client.State.can_submit && !client.State.feedback.E.current && client.State.feedback.A.current, "Repair invalidates E feedback only");
            client.SaveFeedback(rating); yield return Idle();
            string priorTask = client.State.task_id;
            client.SubmitTask(); yield return Idle();
            Check(client.UnknownOutcome && client.CanRetry, "Lost submission response remains recoverable");
            client.Retry(); yield return Idle();
            Check(client.State.lifecycle == "submitted" && !string.IsNullOrEmpty(client.State.submission_id) && !client.CanEdit, "Submission freezes evaluated results");
            // Defense in depth: even an unexpected hidden result in a response
            // cannot escape the projection into settings, history or avatar.
            var injected = JsonUtility.FromJson<ComparisonView>(JsonUtility.ToJson(client.State));
            injected.results_visible = false;
            injected.branches.Get(injected.selected_condition).result.state.settings.avatar_id = "nailong";
            var projection = TutorComparisonClient.Project(injected);
            Check(projection.settings.avatar_id == injected.baseline.settings.avatar_id && projection.changes.Length == injected.baseline.changes.Length && projection.conversation.Length == injected.baseline.conversation.Length, "Projection rejects hidden result values across appearance, history and conversation");
            client.AdvanceToTask("{\"task_code\":\"UNITY-NEXT\",\"domain\":\"reply_length\",\"scenario\":\"C2\",\"settings\":{\"reply_length\":\"detailed\"}}"); yield return Idle();
            Check(client.UnknownOutcome && client.State.task_id == priorTask, "Lost next response cannot silently switch task");
            client.Retry(); yield return Idle();
            Check(client.State.task_id != priorTask && client.State.previous_task_id == priorTask && client.State.sequence_index == 2, "Next replay follows exactly one new linked task");
            Check(panel.DisplayedLength == "Detailed" && client.View.conversation.Length == 0 && !client.State.results_visible && client.State.feedback.E.feedback_revision == 0, "New task accepts a partial explicit baseline and resets conversation and feedback");
            panel.PauseButton.onClick.Invoke(); yield return Idle();
            panel.CloseButton.onClick.Invoke(); yield return Idle();
            Check(client.State.lifecycle == "aborted" && string.IsNullOrEmpty(client.State.submission_id) && !panel.SendButton.interactable && panel.StrategyButtons.All(b => !b.interactable), "Exit while paused needs no questionnaire and is not a submission");
            Result = "PASS: " + passed.Count + " checks"; Save(); Debug.Log("TUTOR_COMPARISON_CHECKS " + Result);
        }
        IEnumerator Select(string c)
        {
            panel.StrategyButtons[Array.IndexOf(TutorComparisonClient.Conditions, c)].onClick.Invoke(); yield return Idle();
            Check(client.Selected == c, "Selected " + c);
        }
        IEnumerator Idle()
        {
            yield return null;
            yield return Wait(() => !client.Busy, "HTTP command completed");
        }
        IEnumerator Wait(Func<bool> predicate, string label)
        {
            float deadline = Time.realtimeSinceStartup + 20;
            while (!predicate() && Time.realtimeSinceStartup < deadline) yield return null;
            Check(predicate(), label); yield return null;
        }
        void Hidden(string label)
        {
            Check(!client.State.results_visible && client.State.first_reveal == null && panel.DisplayedLength == "Balanced"
                && !panel.DisplayedConversation.Contains("Active recall means") && client.View.changes.Length == 0
                && TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).result == null), label + ": baseline only");
        }
        void Check(bool okay, string label)
        {
            if (!okay) { Result = "FAIL: " + label; Save(); throw new InvalidOperationException("TUTOR_COMPARISON_CHECK_FAILED: " + label); }
            passed.Add(label);
        }
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllText(Path.Combine(Folder, "checks.txt"), Result + "\n" + string.Join("\n", passed)); }
        void Capture(string name)
        {
            Canvas.ForceUpdateCanvases(); Directory.CreateDirectory(Folder);
            var camera = Camera.main; var old = camera.targetTexture; var previous = RenderTexture.active;
            var target = new RenderTexture(1600, 1000, 24); camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            var image = new Texture2D(1600, 1000, TextureFormat.RGB24, false); image.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(Folder, name + ".png"), image.EncodeToPNG());
            camera.targetTexture = old; RenderTexture.active = previous; Destroy(image); target.Release(); Destroy(target);
        }
    }
}
#endif
