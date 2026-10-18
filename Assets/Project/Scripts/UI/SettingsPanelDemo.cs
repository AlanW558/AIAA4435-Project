using System;
using System.Collections;
using IAI.Interaction;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace IAI.UI
{
    /// <summary>Presentation-only state. No tutor, audio, LLM, or study-policy side effects.</summary>
    public sealed class SettingsPanelDemo : MonoBehaviour
    {
        [Serializable]
        public sealed class PreviewValues
        {
            public float speechRate = 1f;
            public int replyLength = 1;
            public int tone = 1;
            public int voice;
        }

        public ConversationSeat seat;
        public CanvasGroup visibilityGroup;
        public MeshRenderer backdrop;
        public CanvasGroup[] pages;
        public Text[] homeValues;
        public Slider rateSlider, lengthSlider;
        public Text rateValue, lengthValue, lengthDescription;
        public PanelControlFeedback[] toneOptions, voiceOptions;
        public GameObject[] toneChecks, voiceChecks;
        public PreviewValues values = new PreviewValues();
        public int CurrentPage { get; private set; }
        public bool IsPageTransitioning { get; private set; }
        public float Visibility => visibility;
        public bool CanInteract => seat && seat.IsSeated && visibility > .98f && !IsPageTransitioning;

        static readonly string[] Lengths = { "Brief", "Balanced", "Detailed" };
        static readonly string[] LengthDescriptions = { "A short, focused response.", "Enough detail to keep the conversation flowing.", "More explanation, context and examples." };
        static readonly string[] Tones = { "Professional", "Friendly", "Encouraging" };
        static readonly string[] Voices = { "Voice A", "Voice B", "Voice C" };
        Material material;
        float visibility;
        Coroutine pageRoutine;

        void Awake()
        {
            material = new Material(backdrop.sharedMaterial);
            backdrop.sharedMaterial = material;
            foreach (var page in pages) { page.gameObject.SetActive(false); page.alpha = 0; }
            pages[0].gameObject.SetActive(true);
            pages[0].alpha = 1;
            rateSlider.onValueChanged.AddListener(ChangeRate);
            lengthSlider.onValueChanged.AddListener(ChangeLength);
            RefreshValues();
            ApplyVisibility(0);
        }

        void Update()
        {
            float target = seat.IsSeated ? 1 : 0;
            visibility = Mathf.MoveTowards(visibility, target, Time.unscaledDeltaTime * 3.2f);
            ApplyVisibility(visibility);
            visibilityGroup.interactable = visibilityGroup.blocksRaycasts = CanInteract;
            if (!seat.IsSeated && IsPageTransitioning) FinishPageImmediately();
            if (visibility < .001f && !seat.IsSeated && CurrentPage != 0) SetPageImmediately(0);
        }

        void ApplyVisibility(float alpha)
        {
            visibilityGroup.alpha = alpha;
            backdrop.enabled = alpha > .001f;
            if (material) material.SetFloat("_Visibility", alpha);
        }

        public void OpenPage(int page)
        {
            if (!CanInteract || page < 0 || page >= pages.Length || page == CurrentPage) return;
            pageRoutine = StartCoroutine(TransitionTo(page));
        }

        IEnumerator TransitionTo(int page)
        {
            IsPageTransitioning = true;
            visibilityGroup.interactable = visibilityGroup.blocksRaycasts = false;
            if (EventSystem.current) EventSystem.current.SetSelectedGameObject(null);
            int direction = page == 0 ? -1 : 1;
            var outgoing = pages[CurrentPage];
            var outgoingRect = (RectTransform)outgoing.transform;
            for (float t = 0; t < .12f; t += Time.unscaledDeltaTime)
            {
                float k = Mathf.SmoothStep(0, 1, t / .12f);
                outgoing.alpha = 1 - k;
                outgoingRect.anchoredPosition = new Vector2(-direction * 18 * k, 0);
                yield return null;
            }
            outgoing.gameObject.SetActive(false);
            outgoingRect.anchoredPosition = Vector2.zero;
            CurrentPage = page;
            var incoming = pages[page];
            var incomingRect = (RectTransform)incoming.transform;
            incoming.gameObject.SetActive(true);
            for (float t = 0; t < .18f; t += Time.unscaledDeltaTime)
            {
                float k = Mathf.SmoothStep(0, 1, t / .18f);
                incoming.alpha = k;
                incomingRect.anchoredPosition = new Vector2(direction * 18 * (1 - k), 0);
                yield return null;
            }
            incoming.alpha = 1;
            incomingRect.anchoredPosition = Vector2.zero;
            IsPageTransitioning = false;
            pageRoutine = null;
        }

        void ChangeRate(float rate)
        {
            if (!CanInteract) { RefreshValues(); return; }
            values.speechRate = Mathf.Round(rate * 100) / 100f;
            RefreshValues();
        }
        void ChangeLength(float length)
        {
            if (!CanInteract) { RefreshValues(); return; }
            values.replyLength = Mathf.Clamp(Mathf.RoundToInt(length), 0, 2);
            RefreshValues();
        }
        public void ChooseTone(int index)
        {
            if (!CanInteract || index < 0 || index >= Tones.Length) return;
            values.tone = index;
            RefreshValues();
        }
        public void ChooseVoice(int index)
        {
            if (!CanInteract || index < 0 || index >= Voices.Length) return;
            values.voice = index;
            RefreshValues();
        }
        public void ResetCurrent()
        {
            if (!CanInteract) return;
            if (CurrentPage == 0) values = new PreviewValues();
            else if (CurrentPage == 1) values.speechRate = 1;
            else if (CurrentPage == 2) values.replyLength = 1;
            else if (CurrentPage == 3) values.tone = 1;
            else if (CurrentPage == 4) values.voice = 0;
            RefreshValues();
        }

        void RefreshValues()
        {
            values.speechRate = Mathf.Clamp(values.speechRate, .7f, 1.3f);
            values.replyLength = Mathf.Clamp(values.replyLength, 0, 2);
            values.tone = Mathf.Clamp(values.tone, 0, 2);
            values.voice = Mathf.Clamp(values.voice, 0, 2);
            rateSlider.SetValueWithoutNotify(values.speechRate);
            lengthSlider.SetValueWithoutNotify(values.replyLength);
            rateValue.text = values.speechRate.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture) + "×";
            lengthValue.text = Lengths[values.replyLength];
            lengthDescription.text = LengthDescriptions[values.replyLength];
            homeValues[0].text = rateValue.text;
            homeValues[1].text = lengthValue.text;
            homeValues[2].text = Tones[values.tone];
            homeValues[3].text = Voices[values.voice];
            for (int i = 0; i < 3; i++)
            {
                toneOptions[i].selected = i == values.tone;
                voiceOptions[i].selected = i == values.voice;
                toneChecks[i].SetActive(i == values.tone);
                voiceChecks[i].SetActive(i == values.voice);
            }
        }

        void FinishPageImmediately()
        {
            if (pageRoutine != null) StopCoroutine(pageRoutine);
            pageRoutine = null;
            IsPageTransitioning = false;
            SetPageImmediately(CurrentPage);
        }
        void SetPageImmediately(int page)
        {
            CurrentPage = page;
            for (int i = 0; i < pages.Length; i++)
            {
                pages[i].alpha = i == page ? 1 : 0;
                ((RectTransform)pages[i].transform).anchoredPosition = Vector2.zero;
                pages[i].gameObject.SetActive(i == page);
            }
        }
        void OnDisable()
        {
            FinishPageImmediately();
            visibility = 0;
            ApplyVisibility(0);
            visibilityGroup.interactable = visibilityGroup.blocksRaycasts = false;
        }
        void OnDestroy() { if (material) Destroy(material); }
    }
}
