#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    // Engineering-only checks against a bounded localhost service, not a study UI.
    public sealed class TutorComparisonAcceptanceChecks : MonoBehaviour
    {
        [Serializable] class ServerStatus { public string output, mode; public int provider_attempts; }
        [Serializable] class Fault { public string fault, operation, task_id; public int revision; }
        public bool live;
        public string Result { get; private set; } = "RUNNING";
        TutorComparisonClient client;
        TutorPanel panel;
        string folder, response;
        bool hiddenLeak;
        int minimumRevision = -1;
        bool rollback;
        readonly List<string> passed = new List<string>();
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            if (!client || !panel || client.endpoint != "http://127.0.0.1:8769") throw new InvalidOperationException("Explicit comparison acceptance endpoint required.");
            yield return Http("/engineering/status");
            var server = JsonUtility.FromJson<ServerStatus>(response);
            folder = server.output;
            Check(server.mode == (live ? "live" : "mock"), "Explicit acceptance mode matches server");
            client.Changed += Observe;
            client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.feedbackVersion = "task-feedback-q1-q7-v1"; client.Connect(); yield return Idle();
            Check(client.Connected && client.State.mode == server.mode, "Unity comparison connects through actual HTTP");
            if (live) yield return Live(); else yield return Faults();
            Check(!hiddenLeak, "Every observed pre-reveal UI state used the common baseline");
            Result = "PASS: " + passed.Count + " behavioral checks";
            Save(); Debug.Log("TUTOR_COMPARISON_ACCEPTANCE " + Result);
        }
        void OnDestroy() { if (client) client.Changed -= Observe; }
        void Observe()
        {
            if (!client.Connected) return;
            if (minimumRevision >= 0 && client.State.revision < minimumRevision) rollback = true;
            if (!client.State.results_visible)
                hiddenLeak |= JsonUtility.ToJson(client.View.settings) != JsonUtility.ToJson(client.State.baseline.settings)
                    || client.View.conversation.Length != client.State.baseline.conversation.Length
                    || client.View.changes.Length != client.State.baseline.changes.Length
                    || TutorComparisonClient.Conditions.Any(c => client.State.branches.Get(c).result != null);
        }
        IEnumerator Live()
        {
            client.SubmitUserUtterance("From now on, give only the key answer without supporting reasons or examples. What is active recall?");
            yield return Idle(); yield return Settled();
            Check(!client.State.results_visible && client.State.branches.A.status == "awaiting_clarification", "Always-ask waits while first results stay hidden");
            Check(client.State.branches.E.status == "waiting" && client.State.branches.S.status == "waiting", "Clear request completes E and S before clarification is answered");
            Capture("01-clear-hidden");
            client.PauseOrResume(); yield return Idle();
            Check(client.Paused && !client.State.results_visible && !client.CanSubmit, "Pausing real-model comparison does not publish early results");
            client.PauseOrResume(); yield return Idle();
            foreach (string c in TutorComparisonClient.Conditions)
            {
                if (client.State.branches.Get(c).status != "awaiting_clarification") continue;
                yield return Select(c);
                if (c == "A") client.SubmitUserUtterance("Yes, use only the key answer from now on, without extra reasons or examples.");
                else client.ChooseOption(client.View.question.options.First(o => o.id != "other" && o.id != "cancel").id);
                yield return Idle(); yield return Settled();
            }
            Check(client.State.results_visible, "All real-model branches reveal only after actual clarifications resolve");
            foreach (string c in TutorComparisonClient.Conditions)
            {
                var result = client.State.branches.Get(c).result;
                Check(result.state.settings.reply_length == "brief" && result.state.conversation.Length == 1, c + " independently records the requested Brief answer");
            }
            yield return Select("A");
            Check(panel.DisplayedConversation.Contains(client.View.conversation[0].messages[1].content), "Unity displays the actual model-generated answer");
            Capture("02-clear-revealed"); Snapshot("clear-first");
            string first = client.State.first_reveal.reveal_id;
            yield return Select("E"); client.SetReplyLength(2); yield return Idle(); yield return Settled();
            client.SubmitUserUtterance("Why is that useful when studying?"); yield return Idle(); yield return Settled();
            Check(client.View.conversation.Length == 2 && client.View.conversation.Last().settings.reply_length == "detailed", "E follow-up uses Detailed and its own prior conversation");
            Check(client.State.branches.S.result.state.conversation.Length == 1 && client.State.branches.S.result.state.settings.reply_length == "brief", "Repair does not contaminate S history or settings");
            Check(client.State.first_reveal.reveal_id == first, "First reveal stays fixed during later real-model repair");
            Capture("03-branch-repair"); Snapshot("clear-repaired");
            yield return SubmitEngineeringFeedback();
            string oldTask = client.State.task_id;
            client.AdvanceToTask("{\"task_code\":\"LIVE-AMBIGUITY\",\"domain\":\"reply_length\",\"scenario\":\"C3\",\"settings\":{\"reply_length\":\"detailed\"}}");
            yield return Idle();
            Check(client.State.task_id != oldTask && client.View.settings.reply_length == "detailed" && client.View.conversation.Length == 0, "Next real-model task uses an explicit independent baseline");
            client.SubmitUserUtterance("Make the reply easier to follow. I have not decided whether I want just the key point or a fuller explanation with an example. Explain spaced repetition.");
            yield return Idle(); yield return Settled();
            Check(!client.State.results_visible && client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification", "Materially competing structures cause A and S to ask without revealing E");
            string firstChoice = null, secondChoice = null;
            yield return Select("A");
            var choices = client.View.question.options.Where(o => o.id != "other" && o.id != "cancel").ToArray();
            Check(choices.Length >= 2, "Real interpretation provides distinct shared choices");
            firstChoice = choices[0].id; secondChoice = choices[1].id;
            string aQuestion = client.View.question.question_id;
            client.ChooseOption(firstChoice); yield return Idle(); yield return Settled();
            Check(!client.State.results_visible, "A completed answer remains hidden until S is answered");
            yield return Select("S");
            Check(client.View.question.question_id != aQuestion, "A and S have independent clarification identities");
            client.ChooseOption(secondChoice); yield return Idle(); yield return Settled();
            if (client.State.branches.N.status == "awaiting_clarification")
            { yield return Select("N"); client.ChooseOption(firstChoice); yield return Idle(); yield return Settled(); }
            Check(client.State.results_visible && client.State.branches.A.result.state.settings.reply_length != client.State.branches.S.result.state.settings.reply_length, "Different clarification choices produce independently generated structures");
            yield return Select("S");
            Check(client.View.conversation.Length == 1 && panel.DisplayedConversation.Contains(client.View.conversation[0].messages[1].content), "Second-task answer reaches the selected Unity panel");
            Capture("04-ambiguity-revealed"); Snapshot("ambiguity-final");
            client.Close(); yield return Idle();
            Check(client.State.lifecycle == "aborted" && string.IsNullOrEmpty(client.State.submission_id), "Exit without engineering ratings is separate from submission");
            yield return Http("/engineering/status");
            Check(JsonUtility.FromJson<ServerStatus>(response).provider_attempts <= 14, "Hard live-provider attempt budget respected");
        }
        IEnumerator Faults()
        {
            client.SubmitUserUtterance("Use key points from now on. What is active recall?"); yield return Idle(); yield return Settled();
            yield return Select("A"); client.ChooseOption("c1"); yield return Idle(); yield return Settled();
            Check(client.State.results_visible && client.View.settings.reply_length == "brief", "Fixture comparison fully revealed before recovery checks");
            yield return Arm("malformed", "settings");
            client.SetReplyLength(2); yield return Idle(false);
            Check(client.UnknownOutcome && !client.CanEdit && client.CanRetry, "Malformed successful response is treated as unknown");
            yield return Wait(() => client.View.settings.reply_length == "detailed", "Poll recovers committed setting", 10);
            Check(client.UnknownOutcome, "Polling does not clear uncertain command");
            yield return Settled(); int changes = client.View.changes.Length;
            client.Retry(); yield return Idle(); yield return Settled();
            Check(!client.UnknownOutcome && client.View.changes.Length == changes, "Exact retry does not repeat committed modification");
            int oldRevision = client.State.revision;
            client.SetReplyLength(1); yield return Idle(); yield return Settled();
            minimumRevision = client.State.revision;
            yield return Arm("stale", "view", oldRevision);
            yield return new WaitForSecondsRealtime(1.7f);
            Check(!rollback && client.State.revision >= minimumRevision && client.View.settings.reply_length == "balanced", "Old snapshot never replaces newer comparison state");
            minimumRevision = -1;
            yield return Arm("delay", "settings");
            client.SetReplyLength(0); client.SetReplyLength(2);
            yield return new WaitForSecondsRealtime(.3f);
            client.enabled = false;
            Check(client.UnknownOutcome && !client.Busy, "Component interruption preserves pending request identity");
            client.enabled = true;
            yield return new WaitForSecondsRealtime(2.3f);
            yield return Settled(); changes = client.View.changes.Length;
            client.Retry(); yield return Idle(); yield return Settled();
            Check(!client.UnknownOutcome && client.View.settings.reply_length == "brief" && client.View.changes.Length == changes, "Re-enabled client recovers once and rejects a concurrent second edit");
            Snapshot("fault-final"); Capture("fault-recovered");
            client.Close(); yield return Idle();
        }
        IEnumerator SubmitEngineeringFeedback()
        {
            foreach (string c in TutorComparisonClient.Conditions)
            {
                yield return Select(c);
                client.SaveFeedback("{\"completion\":\"unable_to_judge\",\"ratings\":{\"q2\":\"unable_to_judge\",\"q3\":\"unable_to_judge\",\"q4\":\"unable_to_judge\",\"q5\":\"unable_to_judge\",\"q6\":\"unable_to_judge\",\"q7\":\"unable_to_judge\"}}");
                yield return Idle();
            }
            Check(client.State.can_submit, "Synthetic engineering feedback binds to current result versions");
            client.SubmitTask(); yield return Idle();
            Check(client.State.lifecycle == "submitted", "Submission closes and freezes the first comparison");
        }
        IEnumerator Select(string c)
        { client.Select(c); yield return Idle(); if (client.Selected != c) Fail("Strategy selection failed: " + c); }
        IEnumerator Idle(bool requireSuccess = true)
        {
            yield return Wait(() => !client.Busy, "HTTP command timeout", 30);
            if (requireSuccess && (!string.IsNullOrEmpty(client.Error) || client.UnknownOutcome)) Fail("HTTP recovery required: " + client.Error);
            yield return null;
        }
        IEnumerator Settled()
        {
            yield return Wait(() => TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing" && client.State.branches.Get(c).status != "idle"), "Comparison processing timeout", 150);
            if (TutorComparisonClient.Conditions.Any(c => client.State.branches.Get(c).status == "failed")) Fail("A branch failed; no automatic paid retry. Inspect JSONL provider records.");
        }
        IEnumerator Wait(Func<bool> predicate, string error, float seconds)
        {
            float deadline = Time.realtimeSinceStartup + seconds;
            while (!predicate() && Time.realtimeSinceStartup < deadline) yield return null;
            if (!predicate()) Fail(error);
        }
        IEnumerator Arm(string fault, string operation, int revision = 0)
        { yield return Http("/engineering/arm", JsonUtility.ToJson(new Fault { fault = fault, operation = operation, task_id = client.State.task_id, revision = revision })); }
        IEnumerator Http(string path, string json = null)
        {
            using (var request = new UnityWebRequest(client.endpoint + path, json == null ? "GET" : "POST"))
            {
                request.downloadHandler = new DownloadHandlerBuffer(); request.timeout = 10;
                if (json != null) { request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)); request.SetRequestHeader("Content-Type", "application/json"); }
                yield return request.SendWebRequest(); response = request.downloadHandler.text;
                if (request.result != UnityWebRequest.Result.Success) Fail("Acceptance control request failed: " + path);
            }
        }
        void Check(bool condition, string description) { if (!condition) Fail(description); passed.Add(description); }
        void Fail(string message) { Result = "FAIL: " + message; Save(); throw new InvalidOperationException("TUTOR_COMPARISON_ACCEPTANCE " + Result); }
        void Save()
        {
            if (string.IsNullOrEmpty(folder)) return;
            Directory.CreateDirectory(folder); File.WriteAllText(Path.Combine(folder, "checks.txt"), Result + "\n" + string.Join("\n", passed));
            Snapshot("unity-final");
        }
        void Snapshot(string name)
        { Directory.CreateDirectory(folder); File.WriteAllText(Path.Combine(folder, name + ".json"), JsonUtility.ToJson(client.State, true)); }
        void Capture(string name)
        {
            Canvas.ForceUpdateCanvases(); Directory.CreateDirectory(folder);
            var camera = Camera.main; var old = camera.targetTexture; var previous = RenderTexture.active;
            var target = new RenderTexture(1600, 1000, 24); camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            var image = new Texture2D(1600, 1000, TextureFormat.RGB24, false); image.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(folder, name + ".png"), image.EncodeToPNG());
            camera.targetTexture = old; RenderTexture.active = previous; Destroy(image); target.Release(); Destroy(target);
        }
    }
}
#endif
