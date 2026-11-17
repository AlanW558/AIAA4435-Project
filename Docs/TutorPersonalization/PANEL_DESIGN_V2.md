# Interaction panel design — revision 2

This revision supersedes the four-tab design in INTERACTION_REVIEW_AND_PANEL_DESIGN.md. It follows the user's feedback: conversation and Selective interaction are the focus; speech rate, reply length, tone and voice are directly adjustable; appearance changes are outcomes of interaction and belong in the shared change history.

## Structure and wording

Title: **Adaptive Conversational Agent**. No location eyebrow or motivational title. All interface labels, messages and feedback are in English.

Exactly three primary views:

- **Conversation**: messages, requests, and inline Selective clarification. Clear supported requests can apply directly; ambiguous requests present interpretations, a rephrase action, and cancellation before applying a change.
- **Controls**: speech rate, reply length, tone and voice, directly adjustable for the current session. Speech rate and reply length retain the sliders from the main-branch design. Tone and voice retain its option vocabulary. These are four controls within one view, not four primary navigation destinations.
- **History**: one chronological list for appearance outcomes and response-setting changes. Each item shows the affected property, before/after values, source (direct request, clarified request or direct control), status and a scoped undo. The appearance summary is read-only; there is no independent Appearance tab or appearance editor in this design.

Conversation history remains in Conversation. History records the consequences of interactions. During an unresolved clarification, conflicting edits are disabled until the user resolves or cancels it.

## Visual reference

Reference files from local main:

- Assets/Editor/SettingsPanelSetup.cs
- Assets/Project/Shaders/WarmPanel.shader
- Assets/Project/Materials/Interaction/SettingsPanelGlass.mat
- Assets/Project/Scripts/UI/PanelControlFeedback.cs

Retain warm-white typography, rounded translucent surfaces, subtle soft halo and low-opacity controls. The original shader uses a warm tint (1, .955, .865), an interior alpha contribution of .115 and a soft halo contribution up to .045; buttons use approximately .09 idle, .22 hover and .28 selected opacity. The browser design approximates these qualities with translucent warm glass over a contextual background. It does not reproduce Unity geometry or prove VR legibility. Final glass opacity, glow and contrast must be evaluated in the actual scene.

The design preview includes adjustable glass opacity and glow for visual review. Its examples and records are simulated, not study data. Voice A/B/C remain placeholders from main; no model or audio is connected. The Unity runtime, scenes and frozen study protocol were not modified for this revision.

## Preview verification

Verify three primary tabs, direct control changes, clarification cancellation without appearance changes, an appearance outcome in the shared history, and partial undo preserving unrelated response settings. Check desktop and 320px width for clipped controls or horizontal overflow. This does not replace head-mounted display testing.

## Audio preview addition

The user requested a **Play sample** action in Controls, with **Stop sample** during playback. A fixed short sentence uses the current speech rate and voice; audible tone requires supported speech-style controls. Fixed wording cannot demonstrate reply length or fully evaluate linguistic tone. Sample text candidate: “Let's explore this idea together, one step at a time.”

The intended workflow is initial adjustment with listening, followed by ongoing conversation and policy-mediated adjustments. Sample playback is separate from conversational messages, does not change preferences, and uses the same speech path as the tutor. Settings changes during playback stop the old sample. The visual preview reserves the button but disables playback with an explicit not-connected note until Unity audio is implemented.

Policy selection remains a proposed researcher/debug feature, not a new participant-facing control. In formal comparisons, preview, controls and repair remain shared; the policy governs whether to ask or act. Any temporary interaction locks follow common task-stage/state rules. See Study/FINAL_USER_STUDY_PLANNING.md §9 for study implications and pending decisions.

Audio preview layout refinement: keep the sample sentence on the left and Play sample on the right in one compact strip. Remove the extra audio heading and fixed-wording explanation; the existing preview footer communicates the disconnected audio state. The four property controls remain the main content of Controls.
