using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace IAI.Tutor
{
    [Serializable] public sealed class StudyCommandPacket
    {
        public string request_id, operation, study_run_id, payload_json;
        public int expected_revision;
    }
    [Serializable] public sealed class StudyReceipt
    {
        public bool recorded;
        public string request_id, study_run_id, payload_sha256, server_saved_at;
        public int revision;
    }
    [Serializable] public sealed class StudyRejection { public string error, message; }
    [Serializable] public sealed class StudyJournalEntry
    {
        public long sequence;
        public string kind, scope, endpoint, payload, sha256, request_id;
    }

    /// <summary>Immutable text records. A receipt never deletes the original packet.
    /// An incomplete/corrupt file stops recovery rather than silently dropping data.</summary>
    public sealed class TutorStudyJournal
    {
        public string Folder { get; private set; }
        readonly List<StudyJournalEntry> entries = new List<StudyJournalEntry>();
        readonly Dictionary<string, string> receipts = new Dictionary<string, string>();
        readonly HashSet<string> rejected = new HashSet<string>();
        long sequence;
        public IReadOnlyList<StudyJournalEntry> Entries => entries.AsReadOnly();
        public int PendingCount => entries.Count(e => e.kind == "command" && !receipts.ContainsKey(e.request_id) && !rejected.Contains(e.request_id));
        public StudyJournalEntry NextPending => entries.FirstOrDefault(e => e.kind == "command" && !receipts.ContainsKey(e.request_id) && !rejected.Contains(e.request_id));
        public string LatestReceipt => entries.LastOrDefault(e => e.kind == "receipt")?.payload;

        public TutorStudyJournal(string folder)
        {
            Folder = Path.GetFullPath(folder);
            Directory.CreateDirectory(Folder);
            foreach (string temp in Directory.GetFiles(Folder, "*.json.tmp").OrderBy(x => x, StringComparer.Ordinal))
            {
                Validate(File.ReadAllText(temp));
                string final = temp.Substring(0, temp.Length - 4);
                if (File.Exists(final))
                {
                    if (File.ReadAllText(temp) != File.ReadAllText(final)) throw new InvalidDataException("Conflicting study journal files.");
                    File.Delete(temp);
                }
                else File.Move(temp, final);
            }
            foreach (string file in Directory.GetFiles(Folder, "*.json").OrderBy(x => x, StringComparer.Ordinal))
            {
                var entry = Validate(File.ReadAllText(file));
                if (entry.sequence <= sequence || Path.GetFileName(file) != Name(entry)) throw new InvalidDataException("Study journal sequence is invalid.");
                sequence = entry.sequence;
                if (entry.kind == "command" && entries.Any(e => e.kind == "command" && e.request_id == entry.request_id))
                    throw new InvalidDataException("Duplicate study command identity.");
                if (entry.kind == "receipt") ValidateReceipt(entry.request_id, entry.payload);
                if(entry.kind=="rejection") { if(!entries.Any(e=>e.kind=="command"&&e.request_id==entry.request_id))throw new InvalidDataException("Unknown rejected request."); rejected.Add(entry.request_id); }
                entries.Add(entry);
                if (entry.kind == "receipt") receipts.Add(entry.request_id, entry.payload);
            }
        }
        static string Name(StudyJournalEntry e) => e.sequence.ToString("D20") + ".json";
        public static string Hash(string value)
        {
            using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(value))).Replace("-", "").ToLowerInvariant();
        }
        public static bool ValidEndpoint(string value)
        {
            return Uri.TryCreate(value, UriKind.Absolute, out var uri) && (uri.Scheme == "http" || uri.Scheme == "https")
                && string.IsNullOrEmpty(uri.UserInfo) && string.IsNullOrEmpty(uri.Query) && string.IsNullOrEmpty(uri.Fragment)
                && (uri.AbsolutePath == "/" || uri.AbsolutePath == "");
        }
        static StudyJournalEntry Validate(string json)
        {
            var e = JsonUtility.FromJson<StudyJournalEntry>(json);
            if (e == null || e.sequence < 1 || e.payload == null || e.sha256 != Hash(e.payload)
                || (e.kind != "command" && e.kind != "receipt" && e.kind != "draft" && e.kind != "snapshot" && e.kind != "rejection"))
                throw new InvalidDataException("Corrupt or incomplete study journal record.");
            if (e.kind == "command")
            {
                var packet = JsonUtility.FromJson<StudyCommandPacket>(e.payload);
                if (!ValidEndpoint(e.endpoint) || packet == null || !ValidId(packet.request_id) || packet.request_id != e.request_id
                    || packet.payload_json == null || string.IsNullOrEmpty(packet.operation) || packet.expected_revision < 0)
                    throw new InvalidDataException("Invalid stored study command.");
            }
            return e;
        }
        static bool ValidId(string value) => value != null && Regex.IsMatch(value, "\\A[0-9a-f]{32}\\z");
        void Append(StudyJournalEntry e)
        {
            e.sequence = sequence + 1; e.sha256 = Hash(e.payload);
            string json = JsonUtility.ToJson(e); Validate(json);
            string final = Path.Combine(Folder, Name(e)); string temp = final + ".tmp";
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            { stream.Write(bytes, 0, bytes.Length); stream.Flush(true); }
            File.Move(temp, final);
            sequence = e.sequence; entries.Add(e);
        }
        public string Enqueue(string endpoint, StudyCommandPacket packet)
        {
            if (!ValidEndpoint(endpoint) || packet == null || !ValidId(packet.request_id)) throw new ArgumentException("Invalid study packet destination/ID.");
            string json = JsonUtility.ToJson(packet);
            var existing = entries.FirstOrDefault(e => e.kind == "command" && e.request_id == packet.request_id);
            if (existing != null)
            {
                if (existing.payload != json || existing.endpoint != endpoint.TrimEnd('/')) throw new InvalidDataException("Request ID conflicts with a saved packet.");
                return packet.request_id;
            }
            if (PendingCount != 0) throw new InvalidOperationException("Resolve the pending study operation before queuing another; offline drafts can still be saved.");
            Append(new StudyJournalEntry { kind = "command", scope = packet.study_run_id, endpoint = endpoint.TrimEnd('/'), payload = json, request_id = packet.request_id });
            return packet.request_id;
        }
        StudyReceipt ValidateReceipt(string requestId, string json)
        {
            var entry = entries.FirstOrDefault(e => e.kind == "command" && e.request_id == requestId);
            var ack = JsonUtility.FromJson<StudyReceipt>(json);
            if (entry == null || ack == null || !ack.recorded || ack.request_id != requestId || string.IsNullOrEmpty(ack.server_saved_at))
                throw new InvalidDataException("Unmatched study receipt.");
            var packet = JsonUtility.FromJson<StudyCommandPacket>(entry.payload);
            int expected = packet.operation == "create_run" || packet.operation == "register_participant" ? 0 : packet.expected_revision + 1;
            if (ack.revision != expected || ack.payload_sha256 != Hash(packet.payload_json) || (!string.IsNullOrEmpty(packet.study_run_id) && ack.study_run_id != packet.study_run_id))
                throw new InvalidDataException("Study receipt content/identity mismatch.");
            return ack;
        }
        public void Acknowledge(string requestId, string json)
        {
            ValidateReceipt(requestId, json);
            if (receipts.ContainsKey(requestId)) return;
            Append(new StudyJournalEntry { kind = "receipt", request_id = requestId, payload = json });
            receipts.Add(requestId, json);
        }
        public void Reject(string requestId,string response)
        {
            if(string.IsNullOrEmpty(JsonUtility.FromJson<StudyRejection>(response)?.error))throw new InvalidDataException("Unverified server rejection.");
            if(!entries.Any(e=>e.kind=="command"&&e.request_id==requestId))throw new InvalidDataException("Unknown rejected packet.");
            if(rejected.Contains(requestId))return;
            Append(new StudyJournalEntry{kind="rejection",request_id=requestId,payload=response});rejected.Add(requestId);
        }
        public void SaveLocal(string scope, string json, bool serverSnapshot = false)
        {
            if (string.IsNullOrWhiteSpace(scope) || scope.Length > 100 || string.IsNullOrEmpty(json) || json.Length > 2000000)
                throw new ArgumentException("Use a bounded local study draft/snapshot.");
            Append(new StudyJournalEntry { kind = serverSnapshot ? "snapshot" : "draft", scope = scope, payload = json });
        }
        public string RestoreLocal(string scope, bool serverSnapshot = false)
        {
            string kind = serverSnapshot ? "snapshot" : "draft";
            return entries.LastOrDefault(e => e.kind == kind && e.scope == scope)?.payload;
        }
        public void ExportLocalCopy(string newDirectory)
        {
            // Never consume the active journal or overwrite an older export.
            if (Directory.Exists(newDirectory) || File.Exists(newDirectory)) throw new IOException("Choose a new export directory.");
            Directory.CreateDirectory(newDirectory);
            foreach (string file in Directory.GetFiles(Folder, "*.json")) File.Copy(file, Path.Combine(newDirectory, Path.GetFileName(file)), false);
            File.WriteAllText(Path.Combine(newDirectory, "LOCAL_COPY_NOTICE.txt"),
                "Study journal copy. Pending count at copy: " + PendingCount + ". Backend and local records must be reconciled before declaring collection complete. Contains submitted text only; do not add raw audio.\n");
        }
    }
}
