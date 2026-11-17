#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    public sealed class TutorPlaybackChecks : MonoBehaviour
    {
        [Serializable] class AuditState
        { public int started, stopped, completed, failed, events, unique_events, feedback_count, submission_count; public bool bound_correctly, lost_ack; public string[] reply_conditions; }
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        TutorAudioPlayback audio;
        AuditState audit;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-playback-unity"));
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllLines(Path.Combine(Folder, "checks.txt"), passed.Concat(new[] { Result })); }
        void Check(bool ok, string message)
        { if (!ok) { Result = "FAIL: " + message; Save(); throw new Exception(Result); } passed.Add(message); }
        IEnumerator Wait(Func<bool> predicate, string message)
        {
            float until = Time.realtimeSinceStartup + 20;
            while (!predicate() && Time.realtimeSinceStartup < until) yield return null;
            Check(predicate(), message);
        }
        IEnumerator Flush() { yield return Wait(() => TutorPlaybackOutbox.Instance.PendingCount == 0 && TutorPlaybackOutbox.Instance.Error == "", "Playback outbox acknowledged and empty"); }
        IEnumerator Audit(string id)
        {
            using (var r = UnityWebRequest.Get("http://127.0.0.1:8774/fixture/playback-state/" + id))
            { r.timeout = 5; yield return r.SendWebRequest(); Check(r.result == UnityWebRequest.Result.Success, "Read fixture audit summary"); audit = JsonUtility.FromJson<AuditState>(r.downloadHandler.text); }
        }
        IEnumerator Recognize(float marker)
        {
            panel.Speech.RecognizeFixture(TutorSpeechInput.EncodeWav(Enumerable.Repeat(marker, 8000).ToArray(), 1, 16000));
            yield return Wait(() => !panel.Speech.Working && panel.Speech.CanSend, "Synthetic STT text ready for submission");
            panel.Speech.Submit(); yield return Wait(() => !client.Busy, "Recognized text submitted once");
        }
        IEnumerator Select(string condition)
        { client.Select(condition); yield return Wait(() => !client.Busy && client.Selected == condition, "Select " + condition); }
        IEnumerator PlayReply()
        { panel.OpenTab(0); panel.ReplyAudioButton.onClick.Invoke(); yield return Wait(() => audio.Playing, "Visible reply starts playback"); }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>(); audio = panel.Playback;
            client.endpoint = "http://127.0.0.1:8774"; client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.feedbackVersion = "task-feedback-q1-q7-v1"; client.Connect();
            yield return Wait(() => client.Connected && !client.Busy, "Connect to combined speech fixture");
            string original = client.State.task_id;
            panel.OpenTab(1); panel.SampleButton.onClick.Invoke(); yield return Wait(() => audio.Playing, "Baseline sample plays");
            yield return Wait(() => TutorPlaybackOutbox.Instance.Error.Length > 0, "Lost playback ACK is visible as pending delivery");
            audio.Stop(reason: "user_stop");
            var old = TutorPlaybackOutbox.Instance;
            Check(old.PendingCount == 2 && Directory.GetFiles(old.Folder, "*.json").Length == 2, "Start and stop remain on disk before retry");
            Destroy(old.gameObject); yield return null;
            var restored = TutorPlaybackOutbox.Instance;
            Check(restored.PendingCount == 2, "Fresh outbox instance reloads both durable reports");
            yield return Flush(); yield return Audit(original);
            Check(audit.started == 1 && audit.stopped == 1 && audit.events == audit.unique_events && audit.lost_ack, "Lost ACK retry records start and stop exactly once");
            panel.OpenTab(0); yield return Recognize(0);
            yield return Wait(() => client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification" && TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing"), "Initial spoken request reaches all four branches");
            Check(!client.State.results_visible && !audio.CanReply, "Hidden results cannot play while clarification is pending");
            yield return Select("A"); string sQuestion = client.State.branches.S.question.question_id;
            yield return Recognize(.25f); yield return Wait(() => client.Branch.status == "waiting", "A spoken clarification resolves");
            Check(!client.State.results_visible && client.State.branches.S.question.question_id == sQuestion, "A answer does not resolve S or reveal results early");
            yield return Select("S"); yield return Recognize(.25f);
            yield return Wait(() => client.State.results_visible && !client.Busy, "Final clarification reveals all strategies together");
            foreach (string condition in TutorComparisonClient.Conditions)
            {
                yield return Select(condition); yield return PlayReply();
                if (condition == "E") yield return Wait(() => !audio.Active && audio.Status.Contains("complete"), "Natural clip ending is recognized as completion");
                else if (condition == "N")
                {
                    client.PauseOrResume(); yield return Wait(() => client.Paused && !client.Busy && !audio.Active, "Pause stops and queues playback report");
                    client.PauseOrResume(); yield return Wait(() => !client.Paused && !client.Busy, "Resume keeps playback stopped");
                }
                else { yield return new WaitForSecondsRealtime(.2f); audio.Stop(reason: "user_stop"); }
                yield return Flush();
                client.SaveFeedback("{\"completion\":\"fully_met\",\"ratings\":{\"q2\":4,\"q3\":4,\"q4\":4,\"q5\":4,\"q6\":4,\"q7\":4},\"reasons\":[]}");
                yield return Wait(() => !client.Busy && client.State.feedback.Get(condition).complete, "Synthetic engineering feedback binds to " + condition);
            }
            yield return PlayReply();
            client.SubmitTask(); yield return Wait(() => client.State.lifecycle == "submitted" && !client.Busy && !audio.Active, "Task submission stops active audio");
            client.AdvanceToTask("{\"task_code\":\"PLAYBACK-NEXT\",\"domain\":\"tone\",\"scenario\":\"C1\"}");
            yield return Wait(() => client.State.task_id != original && !client.Busy, "Advance to next task while old audit delivery remains independent");
            yield return Flush(); yield return Audit(original);
            Check(audit.bound_correctly && audit.events == audit.unique_events, "All reports retain original audio and branch bindings without duplicate IDs");
            Check(audit.completed == 1 && audit.started == 6 && audit.stopped == 5 && audit.failed == 0, "Natural ending and five interruptions are counted separately");
            Check(audit.reply_conditions.SequenceEqual(new[] { "A", "E", "N", "S" }) && audit.feedback_count == 4, "All four reply strategies and four feedback drafts can be joined");
            Directory.CreateDirectory(Folder); File.WriteAllText(Path.Combine(Folder, "original-task.txt"), original);
            yield return Audit(client.State.task_id); Check(audit.events == 0, "Old reports never attach to the next task");
            Check(Directory.GetFiles(TutorPlaybackOutbox.Instance.Folder, "*.json").Length == 0, "Acknowledged local event files are removed");
            Result = "PASS: " + passed.Count + " checks (synthetic input, silent output and engineering feedback)"; Save(); Debug.Log(Result);
        }
    }
}
#endif
