using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using IAI.Appearance;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json.Linq;

namespace IAI.Tutor
{
    [Serializable] public class ComparisonSnapshot
    { public int revision; public TutorSettings settings; public TutorChange[] changes; public TutorExchange[] conversation; }
    [Serializable] public class ComparisonResult
    { public string outcome, message; public int branch_revision; public ComparisonSnapshot state; }
    [Serializable] public class ComparisonBranch
    { public string branch_id, status, error_code; public int branch_revision; public TutorQuestion question; public ComparisonResult result; }
    [Serializable] public class ComparisonBranches
    {
        public ComparisonBranch E, A, N, S;
        public ComparisonBranch Get(string c) => c == "E" ? E : c == "A" ? A : c == "N" ? N : c == "S" ? S : null;
    }
    [Serializable] public class ComparisonPreparation { public string status; public int attempt; }
    [Serializable] public class ComparisonReveal { public string reveal_id; public int task_revision; }
    [Serializable] public class FeedbackStatus { public int feedback_revision; public bool current, complete; }
    [Serializable] public class ComparisonFeedbackStatuses
    {
        public FeedbackStatus E, A, N, S;
        public FeedbackStatus Get(string c) => c == "E" ? E : c == "A" ? A : c == "N" ? N : S;
    }
    [Serializable] public class ComparisonSequence
    {
        public bool registered, at_module_end, has_next_module, has_next_in_module, all_attributes, attribute_saved, overall_saved, comparison_complete, preference_paused, preference_exited;
        public string preference_scope;
        public int module_index, module_task_index, preference_revision;
    }
    [Serializable] public class PreferenceMutation : TutorMutation { public int expected_preference_revision; public string scope; }
    [Serializable] public class ComparisonView
    {
        public string task_id, phase, mode, selected_condition, initial_query, publication_error, error, message;
        public string lifecycle, series_id, previous_task_id, next_task_id, submission_id;
        public string task_code, domain, scenario, feedback_version;
        public int revision, sequence_index; public bool results_visible, can_submit, audio_available, preparation_required, preparation_confirmed, preparation_locked;
        public ComparisonSequence sequence;
        public ComparisonFeedbackStatuses feedback;
        public ComparisonSnapshot baseline;
        public ComparisonBranches branches;
        public ComparisonPreparation shared_preparation;
        public ComparisonReveal first_reveal, latest_reveal;
        public int round_index; public string round_query;
    }
    [Serializable] public class ComparisonCreate
    { public string request_id, participant_id = "UNITYDEBUG", task_code = "UNITY-COMPARE", domain = "reply_length", scenario = "C1", phase = "debug"; public bool require_preparation; public string feedback_version; }
    [Serializable] public class PreparationLength : TutorMutation { public TutorLengthPatch patch; }
    [Serializable] public class PreparationRate : TutorMutation { public TutorRatePatch patch; }
    [Serializable] public class PreparationTone : TutorMutation { public TutorTonePatch patch; }
    [Serializable] public class PreparationVoice : TutorMutation { public TutorVoicePatch patch; }
    [Serializable] public class ComparisonSelect : TutorMutation { public string condition; }
    [Serializable] public class ComparisonSharedRetry : TutorMutation { public int expected_attempt; }
    [Serializable] public class ComparisonMutation { public string request_id; public int expected_branch_revision; }
    [Serializable] public class ComparisonRequest : ComparisonMutation { public string query; }
    [Serializable] public class ComparisonControl : ComparisonMutation { public TutorLengthPatch patch; }
    [Serializable] public class ComparisonRateControl : ComparisonMutation { public TutorRatePatch patch; }
    [Serializable] public class ComparisonToneControl : ComparisonMutation { public TutorTonePatch patch; }
    [Serializable] public class ComparisonVoiceControl : ComparisonMutation { public TutorVoicePatch patch; }
    [Serializable] public class ComparisonUndo : ComparisonMutation { public string field = "reply_length"; }
    [Serializable] public class ComparisonText { public string text; }
    [Serializable] public class ComparisonOption { public string option_id; }
    [Serializable] public class ComparisonOther : ComparisonOption { public string text; }
    [Serializable] public class ComparisonTextAnswer : ComparisonMutation { public string question_id; public ComparisonText response; }
    [Serializable] public class ComparisonOptionAnswer : ComparisonMutation { public string question_id; public ComparisonOption response; }
    [Serializable] public class ComparisonOtherAnswer : ComparisonMutation { public string question_id; public ComparisonOther response; }
    [Serializable] public class ComparisonFeedbackSave : ComparisonMutation { public int expected_feedback_revision; }
    [Serializable] public class ComparisonPresentation : ComparisonMutation { public string page; }

    /// <summary>Async debug comparison; one gated projection drives ALL visual state.</summary>
    public sealed class TutorComparisonClient : MonoBehaviour, ITutorPanelClient
    {
        public string endpoint = "http://127.0.0.1:8765";
        public bool connectOnStart = true;
        public bool requirePreparation = true;
        public string feedbackVersion = "attribute-feedback-v2";
        public JObject FeedbackDraft(string condition) => feedbackProjection?[condition]?["draft"] as JObject;
        public int FirstConversationCount(string condition) => firstProjection?["branches"]?[condition]?["state"]?["conversation"] is JArray a ? a.Count : 0;
        JObject feedbackProjection, firstProjection;
        [NonSerialized] public bool instructionsOpen;
        public int timeoutSeconds = 20;
        public AppearanceAvatar avatar;
        public ComparisonView State { get; private set; }
        public TutorView View { get; private set; }
        public bool Busy { get; private set; }
        public bool UnknownOutcome { get; private set; }
        public string RecordingError { get; private set; } = "";
        public string Error { get; private set; } = "";
        public event Action Changed;
        public static readonly string[] Conditions = { "E", "A", "N", "S" };
        public bool Connected => State != null && !string.IsNullOrEmpty(State.task_id);
        public string Selected => Connected ? State.selected_condition : "E";
        public ComparisonBranch Branch => Connected ? State.branches.Get(Selected) : null;
        public bool Open => Connected && State.phase != "closed";
        public bool Paused => Connected && State.lifecycle == "paused";
        public bool CanPauseOrResume => Open && !Busy && !UnknownOutcome;
        public bool Available => !studyLocked && CanPauseOrResume && !Paused;
        public bool HasQuestion => Open && !Paused && Branch.status == "awaiting_clarification" && View.question != null;
        public bool HasQueuedAnswer => false; // The backend owns generation scheduling.
        public bool PreparationPending => Connected && State.phase == "awaiting_input" && State.preparation_required && !State.preparation_confirmed;
        public bool CanConfirmPreparation => Available && !instructionsOpen && PreparationPending;
        public bool CanPrepare => CanConfirmPreparation && !State.preparation_locked;
        public bool CanEditBranch => Available && !instructionsOpen && State.results_visible && (Branch.status == "ready" || Branch.status == "stopped");
        public bool CanEdit => CanPrepare || CanEditBranch;
        public bool CanSubmit => Available && !instructionsOpen && !PreparationPending && (State.phase == "awaiting_input" || HasQuestion || CanEditBranch);
        public bool CanUndo => CanEditBranch && (View.changes ?? Array.Empty<TutorChange>()).Any(c => c.kind == "commit" && (c.remaining_fields ?? Array.Empty<string>()).Contains("reply_length"));
        public bool CanStop => Available && !string.IsNullOrEmpty(State.initial_query) && Branch.status != "ready" && Branch.status != "stopped" && Branch.status != "waiting";
        public bool CanRetry => !Busy && (pendingJson != null || pendingNextId != null || !string.IsNullOrEmpty(RecordingError) || Available && (!string.IsNullOrEmpty(State.publication_error) || Branch.status == "failed"));
        public string Activity
        {
            get
            {
                if (!Connected) return "Connect to start a debug comparison.";
                if (State.lifecycle == "submitted") return "Feedback submitted. This task's evaluated results are fixed.";
                if (!Open) return "Comparison ended. This task is closed.";
                if (UnknownOutcome) return "Request outcome unknown. Retry the same request to recover.";
                if (Paused) return "Paused · Resume when ready, or end this task without submitting.";
                if (!string.IsNullOrEmpty(RecordingError)) return RecordingError;
                if (!string.IsNullOrEmpty(State.publication_error)) return "Results remain hidden: recording failed. Retry to publish.";
                if (PreparationPending) return State.preparation_locked ? "Fixed study starting settings · Listen to the sample, then confirm to begin." : "Adjust the shared settings and try the sample, then confirm to begin.";
                if (State.phase == "awaiting_input") return "Shared settings fixed · Record one request for all four strategies.";
                if (!State.results_visible)
                {
                    int asks = Conditions.Count(c => State.branches.Get(c).status == "awaiting_clarification");
                    int fails = Conditions.Count(c => State.branches.Get(c).status == "failed");
                    return fails > 0 ? "Results hidden · Select a failed strategy to retry or stop it."
                        : asks > 0 ? $"Results hidden · {asks} clarification(s) pending. Select a strategy marked Ask."
                        : "Results hidden · Preparing all four strategies...";
                }
                return HasQuestion ? $"{Selected} · Answer this strategy's clarification."
                    : Branch.status == "processing" ? $"{Selected} · Preparing an updated result..."
                    : Branch.status == "failed" ? $"{Selected} · Update failed. Retry or stop this branch."
                    : $"{Selected} · {Branch.result?.outcome ?? "Ready"} · New requests and controls apply to all four strategies.";
            }
        }

        string pendingRoute, pendingJson, pendingNextId, appliedAppearance = "", presentationKey = "";
        sealed class PresentationRecord { public string route; public ComparisonPresentation body; public bool knownFailure; }
        readonly Queue<PresentationRecord> presentations = new Queue<PresentationRecord>();
        bool pendingKnown;
        long commandEpoch;
        UnityWebRequest activeCommand, activePoll, activePresentation;
        float nextPoll;
        void Start()
        {
            endpoint = System.Environment.GetEnvironmentVariable("TUTOR_BACKEND_URL") ?? endpoint;
            if (connectOnStart) Connect();
        }
        void OnEnable() { StartCoroutine(PollLoop()); }
        void Notify() { Changed?.Invoke(); }
        public bool studyManaged;
        public TutorStudyJournal studyJournal;
        public string studyRunId;
        public bool studyLocked;
        public void AttachStudyRuntime(string id)
        {
            if (Busy) return;
            if (activePoll != null) activePoll.Abort();
            commandEpoch++; State = null; pendingJson = pendingRoute = pendingNextId = null; UnknownOutcome = false;
            StartCoroutine(Transfer("/tutor/comparisons/" + id, null, commandEpoch));
        }
        public void Connect()
        { ConnectTask(null); }
        public void ConnectTask(TutorTaskStart task, TutorSequencePlan sequence = null)
        {
            if (studyManaged || Busy || Connected || pendingJson != null) return;
            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) || (uri.Scheme != "http" && uri.Scheme != "https") || !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment))
            { Error = "Set a valid backend URL without credentials, query or fragment."; Notify(); return; }
            var body = new ComparisonCreate { request_id = NewID(), feedback_version = feedbackVersion, require_preparation = task != null || requirePreparation };
            if (task != null) { body.task_code = task.task_code; body.domain = task.domain; body.scenario = task.scenario; }
            string json = JsonUtility.ToJson(body);
            if (sequence != null) json = json.Substring(0, json.Length - 1) + ",\"sequence\":" + JsonUtility.ToJson(sequence) + "}";
            Dispatch("/tutor/comparisons", json);
        }
        static string NewID() => Guid.NewGuid().ToString("N");
        string Route(string op) => "/tutor/comparisons/" + State.task_id + "/" + op;
        void TaskCommand(string op, TutorMutation body)
        {
            if (!CanPauseOrResume || Paused && op != "resume" && op != "close") return;
            body.request_id = NewID(); body.expected_revision = State.revision;
            Dispatch(Route(op), JsonUtility.ToJson(body));
        }
        void BranchCommand(string op, ComparisonMutation body)
        {
            if (!Available) return;
            body.request_id = NewID(); body.expected_branch_revision = Branch.branch_revision;
            Dispatch(Route("branches/" + Selected + "/" + op), JsonUtility.ToJson(body));
        }
        public void Select(string condition)
        {
            if (!PreparationPending && Conditions.Contains(condition) && condition != Selected)
                TaskCommand("select", new ComparisonSelect { condition = condition });
        }
        public void ConfirmPreparation()
        {
            if (CanConfirmPreparation) TaskCommand("confirm_preparation", new TutorMutation());
        }
        public void SubmitUserUtterance(string transcript)
        {
            if (!CanSubmit || string.IsNullOrWhiteSpace(transcript)) return;
            if (HasQuestion) BranchCommand("answer", new ComparisonTextAnswer { question_id = View.question.question_id, response = new ComparisonText { text = transcript.Trim() } });
            else if (State.phase == "awaiting_input") TaskCommand("start", new TutorRequest { query = transcript.Trim() });
            else TaskCommand("round_request", new TutorRequest { query = transcript.Trim() });
        }
        public void SubmitClarification(string transcript)
        {
            if (Available && HasQuestion && !string.IsNullOrWhiteSpace(transcript))
                BranchCommand("answer", new ComparisonOtherAnswer { question_id = View.question.question_id, response = new ComparisonOther { option_id = "other", text = transcript.Trim() } });
        }
        public void ChooseOption(string id)
        {
            if (Available && HasQuestion && id != "other" && (View.question.options ?? Array.Empty<TutorOption>()).Any(o => o.id == id))
                BranchCommand("answer", new ComparisonOptionAnswer { question_id = View.question.question_id, response = new ComparisonOption { option_id = id } });
        }
        public void SetReplyLength(int index)
        {
            if (!CanEdit || index < 0 || index > 2) return;
            string length = new[] { "brief", "balanced", "detailed" }[index];
            if (CanPrepare ? length == View.settings.reply_length : Conditions.All(c=>State.branches.Get(c).result.state.settings.reply_length==length)) return;
            var patch = new TutorLengthPatch { reply_length = length };
            if (CanPrepare) TaskCommand("prepare", new PreparationLength { patch = patch });
            else TaskCommand("round_settings", new PreparationLength { patch = patch });
        }
        public void SetSpeechRate(float value)
        {
            if (!CanEdit || float.IsNaN(value) || float.IsInfinity(value) || value < .7f || value > 1.3f) return;
            value = Mathf.Round(value * 100) / 100;
            if (CanPrepare ? Mathf.Abs(View.settings.speech_rate-value)<.001f : Conditions.All(c=>Mathf.Abs(State.branches.Get(c).result.state.settings.speech_rate-value)<.001f)) return;
            var patch = new TutorRatePatch { speech_rate = value };
            if (CanPrepare) TaskCommand("prepare", new PreparationRate { patch = patch });
            else TaskCommand("round_settings", new PreparationRate { patch = patch });
        }
        public void SetTone(int index)
        {
            if (!CanEdit || index < 0 || index > 2) return;
            string value = new[] { "professional", "friendly", "encouraging" }[index];
            if (CanPrepare ? View.settings.tone==value : Conditions.All(c=>State.branches.Get(c).result.state.settings.tone==value)) return;
            var patch = new TutorTonePatch { tone = value };
            if (CanPrepare) TaskCommand("prepare", new PreparationTone { patch = patch });
            else TaskCommand("round_settings", new PreparationTone { patch = patch });
        }
        public void SetVoice(int index)
        {
            if (!CanEdit || index < 0 || index >= TutorVoiceCatalog.Ids.Length) return;
            string value = TutorVoiceCatalog.Ids[index];
            if (CanPrepare ? View.settings.voice==value : Conditions.All(c=>State.branches.Get(c).result.state.settings.voice==value)) return;
            var patch = new TutorVoicePatch { voice = value };
            if (CanPrepare) TaskCommand("prepare", new PreparationVoice { patch = patch });
            else TaskCommand("round_settings", new PreparationVoice { patch = patch });
        }
        public bool CanUndoSetting(string field) => CanEditBranch && Conditions.All(c =>
            (State.branches.Get(c).result.state.changes ?? Array.Empty<TutorChange>()).Any(change => change.kind=="commit" &&
            (field=="all" ? (change.remaining_fields?.Length ?? 0)>0 : (change.remaining_fields ?? Array.Empty<string>()).Contains(field))));
        public void UndoSetting(string field) { if (CanUndoSetting(field)) TaskCommand("round_undo", new TutorUndo { field = field }); }
        public void UndoReplyLength() { UndoSetting("reply_length"); }
        public void StopBranch() { if (CanStop) BranchCommand("stop", new ComparisonMutation()); }
        public void Close() { TaskCommand("close", new TutorMutation()); }
        public void PauseOrResume() { TaskCommand(Paused ? "resume" : "pause", new TutorMutation()); }
        // Integration boundary for the later questionnaire UI: no default or
        // inferred answers, no survey transcript sent to SubmitUserUtterance.
        public void SaveFeedback(string answersJson)
        {
            if (!CanEditBranch || State.feedback == null || string.IsNullOrWhiteSpace(answersJson)) return;
            var body = new ComparisonFeedbackSave { request_id = NewID(), expected_branch_revision = Branch.branch_revision,
                expected_feedback_revision = State.feedback.Get(Selected).feedback_revision };
            string json = JsonUtility.ToJson(body);
            Dispatch(Route("branches/" + Selected + "/feedback"), json.Substring(0, json.Length - 1) + ",\"answers\":" + answersJson + "}");
        }
        public bool AtPreferenceBoundary => Connected && State.lifecycle == "submitted" && State.sequence?.registered == true && State.sequence.at_module_end && string.IsNullOrEmpty(State.next_task_id);
        public bool PreferenceAvailable => AtPreferenceBoundary && !Busy && !UnknownOutcome && !State.sequence.preference_paused && !State.sequence.preference_exited && !string.IsNullOrEmpty(State.sequence.preference_scope);
        public void SavePreference(string scope, string answersJson)
        {
            if (!PreferenceAvailable || scope != State.sequence.preference_scope) return;
            var body = new PreferenceMutation { request_id = NewID(), expected_revision = State.revision, expected_preference_revision = State.sequence.preference_revision, scope = scope };
            string json = JsonUtility.ToJson(body);
            Dispatch(Route("preference"), json.Substring(0, json.Length - 1) + ",\"answers\":" + answersJson + "}");
        }
        public void PreferenceLifecycle(string operation)
        {
            if (!AtPreferenceBoundary || Busy || UnknownOutcome || State.sequence.preference_exited || !new[] { "preference_pause", "preference_resume", "preference_exit" }.Contains(operation)) return;
            string json = JsonUtility.ToJson(new TutorMutation { request_id = NewID(), expected_revision = State.revision });
            Dispatch(Route(operation), json.Substring(0, json.Length - 1) + ",\"expected_preference_revision\":" + State.sequence.preference_revision + "}");
        }
        public void SubmitTask() { if (Available && State.can_submit) TaskCommand("submit", new TutorMutation()); }
        public void AdvanceToTask(string taskJson)
        {
            if (!Connected || State.lifecycle != "submitted" || Busy || UnknownOutcome || string.IsNullOrWhiteSpace(taskJson)) return;
            if (!string.IsNullOrEmpty(State.next_task_id)) { pendingNextId = State.next_task_id; StartCoroutine(LoadNext()); return; }
            string json = JsonUtility.ToJson(new TutorMutation { request_id = NewID(), expected_revision = State.revision });
            Dispatch(Route("next"), json.Substring(0, json.Length - 1) + ",\"next_task\":" + taskJson + "}");
        }
        public void RecordPresentation(string page, bool visible)
        {
            if (!visible || !Open || Paused) { presentationKey = ""; return; }
            string key = State.task_id + ":" + Selected + ":" + Branch.branch_revision + ":" + State.results_visible + ":" + page;
            if (presentationKey == key) return;
            presentationKey = key;
            presentations.Enqueue(new PresentationRecord { route = Route("branches/" + Selected + "/presentation"),
                body = new ComparisonPresentation { request_id = NewID(), expected_branch_revision = Branch.branch_revision, page = page } });
        }
        public void RefreshState() { if (Connected && !Busy && activePoll == null) StartCoroutine(Fetch()); }
        public void Retry()
        {
            if (!CanRetry) return;
            if (pendingNextId != null) { StartCoroutine(LoadNext()); return; }
            if (pendingJson != null)
            {
                // Unknown outcome: exact body, including create ID. Known audit
                // rejection is cached: a new ID explicitly retries that command.
                string json = pendingJson;
                if (pendingKnown)
                {
                    var old = JsonUtility.FromJson<ComparisonCreate>(json).request_id;
                    json = json.Replace("\"request_id\":\"" + old + "\"", "\"request_id\":\"" + NewID() + "\"");
                }
                Dispatch(pendingRoute, json); return;
            }
            if (!string.IsNullOrEmpty(RecordingError))
            {
                if (presentations.Count > 0 && presentations.Peek().knownFailure) presentations.Peek().body.request_id = NewID();
                RecordingError = ""; return;
            }
            if (!string.IsNullOrEmpty(State.publication_error)) TaskCommand("retry_reveal", new TutorMutation());
            else if (State.shared_preparation.status == "failed" && !State.results_visible)
                TaskCommand("retry_shared", new ComparisonSharedRetry { expected_attempt = State.shared_preparation.attempt });
            else if (Branch.status == "failed") BranchCommand("retry", new ComparisonMutation());
        }
        void Dispatch(string route, string json)
        {
            if (Busy) return;
            commandEpoch++; if (activePoll != null) activePoll.Abort();
            pendingRoute = route; pendingJson = json;
            StartCoroutine(Command(route, json));
        }
        IEnumerator Command(string route, string json)
        {
            Busy = true; Error = ""; Notify();
            try
            {
                yield return Transfer(route, json, commandEpoch);
                if (route.EndsWith("/next") && !UnknownOutcome && pendingJson == null && !string.IsNullOrEmpty(State.next_task_id))
                {
                    pendingNextId = State.next_task_id;
                    yield return Transfer("/tutor/comparisons/" + pendingNextId, null, commandEpoch);
                }
            }
            finally { activeCommand = null; activePoll = null; Busy = false; nextPoll = 0; Notify(); }
        }
        IEnumerator PollLoop()
        {
            while (true)
            {
                if (!Busy && activePoll == null && activePresentation == null && presentations.Count > 0 && string.IsNullOrEmpty(RecordingError)) yield return SendPresentation();
                if (Open && !Busy && activePoll == null && Time.realtimeSinceStartup >= nextPoll) yield return Fetch();
                yield return null;
            }
        }
        IEnumerator LoadNext()
        {
            Busy = true; commandEpoch++; Notify();
            try { yield return Transfer("/tutor/comparisons/" + pendingNextId, null, commandEpoch); }
            finally { activePoll = null; Busy = false; Notify(); }
        }
        IEnumerator SendPresentation()
        {
            var record = presentations.Peek();
            using (var request = new UnityWebRequest(endpoint.TrimEnd('/') + record.route, "POST"))
            {
                activePresentation = request; request.timeout = timeoutSeconds;
                request.downloadHandler = new DownloadHandlerBuffer();
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(record.body)));
                request.SetRequestHeader("Content-Type", "application/json");
                yield return request.SendWebRequest();
                // A stale presentation is not evidence that a newer result was
                // seen. Drop rejected events; never apply their state response.
                if (request.result == UnityWebRequest.Result.Success || request.responseCode == 400 || request.responseCode == 404 || request.responseCode == 409)
                    presentations.Dequeue();
                else
                {
                    record.knownFailure = request.responseCode == 502 || request.responseCode == 503;
                    RecordingError = "Interaction recording interrupted. Select Retry to recover.";
                }
                activePresentation = null;
            }
        }
        IEnumerator Fetch()
        {
            try { yield return Transfer("/tutor/comparisons/" + State.task_id, null, commandEpoch); }
            finally { activePoll = null; nextPoll = Time.realtimeSinceStartup + .5f; }
        }
        IEnumerator Transfer(string route, string json, long epoch)
        {
            string evidence=null; bool storageFailed=false;
            try{if(studyManaged && json!=null)evidence=TutorStudyRuntimeEvidence.Save(studyJournal,studyRunId,route,json);}
            catch(Exception){storageFailed=true;Error="Submitted text could not be saved locally. Request was not sent.";}
            if(storageFailed){Notify();yield break;}
            using (var request = new UnityWebRequest(endpoint.TrimEnd('/') + route, json == null ? "GET" : "POST"))
            {
                if (json == null) activePoll = request; else activeCommand = request;
                request.downloadHandler = new DownloadHandlerBuffer(); request.timeout = timeoutSeconds;
                if (json != null) { request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)); request.SetRequestHeader("Content-Type", "application/json"); }
                yield return request.SendWebRequest();
                if(json==null && ReferenceEquals(activePoll,request))activePoll=null;
                if (epoch != commandEpoch) yield break; // An old poll cannot replace a command result.
                ComparisonView parsed = null;
                try { parsed = JsonUtility.FromJson<ComparisonView>(request.downloadHandler.text); } catch (ArgumentException) { }
                // JsonUtility can instantiate empty nested DTOs for JSON null.
                // Normalize the hidden projection instead of treating those
                // empty objects as completed results or pending questions.
                if (parsed != null && !parsed.results_visible)
                {
                    parsed.first_reveal = null;
                    if (parsed.branches != null)
                        foreach (string c in Conditions)
                            if (parsed.branches.Get(c) != null) parsed.branches.Get(c).result = null;
                }
                bool isNext = Connected && pendingNextId != null && parsed?.task_id == pendingNextId
                    && parsed.previous_task_id == State.task_id && parsed.series_id == State.series_id && parsed.sequence_index == State.sequence_index + 1;
                bool valid = ValidView(parsed) && (!Connected || isNext || parsed.task_id == State.task_id && parsed.revision >= State.revision);
                if (valid)
                {
                    if (isNext) { pendingNextId = null; presentationKey = ""; }
                    State = parsed; feedbackProjection = JObject.Parse(request.downloadHandler.text)["feedback"] as JObject; firstProjection = JObject.Parse(request.downloadHandler.text)["first_reveal"] as JObject; View = Project(parsed); ApplyAppearance();
                }
                bool transport = request.result == UnityWebRequest.Result.ConnectionError || request.result == UnityWebRequest.Result.DataProcessingError
                    || (request.responseCode >= 200 && request.responseCode < 300 && !valid);
                if (request.result == UnityWebRequest.Result.Success && valid)
                {
                    try{TutorStudyRuntimeEvidence.Acknowledge(studyJournal,evidence,request.downloadHandler.text);}
                    catch(Exception){storageFailed=true;UnknownOutcome=true;Error="Reply received but local receipt saving failed. Original input is retained.";}
                    if(storageFailed){Notify();yield break;}
                    if (json != null) { pendingJson = pendingRoute = null; pendingKnown = false; UnknownOutcome = false; }
                    if (!UnknownOutcome && !pendingKnown) Error = "";
                }
                else
                {
                    Error = transport ? "Connection interrupted. Sync or retry the pending request." : parsed?.message ?? "The backend could not process this request. Sync and try again.";
                    if (json != null)
                    {
                        UnknownOutcome = transport;
                        pendingKnown = !transport && (request.responseCode == 502 || request.responseCode == 503);
                        if (!transport && !pendingKnown) pendingJson = pendingRoute = null;
                    }
                }
            }
            Notify();
        }
        static bool ValidView(ComparisonView v) => v != null && !string.IsNullOrEmpty(v.task_id) && v.baseline?.settings != null
            && v.branches != null && Conditions.Contains(v.selected_condition) && Conditions.All(c => v.branches.Get(c) != null)
            && (!v.results_visible || v.first_reveal != null && !string.IsNullOrEmpty(v.first_reveal.reveal_id) && Conditions.All(c => v.branches.Get(c).result?.state?.settings != null));

        // This is also the future audio entry point: only this projection may
        // feed output components. Never read branch.result directly in the UI.
        public static TutorView Project(ComparisonView v)
        {
            var branch = v.branches.Get(v.selected_condition);
            var snapshot = v.results_visible ? branch.result.state : v.baseline;
            return new TutorView { session_id = v.task_id, condition = v.selected_condition, phase = v.phase, mode = v.mode,
                revision = branch.branch_revision, state_revision = snapshot.revision, settings = snapshot.settings, audio_available = v.audio_available,
                changes = snapshot.changes, conversation = snapshot.conversation,
                question = v.phase != "closed" && v.lifecycle != "paused" && branch.status == "awaiting_clarification" && !string.IsNullOrEmpty(branch.question?.question_id) ? branch.question : null,
                message = v.results_visible ? branch.result.message : "", decision = v.results_visible ? branch.result.outcome : "HIDDEN" };
        }
        public void ReapplyAppearance(){appliedAppearance="";ApplyAppearance();}
        void ApplyAppearance()
        {
            if (!avatar || View?.settings == null) return;
            var s = View.settings;
            string key = $"{s.avatar_id}|{s.outfit}|{s.jacket_color}|{s.accessory}|{s.scale}";
            if (key == appliedAppearance) return;
            avatar.EnableDemo(true);
            avatar.Apply(new AppearanceState { avatar_id = s.avatar_id, outfit = s.outfit, jacket_color = s.jacket_color, accessory = s.accessory, scale = s.scale });
            appliedAppearance = key;
        }
        void OnDisable()
        {
            commandEpoch++;
            if (activeCommand != null) { UnknownOutcome = true; pendingKnown = false; activeCommand.Abort(); }
            if (activePoll != null) activePoll.Abort();
            if (activePresentation != null) { activePresentation.Abort(); RecordingError = "Interaction recording interrupted. Select Retry to recover."; }
            StopAllCoroutines(); activeCommand = activePoll = activePresentation = null; Busy = false;
        }
    }
}
