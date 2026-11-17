#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace IAI.Tutor
{
    public sealed class TutorSpeechChecks : MonoBehaviour
    {
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        TutorSpeechInput speech;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-speech-unity"));
        void Check(bool ok, string message)
        {
            if (!ok) { Result = "FAIL: " + message; Save(); throw new Exception(Result); }
            passed.Add(message);
        }
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllLines(Path.Combine(Folder, "checks.txt"), passed.Concat(new[] { Result })); }
        IEnumerator Wait(Func<bool> predicate, string message)
        {
            float until = Time.realtimeSinceStartup + 12;
            while (!predicate() && Time.realtimeSinceStartup < until) yield return null;
            Check(predicate(), message);
        }
        byte[] Wav(float marker = 0) => TutorSpeechInput.EncodeWav(Enumerable.Repeat(marker, 8000).ToArray(), 1, 16000);
        IEnumerator Recognize(float marker)
        {
            speech.RecognizeFixture(Wav(marker));
            yield return Wait(() => !speech.Working, "Recognition request finishes");
        }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>(); speech = panel.Speech;
            panel.OpenTab(0); panel.desktopDebugInput = false; panel.Render();
            Check(panel.DebugInput.readOnly && !panel.SendButton.interactable, "VR transcript is read-only and cannot send while disconnected");
            byte[] stereo = TutorSpeechInput.EncodeWav(new[] { 1f, -1f, .5f, .5f }, 2, 16000);
            Check(stereo.Length == 48 && BitConverter.ToInt16(stereo, 44) == 0 && BitConverter.ToInt16(stereo, 46) > 16000, "PCM16 WAV mixes stereo to mono with a valid header");
            client.endpoint = "http://127.0.0.1:8772"; client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.Connect();
            yield return Wait(() => client.Connected && !client.Busy, "Connect to explicit synthetic speech fixture");
            yield return Recognize(0);
            Check(speech.Transcript == "Compare an easier explanation." && panel.DebugInput.text == speech.Transcript, "Recognized text appears for review");
            Check(client.State.phase == "awaiting_input" && speech.CanSend && panel.SendButton.interactable, "Review does not submit or run four branches");
            yield return new WaitForEndOfFrame();
            Directory.CreateDirectory(Folder); ScreenCapture.CaptureScreenshot(Path.Combine(Folder, "transcript-review.png"));
            yield return new WaitForEndOfFrame();
            panel.SendButton.onClick.Invoke();
            yield return Wait(() => !client.Busy && client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification" && TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing"), "One initial transcript starts all four strategies");
            Check(!client.State.results_visible && client.State.initial_query == "Compare an easier explanation.", "Shared initial input respects reveal barrier");
            client.Select("A"); yield return Wait(() => !client.Busy && client.Selected == "A", "Select asking branch A");
            string siblingQuestion = client.State.branches.S.question.question_id;
            yield return Recognize(.25f);
            Check(speech.CanSend && client.HasQuestion, "Clarification transcript waits for explicit Send");
            speech.Submit();
            yield return Wait(() => !client.Busy && client.State.branches.A.status == "waiting", "Spoken clarification resolves only A");
            Check(!client.State.results_visible && client.State.branches.S.question.question_id == siblingQuestion, "S question remains unchanged and results remain hidden");
            client.Select("S"); yield return Wait(() => !client.Busy && client.Selected == "S", "Select asking branch S");
            speech.RecognizeFixture(Wav(.75f)); yield return new WaitForSeconds(.15f);
            client.Select("E");
            yield return Wait(() => !client.Busy && client.Selected == "E" && !speech.HasCapture, "Switching strategy cancels an in-flight recording");
            yield return new WaitForSeconds(1.7f);
            Check(speech.Transcript == "" && !speech.CanSend && client.State.branches.S.question.question_id == siblingQuestion, "Late STT cannot answer a different branch");
            client.Select("S"); yield return Wait(() => !client.Busy && client.Selected == "S", "Return to S");
            yield return Recognize(.25f);
            client.PauseOrResume(); yield return Wait(() => client.Paused && !client.Busy && !speech.HasCapture, "Pause discards reviewed text");
            client.PauseOrResume(); yield return Wait(() => !client.Paused && !client.Busy, "Resume does not restore old recording");
            Check(speech.Transcript.Length == 0, "Paused transcript stays discarded");
            yield return Recognize(.25f); panel.OpenTab(1);
            Check(!speech.HasCapture && !speech.CanSend, "Leaving Conversation clears reviewed text");
            panel.OpenTab(0); yield return Recognize(.25f); speech.Submit();
            yield return Wait(() => !client.Busy && client.State.results_visible, "Final clarification releases all results together");
            Check(!client.View.audio_available, "Input integration does not falsely claim TTS playback");
            Result = "PASS: " + passed.Count + " checks (synthetic audio; no real microphone/provider calls)"; Save();
            Debug.Log(Result);
        }
    }
}
#endif
