using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    [Serializable] public class TutorTranscribeRequest
    { public string request_id, condition, question_id, audio_base64; public int expected_revision; }
    [Serializable] class TutorTranscript { public string text; }
    [Serializable] class TutorSpeechStatus { public bool configured; }

    /// <summary>Transient microphone audio; review text before the existing mutation.
    /// The captured revision/question prevents delayed speech crossing task boundaries.</summary>
    public sealed class TutorSpeechInput : MonoBehaviour
    {
        public TutorPanel panel;
        public TutorStudyPanel studyPanel;
        public TutorStudyFlowPanel flowPanel;
        bool Survey => studyPanel != null || flowPanel != null;
        public string Transcript { get; private set; } = "";
        public string Status { get; private set; } = "Record a request or clarification.";
        public bool Recording { get; private set; }
        public bool Working { get; private set; }
        public bool HasCapture => context != null;
        public event Action Changed;
        ITutorPanelClient Driver => panel.comparison ? (ITutorPanelClient)panel.comparison : panel.client;
        string Endpoint => panel.comparison ? panel.comparison.endpoint : panel.client.endpoint;
        string context, route, device;
        TutorTranscribeRequest body;
        AudioClip clip;
        UnityWebRequest request;
        float started;
        int epoch;
        public bool CanRecord => flowPanel ? flowPanel.CanRecordComment : Survey ? studyPanel.CanRecordComment : panel && panel.SpeechVisible && Driver != null && Driver.CanSubmit && !Driver.HasQueuedAnswer;
        public bool CanSend => CanRecord && !Working && !Recording && Transcript.Length > 0 && context == CurrentContext();
        string CurrentContext()
        {
            if (!CanRecord) return null;
            var c = panel.comparison;
            if (Survey) return flowPanel ? flowPanel.CommentContext : studyPanel.CommentContext;
            return Endpoint + ":" + (c ? c.State.task_id + ":" + c.State.revision + ":" + c.Selected + ":" + (c.View.question?.question_id ?? "")
                : panel.client.View.session_id + ":" + panel.client.View.revision + ":" + (panel.client.View.question?.question_id ?? ""));
        }
        bool Capture()
        {
            if (!CanRecord) return false;
            context = CurrentContext();
            var c = panel.comparison;
            if(flowPanel)
            {
                route="/study/runs/"+flowPanel.RunId+"/transcribe";
                body=new TutorTranscribeRequest{request_id=Guid.NewGuid().ToString("N"),expected_revision=flowPanel.Revision,
                    condition=flowPanel.CommentCondition,question_id=flowPanel.CommentTarget};return true;
            }
            route = c ? "/tutor/comparisons/" + c.State.task_id + "/transcribe" : "/tutor/sessions/" + panel.client.View.session_id + "/transcribe";
            if (Survey) route = "/tutor/comparisons/" + c.State.task_id + (studyPanel.PreferenceMode ? "/preference-transcribe" : "/survey-transcribe");
            body = new TutorTranscribeRequest { request_id = Guid.NewGuid().ToString("N"),
                expected_revision = Survey ? (studyPanel.PreferenceMode ? c.State.sequence.preference_revision : c.Branch.branch_revision) : c ? c.State.revision : panel.client.View.revision,
                condition = Survey && studyPanel.PreferenceMode ? studyPanel.PreferenceScope : c ? c.Selected : panel.client.View.condition, question_id = Survey ? "" : Driver.View.question?.question_id ?? "" };
            return true;
        }
        public void PressRecord()
        {
            if (Survey && panel.Speech) panel.Speech.Cancel();
            if (panel.Playback) panel.Playback.Stop(reason: "recording_started");
            if (Recording) { FinishRecording(); return; }
            if (Working) { Cancel("Recording cancelled."); return; }
            Cancel();
            if (Capture()) StartCoroutine(BeginRecording(epoch));
        }
        IEnumerator BeginRecording(int token)
        {
            Working = true; Status = "Checking speech service..."; Notify();
            using (var check = UnityWebRequest.Get(Endpoint.TrimEnd('/') + "/speech/status"))
            {
                request = check; check.timeout = 8; yield return check.SendWebRequest(); request = null;
                if (token != epoch) yield break;
                bool configured = false;
                if (check.result == UnityWebRequest.Result.Success)
                { try { configured = JsonUtility.FromJson<TutorSpeechStatus>(check.downloadHandler.text).configured; } catch (Exception) { } }
                if (!configured) { Cancel("Speech service unavailable. Ask the researcher to check the backend."); yield break; }
            }
            Status = "Allow microphone access to record."; Notify();
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(UnityEngine.Android.Permission.Microphone))
            {
                bool answered = false;
                var callbacks = new UnityEngine.Android.PermissionCallbacks();
                callbacks.PermissionGranted += _ => answered = true;
                callbacks.PermissionDenied += _ => answered = true;
                callbacks.PermissionDeniedAndDontAskAgain += _ => answered = true;
                UnityEngine.Android.Permission.RequestUserPermission(UnityEngine.Android.Permission.Microphone, callbacks);
                float until = Time.realtimeSinceStartup + 30;
                while (!answered && Time.realtimeSinceStartup < until && token == epoch) yield return null;
                if (token != epoch) yield break;
                if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(UnityEngine.Android.Permission.Microphone))
                { Cancel("Microphone permission was not granted. Enable it in system settings."); yield break; }
            }
#else
            yield return Application.RequestUserAuthorization(UserAuthorization.Microphone);
            if (token != epoch) yield break;
            if (!Application.HasUserAuthorization(UserAuthorization.Microphone))
            { Cancel("Microphone permission was not granted. Enable it in system settings."); yield break; }
#endif
            if (context != CurrentContext()) { Cancel("Input context changed. Record again."); yield break; }
            try
            {
                if (Microphone.devices.Length == 0) { Cancel("No microphone found."); yield break; }
                device = Microphone.devices[0]; clip = Microphone.Start(device, false, 120, 16000);
                if (!clip) { Cancel("Microphone could not start."); yield break; }
                Recording = true; Working = false; started = Time.realtimeSinceStartup;
                Status = "Recording · press Stop when finished."; Notify();
            }
            catch (Exception) { Cancel("Microphone could not start."); }
        }
        void Update()
        {
            if (context != null && context != CurrentContext()) { Cancel("Input context changed. Record again."); return; }
            if (Recording && Time.realtimeSinceStartup - started >= 119) FinishRecording();
        }
        void OnDisable() { Cancel(); }
        void OnApplicationPause(bool paused) { if (paused) Cancel("Recording cancelled while application was paused."); }
        void ReleaseAudio()
        {
            if (clip) { Microphone.End(device); Destroy(clip); clip = null; }
            Recording = false;
        }
        public void Cancel(string message = "Record a request or clarification.")
        {
            epoch++; StopAllCoroutines();
            if (request != null) { request.Abort(); request.Dispose(); request = null; }
            ReleaseAudio(); body = null; context = null; Transcript = ""; Working = false; Status = message; Notify();
        }
        void FinishRecording()
        {
            try
            {
                int frames = Microphone.GetPosition(device);
                if (frames < clip.frequency / 4) { Cancel("Recording too short. Please record again."); return; }
                var samples = new float[frames * clip.channels];
                if (!clip.GetData(samples, 0)) { Cancel("Could not read microphone audio."); return; }
                byte[] wav = EncodeWav(samples, clip.channels, clip.frequency);
                ReleaseAudio(); StartCoroutine(Recognize(wav, epoch));
            }
            catch (Exception) { Cancel("Could not read microphone audio. Please record again."); }
        }
        public static byte[] EncodeWav(float[] samples, int channels, int rate)
        {
            if (samples == null || channels < 1 || samples.Length % channels != 0 || samples.Length == 0 ||
                (rate != 16000 && rate != 24000 && rate != 48000) || samples.Length / channels > rate * 120)
                throw new ArgumentException("Unsupported recording format.");
            int frames = samples.Length / channels;
            using (var stream = new MemoryStream())
            using (var writer = new BinaryWriter(stream))
            {
                writer.Write(Encoding.ASCII.GetBytes("RIFF")); writer.Write(36 + frames * 2);
                writer.Write(Encoding.ASCII.GetBytes("WAVEfmt ")); writer.Write(16); writer.Write((short)1); writer.Write((short)1);
                writer.Write(rate); writer.Write(rate * 2); writer.Write((short)2); writer.Write((short)16);
                writer.Write(Encoding.ASCII.GetBytes("data")); writer.Write(frames * 2);
                for (int i = 0; i < frames; i++)
                {
                    float mono = 0; for (int c = 0; c < channels; c++) mono += samples[i * channels + c] / channels;
                    if (float.IsNaN(mono) || float.IsInfinity(mono)) throw new ArgumentException("Invalid sample.");
                    writer.Write((short)Mathf.RoundToInt(Mathf.Clamp(mono, -1, 1) * 32767));
                }
                return stream.ToArray();
            }
        }
        IEnumerator Recognize(byte[] wav, int token)
        {
            Working = true; Status = "Recognizing speech..."; Notify();
            body.audio_base64 = Convert.ToBase64String(wav);
            byte[] payload = Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)); body.audio_base64 = null;
            using (var call = new UnityWebRequest(Endpoint.TrimEnd('/') + route, "POST"))
            {
                call.uploadHandler = new UploadHandlerRaw(payload); call.downloadHandler = new DownloadHandlerBuffer();
                call.SetRequestHeader("Content-Type", "application/json"); call.timeout = 75;
                request = call; yield return call.SendWebRequest(); request = null;
                if (token != epoch) yield break;
                if (context != CurrentContext()) { Cancel("Input context changed. Record again."); yield break; }
                if (call.result != UnityWebRequest.Result.Success)
                { Cancel(call.responseCode == 409 ? "Input context changed. Record again." : "Recognition failed. Please record again."); yield break; }
                string text = null;
                try { text = JsonUtility.FromJson<TutorTranscript>(call.downloadHandler.text).text; } catch (Exception) { }
                if (string.IsNullOrWhiteSpace(text) || text.Length > 8000) { Cancel("No speech recognized. Please record again."); yield break; }
                Transcript = text.Trim(); Working = false; Status = Survey ? "Check the transcript, then Use text or record again." : "Check the transcript, then Send or Record again."; Notify();
            }
        }
        public void Submit()
        {
            if (!CanSend) return;
            string text = Transcript; var target = Driver;
            if (Survey) { if(flowPanel)flowPanel.ConfirmComment(text);else studyPanel.ConfirmComment(text); Cancel("Comment confirmed. Save this rating when ready."); }
            else { Cancel("Submitted."); target.SubmitUserUtterance(text); }
        }
        void Notify() { Changed?.Invoke(); }
#if UNITY_EDITOR
        public void RecognizeFixture(byte[] wav)
        { Cancel(); if (Capture()) StartCoroutine(Recognize(wav, epoch)); }
#endif
    }
}
