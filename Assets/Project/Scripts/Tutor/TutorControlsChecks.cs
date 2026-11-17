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
            client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.Connect(); yield return Idle();
            Check(client.Connected, "Comparison connects"); Locked("Initial request");
            client.SubmitUserUtterance("Compare an easier explanation."); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification", "Clarifications ready");
            Locked("Hidden E result");
            yield return Select("A"); Locked("Awaiting clarification"); client.ChooseOption("c1"); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "waiting", "A clarification completed");
            yield return Select("S"); client.ChooseOption("c1"); yield return Idle();
            yield return Wait(() => client.State.results_visible, "Results revealed together");
            yield return Select("E"); panel.OpenTab(1);
            Check(panel.RateSlider.interactable && panel.LengthSlider.interactable && panel.ToneButtons.All(b => b.interactable) && panel.VoiceButtons.All(b => b.interactable), "All four controls enabled");
            Check(!panel.SampleButton.interactable && panel.DisplayedVoice.Contains("Audio not connected"), "No false audio availability");
            var drag = panel.RateSlider.GetComponent<TutorLengthCommit>();
            int changes = client.View.changes.Length;
            drag.OnPointerDown(new PointerEventData(EventSystem.current)); panel.RateSlider.value = .913f;
            yield return new WaitForSecondsRealtime(.6f);
            Check(Mathf.Abs(panel.RateSlider.value - .913f) < .001f && client.View.changes.Length == changes, "Polling preserves uncommitted rate drag");
            drag.OnPointerUp(new PointerEventData(EventSystem.current)); yield return Idle();
            Check(client.UnknownOutcome, "Lost control response requires same-request recovery"); Locked("Unknown control outcome");
            client.Retry(); yield return Idle(); yield return Ready();
            Check(!client.UnknownOutcome && Mathf.Abs(client.View.settings.speech_rate - .91f) < .001f && client.View.changes.Length == changes + 1, "Rate rounds to hundredths and commits exactly once on retry");
            drag.OnPointerUp(new PointerEventData(EventSystem.current)); yield return null;
            Check(!client.Busy && client.View.changes.Length == changes + 1, "Duplicate release does not submit");
            panel.ToneButtons[1].onClick.Invoke(); Locked("Busy tone request"); yield return Idle(); yield return Ready();
            panel.VoiceButtons[0].onClick.Invoke(); yield return Idle(); yield return Ready();
            Check(client.View.settings.tone == "friendly" && client.View.settings.voice == "voice_a", "Tone and Voice controls reach backend");
            Check(panel.ToneButtons[1].GetComponent<PanelControlFeedback>().selected && panel.VoiceButtons[0].GetComponent<PanelControlFeedback>().selected, "Selected buttons reflect confirmed values");
            changes = client.View.changes.Length;
            client.SetTone(1); client.SetVoice(0); client.SetSpeechRate(.91f); client.SetSpeechRate(float.NaN); client.SetSpeechRate(2); client.SetTone(7);
            Check(!client.Busy && client.View.changes.Length == changes, "No-op and invalid controls are not sent");
            Check(panel.VoiceButtons.Length == 5, "Five selected voices are visible");
            for (int i = 0; i < TutorVoiceCatalog.Ids.Length; i++)
            {
                panel.VoiceButtons[i].onClick.Invoke(); yield return Idle(); yield return Ready();
                Check(client.View.settings.voice == TutorVoiceCatalog.Ids[i] && panel.VoiceButtons[i].GetComponent<PanelControlFeedback>().selected, "Voice option " + TutorVoiceCatalog.Labels[i] + " routes and highlights correctly");
            }
            client.SetVoice(0); yield return Idle(); yield return Ready();
            Capture("controls");
            drag.OnPointerDown(new PointerEventData(EventSystem.current)); panel.RateSlider.value = 1.25f;
            yield return Select("S"); drag.OnPointerUp(new PointerEventData(EventSystem.current)); yield return null;
            Check(!client.Busy && client.View.settings.speech_rate == 1 && client.View.settings.tone == "professional" && client.View.settings.voice == "voice_d", "Branch switch cancels drag and preserves isolation");
            yield return Select("E");
            drag.OnPointerDown(new PointerEventData(EventSystem.current)); panel.RateSlider.value = 1.23f;
            client.PauseOrResume(); yield return Idle(); Locked("Paused");
            client.PauseOrResume(); yield return Idle(); drag.OnPointerUp(new PointerEventData(EventSystem.current)); yield return null;
            Check(!client.Busy && Mathf.Abs(client.View.settings.speech_rate - .91f) < .001f, "Pause-resume cancels stale release");
            drag.OnPointerDown(new PointerEventData(EventSystem.current)); panel.RateSlider.value = 1.2f;
            panel.OpenTab(2); drag.OnPointerUp(new PointerEventData(EventSystem.current)); yield return null;
            Check(!client.Busy && Mathf.Abs(client.View.settings.speech_rate - .91f) < .001f, "Tab switch cancels stale release");
            panel.SelectUndoField("tone"); panel.UndoButton.onClick.Invoke(); yield return Idle(); yield return Ready();
            Check(client.View.settings.tone == "professional" && client.View.settings.voice == "voice_a" && Mathf.Abs(client.View.settings.speech_rate - .91f) < .001f, "Scoped tone undo preserves newer Voice and rate");
            Check(panel.SelectedUndoField == "tone" && !panel.UndoButton.interactable, "Exhausted undo target stays selected and disabled");
            panel.UndoNext.onClick.Invoke(); Check(panel.SelectedUndoField != "tone" && panel.UndoButton.interactable, "Selector cycles to an available field");
            client.SubmitUserUtterance("Make it green and slightly larger."); yield return Idle(); yield return Ready();
            panel.SelectUndoField("jacket_color"); panel.UndoButton.onClick.Invoke(); yield return Idle(); yield return Ready();
            Check(client.View.settings.jacket_color == "blue" && Mathf.Abs(client.View.settings.scale - 1.05f) < .001f && panel.DisplayedHistory.Contains("Partly undone"), "History selector supports appearance field undo");
            panel.SelectUndoField("all"); panel.UndoButton.onClick.Invoke(); yield return Idle(); yield return Ready();
            Check(client.View.settings.scale == 1 && client.View.settings.voice == "voice_a", "Whole-change undo only restores latest remaining edit");
            Capture("history");
            client.SubmitUserUtterance("Test a recoverable generation failure."); yield return Idle();
            yield return Wait(() => client.Branch.status == "failed", "Generation failure visible"); Locked("Failed branch");
            client.Retry(); yield return Idle(); yield return Ready();
            client.SubmitUserUtterance("For the next answer only, use encouraging wording and Voice B."); yield return Idle(); yield return Ready();
            Check(client.View.settings.tone == "professional" && client.View.settings.voice == "voice_a" && panel.DisplayedConversation.Contains("one answer"), "One-answer reservation leaves session controls unchanged");
            client.SubmitUserUtterance("Why does it help?"); yield return Idle(); yield return Ready();
            Check(panel.DisplayedConversation.Contains("Answer settings · Brief · Encouraging · 0.91× · Voice B"), "Answer-specific snapshot shown in transcript");
            Check(panel.DisplayedTone == "Professional" && panel.DisplayedVoice.Contains("Voice A"), "Persistent settings remain distinct from answer snapshot");
            client.Close(); yield return Idle(); Locked("Closed comparison");
            yield return SingleSession();
            Result = "PASS: " + passed.Count + " checks"; Save(); Debug.Log("TUTOR_CONTROLS " + Result);
        }
        IEnumerator SingleSession()
        {
            var root = new GameObject("Single-session controls checks"); root.SetActive(false); root.transform.position = new Vector3(100, 0, 0);
            var single = root.AddComponent<TutorClient>(); single.connectOnStart = false; single.endpoint = "http://127.0.0.1:8771"; single.condition = "E";
            var ui = root.AddComponent<TutorPanel>(); ui.client = single; ui.desktopDebugInput = true;
            root.SetActive(true); yield return null; single.Connect(); yield return Wait(() => !single.Busy && single.Connected, "Single session connects");
            single.SetSpeechRate(1.12f); yield return Wait(() => !single.Busy, "Single rate control completes");
            single.SetTone(1); yield return Wait(() => !single.Busy, "Single tone control completes");
            single.SetVoice(0); yield return Wait(() => !single.Busy, "Single Voice control completes");
            Check(single.Error == "" && single.View.settings.speech_rate == 1.12f && single.View.settings.tone == "friendly" && single.View.settings.voice == "voice_a", "All new single-session DTOs accepted");
            ui.OpenTab(1);
            var drag = ui.RateSlider.GetComponent<TutorLengthCommit>();
            drag.OnPointerDown(new PointerEventData(EventSystem.current)); ui.RateSlider.value = .8f;
            ui.OpenTab(0); ui.OpenTab(1);
            Check(!drag.IsDragging && ui.RateSlider.value == 1.12f && !single.Busy, "Single-session tab changes restore confirmed slider without polling or release");
            single.SubmitUserUtterance("For the next answer only, use encouraging wording and Voice B."); yield return Wait(() => !single.Busy, "Single temporary request completes");
            Check(ui.DisplayedConversation.Contains("NEXT REPLY ONLY") && ui.DisplayedConversation.Contains("Voice B") && ui.DisplayedTone == "Friendly", "Single pending override shown separately from session settings");
            ui.SelectUndoField("voice"); ui.UndoButton.onClick.Invoke(); yield return Wait(() => !single.Busy, "Single scoped undo completes");
            Check(single.View.settings.voice == "voice_d" && single.View.settings.tone == "friendly" && !ui.DisplayedConversation.Contains("NEXT REPLY ONLY"), "Single undo clears pending override without resetting tone");
            Destroy(root);
        }
        void Locked(string state)
        { Check(!panel.RateSlider.interactable && !panel.LengthSlider.interactable && panel.ToneButtons.All(b => !b.interactable) && panel.VoiceButtons.All(b => !b.interactable) && !panel.UndoButton.interactable && !panel.SampleButton.interactable, state + " gates all controls"); }
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
            Canvas.ForceUpdateCanvases(); Directory.CreateDirectory(Folder);
            var camera = Camera.main; var old = camera.targetTexture; var previous = RenderTexture.active;
            var target = new RenderTexture(1600, 1000, 24); camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            var image = new Texture2D(1600, 1000, TextureFormat.RGB24, false); image.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(Folder, name + ".png"), image.EncodeToPNG());
            camera.targetTexture = old; RenderTexture.active = previous; Destroy(image); target.Release(); Destroy(target);
        }
    }
}
#endif
