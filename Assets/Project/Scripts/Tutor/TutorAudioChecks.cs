#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Tutor
{
    public sealed class TutorAudioChecks : MonoBehaviour
    {
        [Serializable] class Counts { public int calls; }
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        TutorAudioPlayback audio;
        int count;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-audio-unity"));
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllLines(Path.Combine(Folder, "checks.txt"), passed.Concat(new[] { Result })); }
        void Check(bool ok, string message)
        { if (!ok) { Result = "FAIL: " + message; Save(); throw new Exception(Result); } passed.Add(message); }
        IEnumerator Wait(Func<bool> predicate, string message)
        {
            float until = Time.realtimeSinceStartup + 15;
            while (!predicate() && Time.realtimeSinceStartup < until) yield return null;
            Check(predicate(), message);
        }
        IEnumerator Ready() { yield return Wait(() => !client.Busy && client.CanEdit, "Selected branch settles"); }
        IEnumerator Count()
        {
            using (var r = UnityWebRequest.Get("http://127.0.0.1:8773/fixture/tts-count"))
            { r.timeout = 5; yield return r.SendWebRequest(); Check(r.result == UnityWebRequest.Result.Success, "Fixture synthesis count available"); count = JsonUtility.FromJson<Counts>(r.downloadHandler.text).calls; }
        }
        IEnumerator PlaySample()
        { panel.OpenTab(1); panel.SampleButton.onClick.Invoke(); yield return Wait(() => audio.Playing, "Sample starts from decoded WAV"); }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>(); audio = panel.Playback;
            var wav = TutorSpeechInput.EncodeWav(new float[1600], 1, 16000);
            var decoded = TutorAudioPlayback.DecodeWav(wav);
            Check(decoded.channels == 1 && decoded.frequency == 16000 && decoded.samples == 1600, "WAV decoder preserves PCM frames and sample rate"); Destroy(decoded);
            bool rejected = false; try { TutorAudioPlayback.DecodeWav(wav.Take(wav.Length - 1).ToArray()); } catch (InvalidDataException) { rejected = true; }
            Check(rejected, "Truncated WAV cannot reach playback");
            panel.OpenTab(1); Check(!audio.CanSample, "Disconnected sample is disabled");
            client.endpoint = "http://127.0.0.1:8773"; client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.Connect();
            yield return Wait(() => client.Connected && !client.Busy, "Connect to explicit audio fixture");
            Check(client.View.audio_available && audio.CanSample, "Configured TTS capability enables baseline sample");
            yield return PlaySample(); yield return Count(); int firstCount = count;
            Check(panel.GetComponent<AudioSource>().pitch == 1, "Playback does not multiply speech rate or alter voice pitch");
            Check(audio.Status.Contains("Voice D"), "Default sample uses Voice D");
            panel.SampleButton.onClick.Invoke(); Check(!audio.Active, "Stop sample releases playback");
            yield return PlaySample(); yield return Count();
            Check(count == firstCount, "Replay uses speech cache without another synthesis");
            panel.OpenTab(0); Check(!audio.Active, "Switching pages stops sample");
            client.SubmitUserUtterance("Compare an easier explanation.");
            yield return Wait(() => !client.Busy && client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification" && TutorComparisonClient.Conditions.All(c => client.State.branches.Get(c).status != "processing"), "All initial branches settle behind reveal barrier");
            Check(!audio.CanReply && !audio.Playing, "No early reply playback before all clarifications");
            foreach (string c in new[] { "A", "S" })
            {
                client.Select(c); yield return Wait(() => !client.Busy && client.Selected == c, "Select asking branch " + c);
                client.ChooseOption("c1"); yield return Wait(() => !client.Busy && !client.HasQuestion && client.Branch.status != "processing", "Resolve " + c);
            }
            yield return Wait(() => client.State.results_visible && !client.Busy, "Results reveal together");
            Check(!audio.Active && audio.CanReply, "Revealed replies wait for participant playback choice");
            panel.ReplyAudioButton.onClick.Invoke(); yield return Wait(() => audio.Playing, "Latest reply plays");
            client.Select("E"); yield return Wait(() => !client.Busy && client.Selected == "E" && !audio.Active, "Strategy switch stops previous branch audio");
            panel.OpenTab(1); client.SetVoice(0); yield return Ready();
            yield return PlaySample(); Check(audio.Status.Contains("Voice A"), "Sample follows the current voice setting");
            yield return new WaitForEndOfFrame(); Directory.CreateDirectory(Folder);
            ScreenCapture.CaptureScreenshot(Path.Combine(Folder, "sample-playing.png")); yield return new WaitForEndOfFrame();
            panel.OpenTab(0); panel.ReplyAudioButton.onClick.Invoke();
            yield return Wait(() => audio.Playing, "Old reply remains playable after setting change");
            Check(audio.Status.Contains("Voice D"), "Old reply uses its original voice snapshot");
            panel.Speech.RecognizeFixture(TutorSpeechInput.EncodeWav(new float[8000], 1, 16000)); yield return null;
            Check(!audio.Active, "Speech recognition and reply playback cannot overlap"); panel.Speech.Cancel();
            panel.OpenTab(1); client.SetVoice(2); yield return Ready();
            panel.SampleButton.onClick.Invoke(); yield return new WaitForSeconds(.2f);
            Check(audio.Loading, "Delayed fixture synthesis is pending"); panel.OpenTab(0);
            yield return new WaitForSeconds(1.7f);
            Check(!audio.Playing && !audio.Loading, "Late sample cannot play after leaving its context");
            panel.OpenTab(1); client.SetVoice(4); yield return Ready(); panel.SampleButton.onClick.Invoke();
            yield return Wait(() => !audio.Loading, "Synthesis failure completes without automatic retry");
            Check(!audio.Playing && audio.Status.Contains("unavailable") && audio.CanSample, "Synthesis failure leaves settings intact and offers explicit retry");
            client.SetVoice(3); yield return Ready(); yield return PlaySample();
            client.PauseOrResume(); yield return Wait(() => client.Paused && !client.Busy && !audio.Active, "Pause stops active audio");
            client.PauseOrResume(); yield return Wait(() => !client.Paused && !client.Busy, "Resume task");
            Check(!audio.Active, "Resume never replays old audio automatically");
            yield return PlaySample(); client.Close(); yield return Wait(() => !client.Open && !client.Busy && !audio.Active, "Ending task stops audio");
            Result = "PASS: " + passed.Count + " checks (silent fixture WAV; no paid calls or microphone recording)"; Save(); Debug.Log(Result);
        }
    }
}
#endif
