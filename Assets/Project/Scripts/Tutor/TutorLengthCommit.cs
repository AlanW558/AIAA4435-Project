using UnityEngine;
using UnityEngine.EventSystems;

namespace IAI.Tutor
{
    // Sliders edit a local draft. Only Confirm changes sends the complete patch.
    // Never carry a gesture into another branch/state.
    public sealed class TutorLengthCommit : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, ISubmitHandler
    {
        public TutorPanel panel;
        public bool speechRate;
        public bool IsDragging { get; private set; }
        string context;
        public void OnPointerDown(PointerEventData eventData)
        {
            IsDragging = panel && panel.CanEditControls;
            context = IsDragging ? panel.ControlContext : null;
        }
        public void CancelDrag() { IsDragging = false; context = null; }
        public void OnPointerUp(PointerEventData eventData)
        {
            bool commit = IsDragging && panel && panel.CanEditControls && context == panel.ControlContext;
            CancelDrag();
            if (commit) Commit(); else if (panel) panel.Render();
        }
        public void OnSubmit(BaseEventData eventData) { if (panel && panel.CanEditControls) Commit(); }
        void Commit() { if (speechRate) panel.CommitRate(); else panel.CommitLength(); }
        void OnDisable() { CancelDrag(); }
    }
}
