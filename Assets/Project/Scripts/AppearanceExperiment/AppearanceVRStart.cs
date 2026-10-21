using System.Collections;
using IAI.Interaction;
using UnityEngine;

namespace IAI.Appearance
{
    // One initial placement under the existing seat fade; tracked head pose is never animated.
    public sealed class AppearanceVRStart : MonoBehaviour
    {
        public ConversationSeat seat;
        IEnumerator Start()
        {
            Screen.sleepTimeout=SleepTimeout.NeverSleep;
            yield return new WaitForSecondsRealtime(1.5f);
            if(!seat||!seat.origin||!seat.origin.Camera)yield break;
            seat.origin.MatchOriginUpCameraForward(Vector3.up,seat.seatAnchor.forward);
            seat.origin.MoveCameraToWorldLocation(seat.seatAnchor.TransformPoint(new Vector3(0,1.6f,-.5f)));
            yield return null;
            seat.TrySit();
        }
    }
}
