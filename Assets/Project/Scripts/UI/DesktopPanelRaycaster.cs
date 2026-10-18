using System.Collections.Generic;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.UI
{
    // Desktop testing and XR can share a canvas without reporting the same XR hit twice.
    public sealed class DesktopPanelRaycaster : GraphicRaycaster
    {
        public override void Raycast(PointerEventData eventData, List<RaycastResult> results)
        {
            if (!(eventData is TrackedDeviceEventData)) base.Raycast(eventData, results);
        }
    }
}
