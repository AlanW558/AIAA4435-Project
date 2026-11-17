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
    [Serializable] public class TutorPlaybackReport
    {
        public string event_id, audio_request_id, reason, client_time_utc;
        public string @event;
        public float position_seconds, elapsed_seconds;
    }
    [Serializable] class PlaybackPacket { public string endpoint, route; public TutorPlaybackReport report; }
    [Serializable] class PlaybackAck { public bool recorded; public string event_id; }

    /// <summary>Text-only write-before-send outbox. Per-event files survive scene
    /// changes and restarts; exact IDs make lost-response retries idempotent.</summary>
    public sealed class TutorPlaybackOutbox : MonoBehaviour
    {
        static TutorPlaybackOutbox instance;
        public static TutorPlaybackOutbox Instance
        {
            get
            {
                if (!instance)
                {
                    var root = new GameObject("Tutor playback audit delivery");
                    instance = root.AddComponent<TutorPlaybackOutbox>(); DontDestroyOnLoad(root);
                }
                return instance;
            }
        }
        sealed class Pending { public string path; public PlaybackPacket packet; public bool saved; }
        readonly Queue<Pending> pending = new Queue<Pending>();
        public int PendingCount => pending.Count;
        public string Error { get; private set; } = "";
        public bool CanStart => loaded && Error.Length == 0 && pending.Count < 4094 && pending.All(p => p.saved);
        public string Folder { get; private set; }
        bool loaded;
        long sequence;
        void Awake()
        {
#if UNITY_EDITOR
            Folder = Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/playback-outbox"));
#else
            Folder = Path.Combine(Application.persistentDataPath, "TutorPlaybackOutbox");
#endif
            try
            {
                Directory.CreateDirectory(Folder);
                foreach (string temp in Directory.GetFiles(Folder, "*.json.tmp"))
                {
                    // Recover a fully flushed event if shutdown preceded rename.
                    var packet = JsonUtility.FromJson<PlaybackPacket>(File.ReadAllText(temp));
                    if (packet?.report == null) throw new InvalidDataException("Incomplete playback outbox write.");
                    string final = temp.Substring(0, temp.Length - 4);
                    if (File.Exists(final))
                    { if (File.ReadAllText(final) != File.ReadAllText(temp)) throw new InvalidDataException("Conflicting playback outbox files."); File.Delete(temp); }
                    else File.Move(temp, final);
                }
                foreach (string file in Directory.GetFiles(Folder, "*.json").OrderBy(p => p, StringComparer.Ordinal))
                {
                    var packet = JsonUtility.FromJson<PlaybackPacket>(File.ReadAllText(file));
                    if (packet == null || packet.report == null || !ValidEndpoint(packet.endpoint) ||
                        string.IsNullOrEmpty(packet.route) || !packet.route.StartsWith("/tutor/", StringComparison.Ordinal) || !packet.route.EndsWith("/playback", StringComparison.Ordinal))
                        throw new InvalidDataException("Invalid pending playback report.");
                    pending.Enqueue(new Pending { path = file, packet = packet, saved = true });
                    long parsed; if (long.TryParse(Path.GetFileName(file).Split('_')[0], out parsed)) sequence = Math.Max(sequence, parsed);
                }
                loaded = true;
            }
            catch (Exception) { Error = "Playback log could not be loaded. Ask the researcher to check local storage."; }
        }
        static bool ValidEndpoint(string endpoint) => Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) &&
            (uri.Scheme == "http" || uri.Scheme == "https") && string.IsNullOrEmpty(uri.UserInfo) && string.IsNullOrEmpty(uri.Query) && string.IsNullOrEmpty(uri.Fragment);
        void OnEnable() { StartCoroutine(Deliver()); }
        public void Enqueue(string endpoint, string route, TutorPlaybackReport report)
        {
            if (!ValidEndpoint(endpoint)) { Error = "Playback log has an invalid backend address."; return; }
            sequence = Math.Max(sequence + 1, DateTime.UtcNow.Ticks);
            var item = new Pending { path = Path.Combine(Folder, sequence.ToString("D20") + "_" + report.event_id + ".json"),
                packet = new PlaybackPacket { endpoint = endpoint.TrimEnd('/'), route = route, report = report } };
            pending.Enqueue(item);
            Save(item); // Keep failed writes in memory and block new playback; delivery retries the write.
        }
        bool Save(Pending item)
        {
            if (item.saved) return true;
            try
            {
                string temp = item.path + ".tmp";
                using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(JsonUtility.ToJson(item.packet));
                    stream.Write(bytes, 0, bytes.Length); stream.Flush(true);
                }
                File.Move(temp, item.path); item.saved = true; return true;
            }
            catch (Exception) { Error = "Playback log pending: local storage write failed. Retrying."; return false; }
        }
        IEnumerator Deliver()
        {
            while (true)
            {
                if (!loaded || pending.Count == 0) { yield return new WaitForSecondsRealtime(.2f); continue; }
                var item = pending.Peek();
                if (!Save(item)) { yield return new WaitForSecondsRealtime(3); continue; }
                bool accepted = false;
                using (var call = new UnityWebRequest(item.packet.endpoint + item.packet.route, "POST"))
                {
                    call.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(item.packet.report)));
                    call.downloadHandler = new DownloadHandlerBuffer(); call.SetRequestHeader("Content-Type", "application/json"); call.timeout = 8;
                    yield return call.SendWebRequest();
                    if (call.result == UnityWebRequest.Result.Success)
                    {
                        try
                        {
                            var ack = JsonUtility.FromJson<PlaybackAck>(call.downloadHandler.text);
                            accepted = ack != null && ack.recorded && ack.event_id == item.packet.report.event_id;
                        }
                        catch (Exception) { }
                    }
                }
                if (accepted)
                {
                    try { File.Delete(item.path); pending.Dequeue(); Error = ""; }
                    catch (Exception) { Error = "Playback log acknowledged; local cleanup pending. Retrying safely."; }
                }
                else Error = "Playback log pending. Retrying delivery to the original task.";
                if (Error.Length > 0) yield return new WaitForSecondsRealtime(3);
            }
        }
    }
}
