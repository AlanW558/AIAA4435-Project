using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    [Serializable] public sealed class StudyRecoveryState { public string study_run_id, data_contract_version; public int revision; }
    [Serializable] public sealed class StudyRecoveryHeader { public StudyRecoveryState state; public bool replay_model_calls; }
    /// <summary>Transport for the new study contract, not a replacement tutor engine.
    /// Restores its durable queue; only explicit Retry sends a saved command after
    /// restart. A questionnaire controller must wait for a matching acknowledgement.</summary>
    public sealed class TutorStudyDataClient : MonoBehaviour
    {
        public string endpoint = "http://127.0.0.1:8765";
        public TutorStudyJournal Journal { get; private set; }
        public bool Busy { get; private set; }
        public bool Ready => Journal != null && !Busy && !StorageFault && Journal.PendingCount == 0;
        public bool StorageFault { get; private set; }
        public string Error { get; private set; } = "";
        public string LastReceiptJson { get; private set; }
        public string RejectedRequestId { get; private set; }
        public string LastSnapshotJson { get; private set; }
        public event Action<string> Saved;
        public event Action<string> Restored;
        void Awake()
        {
            string folder;
#if UNITY_EDITOR
            folder = System.Environment.GetEnvironmentVariable("IAI_STUDY_JOURNAL_DIR") ?? Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/study-journal"));
#else
            folder = Path.Combine(Application.persistentDataPath, "StudyData", "journal");
#endif
            try
            {
                Journal = new TutorStudyJournal(folder);
                LastReceiptJson = Journal.LatestReceipt;
                if (Journal.PendingCount > 0) Error = "A saved study operation is pending. Retry it before continuing.";
            }
            catch (Exception) { StorageFault = true; Error = "Study storage could not be recovered. Keep the local files for inspection."; }
        }
        public string Send(string operation, string studyRunId, int revision, string payloadJson)
        {
            if (!Ready) throw new InvalidOperationException("Study storage is not ready or another operation is pending.");
            var packet = new StudyCommandPacket { request_id = Guid.NewGuid().ToString("N"), operation = operation,
                study_run_id = studyRunId, expected_revision = revision, payload_json = payloadJson };
            try { Journal.Enqueue(endpoint, packet); }
            catch (Exception) { StorageFault = true; Error = "Study operation was not sent: local saving failed."; throw; }
            Retry(); return packet.request_id;
        }
        public bool SaveDraft(string questionnaireId, string draftJson)
        { return SaveLocalDraft("draft:" + questionnaireId,draftJson); }
        public bool SaveLocalDraft(string scope,string draftJson)
        {
            if (Journal == null || StorageFault) return false;
            try { Journal.SaveLocal(scope, draftJson); return true; }
            catch (Exception) { StorageFault = true; Error = "The questionnaire draft could not be saved locally."; return false; }
        }
        public void Retry()
        {
            if (Journal == null || StorageFault || Busy || Journal.NextPending == null) return;
            StartCoroutine(Deliver());
        }
        IEnumerator Deliver()
        {
            Busy = true;
            var entry = Journal.NextPending;
            using (var request = new UnityWebRequest(entry.endpoint + "/study/commands", "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(entry.payload));
                request.downloadHandler = new DownloadHandlerBuffer(); request.timeout = 20;
                request.SetRequestHeader("Content-Type", "application/json");
                yield return request.SendWebRequest();
                if (request.result == UnityWebRequest.Result.Success)
                {
                    try { Journal.Acknowledge(entry.request_id, request.downloadHandler.text); LastReceiptJson = request.downloadHandler.text; Error = ""; }
                    catch (Exception) { StorageFault = true; Error = "Study receipt could not be verified/saved. The original packet is retained."; }
                }
                else
                {
                    if(request.responseCode>=400 && request.responseCode<500)
                    {
                        try{Journal.Reject(entry.request_id,request.downloadHandler.text);RejectedRequestId=entry.request_id;}
                        catch(Exception){StorageFault=true;}
                    }
                    Error = request.responseCode >= 400 && request.responseCode < 500
                    ? "Study data conflict or invalid request. Original local packet retained; inspect before continuing."
                    : "Study connection interrupted. Retry the same saved request; do not create a replacement.";
                }
            }
            Busy = false;
            if (Error.Length == 0) Saved?.Invoke(LastReceiptJson);
        }
        public void Restore(string studyRunId)
        {
            if (!Ready || !TutorStudyJournal.ValidEndpoint(endpoint) || !Guid.TryParseExact(studyRunId, "N", out _)) return;
            StartCoroutine(Fetch(studyRunId));
        }
        IEnumerator Fetch(string studyRunId)
        {
            Busy = true;
            using (var request = UnityWebRequest.Get(endpoint.TrimEnd('/') + "/study/runs/" + studyRunId + "/snapshot"))
            {
                request.timeout = 20;
                yield return request.SendWebRequest();
                if (request.result == UnityWebRequest.Result.Success)
                {
                    try
                    {
                        var header = JsonUtility.FromJson<StudyRecoveryHeader>(request.downloadHandler.text);
                        if (header?.state == null || header.state.study_run_id != studyRunId || header.state.data_contract_version != "study-data-contract-v1" || header.replay_model_calls)
                            throw new InvalidDataException("Recovery snapshot identity/version mismatch.");
                        Journal.SaveLocal("run:" + studyRunId, request.downloadHandler.text, true);
                        LastSnapshotJson = request.downloadHandler.text; Error = "";
                    }
                    catch (Exception) { StorageFault = true; Error = "Recovered study state could not be saved locally."; }
                }
                else Error = "Could not restore study state. Existing local data have been retained.";
            }
            Busy = false;
            if (Error.Length == 0) Restored?.Invoke(LastSnapshotJson);
        }
        void OnDisable() { StopAllCoroutines(); Busy = false; }
    }
}
