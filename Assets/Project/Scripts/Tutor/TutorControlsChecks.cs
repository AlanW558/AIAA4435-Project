#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using IAI.UI;

namespace IAI.Tutor
{
    // HTTP + real panel acceptance, using the explicit local fixture on port 8771.
    public sealed class TutorControlsChecks : MonoBehaviour
    {
        public string Result { get; private set; } = "Running";
        readonly List<string> passed = new List<string>();
        TutorComparisonClient client;
        TutorPanel panel;
        string Folder => Path.GetFullPath(Path.Combine(Application.dataPath, "../StudyData/macos/tutor-controls-unity"));
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            client.endpoint = "http://127.0.0.1:8771";
            panel.OpenTab(1); panel.Render(); Locked("Disconnected");
            client.requirePreparation = false;
            client.Connect(); yield return Idle();
            Check(client.Connected, "Comparison connects"); Locked("Initial request");
            client.SubmitUserUtterance("Compare an easier explanation."); yield return Idle();
            yield return Wait(() => !client.Busy && client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification" && TutorComparisonClient.Conditions.All(c=>client.State.branches.Get(c).status!="processing"&&client.State.branches.Get(c).status!="idle"), "Initial branches settled with clarifications ready");
            Locked("Hidden results");
            foreach(string condition in new[]{"A","S"})
            { yield return Select(condition);client.ChooseOption("c1");yield return Idle();yield return Wait(()=>client.Branch.status!="processing","Clarification settled"); }
            yield return Wait(() => client.State.results_visible, "Results reveal together");
            yield return Select("E"); panel.OpenTab(1);
            Check(panel.GetComponentsInChildren<UnityEngine.UI.Button>(true).All(b=>!b.name.Contains("sample")),"Fixed samples removed");
            int revision=client.State.revision, changes=client.View.changes.Length;
            var drag=panel.RateSlider.GetComponent<TutorLengthCommit>();
            drag.OnPointerDown(new PointerEventData(EventSystem.current));panel.RateSlider.value=.913f;drag.OnPointerUp(new PointerEventData(EventSystem.current));
            panel.LengthSlider.value=2;panel.CommitLength();panel.ToneButtons[1].onClick.Invoke();panel.VoiceButtons[0].onClick.Invoke();
            yield return new WaitForSecondsRealtime(.6f);
            Check(client.State.revision==revision && !client.Busy && client.View.changes.Length==changes,"All four local choices make zero API mutations");
            Check(panel.HasPendingControls && panel.ConfirmControlsButton.interactable,"Pending draft exposes one confirmation");
            panel.ConfirmControlsButton.onClick.Invoke();yield return Idle();yield return Ready();
            Check(TutorComparisonClient.Conditions.All(c=>{var v=client.State.branches.Get(c).result.state.settings;return Mathf.Abs(v.speech_rate-.91f)<.001f&&v.reply_length=="detailed"&&v.tone=="friendly"&&v.voice=="voice_a";}),"Single confirmed full patch reaches every strategy");
            Check(client.View.changes.Length==changes+1,"One confirmation creates one setting commit per branch");
            Check(!panel.HasPendingControls && !panel.ConfirmControlsButton.interactable,"Unified reveal replaces the confirmed draft without requiring another confirmation");
            Check(client.View.conversation.Last().settings.voice=="voice_a","Confirmation produces a new generated reply with effective settings");
            revision=client.State.revision;panel.ConfirmControlsButton.onClick.Invoke();yield return null;
            Check(!client.Busy&&client.State.revision==revision,"Duplicate confirmation is a no-op");
            panel.OpenTab(1);panel.VoiceButtons[4].onClick.Invoke();yield return Select("S");
            Check(!panel.HasPendingControls&&client.View.settings.voice=="voice_a","Changing viewed strategy clears an obsolete local draft");
            panel.RateSlider.value=1.2f;client.PauseOrResume();yield return Idle();Locked("Paused");client.PauseOrResume();yield return Idle();
            Check(!panel.HasPendingControls&&Mathf.Abs(panel.RateSlider.value-.91f)<.001f,"Pause/resume discards unconfirmed draft");
            Check(panel.VoiceButtons.Length==5 && panel.VoiceButtons[0].GetComponentInChildren<UnityEngine.UI.Text>().text.Contains("Female")&&panel.VoiceButtons[3].GetComponentInChildren<UnityEngine.UI.Text>().text.Contains("Male"),"Voice choices show gendered public names");
            Capture("controls");
            Result="PASS: "+passed.Count+" checks";Save();Debug.Log("TUTOR_CONTROLS "+Result);
        }
        void Locked(string state)
        { Check(!panel.RateSlider.interactable && !panel.LengthSlider.interactable && panel.ToneButtons.All(b => !b.interactable) && panel.VoiceButtons.All(b => !b.interactable) && !panel.UndoButton.interactable && !panel.ConfirmControlsButton.interactable, state + " gates all controls"); }
        IEnumerator Ready() { yield return Wait(() => client.Branch.status == "ready", "Branch ready"); }
        IEnumerator Select(string value) { client.Select(value); yield return Idle(); Check(client.Selected == value, "Selected " + value); }
        IEnumerator Idle() { yield return null; yield return Wait(() => !client.Busy, "HTTP command completed"); }
        IEnumerator Wait(Func<bool> condition, string label)
        {
            float deadline = Time.realtimeSinceStartup + 20;
            while (!condition() && Time.realtimeSinceStartup < deadline) yield return null;
            Check(condition(), label); yield return null;
        }
        void Check(bool okay, string label)
        {
            if (!okay) { Result = "FAIL: " + label; Save(); throw new InvalidOperationException(Result); }
            passed.Add(label);
        }
        void Save() { Directory.CreateDirectory(Folder); File.WriteAllText(Path.Combine(Folder, "checks.txt"), Result + "\n" + string.Join("\n", passed)); }
        void Capture(string name)
        {
            panel.OpenTab(1);
            Canvas.ForceUpdateCanvases(); Directory.CreateDirectory(Folder);
            foreach(var button in panel.VoiceButtons.Concat(panel.ToneButtons).Concat(new[]{panel.ConfirmControlsButton}))
            {
                var label=button.GetComponentInChildren<UnityEngine.UI.Text>();
                Check(label.preferredWidth<=label.rectTransform.rect.width+1 && label.preferredHeight<=label.rectTransform.rect.height+1,"Core label fits: "+button.name);
            }
            var camera = Camera.main; var old = camera.targetTexture; var previous = RenderTexture.active;
            var position=camera.transform.position;var rotation=camera.transform.rotation;float fov=camera.fieldOfView;
            camera.transform.position=panel.transform.position+panel.transform.up*.08f-panel.transform.forward*1.45f;
            camera.transform.rotation=panel.transform.rotation;camera.fieldOfView=52;
            var target = new RenderTexture(1800, 1500, 24); camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            var image = new Texture2D(1800, 1500, TextureFormat.RGB24, false); image.ReadPixels(new Rect(0, 0, 1800, 1500), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(Folder, name + ".png"), image.EncodeToPNG());
            camera.targetTexture = old; RenderTexture.active = previous; Destroy(image); target.Release(); Destroy(target);
            camera.transform.SetPositionAndRotation(position,rotation);camera.fieldOfView=fov;
        }
    }
}
#endif
