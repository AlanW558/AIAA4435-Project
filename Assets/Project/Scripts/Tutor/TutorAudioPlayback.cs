using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    [Serializable] class TutorAudioRequest
    { public string request_id, condition, purpose; public int expected_revision, exchange_id; }
    [Serializable] class TutorQuestionAudioRequest : TutorAudioRequest { public string question_id; }

    /// <summary>One manually requested clip, bound to a visible task/branch revision.
    /// Never synthesize from client-provided text or mutate speech with AudioSource.pitch.</summary>
    public sealed class TutorAudioPlayback : MonoBehaviour
    {
        public TutorPanel panel;
        public bool Loading { get; private set; }
        public bool Playing => source && source.isPlaying;
        public bool Active => Loading || Playing;
        public string Purpose { get; private set; } = "";
        public string Status { get; private set; } = "";
        public event Action Changed;
        ITutorPanelClient Driver => panel.comparison ? (ITutorPanelClient)panel.comparison : panel.client;
        string Endpoint => panel.comparison ? panel.comparison.endpoint : panel.client.endpoint;
        AudioSource source;
        AudioClip clip;
        UnityWebRequest request;
        string captured;
        int epoch;
        TutorPlaybackOutbox outbox;
        string reportEndpoint, reportRoute, audioRequestId;
        float playbackBegan, lastPosition;
        bool reportedStart;
        string automaticallySpokenQuestion = "";
        public string AuditError => outbox ? outbox.Error : "";
        bool EligibleFor(bool question)
        {
                if (!panel || !panel.isActiveAndEnabled || panel.Study && panel.Study.SpeechBusy || StudySurveyBusy || panel.TaskCardOpen || panel.seat && !panel.seat.IsSeated || Driver == null || !Driver.Connected ||
                    Driver.Busy || Driver.UnknownOutcome || (!question && Driver.HasQuestion) || Driver.HasQueuedAnswer || !Driver.View.audio_available ||
                    panel.client && panel.client.studyLocked ||
                    panel.Speech && (panel.Speech.Recording || panel.Speech.Working)) return false;
                var c = panel.comparison;
                bool review=c && panel.StudyFlow && panel.StudyFlow.CanReviewAttributeResults && !c.Paused &&
                    !c.instructionsOpen && c.State.results_visible && (c.Branch.status=="ready" || c.Branch.status=="stopped");
                return !c || review || c.Available && (c.State.phase == "awaiting_input" || c.CanEdit);
        }
        bool Eligible => EligibleFor(false);
        bool StudySurveyBusy => panel && panel.StudyFlow && panel.StudyFlow.Speech && (panel.StudyFlow.Speech.Recording || panel.StudyFlow.Speech.Working);
        TutorExchange Latest => (Driver?.View?.conversation ?? Array.Empty<TutorExchange>()).LastOrDefault();
        public bool CanReply => Eligible && panel.CurrentTab == 0 && (!panel.comparison || panel.comparison.State.results_visible) && Latest != null;
        public bool CanClarification => panel && !panel.comparison && panel.CurrentTab==0 && EligibleFor(true) && Driver.HasQuestion;
        string Context() => !(Purpose == "clarification" ? CanClarification : Eligible) ? null : Endpoint + ":" + Driver.View.session_id + ":" + Driver.View.condition + ":" +
            (panel.comparison ? panel.comparison.State.revision : Driver.View.revision) + ":" + panel.CurrentTab + ":" + (Purpose=="clarification" ? Driver.View.question.question_id : "");
        void Awake()
        {
            source = gameObject.AddComponent<AudioSource>();
            source.playOnAwake = false; source.loop = false; source.spatialBlend = 0;
            source.pitch = 1; source.volume = 1; source.dopplerLevel = 0; source.reverbZoneMix = 0;
        }
        public void ToggleClarification() { if (Active) Stop(reason: "user_stop"); else if (CanClarification) Begin("clarification", 0, Driver.View.settings); }
        public void ToggleReply() { if (Active) Stop(reason: "user_stop"); else if (CanReply) Begin("reply", Latest.id, Latest.settings); }
        void Begin(string purpose, int exchange, TutorSettings settings)
        {
            Stop(reason: "new_playback");
            outbox = TutorPlaybackOutbox.Instance;
            if (!outbox.CanStart) { Status = outbox.Error.Length > 0 ? outbox.Error : "Playback log pending. Please wait for synchronization."; Notify(); return; }
            Purpose = purpose; captured = Context();
            if(purpose=="clarification") automaticallySpokenQuestion=Driver.View.session_id+":"+Driver.View.question.question_id;
            var c = panel.comparison;
            TutorAudioRequest body = purpose=="clarification" ? new TutorQuestionAudioRequest { question_id=Driver.View.question.question_id } : new TutorAudioRequest();
            body.request_id=Guid.NewGuid().ToString("N");body.purpose=purpose;body.exchange_id=exchange;
            body.condition=Driver.View.condition;body.expected_revision=c ? c.State.revision : Driver.View.revision;
            string route = c ? "/tutor/comparisons/" + c.State.task_id + "/audio" : "/tutor/sessions/" + Driver.View.session_id + "/audio";
            reportEndpoint = Endpoint; reportRoute = route.Substring(0, route.Length - "audio".Length) + "playback";
            audioRequestId = body.request_id; reportedStart = false; lastPosition = 0;
            string description = TutorHistoryPresentation.Value(settings, "voice") + " · " + settings.tone + " · " +
                settings.speech_rate.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "×";
            StartCoroutine(Fetch(route, body, description, epoch));
        }
        IEnumerator Fetch(string route, TutorAudioRequest body, string description, int token)
        {
            Loading = true; Status = "Preparing " + Purpose + " audio..."; Notify();
            using (var call = new UnityWebRequest(Endpoint.TrimEnd('/') + route, "POST"))
            {
                call.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));
                call.downloadHandler = new DownloadHandlerBuffer(); call.timeout = 130;
                call.SetRequestHeader("Content-Type", "application/json"); request = call;
                yield return call.SendWebRequest(); request = null;
                if (token != epoch) yield break;
                if (captured != Context()) { Stop("Audio context changed. Select Play again."); yield break; }
                if (call.result != UnityWebRequest.Result.Success)
                { Stop(call.responseCode == 409 ? "Audio context changed. Select Play again." : "Audio unavailable. Select Play to try again."); yield break; }
                try
                {
                    clip = DecodeWav(call.downloadHandler.data);
                    source.clip = clip; source.pitch = 1; playbackBegan = Time.realtimeSinceStartup;
                    source.Play(); Report("started", "play_requested", 0, 0); reportedStart = true;
                    if (outbox.Error.Length > 0) { Stop("Playback log pending. Audio was stopped.", "playback_error", "failed"); yield break; }
                    Loading = false;
                    Status = "Playing " + Purpose + " · " + description; Notify();
                }
                catch (Exception)
                {
                    if (!reportedStart) Report("failed", "decode_error", 0, 0);
                    Stop("Could not decode audio. Select Play to try again.", "playback_error", "failed");
                }
            }
        }
        void Update()
        {
            if (!Active && CanClarification && panel.client.QuestionForAutomaticSpeech==Driver.View.question.question_id)
            {
                string key=Driver.View.session_id+":"+Driver.View.question.question_id;
                if(key!=automaticallySpokenQuestion)
                { automaticallySpokenQuestion=key;Begin("clarification",0,Driver.View.settings); }
            }
            if (captured == null) return;
            if (captured != Context()) { Stop(reason: ContextReason()); return; }
            if (Playing) lastPosition = Mathf.Max(lastPosition, source.time);
            if (!Loading && clip && !Playing)
            {
                // Audio-thread buffers and main-thread timers need not end on
                // the same frame. Use the decoded clip's playback position.
                bool ended = Mathf.Max(lastPosition, source.time) >= clip.length - .05f;
                if (ended) lastPosition = clip.length;
                Stop(ended ? "Playback complete. Select Play to listen again." : "Playback stopped unexpectedly. Select Play to retry.",
                    ended ? "natural_end" : "playback_error", ended ? "completed" : "failed");
            }
        }
        string ContextReason()
        {
            if (panel.comparison && panel.comparison.Connected)
            { if (panel.comparison.Paused) return "task_paused"; if (!panel.comparison.Open) return "task_closed"; }
            if (panel.Speech && (panel.Speech.Recording || panel.Speech.Working)) return "recording_started";
            return "context_changed";
        }
        void Report(string state, string reason, float position, float elapsed)
        {
            if (!outbox || string.IsNullOrEmpty(audioRequestId)) return;
            outbox.Enqueue(reportEndpoint, reportRoute, new TutorPlaybackReport { event_id = Guid.NewGuid().ToString("N"),
                audio_request_id = audioRequestId, @event = state, reason = reason, position_seconds = position,
                elapsed_seconds = elapsed, client_time_utc = DateTime.UtcNow.ToString("o") });
        }
        public void Stop(string message = "", string reason = "context_changed", string terminal = "stopped")
        {
            if (reportedStart)
            {
                float position = clip ? Mathf.Min(clip.length, Mathf.Max(lastPosition, source ? source.time : 0)) : lastPosition;
                Report(terminal, reason, position, Mathf.Max(0, Time.realtimeSinceStartup - playbackBegan)); reportedStart = false;
            }
            epoch++; StopAllCoroutines();
            if (request != null) { request.Abort(); request.Dispose(); request = null; }
            if (source) { source.Stop(); source.clip = null; }
            if (clip) { Destroy(clip); clip = null; }
            Loading = false; captured = null; Status = message; Notify();
        }
        void SuppressOldQuestionReplay()
        { if(panel && !panel.comparison && panel.client && panel.client.HasQuestion) automaticallySpokenQuestion=panel.client.View.session_id+":"+panel.client.View.question.question_id; }
        void OnDisable() { SuppressOldQuestionReplay();Stop(reason: "component_disabled"); }
        void OnApplicationPause(bool paused) { if (paused) { SuppressOldQuestionReplay();Stop(reason: "application_paused"); } }
        void Notify() { Changed?.Invoke(); }

        public static AudioClip DecodeWav(byte[] bytes)
        {
            if (bytes == null || bytes.Length < 44 || bytes.Length > 8000000) throw new InvalidDataException("Invalid WAV size.");
            using (var stream = new MemoryStream(bytes, false))
            using (var reader = new BinaryReader(stream))
            {
                if (Encoding.ASCII.GetString(reader.ReadBytes(4)) != "RIFF") throw new InvalidDataException("Not RIFF.");
                long end = reader.ReadUInt32() + 8L;
                if (end != bytes.Length || Encoding.ASCII.GetString(reader.ReadBytes(4)) != "WAVE") throw new InvalidDataException("Invalid WAV container.");
                int rate = 0, dataAt = -1, dataLength = 0; bool format = false;
                while (stream.Position + 8 <= end)
                {
                    string id = Encoding.ASCII.GetString(reader.ReadBytes(4)); uint size = reader.ReadUInt32();
                    long start = stream.Position, next = start + size + (size % 2);
                    if (next > end) throw new InvalidDataException("Truncated WAV chunk.");
                    if (id == "fmt ")
                    {
                        if (format || size < 16 || reader.ReadUInt16() != 1 || reader.ReadUInt16() != 1) throw new InvalidDataException("Expected mono PCM.");
                        rate = reader.ReadInt32(); int byteRate = reader.ReadInt32();
                        if ((rate != 16000 && rate != 24000 && rate != 48000) || byteRate != rate * 2 || reader.ReadUInt16() != 2 || reader.ReadUInt16() != 16)
                            throw new InvalidDataException("Expected PCM16 WAV.");
                        format = true;
                    }
                    else if (id == "data")
                    {
                        if (dataAt >= 0 || size == 0 || size % 2 != 0) throw new InvalidDataException("Invalid PCM data.");
                        dataAt = (int)start; dataLength = (int)size;
                    }
                    stream.Position = next;
                }
                if (!format || dataAt < 0 || stream.Position != end) throw new InvalidDataException("Missing WAV chunks.");
                var pcm = new float[dataLength / 2]; stream.Position = dataAt;
                for (int i = 0; i < pcm.Length; i++) pcm[i] = reader.ReadInt16() / 32768f;
                var audio = AudioClip.Create("Tutor speech", pcm.Length, 1, rate, false);
                if (!audio.SetData(pcm, 0)) { Destroy(audio); throw new InvalidDataException("Could not load PCM."); }
                return audio;
            }
        }
    }
}
