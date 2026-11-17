using System;
using System.Collections.Generic;
using System.Linq;
using IAI.UI;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.Tutor
{
    /// <summary>Independent, opaque study surface. Hiding never submits or discards answers.</summary>
    public sealed partial class TutorStudyPanel : MonoBehaviour
    {
        public const string Version = "attribute-feedback-v2";
        public static readonly string[] RatingKeys = { "effort_ease", "control", "clarification_appropriateness", "satisfaction" };
        public static readonly string[] CompletionKeys = { "fully_met", "partly_met", "not_met", "unable_to_judge" };
        public bool MaterialPageOpen => Visible && tab == 0 && !PreferenceMode;
        public Button[] MaterialButtons { get; private set; }
        Text materialStatus;
        public Button TaskButton { get; private set; }
        public Button BeginButton { get; private set; }
        public Button NextButton { get; private set; }
        public Button PauseButton { get; private set; }
        public Button EndButton { get; private set; }
        public Button SaveButton { get; private set; }
        public Button ToggleButton { get; private set; }
        public Button[] CompletionButtons { get; private set; }
        public Button[][] RatingButtons { get; private set; }
        public TutorSpeechInput Speech { get; private set; }
        public bool Visible { get; private set; } = true;
        public bool SpeechBusy => Speech && (Speech.Recording || Speech.Working);
        public bool CanRecordComment => (PreferenceMode ? client.PreferenceAvailable : Eligible && tab == 2) && Visible && !(owner.Speech && (owner.Speech.Recording || owner.Speech.Working));
        public string CommentContext => !CanRecordComment ? null : PreferenceMode ? client.endpoint + ":preference:" + PreferenceKey + ":" + client.State.sequence.preference_revision : client.endpoint + ":survey:" + Key + ":" + client.Branch.branch_revision + ":" + client.State.feedback.Get(client.Selected).feedback_revision;
        public string CurrentAnswers => Draft()?.answers.ToString(Formatting.None) ?? "{}";
        public bool HasUnsavedAnswers => client.Connected && drafts.Any(x => x.Key.StartsWith(client.State.task_id + ":", StringComparison.Ordinal) && x.Value.dirty);
        TutorPanel owner;
        TutorComparisonClient client => owner.comparison;
        TutorTaskNavigation nav => owner.Navigation;
        string Key => client.Connected ? client.State.task_id + ":" + client.Selected : "";
        bool Eligible => owner && client.Connected && client.State.feedback_version == Version && client.State.results_visible && client.CanEditBranch && !client.Paused;
        bool Editable => Eligible && !SpeechBusy;
        sealed class DraftState
        {
            public JObject answers = new JObject { ["ratings"] = new JObject(), ["reasons"] = new JArray(), ["comment"] = "", ["comment_confirmed"] = false };
            public int branchRevision, feedbackRevision;
            public bool dirty, saving;
        }
        readonly Dictionary<string, DraftState> drafts = new Dictionary<string, DraftState>();
        Canvas canvas;
        CanvasGroup seatedVisibility;
        GameObject body, taskPage, ratingPage, notesPage;
        Button questionnaireButton, notesButton, record, useText, clearText;
        Button[] conditions, reasons;
        Text progress, status, taskTitle, instructions, feedbackHeading, reasonHelp, comment, speechStatus;
        ScrollRect taskScroll, commentScroll;
        Font font;
        int tab;
        string lastTask = "", lastKey = "";
        bool lastCard;
        readonly Color paper = new Color(.96f, .94f, .88f, 1);
        readonly Color ink = new Color(.14f, .20f, .22f, 1);
        readonly Color accent = new Color(.17f, .38f, .40f, 1);
        readonly Color neutral = new Color(.86f, .87f, .83f, 1);
        static readonly string[] ReasonKeys = { "target_mismatch", "unwanted_change", "not_maintained", "hard_to_verify", "interaction_problem", "other" };

        public void Initialize(TutorPanel panel)
        {
            owner = panel; font = owner.font;
            var anchor = owner.seat ? owner.seat.seatAnchor : null;
            var camera = Camera.main;
            Vector3 eye = anchor ? anchor.position + Vector3.up * owner.seat.seatedEyeHeight : camera ? camera.transform.position : Vector3.up * 1.35f;
            // Fixed seated layout relative to the tutor, not the current head gaze.
            Vector3 forward = client.avatar ? client.avatar.transform.position - eye : anchor ? anchor.forward : camera ? camera.transform.forward : Vector3.forward;
            forward = Vector3.ProjectOnPlane(forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < .5f) forward = Vector3.forward;
            var frame = Quaternion.LookRotation(forward, Vector3.up);
            transform.position = eye + frame * owner.studySeatOffset;
            transform.rotation = Quaternion.LookRotation(transform.position - eye, Vector3.up);
            Build();
            Speech = gameObject.AddComponent<TutorSpeechInput>(); Speech.panel = owner; Speech.studyPanel = this;
            Speech.Changed += Render;
            client.Changed += Render;
            Render();
        }
        void OnDestroy() { if (owner && client) client.Changed -= Render; }
        void OnDisable() { if (Speech) Speech.Cancel(); }
        void Update()
        {
            if (!owner) return;
            bool seated = !owner.seat || owner.seat.IsSeated;
            seatedVisibility.alpha = seated ? 1 : 0;
            seatedVisibility.blocksRaycasts = seatedVisibility.interactable = seated;
            if (!seated && Speech && Speech.HasCapture) Speech.Cancel();
            if (!canvas.worldCamera) canvas.worldCamera = Camera.main;
            Render();
        }
        public void ToggleVisible()
        {
            Visible = !Visible;
            if (!Visible)
            {
                if (Speech) Speech.Cancel();
                if (client.Connected && nav.CanBegin) nav.Begin();
            }
            owner.Render(); Render();
        }
        public void OpenPage(int index)
        {
            if (Speech) Speech.Cancel();
            Visible = true; tab = index;
            if (index == 0) { nav.ShowDetails(); if (owner.Speech) owner.Speech.Cancel(); if (owner.Playback) owner.Playback.Stop(reason: "page_changed"); }
            else if (client.Connected && nav.CanBegin) nav.Begin();
            owner.Render(); Render();
        }
        DraftState Draft()
        {
            if (!client.Connected || !client.State.results_visible || client.State.feedback_version != Version) return null;
            var saved = client.FeedbackDraft(client.Selected);
            int savedRevision = saved?.Value<int>("feedback_revision") ?? 0;
            int branchRevision = client.Branch.branch_revision;
            if (!drafts.TryGetValue(Key, out var d))
            {
                d = new DraftState { branchRevision = branchRevision, feedbackRevision = savedRevision };
                if (saved?["answers"] is JObject answers) d.answers = (JObject)answers.DeepClone();
                d.dirty = saved != null && saved.Value<int>("branch_revision") != branchRevision;
                drafts.Add(Key, d);
            }
            if (d.branchRevision != branchRevision)
            { d.branchRevision = branchRevision; d.dirty = true; d.saving = false; }
            if (savedRevision > d.feedbackRevision && (!d.dirty || d.saving))
            {
                d.answers = (JObject)saved["answers"].DeepClone(); d.feedbackRevision = savedRevision;
                d.dirty = saved.Value<int>("branch_revision") != branchRevision; d.saving = false;
            }
            return d;
        }
        public void ChooseCompletion(string value)
        {
            if (!Editable || !CompletionKeys.Contains(value)) return;
            var d = Draft(); d.answers["completion"] = value;
            if (value == "fully_met") d.answers["reasons"] = new JArray();
            d.dirty = true; Render();
        }
        public void ChooseRating(string key, int value)
        {
            if (!Editable || !RatingKeys.Contains(key) || value < 0 || value > 7) return;
            var d = Draft(); ((JObject)d.answers["ratings"])[key] = value == 0 ? new JValue("unable_to_judge") : new JValue(value);
            d.dirty = true; Render();
        }
        bool LaterInteraction => client.Connected && client.State.results_visible && client.Branch.result?.state != null &&
            client.Branch.result.state.conversation.Length > client.FirstConversationCount(client.Selected);
        void ToggleReason(string key)
        {
            if (!Editable || key == "not_maintained" && !LaterInteraction) return;
            var d = Draft(); if (d.answers.Value<string>("completion") == null || d.answers.Value<string>("completion") == "fully_met") return;
            var array = (JArray)d.answers["reasons"]; var match = array.FirstOrDefault(x => (string)x == key);
            if (match == null) array.Add(key); else match.Remove();
            d.dirty = true; Render();
        }
        public void ConfirmComment(string text)
        {
            // The recorder checks the captured task/branch/feedback context before calling this.
            if (string.IsNullOrWhiteSpace(text) || text.Length > 4000) return;
            if (PreferenceMode)
            {
                if (!client.PreferenceAvailable) return;
                var preference = PreferenceDraft(); preference["comment"] = text.Trim(); preference["comment_confirmed"] = true; Render(); return;
            }
            if (!Eligible) return;
            var d = Draft(); d.answers["comment"] = text.Trim(); d.answers["comment_confirmed"] = true; d.dirty = true; Render();
        }
        bool Complete(DraftState d) => d != null && CompletionKeys.Contains(d.answers.Value<string>("completion")) && RatingKeys.All(k => d.answers["ratings"]?[k] != null);
        public void SaveRating()
        {
            if (PreferenceMode) { SubmitPreference(); return; }
            var d = Draft(); if (!Editable || !Complete(d) || Speech && Speech.HasCapture) return;
            d.saving = true;
            client.SaveFeedback(d.answers.ToString(Formatting.None));
            Render();
        }
        public void Render()
        {
            if (!owner || !body) return;
            if (RenderPreference()) return;
            EndButton.GetComponentInChildren<Text>().text = "Exit task without submitting";
            var d = Draft();
            string task = client.Connected ? client.State.task_id : "";
            if (task != lastTask) { lastTask = task; tab = 0; Visible = true; }
            if (nav.ShowCard && !lastCard) { tab = 0; Visible = true; }
            lastCard = nav.ShowCard;
            if (lastKey != Key) { lastKey = Key; if (Speech && Speech.HasCapture) Speech.Cancel(); }
            body.SetActive(Visible);
            ToggleButton.GetComponentInChildren<Text>().text = Visible ? "Hide study panel" : "Show study panel";
            progress.text = nav.Progress;
            taskPage.SetActive(tab == 0); ratingPage.SetActive(tab == 1); notesPage.SetActive(tab == 2);
            Tint(TaskButton, tab == 0); Tint(questionnaireButton, tab == 1); Tint(notesButton, tab == 2);
            taskTitle.text = nav.Title;
            if (instructions.text != nav.Instructions) { instructions.text = nav.Instructions; FitScroll(taskScroll, instructions); }
            var materials = nav.StudyPreview ? nav.Task?.materials : null;
            for (int i = 0; i < MaterialButtons.Length; i++)
            {
                bool materialShown = materials != null && i < materials.Length;
                MaterialButtons[i].gameObject.SetActive(materialShown);
                MaterialButtons[i].interactable = materialShown && owner.Playback && owner.Playback.CanMaterial;
                if (materialShown) MaterialButtons[i].GetComponentInChildren<Text>().text = owner.Playback && owner.Playback.Active ? "Stop sample" : "Play · " + materials[i].label;
            }
            materialStatus.text = materials != null && materials.Length > 0 ? !client.Connected ? "Start the task to enable listening samples." : owner.Playback.Status : "";
            BeginButton.interactable = nav.CanBegin;
            BeginButton.GetComponentInChildren<Text>().text = client.Connected ? "Continue task" : "Start task";
            bool supported = client.Connected && client.State.feedback_version == Version;
            feedbackHeading.text = !supported ? "Read the task instructions, then select Start task." : !client.State.results_visible ? "Complete the interaction before rating the results." : $"Evaluate {client.Selected} · {(client.State.feedback.Get(client.Selected).complete && d != null && !d.dirty ? "Saved" : "Not yet saved for this result")}";
            for (int i = 0; i < conditions.Length; i++)
            {
                string c = TutorComparisonClient.Conditions[i];
                conditions[i].interactable = supported && client.Available && client.State.results_visible && !SpeechBusy;
                Tint(conditions[i], client.Connected && client.Selected == c);
                conditions[i].GetComponentInChildren<Text>().text = c + (supported && client.State.feedback.Get(c).complete && !(drafts.TryGetValue(task + ":" + c, out var other) && other.dirty) ? " · Saved" : "");
            }
            for (int i = 0; i < CompletionButtons.Length; i++) { CompletionButtons[i].interactable = Editable; Tint(CompletionButtons[i], d?.answers.Value<string>("completion") == CompletionKeys[i]); }
            for (int i = 0; i < RatingButtons.Length; i++)
                for (int j = 0; j < 8; j++)
                {
                    RatingButtons[i][j].interactable = Editable;
                    Tint(RatingButtons[i][j], d?.answers["ratings"]?[RatingKeys[i]]?.ToString() == (j == 7 ? "unable_to_judge" : (j + 1).ToString()));
                }
            bool reasonApplicable = d != null && d.answers.Value<string>("completion") != null && d.answers.Value<string>("completion") != "fully_met";
            reasonHelp.text = reasonApplicable ? "Optional reasons · select any that apply" : "Reasons apply to partly met, not met or unable to judge.\nYou may add a comment for any outcome.";
            for (int i = 0; i < reasons.Length; i++)
            {
                reasons[i].interactable = Editable && reasonApplicable && (ReasonKeys[i] != "not_maintained" || LaterInteraction);
                Tint(reasons[i], d != null && ((JArray)d.answers["reasons"]).Any(x => (string)x == ReasonKeys[i]));
            }
            string shown = Speech && Speech.Transcript.Length > 0 ? Speech.Transcript : d?.answers.Value<string>("comment") ?? "";
            if (comment.text != shown) { comment.text = shown; FitScroll(commentScroll, comment); }
            speechStatus.text = Speech ? Speech.Status : "Optional spoken comment.";
            record.interactable = Speech && (CanRecordComment || SpeechBusy);
            record.GetComponentInChildren<Text>().text = Speech && Speech.Recording ? "Stop recording" : Speech && Speech.Working ? "Cancel" : "Record comment";
            useText.interactable = Speech && Speech.CanSend && Speech.Transcript.Length <= 4000;
            clearText.interactable = Editable || Speech && Speech.HasCapture;
            SaveButton.interactable = Editable && Complete(d) && !(Speech && Speech.HasCapture);
            SaveButton.GetComponentInChildren<Text>().text = d != null && d.dirty ? "Save / confirm this rating" : "Save this rating";
            NextButton.interactable = nav.CanNext && !HasUnsavedAnswers && !(Speech && Speech.HasCapture);
            NextButton.GetComponentInChildren<Text>().text = nav.HasNextInModule ? "Submit feedback & next task" : "Submit task feedback";
            PauseButton.interactable = EndButton.interactable = client.CanPauseOrResume;
            PauseButton.GetComponentInChildren<Text>().text = client.Paused ? "Resume" : "Pause";
            status.text = client.Error.Length > 0 ? client.Error : client.Busy ? "Saving / synchronizing..." : client.UnknownOutcome ? "Save outcome unknown. Use Retry on the system panel." : client.Paused ? "Paused. Your answers are kept." : HasUnsavedAnswers ? "Unsaved answers · save each edited strategy before continuing." : nav.Guidance;
        }
        void Build()
        {
            var root = Rect("Study canvas", transform, Vector2.zero, new Vector2(820, 1050)); root.localScale = Vector3.one * .0009f;
            canvas = root.gameObject.AddComponent<Canvas>(); canvas.renderMode = RenderMode.WorldSpace; canvas.worldCamera = Camera.main;
            root.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>().checkFor3DOcclusion = true;
            root.gameObject.AddComponent<DesktopPanelRaycaster>(); seatedVisibility = root.gameObject.AddComponent<CanvasGroup>();
            var sheet = Rect("Opaque paper", root, Vector2.zero, new Vector2(820, 1050)); body = sheet.gameObject;
            sheet.gameObject.AddComponent<Image>().color = paper;
            Label(sheet, "Title", "Study · Task & feedback", new Vector2(-90, 475), new Vector2(590, 48), 30);
            progress = Label(sheet, "Progress", "", new Vector2(0, 429), new Vector2(750, 40), 19);
            TaskButton = Button(sheet, "Task instructions", new Vector2(-250, 377), new Vector2(235, 44), () => OpenPage(0));
            questionnaireButton = Button(sheet, "Questionnaire", new Vector2(0, 377), new Vector2(235, 44), () => OpenPage(1));
            notesButton = Button(sheet, "Optional notes", new Vector2(250, 377), new Vector2(235, 44), () => OpenPage(2));
            conditions = new Button[4];
            for (int i = 0; i < 4; i++) { string c = TutorComparisonClient.Conditions[i]; conditions[i] = Button(sheet, c, new Vector2(-279 + 186 * i, 322), new Vector2(174, 42), () => { if (Speech) Speech.Cancel(); client.Select(c); }); }
            feedbackHeading = Label(sheet, "Rating context", "", new Vector2(0, 276), new Vector2(750, 44), 18);
            taskPage = Rect("Task page", sheet, Vector2.zero, new Vector2(750, 500)).gameObject;
            taskTitle = Label(taskPage.transform, "Task title", "", new Vector2(0, 205), new Vector2(740, 70), 26);
            taskScroll = Scroll(taskPage.transform, new Vector2(0, -15), new Vector2(740, 345), out instructions);
            MaterialButtons = new Button[3];
            for (int i = 0; i < 3; i++) { int index = i; MaterialButtons[i] = Button(taskPage.transform, "Play material", new Vector2(-250 + i * 250, -218), new Vector2(240, 42), () => owner.Playback.ToggleMaterial(index)); }
            materialStatus = Label(taskPage.transform, "Listening status", "", new Vector2(0, -321), new Vector2(740, 50), 17);
            BeginButton = Button(taskPage.transform, "Start task", new Vector2(0, -265), new Vector2(420, 48), () => { nav.Begin(); owner.Render(); });
            ratingPage = Rect("Ratings", sheet, Vector2.zero, new Vector2(750, 620)).gameObject;
            Label(ratingPage.transform, "Completion question", "To what extent did this approach's final outcome meet the task requirements?", new Vector2(0, 217), new Vector2(740, 72), 21);
            Label(ratingPage.transform, "Completion help", "Consider the requested change and settings that should stay unchanged.", new Vector2(0, 161), new Vector2(740, 28), 16);
            CompletionButtons = new Button[4]; string[] completion = { "Fully met", "Partly met", "Not met", "Unable to judge" };
            for (int i = 0; i < 4; i++) { int n = i; CompletionButtons[i] = Button(ratingPage.transform, completion[i], new Vector2(-279 + i * 186, 121), new Vector2(174, 44), () => ChooseCompletion(CompletionKeys[n])); }
            string[] questions = {
                "Trying to make this adjustment with this approach required little effort.",
                "With this approach, I felt in control of what was changed.",
                "This approach's decision about whether to ask for clarification suited my needs.",
                "I am satisfied with my experience of using this approach for this task." };
            RatingButtons = new Button[4][];
            for (int i = 0; i < 4; i++)
            {
                int row = i; float y = 59 - i * 101;
                Label(ratingPage.transform, RatingKeys[i], questions[i], new Vector2(0, y), new Vector2(740, 52), 20);
                RatingButtons[i] = new Button[8];
                for (int j = 0; j < 8; j++) { int value = j == 7 ? 0 : j + 1; RatingButtons[i][j] = Button(ratingPage.transform, j == 7 ? "Unable to judge" : value.ToString(), new Vector2(j == 7 ? 289 : -337 + j * 84, y - 43), new Vector2(j == 7 ? 160 : 77, 37), () => ChooseRating(RatingKeys[row], value)); }
            }
            Label(ratingPage.transform, "Scale anchors", "1 Strongly disagree · 2 Disagree · 3 Somewhat disagree · 4 Neither agree nor disagree\n5 Somewhat agree · 6 Agree · 7 Strongly agree", new Vector2(0, -329), new Vector2(745, 52), 16);
            notesPage = Rect("Optional notes", sheet, Vector2.zero, new Vector2(750, 620)).gameObject;
            reasonHelp = Label(notesPage.transform, "Reason help", "", new Vector2(0, 218), new Vector2(740, 60), 19);
            string[] labels = { "Requested change did not meet the requirements", "Something that should stay unchanged was changed", "Change was not maintained during later interaction", "Could not tell whether the change met the requirements", "Speech, playback or interaction problem", "Another reason" };
            reasons = new Button[6];
            for (int i = 0; i < 6; i++) { int n = i; reasons[i] = Button(notesPage.transform, labels[i], new Vector2(0, 161 - i * 45), new Vector2(740, 39), () => ToggleReason(ReasonKeys[n])); }
            commentScroll = Scroll(notesPage.transform, new Vector2(0, -160), new Vector2(740, 150), out comment);
            speechStatus = Label(notesPage.transform, "Speech status", "", new Vector2(0, -262), new Vector2(740, 44), 16);
            record = Button(notesPage.transform, "Record comment", new Vector2(-249, -319), new Vector2(238, 44), () => Speech.PressRecord());
            useText = Button(notesPage.transform, "Use text", new Vector2(0, -319), new Vector2(238, 44), () => Speech.Submit());
            clearText = Button(notesPage.transform, "Discard / clear", new Vector2(249, -319), new Vector2(238, 44), () => { Speech.Cancel(); if (Eligible) { var d = Draft(); d.answers["comment"] = ""; d.answers["comment_confirmed"] = false; d.dirty = true; } });
            status = Label(sheet, "Study status", "", new Vector2(0, -383), new Vector2(750, 44), 17);
            SaveButton = Button(sheet, "Save this rating", new Vector2(-190, -435), new Vector2(365, 48), SaveRating);
            NextButton = Button(sheet, "Submit feedback & next task", new Vector2(190, -435), new Vector2(365, 48), () => { if (PreferenceMode) { nav.ContinueModule(); owner.Render(); } else if (!HasUnsavedAnswers && !(Speech && Speech.HasCapture)) { nav.Next(); owner.Render(); } });
            PauseButton = Button(sheet, "Pause", new Vector2(-190, -489), new Vector2(365, 38), () => { Speech.Cancel(); if (PreferenceMode) client.PreferenceLifecycle(client.State.sequence.preference_paused ? "preference_resume" : "preference_pause"); else client.PauseOrResume(); });
            EndButton = Button(sheet, "Exit task without submitting", new Vector2(190, -489), new Vector2(365, 38), () => { Speech.Cancel(); if (PreferenceMode) client.PreferenceLifecycle("preference_exit"); else client.Close(); });
            BuildPreferences(sheet);
            ToggleButton = Button(root, "Hide study panel", new Vector2(190, 560), new Vector2(370, 50), ToggleVisible);
        }
        void Tint(Button b, bool selected)
        { b.targetGraphic.color = selected ? accent : neutral; b.GetComponentInChildren<Text>().color = selected ? Color.white : ink; }
        Text Label(Transform parent, string name, string value, Vector2 pos, Vector2 size, int points)
        {
            var t = Rect(name, parent, pos, size).gameObject.AddComponent<Text>(); t.font = font; t.text = value; t.fontSize = points; t.color = ink;
            t.supportRichText = false; t.raycastTarget = false; t.alignment = TextAnchor.MiddleLeft; t.horizontalOverflow = HorizontalWrapMode.Wrap; t.verticalOverflow = VerticalWrapMode.Truncate; return t;
        }
        Button Button(Transform parent, string caption, Vector2 pos, Vector2 size, Action action)
        {
            var rt = Rect(caption, parent, pos, size); var image = rt.gameObject.AddComponent<Image>(); image.color = neutral;
            var b = rt.gameObject.AddComponent<Button>(); b.targetGraphic = image; b.navigation = new Navigation { mode = Navigation.Mode.None };
            var colors = b.colors; colors.disabledColor = new Color(.74f, .74f, .74f, 1); b.colors = colors;
            var text = Label(rt, "Label", caption, Vector2.zero, size - new Vector2(12, 2), 18); text.alignment = TextAnchor.MiddleCenter;
            b.onClick.AddListener(() => action()); return b;
        }
        ScrollRect Scroll(Transform parent, Vector2 pos, Vector2 size, out Text text)
        {
            var viewport = Rect("Text viewport", parent, pos, size); viewport.gameObject.AddComponent<Image>().color = new Color(1, .995f, .97f, 1); viewport.gameObject.AddComponent<RectMask2D>();
            var content = Rect("Content", viewport, Vector2.zero, size); content.anchorMin = content.anchorMax = new Vector2(.5f, 1); content.pivot = new Vector2(.5f, 1);
            text = Label(content, "Text", "", Vector2.zero, size - new Vector2(24, 10), 21); text.alignment = TextAnchor.UpperLeft;
            text.rectTransform.anchorMin = text.rectTransform.anchorMax = new Vector2(.5f, 1); text.rectTransform.pivot = new Vector2(.5f, 1); text.rectTransform.anchoredPosition = new Vector2(0, -8);
            var scroll = viewport.gameObject.AddComponent<ScrollRect>(); scroll.content = content; scroll.viewport = viewport; scroll.horizontal = false; scroll.movementType = ScrollRect.MovementType.Clamped;
            Button(parent, "^", pos + new Vector2(size.x / 2 + 17, size.y / 2 - 20), new Vector2(28, 34), () => scroll.verticalNormalizedPosition = Mathf.Clamp01(scroll.verticalNormalizedPosition + .25f));
            Button(parent, "v", pos + new Vector2(size.x / 2 + 17, size.y / 2 - 62), new Vector2(28, 34), () => scroll.verticalNormalizedPosition = Mathf.Clamp01(scroll.verticalNormalizedPosition - .25f));
            return scroll;
        }
        static void FitScroll(ScrollRect scroll, Text text)
        { float height = Mathf.Max(scroll.viewport.rect.height, text.preferredHeight + 22); scroll.content.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, height); text.rectTransform.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, height - 16); scroll.verticalNormalizedPosition = 1; }
        static RectTransform Rect(string name, Transform parent, Vector2 pos, Vector2 size)
        { var rt = new GameObject(name, typeof(RectTransform)).GetComponent<RectTransform>(); rt.SetParent(parent, false); rt.anchorMin = rt.anchorMax = new Vector2(.5f, .5f); rt.anchoredPosition = pos; rt.sizeDelta = size; return rt; }
    }
}
