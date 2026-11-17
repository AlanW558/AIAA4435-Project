using System;
using System.Linq;
using System.Text;
using IAI.Interaction;
using IAI.UI;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.Tutor
{
    /// <summary>Warm world-space Conversation / Controls / History panel.</summary>
    public sealed class TutorPanel : MonoBehaviour
    {
        public TutorClient client;
        public TutorComparisonClient comparison;
        public TextAsset taskSequence;
        public bool durableStudy;
        public bool freeTesting;
        TutorComparisonClient freeComparison; TutorClient freeSelective;
        Button comparisonModeButton, selectiveModeButton; Text modeTitle;
        public TutorStudyFlowPanel StudyFlow { get; private set; }
        public TutorTaskNavigation Navigation { get; private set; }
        public bool TaskCardOpen => StudyFlow ? StudyFlow.InstructionsOpen : comparison && Navigation != null && (!comparison.Connected || Navigation.Active) && Navigation.ShowCard;
        public TutorStudyPanel Study { get; private set; }
        public Vector3 studySeatOffset = new Vector3(-1.04f, .10f, 1.52f);
        public float panelMinimumBottomY = .80f;
        public Button TaskDetailsButton => Study ? Study.TaskButton : null;
        public Button NextTaskButton => Study ? Study.NextButton : null;
        public Button BeginTaskButton => Study ? Study.BeginButton : null;
        string navigationKey = "";
        ITutorPanelClient Driver => comparison ? (ITutorPanelClient)comparison : client;
        public ConversationSeat seat;
        public bool desktopDebugInput;
        public TutorSpeechInput Speech { get; private set; }
        public TutorAudioPlayback Playback { get; private set; }
        public Button ReplyAudioButton { get; private set; }
        Text replyAudioStatus, sampleStatus;
        Font interfaceFont;
        public bool SpeechVisible => isActiveAndEnabled && !(StudyFlow && StudyFlow.Speech && (StudyFlow.Speech.Recording || StudyFlow.Speech.Working)) && !(Study && Study.SpeechBusy) && !TaskCardOpen && CurrentTab == 0 && (!seat || seat.IsSeated);
        public Button RecordButton { get; private set; }
        Text speechPlaceholder;
        public Font font;
        public Sprite rounded;
        public Material glassMaterial;
        public int CurrentTab { get; private set; }
        public InputField DebugInput { get; private set; }
        public Slider RateSlider { get; private set; }
        public Button SampleButton { get; private set; }
        public Button[] ToneButtons { get; private set; }
        public Button[] VoiceButtons { get; private set; }
        public Button UndoPrevious { get; private set; }
        public Button UndoNext { get; private set; }
        public string SelectedUndoField { get; private set; } = "reply_length";
        public bool CanEditControls => Driver != null && Driver.CanEdit;
        public string ControlContext => Driver == null || !Driver.Connected ? "" : Driver.View.session_id + ":" + Driver.View.condition + ":" + Driver.View.revision + ":" + (comparison && comparison.Paused);
        public string DisplayedRate => rateValue ? rateValue.text : "";
        public string DisplayedTone => toneValue ? toneValue.text : "";
        public string DisplayedVoice => voiceValue ? voiceValue.text : "";
        public Slider LengthSlider { get; private set; }
        public Button SendButton { get; private set; }
        public Button RetryButton { get; private set; }
        public Button UndoButton { get; private set; }
        public Button StopButton { get; private set; }
        public Button CloseButton => Study ? Study.EndButton : null;
        public Button PauseButton => Study ? Study.PauseButton : null;
        public Button ConfirmPreparationButton { get; private set; }
        GameObject preparationStrip;
        string preparingTask = "";
        public Button[] StrategyButtons { get; private set; } = Array.Empty<Button>();
        public Button[] OptionButtons { get; private set; } = Array.Empty<Button>();
        public string DisplayedConversation => conversationText ? conversationText.text : "";
        public string DisplayedHistory => historyText ? historyText.text : "";
        public string DisplayedLength => lengthValue ? lengthValue.text : "";
        public string DisplayedStatus => status ? status.text : "";
        readonly Color ink = new Color(1f, .97f, .90f);
        Canvas canvas;
        CanvasGroup visibility;
        GameObject[] pages;
        Button[] tabs;
        Button connect, sync;
        Text badge, status, conversationText, historyText, lengthValue, lengthDescription, appearance, rateValue, toneValue, voiceValue;
        RectTransform conversationViewport, questionArea, optionsRoot;
        ScrollRect conversationScroll, historyScroll;
        Text questionText, undoField;
        string controlContext = "";
        static readonly string[] UndoFields = new[] { "all" }.Concat(TutorHistoryPresentation.Fields).ToArray();
        Text pauseOverlay;
        bool otherAnswer;
        string questionKey = "";
        string inputContext = "";
        Material ownedGlass;
        Renderer glass;

        public bool CanSwitchFreeMode => freeTesting && Driver!=null && !Driver.Busy && !Driver.UnknownOutcome && !Driver.HasQuestion && !Driver.HasQueuedAnswer &&
            (!comparison || !comparison.Connected || comparison.PreparationPending || comparison.State.phase=="awaiting_input" || comparison.State.results_visible && TutorComparisonClient.Conditions.All(c=>new[]{"ready","stopped"}.Contains(comparison.State.branches.Get(c).status))) &&
            !(Speech && (Speech.Recording || Speech.Working));
        public void SelectFreeMode(bool compare)
        {
            if(!CanSwitchFreeMode || compare==(comparison!=null))return;
            Speech.Cancel();Playback.Stop(reason:"mode_changed");CancelControlDrags();Driver.Changed-=Render;
            var avatar=comparison?comparison.avatar:client.avatar;
            if(comparison){comparison.avatar=null;comparison.enabled=false;}
            else{client.avatar=null;client.enabled=false;}
            comparison=compare?freeComparison:null;client=compare?null:freeSelective;
            if(!compare)client.endpoint=freeComparison.endpoint;
            if(compare){comparison.avatar=avatar;comparison.enabled=true;comparison.ReapplyAppearance();}
            else{client.avatar=avatar;client.enabled=true;client.ReapplyAppearance();}
            Driver.Changed+=Render;
            foreach(var b in StrategyButtons)b.gameObject.SetActive(compare);
            preparationStrip.SetActive(false);pauseOverlay.gameObject.SetActive(false);
            if(StopButton)StopButton.gameObject.SetActive(compare);
            inputContext="";OpenTab(0);Render();
            if(!Driver.Connected)Driver.Connect();
        }

        public void UseNaturalClient(TutorClient natural)
        {
            if(client==natural && !comparison)return;
            if(Driver!=null)Driver.Changed-=Render;
            if(Speech)Speech.Cancel();if(Playback)Playback.Stop(reason:"module_changed");
            if(comparison)comparison.enabled=false;
            comparison=null;client=natural;Navigation=null;client.Changed+=Render;
            foreach(var b in StrategyButtons)b.gameObject.SetActive(false);
            if(StopButton)StopButton.gameObject.SetActive(false);
            if(preparationStrip)preparationStrip.SetActive(false);
            if(pauseOverlay)pauseOverlay.gameObject.SetActive(false);
            OpenTab(0);Render();
        }
        public void LoadStudyPreview(bool studyPreview)
        {
            if (!comparison || comparison.Connected || comparison.Busy || comparison.UnknownOutcome || comparison.CanRetry)
                throw new InvalidOperationException("Choose materials before starting a comparison.");
            taskSequence = Resources.Load<TextAsset>(studyPreview ? "Tutor/StudyTaskSequence" : "Tutor/PracticeTaskSequence");
            Navigation = new TutorTaskNavigation(comparison, taskSequence ? taskSequence.text : "");
            Render();
        }

        void Awake()
        {
            interfaceFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (!font) font = interfaceFont;
            if (freeTesting)
            {
                durableStudy=false;
                if (!comparison) { comparison=gameObject.AddComponent<TutorComparisonClient>();comparison.connectOnStart=false;comparison.endpoint=client?client.endpoint:"http://127.0.0.1:8765";comparison.avatar=client?client.avatar:null; }
                freeComparison=comparison;
                freeSelective=client?client:gameObject.AddComponent<TutorClient>();
                freeSelective.connectOnStart=false;freeSelective.useEnvironmentEndpoint=false;freeSelective.condition="S";freeSelective.endpoint=comparison.endpoint;freeSelective.avatar=null;freeSelective.enabled=false;
                client=null;
            }
            if (comparison && !durableStudy && !freeTesting)
            {
                var sequence = taskSequence ? taskSequence : Resources.Load<TextAsset>("Tutor/PracticeTaskSequence");
                Navigation = new TutorTaskNavigation(comparison, sequence ? sequence.text : "");
            }
            Build();
            Speech = gameObject.AddComponent<TutorSpeechInput>(); Speech.panel = this;
            Speech.Changed += RenderSpeech;
            Playback = gameObject.AddComponent<TutorAudioPlayback>(); Playback.panel = this;
            Playback.Changed += RenderAudio;
            if (comparison && !freeTesting)
            {
                var root = new GameObject("Study questionnaire panel");
                root.transform.SetParent(transform.parent, false);
                if(durableStudy){StudyFlow=root.AddComponent<TutorStudyFlowPanel>();StudyFlow.Initialize(this);}
                else {Study = root.AddComponent<TutorStudyPanel>(); Study.Initialize(this);}
            }
        }
        void OnEnable() { if (Driver != null) Driver.Changed += Render; }
        void Start() { Render(); }
        void OnDisable() { if (Driver != null) Driver.Changed -= Render; if (Speech) Speech.Cancel(); if (Playback) Playback.Stop(reason: "component_disabled"); }
        void OnDestroy() { if (ownedGlass) Destroy(ownedGlass); if (Study) Destroy(Study.gameObject); if(StudyFlow) Destroy(StudyFlow.gameObject); }
        void Update()
        {
            if (Navigation != null)
            {
                Navigation.Update();
                string key = Navigation.Progress + ":" + Navigation.Guidance + ":" + TaskCardOpen + ":" + Navigation.CanNext + ":" + Navigation.CanBegin;
                if (navigationKey != key) { navigationKey = key; Render(); }
            }
            bool visible = !seat || seat.IsSeated;
            visibility.alpha = Mathf.MoveTowards(visibility.alpha, visible ? 1 : 0, Time.unscaledDeltaTime * 3.2f);
            visibility.interactable = visibility.blocksRaycasts = visible && visibility.alpha > .98f;
            if (ownedGlass) ownedGlass.SetFloat("_Visibility", visibility.alpha);
            if (glass) glass.enabled = visibility.alpha > .001f;
            if (!canvas.worldCamera) canvas.worldCamera = Camera.main;
            if (comparison) comparison.RecordPresentation(new[] { "conversation", "controls", "history" }[CurrentTab], !TaskCardOpen && visible && visibility.alpha > .98f);
            RefreshSpeechButtons();
            RenderAudio();
        }

        void Build()
        {
            var surface = GameObject.CreatePrimitive(PrimitiveType.Quad);
            surface.name = "Warm glass and soft halo";
            surface.transform.SetParent(transform, false);
            // Extend mainly upward; the shader's rounded visible area is smaller than its quad.
            surface.transform.localPosition = new Vector3(0, .08f, .06f);
            surface.transform.localScale = new Vector3(1.04f, comparison ? 1.20f : 1.08f, 1);
            Destroy(surface.GetComponent<Collider>());
            glass = surface.GetComponent<Renderer>();
            ownedGlass = glassMaterial ? new Material(glassMaterial) : new Material(Shader.Find("IAI/Warm Curved Panel"));
            ownedGlass.SetColor("_Tint", new Color(1, .955f, .865f));
            glass.sharedMaterial = ownedGlass;
            var root = Rect("Adaptive Agent Canvas", transform, Vector2.zero, new Vector2(960, comparison ? 1040 : 920));
            root.localScale = Vector3.one * .001f;
            root.localPosition = new Vector3(0, .06f, 0);
            canvas = root.gameObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace; canvas.worldCamera = Camera.main;
            var xr = root.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>();
            xr.checkFor3DOcclusion = true; xr.checkFor2DOcclusion = false;
            root.gameObject.AddComponent<DesktopPanelRaycaster>();
            visibility = root.gameObject.AddComponent<CanvasGroup>();
            visibility.alpha = seat ? 0 : 1;
            float headingY = comparison ? 410 : 350;
            WorldSpacePanelDragHandle.Attach(root,transform,new Vector2(0,headingY+65),new Vector2(900,44),interfaceFont,ink,panelMinimumBottomY);
            modeTitle = Label(root, "Title", comparison ? "Four-strategy comparison" : "Selective conversation", new Vector2(0, headingY), new Vector2(880, 54), 32);
            modeTitle.font = interfaceFont;
            if (freeTesting)
            {
                modeTitle.gameObject.SetActive(false);
                comparisonModeButton=Button(root,"Comparison mode","Four-strategy comparison",new Vector2(-224,headingY),new Vector2(430,54),()=>SelectFreeMode(true));
                selectiveModeButton=Button(root,"Selective mode","Selective conversation",new Vector2(224,headingY),new Vector2(430,54),()=>SelectFreeMode(false));
                SetInterfaceText(comparisonModeButton,30);SetInterfaceText(selectiveModeButton,30);
            }
            badge = Label(root, "Session", "NOT CONNECTED", new Vector2(362, headingY), new Vector2(150, 52), 16, TextAnchor.MiddleRight);
            badge.gameObject.SetActive(false);
            badge.resizeTextForBestFit = true; badge.resizeTextMinSize = 11; badge.resizeTextMaxSize = 16;
            if (comparison)
            {
                StrategyButtons = new Button[4];
                for (int i = 0; i < 4; i++)
                {
                    string condition = TutorComparisonClient.Conditions[i];
                    StrategyButtons[i] = Button(root, "Strategy " + condition, condition, new Vector2(-330 + i * 220, 346), new Vector2(204, 60), () => comparison.Select(condition));
                    SetInterfaceText(StrategyButtons[i], 29);
                }
                var preparation = Rect("Shared preparation", root, new Vector2(0, 350), new Vector2(880, 54));
                preparationStrip = preparation.gameObject;
                Label(preparation, "Preparation heading", "Shared starting settings", new Vector2(-170, 0), new Vector2(530, 50), 24);
                ConfirmPreparationButton = Button(preparation, "Confirm preparation", "Confirm settings", new Vector2(300, 0), new Vector2(280, 48), () => {
                    if (!comparison.CanConfirmPreparation) return;
                    if (Playback) Playback.Stop(reason: "context_changed");
                    comparison.ConfirmPreparation();
                });
                preparationStrip.SetActive(false);
            }
            tabs = new Button[3]; pages = new GameObject[3];
            string[] names = { "Conversation", "Controls", "History" };
            for (int i = 0; i < 3; i++)
            {
                int index = i;
                tabs[i] = Button(root, "Tab " + names[i], names[i], new Vector2(-296 + i * 296, 286), new Vector2(278, 48), () => OpenTab(index));
                SetInterfaceText(tabs[i], 30);
                pages[i] = Rect(names[i] + " page", root, new Vector2(0, -20), new Vector2(880, 540)).gameObject;
            }
            BuildConversation(pages[0].transform);
            BuildControls(pages[1].transform);
            BuildHistory(pages[2].transform);
            status = Label(root, "Status", "Connect to start a debug session.", new Vector2(0, -340), new Vector2(880, 48), 23);
            status.font = interfaceFont;
            connect = Button(root, "Connect", comparison && !freeTesting ? "Start task" : "Connect", new Vector2(-310, -382), new Vector2(220, 36), () => { if (Navigation != null) { Navigation.Begin(); Render(); } else Driver.Connect(); });
            sync = Button(root, "Sync", "Sync state", new Vector2(-55, -382), new Vector2(220, 36), () => Driver.RefreshState());
            RetryButton = Button(root, "Retry", "Retry / continue reply", new Vector2(250, -382), new Vector2(330, 36), () => Driver.Retry());
            if (comparison)
            {
                var footer = new[] { connect, sync, RetryButton };
                for (int i = 0; i < footer.Length; i++)
                {
                    var rect = footer[i].GetComponent<RectTransform>();
                    rect.anchoredPosition = new Vector2(-366 + i * 146.4f, -382); rect.sizeDelta = new Vector2(220, 44);
                    var label = footer[i].GetComponentInChildren<Text>();
                    label.rectTransform.sizeDelta = new Vector2(200, 40);
                }
                RetryButton.GetComponentInChildren<Text>().text = "Retry";
                StopButton = Button(root, "Stop branch", "Stop branch", new Vector2(219.6f, -382), new Vector2(220, 44), () => comparison.StopBranch());
                pauseOverlay = Label(root, "Paused message", "Comparison paused\n\nResume when you are ready.\nYou can also end this task without submitting feedback.", Vector2.zero, new Vector2(820, 240), 26, TextAnchor.MiddleCenter);
                pauseOverlay.gameObject.SetActive(false);
                connect.gameObject.SetActive(false);
                sync.GetComponent<RectTransform>().anchoredPosition = new Vector2(-285, -382);
                RetryButton.GetComponent<RectTransform>().anchoredPosition = new Vector2(0, -382);
                StopButton.GetComponent<RectTransform>().anchoredPosition = new Vector2(285, -382);
            }
            connect.GetComponent<RectTransform>().anchoredPosition = new Vector2(0, -382);
            foreach (var b in new[] { connect, sync, RetryButton, StopButton })
                if (b) SetInterfaceText(b, 24);
            if (!FindObjectOfType<EventSystem>())
            {
                var events = new GameObject("Tutor XR UI events", typeof(EventSystem), typeof(XRUIInputModule));
                var module = events.GetComponent<XRUIInputModule>();
                module.enableXRInput = module.enableMouseInput = module.enableBuiltinActionsAsFallback = true;
                events.GetComponent<EventSystem>().sendNavigationEvents = false;
            }
            OpenTab(0);
        }

        void BuildConversation(Transform p)
        {
            conversationScroll = Scroll(p, "Conversation transcript", new Vector2(-20, 40), new Vector2(832, 390), out conversationText);
            conversationViewport = conversationScroll.GetComponent<RectTransform>();
            Button(p, "Transcript up", "↑", new Vector2(420, 212), new Vector2(36, 40), () => ScrollBy(conversationScroll, .25f));
            Button(p, "Transcript down", "↓", new Vector2(420, 164), new Vector2(36, 40), () => ScrollBy(conversationScroll, -.25f));
            questionArea = Rect("Clarification", p, new Vector2(0, -80), new Vector2(880, 220));
            questionText = Label(questionArea, "Question", "", new Vector2(0, 80), new Vector2(860, 64), 26);
            optionsRoot = Rect("Options", questionArea, new Vector2(0, -20), new Vector2(880, 160));
            var entry = Rect("Speech transcript", p, new Vector2(0, -245), new Vector2(550, 70));
            var bg = entry.gameObject.AddComponent<Image>(); bg.color = new Color(1, .96f, .88f, .10f); bg.sprite = rounded; bg.type = Image.Type.Sliced;
            var inputLabel = Label(entry, "Text", "", Vector2.zero, new Vector2(524, 64), 24);
            inputLabel.supportRichText = false;
            var placeholder = Label(entry, "Placeholder", "Record a request or clarification.", Vector2.zero, new Vector2(524, 64), 23);
            speechPlaceholder = placeholder;
            placeholder.color = new Color(1, .97f, .90f, .55f);
            DebugInput = entry.gameObject.AddComponent<InputField>();
            DebugInput.textComponent = inputLabel; DebugInput.placeholder = placeholder; DebugInput.targetGraphic = bg;
            DebugInput.lineType = InputField.LineType.MultiLineNewline; DebugInput.characterLimit = 8000;
            DebugInput.onValueChanged.AddListener(_ => RefreshInputAvailability());
            SendButton = Button(p, "Send", "Send", new Vector2(365, -245), new Vector2(145, 70), () => { if (Speech && Speech.HasCapture) Speech.Submit(); else SubmitDebug(); });
            RecordButton = Button(p, "Record speech", "Record", new Vector2(-365, -245), new Vector2(145, 70), () => Speech.PressRecord());
            ReplyAudioButton = Button(p, "Play reply", "Play reply", new Vector2(352, -184), new Vector2(164, 40), () => Playback.ToggleReply());
            replyAudioStatus = Label(p, "Reply audio status", "", new Vector2(-96, -184), new Vector2(650, 40), 21);
        }
        void BuildControls(Transform p)
        {
            Surface(p, "Sample strip", new Vector2(0, 222), new Vector2(880, 54), .07f);
            Label(p, "Sample sentence", "Let's explore this idea together, one step at a time.", new Vector2(-112, 222), new Vector2(620, 48), 27);
            SampleButton = Button(p, "Play sample", "Play sample", new Vector2(344, 222), new Vector2(188, 44), () => Playback.ToggleSample());
            SetInterfaceText(SampleButton, 29);
            SampleButton.interactable = false;
            // Reserve a small line for live audio feedback; no permanent boilerplate.
            sampleStatus = Label(p, "Sample status", "", new Vector2(0, 179), new Vector2(860, 30), 22);
            Label(p, "Speech rate heading", "Speech rate", new Vector2(-250, 140), new Vector2(360, 46), 36);
            rateValue = Label(p, "Speech rate value", "—", new Vector2(235, 140), new Vector2(390, 46), 34, TextAnchor.MiddleRight);
            RateSlider = SliderControl(p, "Speech rate", new Vector2(0, 94), .7f, 1.3f, false);
            var rateCommit = RateSlider.gameObject.AddComponent<TutorLengthCommit>(); rateCommit.panel = this; rateCommit.speechRate = true;
            RateSlider.onValueChanged.AddListener(value => { if (CanEditControls) rateValue.text = value.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "× default"; });
            Label(p, "Reply length heading", "Reply length", new Vector2(-250, 22), new Vector2(360, 46), 36);
            lengthValue = Label(p, "Reply length value", "—", new Vector2(260, 22), new Vector2(340, 46), 34, TextAnchor.MiddleRight);
            LengthSlider = SliderControl(p, "Reply length", new Vector2(0, -24), 0, 2, true);
            var commit = LengthSlider.gameObject.AddComponent<TutorLengthCommit>(); commit.panel = this;
            LengthSlider.onValueChanged.AddListener(value => { if (Driver == null || !Driver.CanEdit) return; lengthValue.text = LengthName((int)value); });
            lengthDescription = Label(p, "Reply length description", "", new Vector2(0, -65), new Vector2(860, 38), 28);
            Label(p, "Tone heading", "Tone", new Vector2(-250, -116), new Vector2(360, 44), 36);
            toneValue = Label(p, "Tone value", "—", Vector2.zero, new Vector2(390, 44), 24, TextAnchor.MiddleRight);
            toneValue.gameObject.SetActive(false); // The selected option already identifies the current tone.
            ToneButtons = Choices(p, "Tone", new[] { "Professional", "Friendly", "Encouraging" }, -162, i => Driver.SetTone(i));
            Label(p, "Voice heading", "Voice", new Vector2(-250, -222), new Vector2(360, 44), 36);
            voiceValue = Label(p, "Voice value", "—", Vector2.zero, new Vector2(390, 44), 24, TextAnchor.MiddleRight);
            voiceValue.gameObject.SetActive(false);
            VoiceButtons = Choices(p, "Voice", TutorVoiceCatalog.Labels, -268, i => Driver.SetVoice(i));
            foreach (var text in p.GetComponentsInChildren<Text>(true)) text.font = interfaceFont;
        }
        void BuildHistory(Transform p)
        {
            appearance = Label(p, "Appearance summary", "Appearance will be read from the session.", new Vector2(0, 211), new Vector2(870, 60), 25);
            historyScroll = Scroll(p, "Change history", new Vector2(-20, -5), new Vector2(832, 355), out historyText);
            Button(p, "History up", "↑", new Vector2(420, 150), new Vector2(36, 40), () => ScrollBy(historyScroll, .25f));
            Button(p, "History down", "↓", new Vector2(420, 102), new Vector2(36, 40), () => ScrollBy(historyScroll, -.25f));
            UndoPrevious = Button(p, "Previous undo field", "‹", new Vector2(-395, -211), new Vector2(60, 34), () => CycleUndo(-1));
            undoField = Label(p, "Undo field", "Reply length", new Vector2(0, -211), new Vector2(710, 38), 25, TextAnchor.MiddleCenter);
            UndoNext = Button(p, "Next undo field", "›", new Vector2(395, -211), new Vector2(60, 34), () => CycleUndo(1));
            UndoButton = Button(p, "Undo selected field", "Undo latest reply-length change", new Vector2(0, -258), new Vector2(860, 44), () => Driver.UndoSetting(SelectedUndoField));
        }
        public void OpenTab(int index)
        {
            if (pages == null || index < 0 || index >= pages.Length) return;
            bool changed = CurrentTab != index;
            if (changed) { CancelControlDrags(); if (Speech) Speech.Cancel(); if (Playback) Playback.Stop(reason: "page_changed"); }
            CurrentTab = index;
            for (int i = 0; i < pages.Length; i++)
            {
                pages[i].SetActive(i == index && !TaskCardOpen && (!comparison || !comparison.Paused));
                tabs[i].GetComponent<PanelControlFeedback>().selected = i == index;
                tabs[i].interactable = !TaskCardOpen && (!comparison || !comparison.Paused);
            }
            if (changed && status) Render();
        }
        public void SelectUndoField(string field)
        {
            if (!UndoFields.Contains(field)) return;
            SelectedUndoField = field; Render();
        }
        void CycleUndo(int step)
        {
            if (!CanEditControls) return;
            int current = Array.IndexOf(UndoFields, SelectedUndoField);
            for (int i = 1; i < UndoFields.Length; i++)
            {
                string field = UndoFields[(current + step * i + UndoFields.Length * 2) % UndoFields.Length];
                if (Driver.CanUndoSetting(field)) { SelectUndoField(field); return; }
            }
        }
        void CancelControlDrags()
        {
            if (LengthSlider) LengthSlider.GetComponent<TutorLengthCommit>().CancelDrag();
            if (RateSlider) RateSlider.GetComponent<TutorLengthCommit>().CancelDrag();
        }
        public void CommitRate() { if (CanEditControls) { Driver.SetSpeechRate(RateSlider.value); Render(); } else Render(); }
        public void CommitLength() { if (Driver != null && Driver.CanEdit) { Driver.SetReplyLength(Mathf.RoundToInt(LengthSlider.value)); Render(); } else Render(); }
        public void SubmitDebug()
        {
            if (!desktopDebugInput || Driver == null || !Driver.CanSubmit || string.IsNullOrWhiteSpace(DebugInput.text)) return;
            if (otherAnswer && Driver.HasQuestion) Driver.SubmitClarification(DebugInput.text);
            else Driver.SubmitUserUtterance(DebugInput.text);
            if (comparison) DebugInput.text = "";
        }
        public void Render()
        {
            if (Driver == null || !badge) return;
            if (Navigation != null)
            {
                Navigation.Update(); comparison.instructionsOpen = TaskCardOpen;
                if (Study) Study.Render();
            }
            var v = Driver.View;
            if (controlContext != ControlContext || !CanEditControls) { CancelControlDrags(); controlContext = ControlContext; }
            badge.text = Driver.Connected ? $"DEBUG · {v.condition}\n{v.mode.ToUpperInvariant()}" : "NOT CONNECTED";
            status.text = !string.IsNullOrEmpty(Driver.Error) ? Driver.Error : Driver.Busy ? Driver.Activity
                : Driver.UnknownOutcome ? "Previous request still needs confirmation. Select Retry to recover it safely."
                : Driver.HasQueuedAnswer ? "A reply is pending. Select Retry / continue reply to finish it."
                : Driver.Connected && v.decision == "UNRESOLVED" ? v.message
                : Driver.HasQuestion ? "Reply to the displayed clarification only."
                : Driver.Connected ? "Ready · Record a request, or adjust session settings in Controls." : "Connect to start a debug session.";
            if (comparison)
            {
                status.text = string.IsNullOrEmpty(Driver.Error) ? comparison.Activity : Driver.Error;
                if (!comparison.Connected && string.IsNullOrEmpty(Driver.Error)) status.text = freeTesting ? "Connect to begin free testing." : "Open the Study panel to read the task and begin.";
                bool preparing = comparison.PreparationPending;
                preparationStrip.SetActive(preparing && !TaskCardOpen);
                ConfirmPreparationButton.interactable = comparison.CanConfirmPreparation;
                if (preparing && preparingTask != comparison.State.task_id)
                { preparingTask = comparison.State.task_id; OpenTab(1); }
                else if (!preparing && comparison.Connected && comparison.State.preparation_confirmed && preparingTask == comparison.State.task_id)
                { preparingTask = ""; OpenTab(0); }
                string context = comparison.Connected ? comparison.State.task_id + ":" + comparison.Selected + ":" + (v.question?.question_id ?? "") : "";
                if (inputContext != context) { inputContext = context; otherAnswer = false; DebugInput.text = ""; LengthSlider.GetComponent<TutorLengthCommit>().CancelDrag(); }
                string[] names = { "Always act", "Always ask", "Native", "Selective" };
                for (int i = 0; i < StrategyButtons.Length; i++)
                {
                    StrategyButtons[i].gameObject.SetActive(!preparing && !TaskCardOpen);
                    string condition = TutorComparisonClient.Conditions[i];
                    string state = comparison.Connected ? comparison.State.branches.Get(condition).status : "idle";
                    string caption = state == "awaiting_clarification" ? "Ask" : state == "processing" ? "Preparing" : state == "failed" ? "Needs attention" : Capital(state);
                    var strategyText = StrategyButtons[i].GetComponentInChildren<Text>();
                    bool ordinary = state == "ready" || state == "idle";
                    strategyText.text = ordinary ? names[i] : names[i] + "\n" + caption;
                    strategyText.fontSize = ordinary ? 29 : 24;
                    strategyText.fontStyle = condition == comparison.Selected ? FontStyle.Bold : FontStyle.Normal;
                    StrategyButtons[i].GetComponent<PanelControlFeedback>().selected = condition == comparison.Selected;
                    StrategyButtons[i].interactable = comparison.Available;
                }
                StopButton.interactable = comparison.CanStop;
                pauseOverlay.gameObject.SetActive(comparison.Paused);
                OpenTab(CurrentTab);
                if (comparison.Connected) badge.text = "DEBUG · " + (preparing ? "SETUP" : comparison.State.results_visible ? "COMPARE" : "BASELINE") + "\n" + (v.mode ?? "").ToUpperInvariant();
            }
            // Keep actionable warnings, but omit the repeated ready/completed instruction on Controls.
            bool controlsReady = CurrentTab == 1 && Driver.Connected && !Driver.Busy && !Driver.UnknownOutcome && !Driver.HasQuestion && !Driver.HasQueuedAnswer && string.IsNullOrEmpty(Driver.Error) && v.decision != "UNRESOLVED";
            if (comparison) controlsReady &= comparison.Connected && comparison.State.results_visible && comparison.State.lifecycle == "active" && comparison.Branch.status == "ready" && string.IsNullOrEmpty(comparison.RecordingError) && string.IsNullOrEmpty(comparison.State.publication_error);
            if (controlsReady) status.text = CanEditControls ? (comparison?"Controls apply to all four strategies.":"Controls apply to Selective.") : "Settings are locked for this step.";
            modeTitle.text=(comparison?"Four-strategy comparison":"Selective conversation")+(durableStudy?" · Study task":"");
            if(freeTesting)
            {
                comparisonModeButton.interactable=selectiveModeButton.interactable=CanSwitchFreeMode;
                comparisonModeButton.GetComponent<PanelControlFeedback>().selected=comparison;
                selectiveModeButton.GetComponent<PanelControlFeedback>().selected=!comparison;
                connect.gameObject.SetActive(!Driver.Connected);
            }
            connect.interactable = !Driver.Busy && !Driver.Connected;
            sync.gameObject.SetActive(Driver.Connected);
            sync.interactable = Driver.Connected && !Driver.Busy;
            RetryButton.interactable = Driver.CanRetry;
            if (CurrentTab == 1)
            {
                RetryButton.gameObject.SetActive(Driver.Connected && Driver.CanRetry);
                if (StopButton) StopButton.gameObject.SetActive(comparison && comparison.CanStop);
            }
            else
            {
                RetryButton.gameObject.SetActive(Driver.Connected);
                if (StopButton) StopButton.gameObject.SetActive(comparison);
            }
            UndoButton.interactable = Driver.CanUndoSetting(SelectedUndoField);
            undoField.text = SelectedUndoField == "all" ? "Latest change · all remaining fields" : TutorHistoryPresentation.Label(SelectedUndoField);
            UndoButton.GetComponentInChildren<Text>().text = UndoButton.interactable ? "Undo latest " + (SelectedUndoField == "all" ? "change" : TutorHistoryPresentation.Label(SelectedUndoField).ToLowerInvariant() + " change") : "No available change to undo";
            UndoPrevious.interactable = UndoNext.interactable = CanEditControls && UndoFields.Any(f => f != SelectedUndoField && Driver.CanUndoSetting(f));
            LengthSlider.interactable = RateSlider.interactable = CanEditControls;
            SampleButton.interactable = Playback && Playback.CanSample;
            foreach (var button in ToneButtons.Concat(VoiceButtons)) button.interactable = CanEditControls;
            if (Driver.Connected)
            {
                string[] lengths = { "brief", "balanced", "detailed" };
                int index = Array.IndexOf(lengths, v.settings.reply_length);
                var commit = LengthSlider.GetComponent<TutorLengthCommit>();
                if (!Driver.CanEdit) commit.CancelDrag();
                if (!commit.IsDragging)
                {
                    LengthSlider.SetValueWithoutNotify(Mathf.Max(0, index));
                    lengthValue.text = LengthName(index);
                }
                lengthDescription.text = index == 0 ? "Key answer only" : index == 1 ? "Key answer + a short reason" : "Key answer + explanation + a relevant example or steps";
                if (!RateSlider.GetComponent<TutorLengthCommit>().IsDragging)
                {
                    RateSlider.SetValueWithoutNotify(v.settings.speech_rate);
                    rateValue.text = v.settings.speech_rate.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "× default";
                }
                toneValue.text = Capital(v.settings.tone);
                voiceValue.text = TutorHistoryPresentation.Value(v.settings, "voice") + (v.audio_available ? "" : " · Audio not connected");
                string[] tones = { "professional", "friendly", "encouraging" }, voices = TutorVoiceCatalog.Ids;
                for (int i = 0; i < 3; i++)
                {
                    ToneButtons[i].GetComponent<PanelControlFeedback>().selected = v.settings.tone == tones[i];
                    ToneButtons[i].GetComponentInChildren<Text>().fontStyle = v.settings.tone == tones[i] ? FontStyle.Bold : FontStyle.Normal;
                }
                for (int i = 0; i < voices.Length; i++)
                {
                    VoiceButtons[i].GetComponent<PanelControlFeedback>().selected = v.settings.voice == voices[i];
                    VoiceButtons[i].GetComponentInChildren<Text>().fontStyle = v.settings.voice == voices[i] ? FontStyle.Bold : FontStyle.Normal;
                }
                appearance.text = $"Appearance · {Capital(v.settings.avatar_id)} · {Capital(v.settings.outfit)}\n{Capital(v.settings.jacket_color)} · {Capital(v.settings.accessory)} · {v.settings.scale:0.00}×";
            }
            var transcript = new StringBuilder();
            if (comparison && comparison.Connected && !comparison.State.results_visible && !string.IsNullOrEmpty(comparison.State.initial_query))
                transcript.Append("SHARED REQUEST\n").Append(comparison.State.round_query ?? comparison.State.initial_query).Append("\n\n");
            if (comparison && comparison.Connected && comparison.State.results_visible && !string.IsNullOrEmpty(v.message)
                && (comparison.Branch.status == "ready" || comparison.Branch.status == "stopped"))
                transcript.Append("SETTING UPDATE · ").Append(comparison.Selected).Append('\n').Append(v.message).Append("\n\n");
            if (Driver.Connected)
            {
                if (v.next_turn_override != null)
                {
                    var pending = v.next_turn_override;
                    var fields = new[] { "speech_rate", "reply_length", "tone", "voice" }.Where(f => f == "speech_rate" ? pending.speech_rate > 0 : f == "reply_length" ? !string.IsNullOrEmpty(pending.reply_length) : f == "tone" ? !string.IsNullOrEmpty(pending.tone) : !string.IsNullOrEmpty(pending.voice));
                    if (fields.Any()) transcript.Append("NEXT REPLY ONLY\n").Append(string.Join(" · ", fields.Select(f => TutorHistoryPresentation.Label(f) + ": " + TutorHistoryPresentation.Value(pending, f)))).Append("\n\n");
                }
                foreach (var exchange in v.conversation ?? Array.Empty<TutorExchange>())
                {
                    foreach (var message in exchange.messages ?? Array.Empty<TutorMessage>())
                    {
                        transcript.Append(message.role == "user" ? "YOU\n" : "TUTOR\n").Append(message.content).Append("\n");
                        if (message.role != "user" && exchange.settings != null)
                            transcript.Append("Answer settings · ").Append(string.Join(" · ", new[] { "reply_length", "tone", "speech_rate", "voice" }.Select(f => TutorHistoryPresentation.Value(exchange.settings, f)))).Append("\n");
                        transcript.Append("\n");
                    }
                }
                foreach (var job in v.generation_jobs ?? Array.Empty<TutorJob>())
                    if (job.status != "completed") transcript.Append("YOU · reply pending\n").Append(job.query).Append("\n\n");
                if (Driver.HasQuestion && (!comparison || comparison.State.results_visible || v.question.original_query != comparison.State.initial_query))
                    transcript.Append("REQUEST\n").Append(v.question.original_query).Append("\n\n");
                foreach (var query in v.deferred_questions ?? Array.Empty<string>()) transcript.Append("QUESTION · adjustment unresolved\n").Append(query).Append("\n\n");
            }
            SetScrollText(conversationScroll, conversationText, transcript.Length == 0 ? "Your conversation will appear here." : transcript.ToString());
            var history = new StringBuilder();
            if (Driver.Connected)
                foreach (var change in (v.changes ?? Array.Empty<TutorChange>()).Reverse())
                {
                    history.Append(TutorHistoryPresentation.Format(change));
                }
            SetScrollText(historyScroll, historyText, history.Length == 0 ? "No setting changes yet. Appearance outcomes and setting changes belong here." : history.ToString(), true);
            RenderQuestion(); RefreshInputAvailability();
        }
        void RenderQuestion()
        {
            bool ask = Driver.HasQuestion;
            questionArea.gameObject.SetActive(ask);
            conversationViewport.anchoredPosition = ask ? new Vector2(-20, 143) : new Vector2(-20, 40);
            conversationViewport.sizeDelta = new Vector2(832, ask ? 184 : 390);
            string key = ask ? Driver.View.question.question_id : "";
            if (key != questionKey)
            {
                foreach (Transform child in optionsRoot) { child.gameObject.SetActive(false); Destroy(child.gameObject); }
                questionKey = key; otherAnswer = false;
                OptionButtons = Array.Empty<Button>();
                if (ask)
                {
                    var options = Driver.View.question.options ?? Array.Empty<TutorOption>();
                    OptionButtons = new Button[options.Length];
                    for (int i = 0; i < options.Length; i++)
                    {
                        string id = options[i].id;
                        OptionButtons[i] = Button(optionsRoot, "Option " + id, options[i].label,
                            new Vector2(i % 2 == 0 ? -222 : 222, 48 - (i / 2) * 64), new Vector2(430, 60), () => {
                                if (id == "other") { otherAnswer = true; if (desktopDebugInput) { DebugInput.text = ""; DebugInput.ActivateInputField(); } }
                                else Driver.ChooseOption(id);
                            });
                        OptionButtons[i].GetComponentInChildren<Text>().resizeTextMinSize = 14;
                    }
                }
            }
            if (ask) { questionText.supportRichText = false; questionText.text = Driver.View.question.text; }
            foreach (var button in OptionButtons) button.interactable = !Driver.Busy && !Driver.UnknownOutcome;
        }
        void RefreshInputAvailability()
        {
            if (!DebugInput || Driver == null) return;
            DebugInput.readOnly = !desktopDebugInput || Speech && Speech.HasCapture;
            DebugInput.interactable = Driver.CanSubmit;
            RefreshSpeechButtons();
        }
        void RenderAudio()
        {
            if (!Playback || !ReplyAudioButton || Driver == null) return;
            bool ask = Driver.HasQuestion;
            ReplyAudioButton.gameObject.SetActive(!ask); replyAudioStatus.gameObject.SetActive(!ask);
            SampleButton.interactable = Playback.CanSample || Playback.Active && Playback.Purpose == "sample";
            ReplyAudioButton.interactable = Playback.CanReply || Playback.Active && Playback.Purpose == "reply";
            string active = Playback.Loading ? "Cancel audio" : "Stop " + Playback.Purpose;
            SampleButton.GetComponentInChildren<Text>().text = Playback.Active && Playback.Purpose == "sample" ? active : "Play sample";
            ReplyAudioButton.GetComponentInChildren<Text>().text = Playback.Active && Playback.Purpose == "reply" ? active : "Play reply";
            replyAudioStatus.text = Playback.Purpose == "reply" && Playback.Status.Length > 0 ? Playback.Status : "Listen to the latest reply using its original settings.";
            sampleStatus.text = Playback.Purpose == "sample" ? Playback.Status.Replace(" Select Play to listen again.", "") : "";
            if (Playback.AuditError.Length > 0) replyAudioStatus.text = sampleStatus.text = Playback.AuditError;
        }
        void RenderSpeech()
        {
            if (!DebugInput || !Speech) return;
            DebugInput.SetTextWithoutNotify(Speech.Transcript);
            speechPlaceholder.text = Speech.Status;
            RefreshInputAvailability();
        }
        void RefreshSpeechButtons()
        {
            if (!Speech || Driver == null) return;
            RecordButton.interactable = Speech.CanRecord || Speech.Working || Speech.Recording;
            RecordButton.GetComponentInChildren<Text>().text = Speech.Recording ? "Stop" : Speech.Working ? "Cancel" : Speech.Transcript.Length > 0 ? "Record again" : "Record";
            var sendLabel=SendButton.GetComponentInChildren<Text>();
            sendLabel.text=Driver.HasQuestion?"Reply":comparison?"Send to all 4":"Send";
            SendButton.interactable = Speech.HasCapture ? Speech.CanSend : desktopDebugInput && Driver.CanSubmit && !string.IsNullOrWhiteSpace(DebugInput.text);
        }
        static string LengthName(int index) => index < 0 || index > 2 ? "—" : new[] { "Brief", "Balanced", "Detailed" }[index];
        static string Capital(string text) => string.IsNullOrEmpty(text) ? "—" : char.ToUpperInvariant(text[0]) + text.Substring(1);
        static void ScrollBy(ScrollRect scroll, float step) { scroll.verticalNormalizedPosition = Mathf.Clamp01(scroll.verticalNormalizedPosition + step); }
        static void SetScrollText(ScrollRect scroll, Text text, string value, bool newestFirst = false)
        {
            if (text.text == value) return;
            text.text = value;
            text.rectTransform.sizeDelta = new Vector2(text.rectTransform.sizeDelta.x, Mathf.Max(scroll.viewport.rect.height, text.preferredHeight + 24));
            scroll.content.sizeDelta = new Vector2(0, text.rectTransform.sizeDelta.y + 12);
            Canvas.ForceUpdateCanvases(); scroll.verticalNormalizedPosition = newestFirst ? 1 : 0;
        }
        Button[] Choices(Transform p, string name, string[] values, float y, Action<int> select)
        {
            var buttons = new Button[values.Length];
            for (int i = 0; i < values.Length; i++)
            {
                int index = i;
                buttons[i] = Button(p, name + " " + values[i], values[i], new Vector2((i - (values.Length - 1) / 2f) * (888f / values.Length), y), new Vector2(888f / values.Length - 20, 52), () => select(index));
                SetInterfaceText(buttons[i], 32);
            }
            return buttons;
        }
        Slider SliderControl(Transform p, string name, Vector2 position, float min, float max, bool whole)
        {
            var root = Rect(name + " slider", p, position, new Vector2(840, 44));
            var track = Surface(root, "Track", Vector2.zero, new Vector2(820, 5), .16f);
            var fillArea = Rect("Fill area", root, Vector2.zero, new Vector2(820, 5));
            var fill = Surface(fillArea, "Fill", Vector2.zero, Vector2.zero, .7f);
            fill.rectTransform.anchorMin = Vector2.zero; fill.rectTransform.anchorMax = Vector2.one;
            var area = Rect("Handle area", root, Vector2.zero, new Vector2(820, 0));
            var handle = Surface(area, "Handle", Vector2.zero, new Vector2(34, 34), .95f);
            handle.raycastTarget = true; track.raycastTarget = true;
            var slider = root.gameObject.AddComponent<Slider>();
            slider.minValue = min; slider.maxValue = max; slider.wholeNumbers = whole;
            slider.fillRect = fill.rectTransform; slider.handleRect = handle.rectTransform; slider.targetGraphic = handle;
            slider.navigation = new UnityEngine.UI.Navigation { mode = UnityEngine.UI.Navigation.Mode.None };
            slider.SetValueWithoutNotify(1);
            return slider;
        }
        ScrollRect Scroll(Transform p, string name, Vector2 pos, Vector2 size, out Text text)
        {
            var viewport = Rect(name, p, pos, size);
            var background = viewport.gameObject.AddComponent<Image>(); background.color = new Color(.12f, .10f, .08f, .16f); background.raycastTarget = true;
            viewport.gameObject.AddComponent<RectMask2D>();
            var content = Rect("Content", viewport, Vector2.zero, new Vector2(size.x, size.y));
            content.anchorMin = new Vector2(0, 1); content.anchorMax = new Vector2(1, 1); content.pivot = new Vector2(.5f, 1); content.sizeDelta = new Vector2(0, size.y);
            text = Label(content, "Text", "", Vector2.zero, new Vector2(size.x - 28, size.y), 28, TextAnchor.UpperLeft);
            text.supportRichText = false;
            text.rectTransform.anchorMin = text.rectTransform.anchorMax = new Vector2(.5f, 1);
            text.rectTransform.pivot = new Vector2(.5f, 1); text.rectTransform.anchoredPosition = new Vector2(0, -12);
            var scroll = viewport.gameObject.AddComponent<ScrollRect>();
            scroll.viewport = viewport; scroll.content = content; scroll.horizontal = false; scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped; scroll.scrollSensitivity = 32;
            return scroll;
        }
        Button Button(Transform p, string name, string caption, Vector2 pos, Vector2 size, Action action)
        {
            var surface = Surface(p, name, pos, size, .09f); surface.raycastTarget = true;
            var button = surface.gameObject.AddComponent<Button>(); button.targetGraphic = surface;
            button.navigation = new UnityEngine.UI.Navigation { mode = UnityEngine.UI.Navigation.Mode.None };
            button.transition = Selectable.Transition.ColorTint;
            var colors = button.colors; colors.disabledColor = new Color(.65f, .65f, .65f, .4f); button.colors = colors;
            surface.gameObject.AddComponent<PanelControlFeedback>().surface = surface;
            button.onClick.AddListener(() => action());
            var text = Label(surface.transform, "Label", caption, Vector2.zero, size - new Vector2(20, 4), 25, TextAnchor.MiddleCenter);
            text.resizeTextForBestFit = true; text.resizeTextMinSize = 21; text.resizeTextMaxSize = 25;
            return button;
        }
        void SetInterfaceText(Button button, int size)
        {
            var text = button.GetComponentInChildren<Text>();
            text.font = interfaceFont; text.resizeTextForBestFit = false; text.fontSize = size;
        }
        Image Surface(Transform p, string name, Vector2 pos, Vector2 size, float alpha)
        {
            var image = Rect(name, p, pos, size).gameObject.AddComponent<Image>();
            image.sprite = rounded; image.type = Image.Type.Sliced; image.color = new Color(1, .96f, .88f, alpha); image.raycastTarget = false;
            return image;
        }
        Text Label(Transform p, string name, string value, Vector2 pos, Vector2 size, int points, TextAnchor align = TextAnchor.MiddleLeft)
        {
            var text = Rect(name, p, pos, size).gameObject.AddComponent<Text>();
            text.font = font; text.fontSize = points; text.color = ink; text.text = value; text.alignment = align; text.raycastTarget = false;
            text.horizontalOverflow = HorizontalWrapMode.Wrap; text.verticalOverflow = VerticalWrapMode.Truncate;
            var shadow = text.gameObject.AddComponent<Shadow>(); shadow.effectColor = new Color(.08f, .06f, .04f, .8f); shadow.effectDistance = new Vector2(.7f, -1.2f);
            return text;
        }
        static RectTransform Rect(string name, Transform p, Vector2 pos, Vector2 size)
        {
            var rt = new GameObject(name, typeof(RectTransform)).GetComponent<RectTransform>(); rt.SetParent(p, false);
            rt.anchorMin = rt.anchorMax = new Vector2(.5f, .5f); rt.sizeDelta = size; rt.anchoredPosition = pos;
            return rt;
        }
    }
}
