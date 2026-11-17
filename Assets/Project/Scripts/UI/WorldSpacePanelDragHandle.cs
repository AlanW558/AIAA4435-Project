using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.UI
{
    /// <summary>Move a world-space panel with its title bar, using mouse or XR UI rays.
    /// The plane is fixed during the drag, so moving the panel does not move the grab plane.</summary>
    public sealed class WorldSpacePanelDragHandle : MonoBehaviour, IInitializePotentialDragHandler,
        IBeginDragHandler, IDragHandler, IEndDragHandler, IPointerUpHandler
    {
        public Transform panelRoot;
        public RectTransform panelBounds;
        public float minimumBottomY = .80f;
        public bool IsDragging { get; private set; }
        Plane dragPlane;
        Vector3 startHit, startPosition;
        int ownerPointer;
        Camera eventCamera;
        readonly Vector3[] corners = new Vector3[4];

        public static WorldSpacePanelDragHandle Attach(RectTransform canvas, Transform panel,
            Vector2 centre, Vector2 size, Font font, Color textColour, float minimumBottom)
        {
            var go=new GameObject("Drag panel title",typeof(RectTransform),typeof(Image));
            var rect=(RectTransform)go.transform;rect.SetParent(canvas,false);rect.anchoredPosition=centre;rect.sizeDelta=size;
            rect.SetAsFirstSibling();
            go.GetComponent<Image>().color=new Color(1,1,1,.015f);
            var handle=go.AddComponent<WorldSpacePanelDragHandle>();handle.panelRoot=panel;handle.panelBounds=canvas;handle.minimumBottomY=minimumBottom;
            var hint=new GameObject("Drag hint",typeof(RectTransform),typeof(Text));
            var hr=(RectTransform)hint.transform;hr.SetParent(rect,false);hr.anchoredPosition=new Vector2(0,size.y*.5f-10);hr.sizeDelta=new Vector2(size.x-20,18);
            var text=hint.GetComponent<Text>();text.text="Drag to move";text.font=font;text.fontSize=13;text.alignment=TextAnchor.MiddleCenter;text.color=textColour;text.raycastTarget=false;
            return handle;
        }

        public void OnInitializePotentialDrag(PointerEventData data){data.useDragThreshold=false;}
        public void OnBeginDrag(PointerEventData data)
        {
            if(IsDragging || !panelRoot || data.button!=PointerEventData.InputButton.Left)return;
            eventCamera=data.pressEventCamera?data.pressEventCamera:GetComponentInParent<Canvas>().worldCamera;
            if(!eventCamera)eventCamera=Camera.main;
            if(!eventCamera)return;
            dragPlane=new Plane(eventCamera.transform.forward,panelRoot.position);
            if(!Hit(data,out startHit))return;
            ownerPointer=data.pointerId;startPosition=panelRoot.position;IsDragging=true;
        }
        bool Hit(PointerEventData data,out Vector3 hit)
        {
            hit=Vector3.zero;
            var xr=data as TrackedDeviceEventData;
            if(xr!=null)
            {
                if(xr.rayPoints==null)return false;
                for(int i=1;i<xr.rayPoints.Count;i++)
                {
                    var segment=xr.rayPoints[i]-xr.rayPoints[i-1];float length=segment.magnitude;
                    if(length<.0001f)continue;
                    var ray=new Ray(xr.rayPoints[i-1],segment/length);float distance;
                    if(dragPlane.Raycast(ray,out distance)&&distance<=length){hit=ray.GetPoint(distance);return true;}
                }
                return false;
            }
            if(!eventCamera)return false;
            var mouseRay=eventCamera.ScreenPointToRay(data.position);float d;
            if(!dragPlane.Raycast(mouseRay,out d))return false;
            hit=mouseRay.GetPoint(d);return true;
        }
        public void OnDrag(PointerEventData data)
        {
            if(!IsDragging || data.pointerId!=ownerPointer || !panelRoot)return;
            Vector3 hit;if(!Hit(data,out hit))return;
            var next=startPosition+hit-startHit;
            if(float.IsNaN(next.x)||float.IsNaN(next.y)||float.IsNaN(next.z)||float.IsInfinity(next.sqrMagnitude))return;
            // Keep the complete panel (including bottom buttons) above the tabletop.
            if(panelBounds)
            {
                panelBounds.GetWorldCorners(corners);float bottom=corners[0].y;
                for(int i=1;i<corners.Length;i++)bottom=Mathf.Min(bottom,corners[i].y);
                next.y=Mathf.Max(next.y,panelRoot.position.y+minimumBottomY-bottom);
            }
            panelRoot.position=next;
        }
        public void OnEndDrag(PointerEventData data){if(data.pointerId==ownerPointer)IsDragging=false;}
        public void OnPointerUp(PointerEventData data){if(data.pointerId==ownerPointer)IsDragging=false;}
        void OnDisable(){IsDragging=false;}
    }
}
