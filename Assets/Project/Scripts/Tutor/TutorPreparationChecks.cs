#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace IAI.Tutor
{
    /// <summary>Explicit synthetic fixture on 8773. No microphone or cloud calls.</summary>
    public sealed class TutorPreparationChecks : MonoBehaviour
    {
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-preparation-unity"));
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllLines(Path.Combine(Folder, "checks.txt"), passed.Concat(new[] { Result })); }
        void Check(bool ok, string message)
        { if (!ok) { Result = "FAIL: " + message; Save(); throw new Exception(Result); } passed.Add(message); }
        IEnumerator Wait(Func<bool> predicate, string message)
        {
            float end = Time.realtimeSinceStartup + 25;
            while (!predicate() && Time.realtimeSinceStartup < end) yield return null;
            Check(predicate(), message);
        }
        IEnumerator Idle()
        {
            yield return null;
            yield return Wait(() => !client.Busy && !client.UnknownOutcome, "Command acknowledged");
            Check(client.Error == "", "No command error");
        }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            Check(client && panel && !client.Connected, "Fresh comparison and real panel");
            client.endpoint = "http://127.0.0.1:8773"; client.requirePreparation = true;
            client.Connect(); yield return Idle();
            Check(client.PreparationPending && client.CanPrepare && panel.CurrentTab == 1, "Preparation opens Controls");
            Check(panel.ConfirmPreparationButton.gameObject.activeInHierarchy && panel.ConfirmPreparationButton.interactable, "Shared confirmation is available");
            Check(panel.StrategyButtons.All(b => !b.gameObject.activeSelf), "Strategy selectors hidden during shared preparation");
            Check(client.View.settings.voice == "voice_d", "Default Voice D retained");
            Check(panel.RateSlider.interactable && panel.LengthSlider.interactable && panel.ToneButtons.All(b => b.interactable) && panel.VoiceButtons.All(b => b.interactable), "All four shared controls available");
            Check(!client.CanSubmit && !panel.Speech.CanRecord && !client.CanUndoSetting("voice"), "Dialogue and branch undo blocked before confirmation");
            client.SubmitUserUtterance("Must not be sent");
            Check(!client.Busy && string.IsNullOrEmpty(client.State.initial_query), "Premature dialogue is not sent");
            panel.VoiceButtons[1].onClick.Invoke(); yield return Idle();
            panel.ToneButtons[1].onClick.Invoke(); yield return Idle();
            client.SetSpeechRate(.9f); yield return Idle();
            client.SetReplyLength(0); yield return Idle();
            Check(client.State.baseline.settings.voice == "voice_b" && client.View.settings.tone == "friendly" && Mathf.Abs(client.View.settings.speech_rate - .9f) < .001f && client.View.settings.reply_length == "brief", "Four edits update shared baseline");
            Check(!client.State.results_visible && TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).result == null), "Preparation exposes no strategy results");
            client.SetVoice(2); yield return Idle();
            panel.SampleButton.onClick.Invoke();
            yield return Wait(() => panel.Playback.Loading, "Delayed sample requested");
            client.SetVoice(1); yield return Idle();
            yield return new WaitForSecondsRealtime(2);
            Check(!panel.Playback.Active, "Changing shared settings discards stale sample");
            panel.SampleButton.onClick.Invoke();
            yield return Wait(() => panel.Playback.Playing, "Current shared sample plays through real audio component");
            client.PauseOrResume(); yield return Idle();
            Check(client.Paused && !client.CanPrepare && !panel.ConfirmPreparationButton.interactable && !panel.RateSlider.interactable, "Pause locks preparation and confirmation");
            yield return Wait(() => !panel.Playback.Active, "Pause stops sample");
            client.PauseOrResume(); yield return Idle();
            Check(client.CanPrepare && panel.CurrentTab == 1, "Resume restores preparation without resetting settings");
            yield return Wait(() => TutorPlaybackOutbox.Instance.PendingCount == 0 && TutorPlaybackOutbox.Instance.Error == "", "Preparation playback reports acknowledged");
            panel.SampleButton.onClick.Invoke();
            yield return Wait(() => panel.Playback.Playing, "Shared sample can be replayed");
            panel.ConfirmPreparationButton.onClick.Invoke(); yield return Idle();
            Check(client.State.preparation_confirmed && !client.PreparationPending && panel.CurrentTab == 0, "Confirmation opens Conversation");
            Check(!panel.Playback.Active && !client.CanEdit && client.CanSubmit && panel.Speech.CanRecord, "Confirmed baseline locked; voice input enabled");
            Check(panel.StrategyButtons.All(b => b.gameObject.activeSelf), "Four strategies available after confirmation");
            client.SetVoice(0); Check(!client.Busy && client.View.settings.voice == "voice_b", "Confirmed baseline cannot be silently edited");
            client.SubmitUserUtterance("Compare an easier explanation."); yield return Idle();
            yield return Wait(() => TutorComparisonClient.Conditions.Any(c => client.State.branches.Get(c).status == "awaiting_clarification"), "Clarification appears after shared request");
            Check(!client.State.results_visible, "Original result reveal barrier remains enforced");
            foreach (string condition in new[] { "A", "S" })
            {
                yield return Wait(() => TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing" && client.State.branches.Get(c).status != "idle"), "Wait for background commits before strategy selection");
                yield return Wait(() => client.State.branches.Get(condition).status != "processing" && client.State.branches.Get(condition).status != "idle", "Branch reaches clarification or settled state");
                if (client.State.branches.Get(condition).status != "awaiting_clarification") continue;
                client.Select(condition); yield return Idle();
                client.ChooseOption("c1"); yield return Idle();
            }
            yield return Wait(() => client.State.results_visible, "Results reveal only after clarification replies");
            Check(TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).result.state.settings.voice == "voice_b" && client.State.branches.Get(c).result.state.settings.tone == "friendly" && Mathf.Abs(client.State.branches.Get(c).result.state.settings.speech_rate - .9f) < .001f), "All four branches retain the shared starting voice, tone and rate");
            Check(client.State.baseline.settings.reply_length == "brief" && client.CanEditBranch, "Common baseline retained; post-result controls remain branch-specific");
            client.Close(); yield return Idle();
            yield return Wait(() => TutorPlaybackOutbox.Instance.PendingCount == 0 && TutorPlaybackOutbox.Instance.Error == "", "All playback reports acknowledged");
            Check(!client.CanEdit && !client.CanSubmit, "Closed task cannot edit or record");
            Result = "PASS: " + passed.Count + " shared preparation checks"; Save();
            Debug.Log(Result);
        }
    }
}
#endif
