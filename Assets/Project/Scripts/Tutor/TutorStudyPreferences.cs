using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace IAI.Tutor
{
    public sealed partial class TutorStudyPanel
    {
        public bool PreferenceMode => owner && nav.AtPreferenceBoundary;
        public string PreferenceScope => client.State?.sequence?.preference_scope ?? "";
        public string CurrentPreferenceAnswers => PreferenceDraft().ToString(Formatting.None);
        public Button[] PreferenceStrategyButtons { get; private set; }
        public Button[] PreferenceCategoryButtons { get; private set; }
        readonly Dictionary<string, JObject> preferenceDrafts = new Dictionary<string, JObject>();
        GameObject preferencePage, preferenceForm;
        Text preferenceQuestion, preferenceHelp, preferenceText, preferenceSpeechStatus, preferenceDone;
        ScrollRect preferenceScroll;
        Button preferenceRecord, preferenceUse, preferenceClear;
        string lastPreferenceStep = "";
        string PreferenceKey => (client.State?.task_id ?? "") + ":" + PreferenceScope;
        bool CanEditPreference => PreferenceMode && client.PreferenceAvailable && Visible && !SpeechBusy;
        bool PreferenceComplete
        {
            get
            {
                var d = PreferenceDraft(); string kind = d.Value<string>("choice_kind"); int n = ((JArray)d["selected_conditions"]).Count;
                return kind == "selected" ? n >= 1 && n <= 4 : kind == "no_clear_preference" && n == 0;
            }
        }
        JObject PreferenceDraft()
        {
            if (!preferenceDrafts.TryGetValue(PreferenceKey, out var d))
            { d = new JObject { ["selected_conditions"] = new JArray(), ["comment"] = "", ["comment_confirmed"] = false }; preferenceDrafts.Add(PreferenceKey, d); }
            return d;
        }
        public void ChoosePreferenceStrategy(string condition)
        {
            if (!CanEditPreference || !TutorComparisonClient.Conditions.Contains(condition)) return;
            var d = PreferenceDraft(); var array = (JArray)d["selected_conditions"];
            var old = array.FirstOrDefault(x => (string)x == condition);
            if (old != null) old.Remove(); else if (array.Count < 4) array.Add(condition); else return;
            d["choice_kind"] = "selected"; Render();
        }
        public void ChoosePreferenceCategory(string kind)
        {
            if (!CanEditPreference || kind != "no_clear_preference") return;
            var d = PreferenceDraft(); d["choice_kind"] = kind; d["selected_conditions"] = new JArray(); Render();
        }
        public void SubmitPreference()
        {
            if (!CanEditPreference || !PreferenceComplete || Speech && Speech.HasCapture) return;
            client.SavePreference(PreferenceScope, CurrentPreferenceAnswers);
        }
        void ClearPreferenceComment()
        { if (Speech) Speech.Cancel(); if (CanEditPreference) { var d = PreferenceDraft(); d["comment"] = ""; d["comment_confirmed"] = false; } Render(); }
        bool RenderPreference()
        {
            bool mode = PreferenceMode;
            preferencePage.SetActive(mode);
            TaskButton.gameObject.SetActive(!mode); questionnaireButton.gameObject.SetActive(!mode); notesButton.gameObject.SetActive(!mode);
            foreach (var button in conditions) button.gameObject.SetActive(!mode);
            feedbackHeading.gameObject.SetActive(!mode);
            if (!mode) { lastPreferenceStep = ""; return false; }
            string step = PreferenceKey;
            if (lastPreferenceStep != step) { lastPreferenceStep = step; Visible = true; if (Speech && Speech.HasCapture) Speech.Cancel(); }
            body.SetActive(Visible); ToggleButton.GetComponentInChildren<Text>().text = Visible ? "Hide study panel" : "Show study panel";
            taskPage.SetActive(false); ratingPage.SetActive(false); notesPage.SetActive(false);
            var sequence = client.State.sequence;
            bool pending = PreferenceScope.Length > 0 && !sequence.preference_exited;
            progress.text = PreferenceScope == "comparison_overall" ? "Practice · Overall attribute comparison" : nav.Progress + " · Preference";
            preferenceForm.SetActive(pending); preferenceDone.gameObject.SetActive(!pending);
            string attribute = nav.Module.direction == "speech_rate" ? "speech-rate" : nav.Module.direction == "reply_length" ? "reply-length" : nav.Module.direction;
            preferenceQuestion.text = PreferenceScope == "comparison_overall"
                ? "Considering the speech-rate, reply-length, tone, and voice tasks, which approach would you prefer to use overall?"
                : $"For {attribute} adjustments, which approach would you prefer to use?";
            preferenceHelp.text = "Select all approaches you prefer (one to four).\nChoose No preference on its own.";
            var d = PreferenceDraft(); var selected = (JArray)d["selected_conditions"];
            for (int i = 0; i < 4; i++)
            {
                bool chosen = selected.Any(x => (string)x == TutorComparisonClient.Conditions[i]);
                PreferenceStrategyButtons[i].interactable = CanEditPreference;
                Tint(PreferenceStrategyButtons[i], chosen);
            }
            PreferenceCategoryButtons[0].interactable = CanEditPreference;
            Tint(PreferenceCategoryButtons[0], d.Value<string>("choice_kind") == "no_clear_preference");
            string text = Speech && Speech.Transcript.Length > 0 ? Speech.Transcript : d.Value<string>("comment") ?? "";
            if (preferenceText.text != text) { preferenceText.text = text; FitScroll(preferenceScroll, preferenceText); }
            preferenceSpeechStatus.text = Speech && Speech.HasCapture ? Speech.Status : "Optional: explain your preference in your own words.";
            preferenceRecord.interactable = Speech && (CanRecordComment || SpeechBusy);
            preferenceRecord.GetComponentInChildren<Text>().text = Speech && Speech.Recording ? "Stop recording" : Speech && Speech.Working ? "Cancel" : "Record reason";
            preferenceUse.interactable = Speech && Speech.CanSend && Speech.Transcript.Length <= 4000;
            preferenceClear.interactable = CanEditPreference || Speech && Speech.HasCapture;
            SaveButton.GetComponentInChildren<Text>().text = "Submit preference";
            SaveButton.interactable = pending && CanEditPreference && PreferenceComplete && !(Speech && Speech.HasCapture);
            NextButton.GetComponentInChildren<Text>().text = nav.HasNextModule ? "Continue to " + nav.NextModuleTitle : sequence.comparison_complete ? "Comparison feedback complete" : "Submit preference first";
            NextButton.interactable = nav.CanContinueModule && !(Speech && Speech.HasCapture);
            PauseButton.interactable = EndButton.interactable = !client.Busy && !client.UnknownOutcome && !sequence.preference_exited && !sequence.comparison_complete;
            PauseButton.GetComponentInChildren<Text>().text = sequence.preference_paused ? "Resume" : "Pause";
            EndButton.GetComponentInChildren<Text>().text = "Exit comparison activity";
            preferenceDone.text = sequence.preference_exited ? "Comparison activity ended.\n\nYour previously submitted feedback has been kept."
                : nav.ComparisonComplete ? sequence.all_attributes
                    ? "Four-attribute comparison feedback saved.\n\nYou may take a break.\nThe Selective natural conversation activity comes next.\nPlease wait for the researcher."
                    : "Practice comparison feedback saved.\n\nThis practice covered only the listed attributes.\nNo overall four-attribute preference was requested."
                : "Your attribute preference has been saved.\n\nContinue when you are ready for the next attribute.";
            status.text = client.Error.Length > 0 ? client.Error : client.Busy ? "Saving / synchronizing..." : client.UnknownOutcome ? "Save outcome unknown. Use Retry on the system panel." : sequence.preference_paused ? "Paused. Your preference draft is kept." : pending ? "No default answer · optional reasons are not required." : "";
            return true;
        }
        void BuildPreferences(Transform sheet)
        {
            preferencePage = Rect("Strategy preference page", sheet, new Vector2(0, 0), new Vector2(750, 780)).gameObject;
            preferenceForm = Rect("Preference form", preferencePage.transform, Vector2.zero, new Vector2(750, 780)).gameObject;
            var root = preferenceForm.transform;
            preferenceQuestion = Label(root, "Preference question", "", new Vector2(0, 323), new Vector2(740, 124), 24);
            preferenceHelp = Label(root, "Preference help", "", new Vector2(0, 220), new Vector2(740, 65), 19);
            string[] labels = { "E · Execute-first", "A · Always-ask", "N · Native-gate", "S · Selective" };
            PreferenceStrategyButtons = new Button[4];
            for (int i = 0; i < 4; i++) { string c = TutorComparisonClient.Conditions[i]; PreferenceStrategyButtons[i] = Button(root, labels[i], new Vector2(i % 2 == 0 ? -190 : 190, 155 - (i / 2) * 62), new Vector2(360, 52), () => ChoosePreferenceStrategy(c)); }
            PreferenceCategoryButtons = new[] { Button(root, "No preference", new Vector2(0, 20), new Vector2(740, 44), () => ChoosePreferenceCategory("no_clear_preference")) };
            preferenceScroll = Scroll(root, new Vector2(0, -135), new Vector2(740, 210), out preferenceText);
            preferenceSpeechStatus = Label(root, "Preference speech status", "", new Vector2(0, -276), new Vector2(740, 44), 17);
            preferenceRecord = Button(root, "Record reason", new Vector2(-249, -331), new Vector2(238, 44), () => Speech.PressRecord());
            preferenceUse = Button(root, "Use text", new Vector2(0, -331), new Vector2(238, 44), () => Speech.Submit());
            preferenceClear = Button(root, "Discard / clear", new Vector2(249, -331), new Vector2(238, 44), ClearPreferenceComment);
            preferenceDone = Label(preferencePage.transform, "Preference saved message", "", new Vector2(0, 40), new Vector2(720, 340), 26);
            preferencePage.SetActive(false);
        }
    }
}
