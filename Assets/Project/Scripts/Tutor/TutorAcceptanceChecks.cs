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
    // Invoked explicitly against the local acceptance server; excluded from builds.
    public sealed class TutorAcceptanceChecks : MonoBehaviour
    {
        public bool live;
        public string Result { get; private set; } = "RUNNING";
        TutorClient client;
        TutorPanel panel;
        readonly List<string> passed = new List<string>();
        string response;
        string Folder => Path.Combine(Application.dataPath, "../StudyData/macos/tutor-acceptance/", live ? "live" : "fixture");
        IEnumerator Start()
        {
            client = FindObjectOfType<TutorClient>(); panel = FindObjectOfType<TutorPanel>();
            yield return Idle();
            Check(client.Connected && client.endpoint == "http://127.0.0.1:8767" && client.View.mode == (live ? "live" : "mock"), "Expected acceptance backend connected");
            if (live) yield return Live(); else yield return Faults();
            Result = "PASS: " + passed.Count + " behavioral checks"; Save(); Debug.Log("TUTOR_ACCEPTANCE " + Result);
        }
        IEnumerator Live()
        {
            yield return Ask("From now on, give only the key points. What is active recall?");
            Check(!client.HasQuestion && client.View.settings.reply_length == "brief" && client.View.conversation.Length == 1, "Clear mixed request applies Brief and generates an answer");
            Check(panel.DisplayedConversation.Contains(client.View.conversation[0].messages[1].content), "Unity displays the actual generated answer");
            yield return Ask("Why is that useful when studying?");
            Check(client.View.settings.reply_length == "brief" && client.View.conversation.Length == 2, "Follow-up retains Brief and extends conversation");
            client.SetReplyLength(2); yield return Idle();
            yield return Ask("What is active recall?");
            Check(client.View.conversation.Last().settings.reply_length == "detailed", "Detailed control reaches actual generation");
            client.SetReplyLength(1); yield return Idle();
            yield return Ask("What is active recall?");
            Check(client.View.conversation.Last().settings.reply_length == "balanced", "Balanced control reaches actual generation");
            client.SetReplyLength(2); yield return Idle();
            yield return Ask("For this answer only, give just the key points: what is active recall?");
            Check(client.View.settings.reply_length == "detailed" && client.View.conversation.Last().settings.reply_length == "brief", "Single-answer Brief leaves persistent Detailed unchanged");
            yield return Ask("How could I use that to study a biology topic?");
            Check(client.View.conversation.Last().settings.reply_length == "detailed", "Next answer returns to persistent Detailed");
            yield return Ask("Restore the reply length from immediately before my most recent slider change. Keep everything else unchanged.");
            Check(!client.HasQuestion && client.View.settings.reply_length == "balanced", "History reference restores the preceding Balanced setting");
            Check(client.View.settings.tone == "professional" && client.View.settings.speech_rate == 1 && client.View.settings.voice == "voice_d", "History restore preserves unrelated properties");
            yield return Ask("Make the replies easier to follow — perhaps just the key points, or perhaps more explanation and examples. I have not decided which.");
            Check(client.HasQuestion && client.View.settings.reply_length == "balanced", "Competing structures ask before changing settings");
            yield return Ask("I mean only the key points, from now on.");
            Check(!client.HasQuestion && client.View.settings.reply_length == "brief", "Natural-language clarification resolves the pending question");
            client.UndoReplyLength(); yield return Idle();
            Check(client.View.settings.reply_length == "balanced" && panel.DisplayedHistory.Contains("UNDO"), "Undo synchronizes history and current length");
        }
        IEnumerator Faults()
        {
            client.SetReplyLength(2); yield return Idle();
            yield return Ask("For this answer only, key points: what is active recall?");
            Check(client.View.settings.reply_length == "detailed" && client.View.conversation[0].settings.reply_length == "brief", "Single-turn override does not change persistent setting");
            yield return Ask("Why does it help?");
            Check(client.View.conversation[1].settings.reply_length == "detailed", "Follow-up returns to persistent setting");
            yield return Arm("drop", "settings");
            client.SetReplyLength(0); yield return Idle(false);
            Check(client.UnknownOutcome && !client.CanEdit && client.CanRetry, "Lost successful mutation response blocks new edits and allows replay");
            client.RefreshState(); yield return Idle();
            Check(client.View.settings.reply_length == "brief" && client.UnknownOutcome && client.CanRetry, "Sync sees committed change but preserves uncertain request");
            Check(panel.DisplayedStatus.Contains("Previous request"), "Sync keeps unresolved transport recovery visible in the panel");
            int changes = client.View.changes.Length;
            client.Retry(); yield return Idle();
            Check(!client.UnknownOutcome && client.View.changes.Length == changes && client.View.idempotent_replay, "Exact mutation replay does not create a second change");
            yield return Arm("malformed", "generate");
            client.SubmitUserUtterance("Why does it help?"); yield return Idle(false);
            Check(client.UnknownOutcome && client.View.conversation.Length == 2, "Invalid success response is treated as unknown, not a fabricated answer");
            client.RefreshState(); yield return Idle();
            Check(client.View.conversation.Length == 3 && client.UnknownOutcome, "Sync retrieves the completed answer while preserving replay requirement");
            client.Retry(); yield return Idle();
            Check(client.View.conversation.Length == 3 && !client.UnknownOutcome && client.View.idempotent_replay, "Completed generation replay writes no duplicate conversation");
            yield return Arm("delay", "settings");
            client.SetReplyLength(2); client.SetReplyLength(1); client.SubmitUserUtterance("Why does it help?"); yield return Idle();
            Check(client.View.settings.reply_length == "detailed" && client.View.conversation.Length == 3, "Busy client rejects concurrent UI submissions");
            yield return Ask("Make the explanation easier.");
            Check(client.HasQuestion, "Clarification exists before conflict injection");
            yield return Http("/tutor/sessions/" + client.View.session_id + "/reset", JsonUtility.ToJson(new TutorMutation {request_id=Guid.NewGuid().ToString("N"), expected_revision=client.View.revision}));
            client.ChooseOption("c1"); yield return Idle(false);
            Check(!string.IsNullOrEmpty(client.Error) && !client.HasQuestion && client.View.settings.reply_length == "balanced", "Stale clarification cannot overwrite reset state");
            client.RefreshState(); yield return Idle();
            Check(!client.HasQuestion && client.CanEdit, "Sync recovers from conflict without replaying stale choice");
            yield return Arm("delay", "settings");
            client.SetReplyLength(0); yield return new WaitForSecondsRealtime(.3f);
            client.enabled = false;
            Check(client.UnknownOutcome && !client.Busy, "Disabling during an in-flight mutation preserves uncertainty");
            client.enabled = true; yield return new WaitForSecondsRealtime(2.1f);
            client.RefreshState(); yield return Idle();
            changes = client.View.changes.Length;
            client.Retry(); yield return Idle();
            Check(client.View.settings.reply_length == "brief" && client.View.changes.Length == changes && !client.UnknownOutcome, "Re-enabled client safely replays interrupted request");
            yield return Ask("Change your voice.");
            Check(client.View.decision == "UNRESOLVED" && panel.DisplayedStatus.Contains("Voice changes are not connected") && client.View.changes.Length == changes, "Unsupported adjustment is visible and leaves settings unchanged");
            yield return Arm("stale", "view");
            client.SetReplyLength(2); yield return Idle();
            int currentRevision = client.View.revision;
            client.RefreshState(); yield return Idle(false);
            Check(!client.LastOk && client.View.revision == currentRevision && client.View.settings.reply_length == "detailed", "Late older snapshot cannot overwrite newer client state");
            client.RefreshState(); yield return Idle();
            Check(client.View.settings.reply_length == "detailed" && client.CanEdit, "Fresh sync recovers after rejecting stale snapshot");
            yield return Http("/tutor/sessions", JsonUtility.ToJson(new TutorCreate {condition="A"}));
            var other = JsonUtility.FromJson<TutorView>(response);
            Check(other.session_id != client.View.session_id && other.settings.reply_length == "balanced" && other.conversation.Length == 0, "New session is isolated from existing changes and conversations");
        }
        IEnumerator Ask(string query)
        {
            client.SubmitUserUtterance(query); yield return Idle(); Save();
        }
        IEnumerator Idle(bool expectSuccess = true)
        {
            yield return null;
            float deadline = Time.realtimeSinceStartup + (live ? 150 : 20);
            while (client.Busy && Time.realtimeSinceStartup < deadline) yield return null;
            Require(!client.Busy, "Operation timed out");
            if (expectSuccess) Require(string.IsNullOrEmpty(client.Error), "Backend error: " + client.Error);
            yield return null;
        }
        IEnumerator Arm(string fault, string operation) { yield return Http("/engineering/arm", "{\"fault\":\""+fault+"\",\"operation\":\""+operation+"\",\"session_id\":\""+client.View.session_id+"\"}"); }
        IEnumerator Http(string path, string json)
        {
            using (var req = new UnityWebRequest(client.endpoint + path, "POST"))
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)); req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json"); req.timeout = 15;
                yield return req.SendWebRequest(); Require(req.result == UnityWebRequest.Result.Success, "Acceptance helper HTTP failed"); response = req.downloadHandler.text;
            }
        }
        void Require(bool okay, string reason)
        {
            if (okay) return; Result = "FAIL: " + reason; Save(); throw new InvalidOperationException("TUTOR_ACCEPTANCE " + Result);
        }
        void Check(bool okay, string reason) { Require(okay, reason); passed.Add(reason); Save(); }
        void Save()
        {
            Directory.CreateDirectory(Folder);
            File.WriteAllText(Path.Combine(Folder, "checks.txt"), Result + "\n" + string.Join("\n", passed));
            if (client && client.View != null) File.WriteAllText(Path.Combine(Folder, "unity-view.json"), JsonUtility.ToJson(client.View, true));
        }
    }
}
#endif
