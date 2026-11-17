#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace IAI.Tutor
{
    // Local HTTP fixture plus observations of real scene meshes/materials.
    public sealed class TutorAppearanceComparisonChecks : MonoBehaviour
    {
        TutorComparisonClient client;
        TutorPanel panel;
        readonly List<string> passed = new List<string>();
        public string Result { get; private set; } = "running";
        string Folder => Path.Combine(Application.dataPath, "../StudyData/macos/tutor-appearance-comparison");
        IEnumerator Start()
        {
            client = GetComponent<TutorComparisonClient>(); panel = FindObjectOfType<TutorPanel>();
            Check(client && panel && client.avatar && client.endpoint == "http://127.0.0.1:8770", "Explicit appearance fixture and existing renderer");
            client.requirePreparation = false; // Legacy branch tests; shared preparation has dedicated acceptance coverage.
            client.Connect(); yield return Idle();
            Check(client.Connected && client.State.mode == "mock", "Connected to fixture without paid provider");
            Observe("liang", "suit", "blue", "glasses", 1);
            client.SubmitUserUtterance("Compare a casual look."); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "awaiting_clarification" && client.State.branches.S.status == "awaiting_clarification", "Appearance clarifications ready");
            foreach (string condition in TutorComparisonClient.Conditions)
            {
                yield return Select(condition);
                Check(!client.State.results_visible && client.View.changes.Length == 0, "Hidden history for " + condition);
                Observe("liang", "suit", "blue", "glasses", 1);
            }
            Snapshot("hidden");
            yield return Select("A"); client.ChooseOption("c2"); yield return Idle();
            yield return Wait(() => client.State.branches.A.status == "waiting", "A finished while S still asks");
            Check(!client.State.results_visible, "A result still hidden");
            Observe("liang", "suit", "blue", "glasses", 1);
            yield return Select("S"); client.ChooseOption("c1"); yield return Idle();
            yield return Wait(() => client.State.results_visible, "Four appearance results open together");
            string first = JsonUtility.ToJson(client.State.first_reveal);
            foreach (string condition in TutorComparisonClient.Conditions)
            {
                yield return Select(condition);
                Observe("liang", condition == "A" ? "suit" : "sport", "blue", condition == "A" ? "none" : "glasses", 1);
            }
            Snapshot("revealed");
            yield return Select("E");
            client.SubmitUserUtterance("Make it green and slightly larger."); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready", "E colour and scale repair ready");
            Observe("liang", "sport", "green", "glasses", 1.05f);
            panel.OpenTab(2); yield return null;
            Check(panel.DisplayedHistory.Contains("Colour: Blue → Green") && panel.DisplayedHistory.Contains("Scale: 1.00× → 1.05×"), "History shows appearance before/after values");
            Check(!panel.DisplayedHistory.Contains("REPLY LENGTH"), "Appearance commits are not mislabeled Reply length");
            client.UndoSetting("jacket_color"); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready", "Scoped colour undo ready");
            Observe("liang", "sport", "blue", "glasses", 1.05f);
            Check(panel.DisplayedHistory.Contains("Partly undone") && panel.DisplayedHistory.Contains("UNDO"), "Partial undo history retains scale change");
            yield return Select("S"); Observe("liang", "sport", "blue", "glasses", 1);
            yield return Select("E");
            var before = client.View.settings;
            client.SubmitUserUtterance("Switch to Nailong."); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready", "Avatar replacement ready");
            Observe("nailong", "none", "yellow", "none", 1);
            var after = client.View.settings;
            Check(before.tone == after.tone && before.voice == after.voice && before.reply_length == after.reply_length && before.speech_rate == after.speech_rate, "Avatar replacement preserves dialogue settings");
            Check(panel.DisplayedHistory.Contains("Avatar: Liang → Nailong"), "Avatar replacement included in shared History");
            Capture("nailong-history");
            client.UndoSetting("all"); yield return Idle();
            yield return Wait(() => client.Branch.status == "ready", "Whole avatar undo ready");
            Observe("liang", "sport", "blue", "glasses", 1.05f);
            Check(JsonUtility.ToJson(client.State.first_reveal) == first, "First appearance snapshot remains immutable");
            Check(panel.GetComponentsInChildren<UnityEngine.UI.ScrollRect>(true).First(s => s.name == "Change history").verticalNormalizedPosition > .99f, "History opens at newest change after update");
            Snapshot("final"); Capture("restored-history");
            Result = "PASS: " + passed.Count + " checks"; Save(); Debug.Log("TUTOR_APPEARANCE_COMPARISON " + Result);
        }
        void Observe(string avatar, string outfit, string colour, string accessory, float scale)
        {
            var a = client.avatar;
            Check(a.ObservedAvatar == avatar && a.ObservedOutfit == outfit && a.ObservedColor == colour && a.ObservedAccessory == accessory && Mathf.Abs(a.ObservedScale - scale) < .001f,
                "Rendered " + avatar + "/" + outfit + "/" + colour + "/" + accessory + "/" + scale);
        }
        IEnumerator Select(string condition)
        { client.Select(condition); yield return Idle(); Check(client.Selected == condition, "Selected " + condition); }
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
        void Snapshot(string name) { Directory.CreateDirectory(Folder); File.WriteAllText(Path.Combine(Folder, name + ".json"), JsonUtility.ToJson(client.State, true)); }
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
