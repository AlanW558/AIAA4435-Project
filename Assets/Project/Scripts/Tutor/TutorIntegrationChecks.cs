#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;

namespace IAI.Tutor
{
    /// <summary>Explicit local-fixture Play-mode checks. Not included in player builds.</summary>
    public sealed class TutorIntegrationChecks : MonoBehaviour
    {
        TutorClient client;
        TutorPanel panel;
        readonly List<string> passed = new List<string>();
        public string Result { get; private set; } = "running";
        string Folder => Path.Combine(Application.dataPath, "../StudyData/macos/tutor-unity");
        IEnumerator Start()
        {
            client = FindObjectOfType<TutorClient>(); panel = FindObjectOfType<TutorPanel>();
            if (!client || !panel || client.endpoint != "http://127.0.0.1:8766") { Fail("Explicit fixture endpoint required"); yield break; }
            yield return Idle();
            Check(client.Connected && client.View.mode == "mock" && client.View.settings.reply_length == "balanced", "Connected to explicit fixture with Balanced");
            panel.DebugInput.text = "Use key points from now on. What is active recall?";
            panel.SendButton.onClick.Invoke(); yield return Idle();
            Check(client.View.settings.reply_length == "brief" && client.View.conversation.Length == 1, "Send applies Brief and automatically generates one answer");
            Check(panel.DisplayedConversation.Contains("Active recall means") && !panel.DisplayedConversation.Contains("Retrieval practice"), "Conversation shows only the actual Brief answer");
            panel.OpenTab(1); panel.LengthSlider.value = 2;
            panel.LengthSlider.GetComponent<TutorLengthCommit>().OnPointerUp(new PointerEventData(EventSystem.current));
            yield return Idle();
            Check(client.View.settings.reply_length == "detailed" && panel.DisplayedLength == "Detailed", "Slider release commits Detailed and synchronizes label");
            Check(client.View.settings.tone == "professional" && client.View.settings.speech_rate == 1, "Length control preserves unrelated settings");
            Capture("controls"); panel.OpenTab(2);
            Check(panel.DisplayedHistory.Contains("Detailed") && panel.UndoButton.interactable, "History displays committed changes and enables undo");
            Capture("history"); panel.UndoButton.onClick.Invoke(); yield return Idle();
            Check(client.View.settings.reply_length == "brief" && panel.DisplayedHistory.Contains("UNDO"), "History undo restores Brief");
            panel.OpenTab(0); client.SubmitUserUtterance("Make the explanation easier."); yield return Idle();
            Check(client.HasQuestion && client.View.settings.reply_length == "brief" && !panel.LengthSlider.interactable && panel.OptionButtons.Length >= 4, "Ambiguous request shows choices while preserving settings");
            Capture("clarification");
            panel.OptionButtons.First(b => b.name == "Option cancel").onClick.Invoke(); yield return Idle();
            Check(!client.HasQuestion && client.View.settings.reply_length == "brief", "Cancel preserves committed setting");
            client.SubmitUserUtterance("Make the explanation easier."); yield return Idle();
            panel.OptionButtons.First(b => b.name == "Option c2").onClick.Invoke(); yield return Idle();
            Check(!client.HasQuestion && client.View.settings.reply_length == "detailed", "Clarification choice commits Detailed");
            client.SubmitUserUtterance("Why does it help?"); yield return Idle();
            Check(client.View.conversation.Length == 2 && panel.DisplayedConversation.Contains("For example"), "Common utterance entry point generates Detailed follow-up");
            client.SubmitUserUtterance("Test a recoverable generation failure."); yield return Idle();
            Check(!string.IsNullOrEmpty(client.Error) && client.View.conversation.Length == 2 && panel.RetryButton.interactable, "Generation failure is visible without a fake conversation entry");
            panel.RetryButton.onClick.Invoke(); yield return Idle();
            Check(string.IsNullOrEmpty(client.Error) && client.View.conversation.Length == 3 && !client.HasQueuedAnswer, "Retry completes the same job exactly once");
            int revision = client.View.revision;
            client.RefreshState(); yield return Idle();
            Check(client.View.revision == revision && client.View.conversation.Length == 3, "Sync preserves authoritative state and conversation");
            Capture("conversation");
            Result = "PASS: " + passed.Count + " checks"; Save(); Debug.Log("TUTOR_UNITY_CHECKS " + Result);
        }
        IEnumerator Idle()
        {
            yield return null;
            float deadline = Time.realtimeSinceStartup + 15;
            while (client.Busy && Time.realtimeSinceStartup < deadline) yield return null;
            Check(!client.Busy, "HTTP operation completed"); yield return null;
        }
        void Check(bool okay, string name)
        {
            if (!okay) { Fail(name); throw new InvalidOperationException("TUTOR_UNITY_CHECK_FAILED: " + name); }
            passed.Add(name);
        }
        void Fail(string name) { Result = "FAIL: " + name; Save(); }
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
