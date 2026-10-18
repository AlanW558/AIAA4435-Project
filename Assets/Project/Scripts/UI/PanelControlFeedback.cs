using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace IAI.UI
{
    public sealed class PanelControlFeedback : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler,
        IPointerDownHandler, IPointerUpHandler
    {
        public Image surface;
        public bool selected;
        public bool isSlider;
        bool hovered, pressed;
        public void OnPointerEnter(PointerEventData e) => hovered = true;
        public void OnPointerExit(PointerEventData e) { hovered = false; }
        public void OnPointerDown(PointerEventData e) { if (e.button == PointerEventData.InputButton.Left) pressed = true; }
        public void OnPointerUp(PointerEventData e) => pressed = false;
        void Update()
        {
            float target = pressed ? .985f : hovered ? 1.018f : 1f;
            if (!isSlider) transform.localScale = Vector3.Lerp(transform.localScale, Vector3.one * target, 1 - Mathf.Exp(-20 * Time.unscaledDeltaTime));
            else if (surface) surface.transform.localScale = Vector3.Lerp(surface.transform.localScale,
                Vector3.one * (pressed ? 1.08f : hovered ? 1.18f : 1f), 1 - Mathf.Exp(-20 * Time.unscaledDeltaTime));
            if (surface)
            {
                float alpha = isSlider ? .98f : selected ? .28f : hovered ? .22f : .09f;
                if (pressed && !isSlider) alpha = .32f;
                surface.color = Color.Lerp(surface.color, new Color(1f, .96f, .88f, alpha), 1 - Mathf.Exp(-18 * Time.unscaledDeltaTime));
            }
        }
        void OnDisable()
        {
            hovered = pressed = false;
            if (!isSlider) transform.localScale = Vector3.one;
            else if (surface) surface.transform.localScale = Vector3.one;
        }
    }
}
