using UnityEngine;
using UnityEngine.UI;

namespace IAI.Interaction
{
    public sealed class SeatInteractionHint : MonoBehaviour
    {
        public ConversationSeat seat;
        public CanvasGroup group;
        public Text title, action, detail;
        public LineRenderer floorRing;
        float visibility;
        bool lastSeated;

        void LateUpdate()
        {
            bool seated = seat.IsSeated;
            bool visible = seated || seat.State == ConversationSeat.SeatState.Available;
            visibility = Mathf.MoveTowards(visibility, visible ? 1 : 0, Time.unscaledDeltaTime * 4.5f);
            group.alpha = visibility;
            if (visibility > 0)
            {
                Vector3 position = seat.seatAnchor.TransformPoint(seated ? new Vector3(.42f, 1.32f, 1.1f) : new Vector3(0, 1.18f, -.12f));
                position.y += .008f * Mathf.Sin(Time.unscaledTime * 1.8f);
                transform.position = position;
                var facing = position - seat.origin.Camera.transform.position;
                transform.rotation = Quaternion.LookRotation(facing, Vector3.up);
                transform.localScale = Vector3.one * ((seated ? .00065f : .001f) * Mathf.Lerp(.95f, 1f, visibility));
            }
            if (seated != lastSeated || string.IsNullOrEmpty(title.text) || !string.IsNullOrEmpty(seat.Feedback))
            {
                title.text = seated ? "SEATED" : "YOUR SEAT";
                action.text = seated ? "B / Y   LEAVE SEAT" : "A / X   SIT DOWN";
                detail.text = seated ? "Look around freely" : "Take a seat to begin";
                if (!string.IsNullOrEmpty(seat.Feedback)) detail.text = seat.Feedback;
#if UNITY_EDITOR
                if (string.IsNullOrEmpty(seat.Feedback)) detail.text += seated ? "  |  Backspace" : "  |  Enter";
#endif
                lastSeated = seated;
            }
            floorRing.enabled = !seated && visibility > .001f && !seat.IsTransitioning;
            float alpha = visibility * (.38f + .08f * Mathf.Sin(Time.unscaledTime * 2));
            var color = new Color(1, .87f, .64f, alpha);
            floorRing.startColor = floorRing.endColor = color;
        }
    }
}
