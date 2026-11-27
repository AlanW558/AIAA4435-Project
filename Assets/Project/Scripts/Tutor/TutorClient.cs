using System;
using System.Collections;
using System.Linq;
using System.Text;
using IAI.Appearance;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    public static class TutorVoiceCatalog
    {
        public static readonly string[] Ids = { "voice_a", "voice_b", "voice_c", "voice_d", "voice_e" };
        public static readonly string[] Labels = { "Female voice 1", "Female voice 2", "Female voice 3", "Male voice 1", "Male voice 2" };
    }
    [Serializable] public class TutorSettings
    {
        public float speech_rate, scale;
        public string reply_length, tone, voice, avatar_id, outfit, jacket_color, accessory;
    }
    [Serializable] public class TutorMessage { public string role, content; }
    [Serializable] public class TutorExchange { public int id; public TutorSettings settings; public TutorMessage[] messages; }
    [Serializable] public class TutorChange
    {
        public int id, target_change_id;
        public string kind, source, query;
        public TutorSettings before, after;
        public string[] remaining_fields;
    }
    [Serializable] public class TutorOption { public string id, label; }
    [Serializable] public class TutorQuestion { public string question_id, text, original_query; public TutorOption[] options; }
    [Serializable] public class TutorJob { public string job_id, query, status, answer; public TutorSettings settings; }
    [Serializable] public class TutorResponse { public string job_id, text, audio_status; public TutorSettings settings; public int exchange_id; }
    [Serializable] public class TutorView
    {
        public string session_id, condition, phase, mode, decision, message, error;
        public int revision, state_revision;
        public bool generation_available, idempotent_replay, audio_available;
        public TutorSettings settings, next_turn_override;
        public TutorChange[] changes;
        public TutorExchange[] conversation;
        public TutorJob[] generation_jobs;
        public TutorQuestion question;
        public TutorResponse response;
        public string[] deferred_questions;
    }
    // Separate wire DTOs are intentional: backend rejects unknown/null extra fields.
    [Serializable] public class TutorCreate { public string condition = "S", phase = "debug", participant_id = "UNITYDEBUG"; }
    [Serializable] public class TutorMutation { public string request_id; public int expected_revision; }
    [Serializable] public class TutorRequest : TutorMutation { public string query; }
    [Serializable] public class TutorQuestionRequest : TutorRequest { public string question_id; }
    [Serializable] public class TutorAnswer : TutorMutation { public string question_id, option_id; }
    [Serializable] public class TutorOtherAnswer : TutorAnswer { public string free_text; }
    [Serializable] public class TutorLengthPatch { public string reply_length; }
    [Serializable] public class TutorControl : TutorMutation { public TutorLengthPatch patch; }
    [Serializable] public class TutorRatePatch { public float speech_rate; }
    [Serializable] public class TutorRateControl : TutorMutation { public TutorRatePatch patch; }
    [Serializable] public class TutorTonePatch { public string tone; }
    [Serializable] public class TutorToneControl : TutorMutation { public TutorTonePatch patch; }
    [Serializable] public class TutorVoicePatch { public string voice; }
    [Serializable] public class TutorVoiceControl : TutorMutation { public TutorVoicePatch patch; }
    [Serializable] public class TutorDialoguePatch
    {
        public float speech_rate;
        public string reply_length, tone, voice;
        public static TutorDialoguePatch From(TutorSettings settings) => new TutorDialoguePatch {
            speech_rate=settings.speech_rate, reply_length=settings.reply_length, tone=settings.tone, voice=settings.voice };
        public bool Matches(TutorSettings settings) => settings != null && Mathf.Abs(speech_rate-settings.speech_rate)<.001f &&
            reply_length==settings.reply_length && tone==settings.tone && voice==settings.voice;
        public bool Valid => !float.IsNaN(speech_rate) && !float.IsInfinity(speech_rate) && speech_rate>=.7f && speech_rate<=1.3f &&
            Array.IndexOf(new[]{"brief","balanced","detailed"},reply_length)>=0 &&
            Array.IndexOf(new[]{"professional","friendly","encouraging"},tone)>=0 && Array.IndexOf(TutorVoiceCatalog.Ids,voice)>=0;
    }
    [Serializable] public class TutorDialogueControl : TutorMutation { public TutorDialoguePatch patch; }
    [Serializable] public class TutorUndo : TutorMutation { public string field = "reply_length"; }
    [Serializable] public class TutorGenerate : TutorMutation { public string job_id; }

    /// <summary>One debug tutor session. No API credentials or provider calls in Unity.</summary>
    public sealed class TutorClient : MonoBehaviour, ITutorPanelClient
    {
        public string endpoint = "http://127.0.0.1:8765";
        public string condition = "S";
        public bool connectOnStart = true;
        public bool useEnvironmentEndpoint = true;
        [Range(5, 180)] public int timeoutSeconds = 120;
        public AppearanceAvatar avatar;
        public TutorView View { get; private set; }
        public bool Busy { get; private set; }
        public string Error { get; private set; } = "";
        public string Activity { get; private set; } = "Not connected";
        public bool LastOk { get; private set; }
        // Only a fresh local request may trigger automatic clarification speech.
        // GET/restore never marks an old pending question for automatic replay.
        public string QuestionForAutomaticSpeech { get; private set; } = "";
        public bool UnknownOutcome { get; private set; }
        public event Action Changed;
        public bool Connected => View != null && !string.IsNullOrEmpty(View.session_id);
        public bool HasQuestion => Connected && View.question != null && !string.IsNullOrEmpty(View.question.question_id);
        public bool CanEdit => !studyLocked && Connected && !Busy && !HasQuestion && !HasQueuedAnswer && !UnknownOutcome;
        public bool CanSubmit => !studyLocked && Connected && !Busy && !UnknownOutcome;
        public bool HasQueuedAnswer => Connected && (View.generation_jobs ?? Array.Empty<TutorJob>()).Any(j => j.status == "queued");
        public bool CanUndo => CanEdit && (View.changes ?? Array.Empty<TutorChange>()).Any(c => c.kind == "commit" && (c.remaining_fields ?? Array.Empty<string>()).Contains("reply_length"));
        public bool CanRetry => !Busy && Connected && ((failedBody != null && (UnknownOutcome || retryKnown && failedBody.expected_revision == View.revision)) || failedBody == null && HasQueuedAnswer);
        string failedRoute, failedJson;
        TutorMutation failedBody;
        bool retryKnown;
        UnityWebRequest activeRequest;
        TutorMutation activeBody;
        string activeRoute, activeJson;
        string appliedAppearance = "";

        public bool studyManaged;
        public TutorStudyJournal studyJournal;
        public string studyRunId;
        public bool studyLocked;
        public void AttachStudyRuntime(string id)
        {
            if (Busy) return;
            View = null; UnknownOutcome = false; QuestionForAutomaticSpeech = "";
            StartCoroutine(Run("/tutor/sessions/" + id, null, null, false));
        }
        void Start()
        {
            if(useEnvironmentEndpoint)endpoint = System.Environment.GetEnvironmentVariable("TUTOR_BACKEND_URL") ?? endpoint;
            if (connectOnStart) Connect();
        }

        void Notify() { Changed?.Invoke(); }
        public void Connect()
        {
            if (studyManaged) return;
            if (Busy || Connected) return;
            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) || (uri.Scheme != "http" && uri.Scheme != "https") || !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment))
            { Error = "Set a valid backend URL without credentials, query or fragment."; Notify(); return; }
            if (Array.IndexOf(new[] { "E", "A", "N", "S" }, condition) < 0)
            { Error = "Select an E/A/N/S debug condition before connecting."; Notify(); return; }
            StartCoroutine(Run("/tutor/sessions", JsonUtility.ToJson(new TutorCreate { condition = condition }), null, false));
        }

        T Prepare<T>(T body) where T : TutorMutation
        { body.request_id = Guid.NewGuid().ToString("N"); body.expected_revision = View.revision; return body; }
        string Route(string operation) => "/tutor/sessions/" + View.session_id + "/" + operation;
        void SendMutation(string operation, TutorMutation body)
        {
            if (!Connected || Busy || UnknownOutcome) return;
            Prepare(body);
            StartCoroutine(Run(Route(operation), JsonUtility.ToJson(body), body, true));
        }

        // The same entry point accepts a future confirmed STT transcript. It does
        // not require a physical keyboard or change study-language rules.
        public void SubmitUserUtterance(string transcript)
        {
            if (string.IsNullOrWhiteSpace(transcript)) return;
            if (HasQuestion) SendMutation("request", new TutorQuestionRequest { query = transcript.Trim(), question_id = View.question.question_id });
            else SendMutation("request", new TutorRequest { query = transcript.Trim() });
        }
        public void ChooseOption(string id)
        {
            if (HasQuestion && id != "other") SendMutation("answer", new TutorAnswer { question_id = View.question.question_id, option_id = id });
        }
        public void SubmitClarification(string transcript)
        {
            if (HasQuestion && !string.IsNullOrWhiteSpace(transcript)) SendMutation("answer", new TutorOtherAnswer {
                question_id = View.question.question_id, option_id = "other", free_text = transcript.Trim() });
        }
        public void SetReplyLength(int index)
        {
            if (!CanEdit || index < 0 || index > 2) return;
            string value = new[] { "brief", "balanced", "detailed" }[index];
            if (View.settings.reply_length == value) return;
            SendMutation("settings", new TutorControl { patch = new TutorLengthPatch { reply_length = value } });
        }
        public void SetSpeechRate(float value)
        {
            if (!CanEdit || float.IsNaN(value) || float.IsInfinity(value) || value < .7f || value > 1.3f) return;
            value = Mathf.Round(value * 100) / 100;
            if (Mathf.Abs(View.settings.speech_rate - value) < .001f) return;
            SendMutation("settings", new TutorRateControl { patch = new TutorRatePatch { speech_rate = value } });
        }
        public void SetTone(int index)
        {
            if (!CanEdit || index < 0 || index > 2) return;
            string value = new[] { "professional", "friendly", "encouraging" }[index];
            if (View.settings.tone == value) return;
            SendMutation("settings", new TutorToneControl { patch = new TutorTonePatch { tone = value } });
        }
        public void SetVoice(int index)
        {
            if (!CanEdit || index < 0 || index >= TutorVoiceCatalog.Ids.Length) return;
            string value = TutorVoiceCatalog.Ids[index];
            if (View.settings.voice == value) return;
            SendMutation("settings", new TutorVoiceControl { patch = new TutorVoicePatch { voice = value } });
        }
        public void SetDialogueSettings(TutorDialoguePatch patch)
        {
            if (!CanEdit || patch == null || !patch.Valid || patch.Matches(View.settings)) return;
            SendMutation("settings", new TutorDialogueControl { patch = patch });
        }
        public bool CanUndoSetting(string field) => CanEdit && TutorHistoryPresentation.CanUndo(View, field);
        public void UndoSetting(string field) { if (CanUndoSetting(field)) SendMutation("undo", new TutorUndo { field = field }); }
        public void UndoReplyLength() { UndoSetting("reply_length"); }
        public void RefreshState()
        {
            if (!Connected || Busy) return;
            StartCoroutine(Run("/tutor/sessions/" + View.session_id, null, null, false));
        }
        public void Retry()
        {
            if (!CanRetry) return;
            if (failedBody == null) { StartCoroutine(ContinueAnswers()); return; }
            // Transport errors have unknown outcome: replay the exact same ID/body.
            // A known 502/503 is cached on the server: retry under a new ID only
            // when the state still matches the failed operation's revision.
            if (!UnknownOutcome) { failedBody.request_id = Guid.NewGuid().ToString("N"); failedJson = JsonUtility.ToJson(failedBody); }
            StartCoroutine(Run(failedRoute, failedJson, failedBody, true));
        }

        IEnumerator Run(string route, string json, TutorMutation body, bool drain)
        {
            Busy = true; Error = ""; Notify();
            try
            {
                yield return Send(route, json, body);
                if (LastOk && drain) yield return Drain();
            }
            finally { Busy = false; Notify(); }
        }
        IEnumerator ContinueAnswers()
        {
            Busy = true; Error = ""; Notify();
            try { yield return Drain(); }
            finally { Busy = false; Notify(); }
        }
        IEnumerator Drain()
        {
            while (Connected && View.generation_available)
            {
                var job = (View.generation_jobs ?? Array.Empty<TutorJob>()).FirstOrDefault(j => j.status == "queued");
                if (job == null) yield break;
                var body = Prepare(new TutorGenerate { job_id = job.job_id });
                yield return Send(Route("generate"), JsonUtility.ToJson(body), body);
                if (!LastOk) yield break;
            }
        }

        IEnumerator Send(string route, string json, TutorMutation body)
        {
            string evidence=null;bool storageFailed=false;
            try{if(studyManaged && json!=null)evidence=TutorStudyRuntimeEvidence.Save(studyJournal,studyRunId,route,json);}
            catch(Exception){storageFailed=true;Error="Submitted text could not be saved locally. Request was not sent.";}
            if(storageFailed){Notify();yield break;}
            LastOk = false;
            Activity = json == null ? "Synchronizing..." : route.EndsWith("/generate") ? "Tutor is preparing a reply..." : "Processing...";
            Notify();
            using (var request = new UnityWebRequest(endpoint.TrimEnd('/') + route, json == null ? "GET" : "POST"))
            {
                activeRequest = request;
                activeBody = body; activeRoute = route; activeJson = json;
                request.downloadHandler = new DownloadHandlerBuffer();
                request.timeout = timeoutSeconds;
                if (json != null) { request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)); request.SetRequestHeader("Content-Type", "application/json"); }
                yield return request.SendWebRequest();
                TutorView parsed = null;
                try { parsed = JsonUtility.FromJson<TutorView>(request.downloadHandler.text); }
                catch (ArgumentException) { }
                bool valid = parsed != null && !string.IsNullOrEmpty(parsed.session_id) && parsed.settings != null
                    && (!Connected || parsed.session_id == View.session_id && parsed.revision >= View.revision);
                if (valid && (!Connected || parsed.session_id == View.session_id) && (!Connected || parsed.revision >= View.revision))
                {
                    string previousQuestion=View?.question?.question_id;
                    if(json!=null && request.result==UnityWebRequest.Result.Success && !parsed.idempotent_replay &&
                        !string.IsNullOrEmpty(parsed.question?.question_id) && parsed.question.question_id!=previousQuestion)
                        QuestionForAutomaticSpeech=parsed.question.question_id;
                    View = parsed;
                    ApplyAppearance();
                }
                bool transport = request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.DataProcessingError || (request.responseCode >= 200 && request.responseCode < 300 && !valid);
                if (request.result == UnityWebRequest.Result.Success && valid)
                {
                    try{TutorStudyRuntimeEvidence.Acknowledge(studyJournal,evidence,request.downloadHandler.text);}
                    catch(Exception){storageFailed=true;UnknownOutcome=true;Error="Reply received but local receipt saving failed. Original input is retained.";}
                    if(storageFailed){Notify();yield break;}
                    LastOk = true; Error = ""; Activity = HasQuestion ? "Clarification pending" : "Ready";
                    // GET does not prove an uncertain mutation failed or succeeded.
                    // Keep its original retry body until an exact replay resolves it.
                    if (json != null || !UnknownOutcome) { failedBody = null; failedRoute = failedJson = null; retryKnown = false; UnknownOutcome = false; }
                }
                else
                {
                    Error = transport ? "Connection interrupted. Sync, then retry to recover the same request." : parsed != null && !string.IsNullOrEmpty(parsed.message) ? parsed.message : "The backend could not process this request.";
                    Activity = "Needs attention";
                    if (body != null)
                    {
                        failedRoute = route; failedJson = json; failedBody = body;
                        UnknownOutcome = transport;
                        retryKnown = !transport && (request.responseCode == 502 || request.responseCode == 503);
                    }
                }
                activeRequest = null;
                activeBody = null;
            }
            Notify();
        }
        public void ReapplyAppearance(){appliedAppearance="";ApplyAppearance();}
        void ApplyAppearance()
        {
            if (!avatar || View == null || View.settings == null) return;
            var s = View.settings;
            string key = $"{s.avatar_id}|{s.outfit}|{s.jacket_color}|{s.accessory}|{s.scale}";
            if (key == appliedAppearance) return;
            avatar.EnableDemo(true);
            avatar.Apply(new AppearanceState { avatar_id = s.avatar_id, outfit = s.outfit, jacket_color = s.jacket_color, accessory = s.accessory, scale = s.scale });
            appliedAppearance = key;
        }
        void OnDisable()
        {
            if (activeRequest != null && activeBody != null)
            {
                failedBody = activeBody; failedRoute = activeRoute; failedJson = activeJson;
                UnknownOutcome = true; retryKnown = false;
                Error = "Request interrupted. Retry to recover the same request.";
            }
            if (activeRequest != null) activeRequest.Abort();
            StopAllCoroutines(); activeRequest = null; activeBody = null; Busy = false;
        }
    }
}
