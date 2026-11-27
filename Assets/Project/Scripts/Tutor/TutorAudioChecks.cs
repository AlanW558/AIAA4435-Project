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
        IEnumerator PlayReply()
        { panel.OpenTab(0); panel.ReplyAudioButton.onClick.Invoke(); yield return Wait(() => audio.Playing, "Generated reply starts from decoded WAV"); }
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>(); audio = panel.Playback;
            var wav = TutorSpeechInput.EncodeWav(new float[1600], 1, 16000);
            var decoded = TutorAudioPlayback.DecodeWav(wav);
            Check(decoded.channels == 1 && decoded.frequency == 16000 && decoded.samples == 1600, "WAV decoder preserves PCM frames and sample rate"); Destroy(decoded);
            bool rejected = false; try { TutorAudioPlayback.DecodeWav(wav.Take(wav.Length - 1).ToArray()); } catch (InvalidDataException) { rejected = true; }
            Check(rejected, "Truncated WAV cannot reach playback");
            panel.OpenTab(1); Check(!audio.CanReply, "Disconnected reply audio is disabled");
            Check(panel.GetComponentsInChildren<UnityEngine.UI.Button>(true).All(b => !b.name.Contains("sample")), "No fixed sample playback controls remain");
            client.endpoint = "http://127.0.0.1:8773"; client.requirePreparation = false;
            client.Connect();
            yield return Wait(() => client.Connected && !client.Busy, "Connect to explicit audio fixture");
            Check(client.View.audio_available && !audio.CanReply, "TTS waits for an actual model reply");
            panel.OpenTab(0);
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
            yield return PlayReply(); yield return Count(); int firstCount=count;
            Check(panel.GetComponent<AudioSource>().pitch == 1, "Playback preserves the provider speech rate and pitch");
            Check(audio.Status.Contains(TutorVoiceCatalog.Labels[3]), "Reply uses the recorded default voice");
            audio.Stop(reason:"user_stop"); yield return PlayReply(); yield return Count();
            Check(count==firstCount, "Replaying the same actual answer uses the TTS cache");
            panel.OpenTab(1); Check(!audio.Active, "Leaving the conversation stops audio");
            panel.VoiceButtons[0].onClick.Invoke();
            Check(!client.Busy && panel.HasPendingControls, "Selecting a voice only changes the local draft");
            panel.ConfirmControlsButton.onClick.Invoke(); yield return Ready(); yield return PlayReply();
            Check(audio.Status.Contains(TutorVoiceCatalog.Labels[0]), "Confirmed controls produce a new answer using the new voice");
            panel.Speech.RecognizeFixture(TutorSpeechInput.EncodeWav(new float[8000], 1, 16000)); yield return null;
            Check(!audio.Active, "Speech recognition and playback cannot overlap"); panel.Speech.Cancel();
            panel.OpenTab(1); panel.VoiceButtons[2].onClick.Invoke(); panel.ConfirmControlsButton.onClick.Invoke(); yield return Ready();
            panel.OpenTab(0); panel.ReplyAudioButton.onClick.Invoke(); yield return new WaitForSeconds(.2f);
            Check(audio.Loading, "Delayed fixture synthesis is pending"); panel.OpenTab(2);
            yield return new WaitForSeconds(1.7f);
            Check(!audio.Playing && !audio.Loading, "Late reply cannot play after leaving its context");
            panel.OpenTab(1); panel.VoiceButtons[4].onClick.Invoke(); panel.ConfirmControlsButton.onClick.Invoke(); yield return Ready();
            panel.OpenTab(0); panel.ReplyAudioButton.onClick.Invoke();
            yield return Wait(() => !audio.Loading, "Synthesis failure completes without automatic retry");
            Check(!audio.Playing && audio.Status.Contains("unavailable") && audio.CanReply, "Failed synthesis leaves the actual reply available for explicit retry");
            panel.OpenTab(1); panel.VoiceButtons[3].onClick.Invoke(); panel.ConfirmControlsButton.onClick.Invoke(); yield return Ready(); yield return PlayReply();
            client.PauseOrResume(); yield return Wait(() => client.Paused && !client.Busy && !audio.Active, "Pause stops active audio");
            client.PauseOrResume(); yield return Wait(() => !client.Paused && !client.Busy, "Resume task");
            Check(!audio.Active, "Resume never replays old reply audio automatically");
            yield return PlayReply(); client.Close(); yield return Wait(() => !client.Open && !client.Busy && !audio.Active, "Ending task stops audio");
            yield return NaturalClarification();
            Result = "PASS: " + passed.Count + " checks (silent fixture WAV; no paid calls or microphone recording)"; Save(); Debug.Log(Result);
        }
        IEnumerator NaturalClarification()
        {
            var root=new GameObject("Natural clarification speech checks");root.SetActive(false);root.transform.position=new Vector3(100,0,0);
            var single=root.AddComponent<TutorClient>();single.connectOnStart=false;single.useEnvironmentEndpoint=false;single.endpoint="http://127.0.0.1:8773";single.condition="S";
            var ui=root.AddComponent<TutorPanel>();ui.client=single;ui.desktopDebugInput=true;root.SetActive(true);yield return null;
            single.Connect();yield return Wait(()=>single.Connected&&!single.Busy,"Natural Selective session connects");
            single.SubmitUserUtterance("Make the explanation easier.");
            yield return Wait(()=>single.HasQuestion&&!single.Busy&&ui.Playback.Playing,"New natural clarification speaks automatically");
            Check(ui.QuestionAudioButton.gameObject.activeSelf&&ui.QuestionAudioButton.interactable,"Question remains visible with explicit replay/stop");
            ui.Playback.Stop(reason:"user_stop");yield return new WaitForSecondsRealtime(.2f);
            Check(!ui.Playback.Active,"Stopped question does not restart automatically");
            string session=single.View.session_id;single.AttachStudyRuntime(session);
            yield return Wait(()=>single.Connected&&!single.Busy,"Restore pending natural question");yield return new WaitForSecondsRealtime(.2f);
            Check(single.HasQuestion&&!ui.Playback.Active,"Restored question keeps text without automatically replaying old audio");
            ui.QuestionAudioButton.onClick.Invoke();yield return Wait(()=>ui.Playback.Playing,"Participant can explicitly replay restored question");
            ui.Speech.RecognizeFixture(TutorSpeechInput.EncodeWav(new float[8000],1,16000));yield return null;
            Check(!ui.Playback.Active,"Speech input interrupts question audio");ui.Speech.Cancel();
            single.ChooseOption("cancel");yield return Wait(()=>!single.Busy&&!single.HasQuestion,"Cancel current adjustment before new request");
            ui.OpenTab(1);ui.VoiceButtons[2].onClick.Invoke();ui.ConfirmControlsButton.onClick.Invoke();yield return Wait(()=>!single.Busy,"Confirm delayed fixture voice");
            single.SubmitUserUtterance("Make the explanation easier.");yield return Wait(()=>ui.Playback.Loading,"New question begins delayed synthesis");
            single.ChooseOption("c1");yield return Wait(()=>!single.Busy&&!single.HasQuestion,"Answer while old question synthesis is pending");
            yield return new WaitForSecondsRealtime(1.7f);
            Check(!ui.Playback.Active,"Answered question never plays late synthesized audio");
            Destroy(root);yield return null;
        }
    }
}
#endif
