using System.Collections;
using UnityEngine;

namespace IAI.Interaction
{
    public sealed class SeatViewFade : MonoBehaviour
    {
        public MeshRenderer overlay;
        Material instance;
        public float Alpha { get; private set; }

        void Awake()
        {
            instance = new Material(overlay.sharedMaterial);
            overlay.sharedMaterial = instance;
            SetAlpha(0f);
        }

        public void SetAlpha(float alpha)
        {
            Alpha = Mathf.Clamp01(alpha);
            if (instance) instance.SetColor("_Color", new Color(0, 0, 0, Alpha));
            if (overlay) overlay.enabled = Alpha > .001f;
        }

        public IEnumerator FadeTo(float target, float seconds)
        {
            float from = Alpha;
            for (float elapsed = 0; elapsed < seconds; elapsed += Time.unscaledDeltaTime)
            {
                SetAlpha(Mathf.Lerp(from, target, Mathf.SmoothStep(0, 1, elapsed / seconds)));
                yield return null;
            }
            SetAlpha(target);
        }

        void OnDisable() => SetAlpha(0);
        void OnDestroy() { if (instance) Destroy(instance); }
    }
}
