using System;
using System.IO;
using IAI.Tutor;
using UnityEngine;
using UnityEditor;

public static class TutorStudyPersistenceChecks
{
    static int checks;
    static void Assert(bool ok, string message) { checks++; if (!ok) throw new Exception(message); }
    static void Throws(Action action, string message)
    {
        bool thrown = false; try { action(); } catch (Exception) { thrown = true; }
        Assert(thrown, message);
    }
    [MenuItem("AIAA4435/Tutor/Study/Verify Durable Journal")]
    public static void Verify()
    {
        checks = 0;
        string root = Path.Combine(Path.GetTempPath(), "iai-study-journal-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string folder = Path.Combine(root, "journal");
            var journal = new TutorStudyJournal(folder);
            var packet = new StudyCommandPacket { request_id = Guid.NewGuid().ToString("N"), operation = "create_run", expected_revision = 0,
                payload_json = "{\"example\":\"confirmed STT 语音\"}" };
            journal.Enqueue("http://127.0.0.1:8765", packet);
            Assert(journal.PendingCount == 1, "Packet must be saved before delivery.");
            journal.SaveLocal("draft:one", "{\"A0\":\"not_met\"}");
            var recovered = new TutorStudyJournal(folder);
            Assert(recovered.PendingCount == 1, "Unacknowledged packet must survive a restart.");
            Assert(recovered.NextPending.payload == journal.NextPending.payload, "Retry must preserve exact payload and ID.");
            Assert(recovered.RestoreLocal("draft:one") == "{\"A0\":\"not_met\"}", "Partial draft must survive.");
            recovered.Enqueue("http://127.0.0.1:8765", packet);
            Assert(recovered.PendingCount == 1, "Same request must not duplicate.");
            packet.payload_json = "{\"changed\":true}";
            Throws(() => recovered.Enqueue("http://127.0.0.1:8765", packet), "Changed content must conflict.");
            packet.payload_json = "{\"example\":\"confirmed STT 语音\"}";
            var ack = new StudyReceipt { recorded = true, request_id = packet.request_id, study_run_id = Guid.NewGuid().ToString("N"),
                server_saved_at = "2026-11-16T00:00:00Z", payload_sha256 = "bad", revision = 0 };
            Throws(() => recovered.Acknowledge(packet.request_id, JsonUtility.ToJson(ack)), "Wrong hash must be rejected.");
            Assert(recovered.PendingCount == 1, "Invalid ACK must not drop a packet.");
            ack.payload_sha256 = TutorStudyJournal.Hash(packet.payload_json);
            recovered.Acknowledge(packet.request_id, JsonUtility.ToJson(ack));
            recovered.Acknowledge(packet.request_id, JsonUtility.ToJson(ack));
            Assert(recovered.PendingCount == 0, "Valid ACK must complete the pending operation.");
            Assert(new TutorStudyJournal(folder).PendingCount == 0, "ACK must survive a restart.");
            Assert(Directory.GetFiles(folder, "*.json").Length == 3, "ACK must retain original text and draft backup.");
            string export = Path.Combine(root, "copy"); recovered.ExportLocalCopy(export);
            Assert(new TutorStudyJournal(export).RestoreLocal("draft:one") != null, "Local backup must be recoverable.");
            Throws(() => recovered.ExportLocalCopy(export), "Existing backup must not be overwritten.");
            string last = Path.Combine(folder, "00000000000000000003.json");
            File.Move(last, last + ".tmp");
            Assert(new TutorStudyJournal(folder).PendingCount == 0, "Flushed temporary receipt must recover after interrupted rename.");
            File.WriteAllText(Path.Combine(folder, "00000000000000000004.json.tmp"), "{incomplete");
            Throws(() => new TutorStudyJournal(folder), "Corrupt trailing data must not be silently skipped.");
            Assert(!TutorStudyJournal.ValidEndpoint("http://secret@localhost:8765"), "Credential-bearing endpoint must be rejected.");
            Directory.CreateDirectory("StudyData/validation/study-persistence-20261116");
            File.WriteAllText("StudyData/validation/study-persistence-20261116/unity-journal.json",
                "{\"checks\":" + checks + ",\"passed\":true,\"headset_tested\":false,\"scope\":\"Unity compilation and real filesystem journal recovery; new questionnaire UI is not connected\"}\n");
            Debug.Log("STUDY_JOURNAL_VERIFIED " + checks);
        }
        finally { Directory.Delete(root, true); }
    }
}
