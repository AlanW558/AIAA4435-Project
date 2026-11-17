using System;
using System.Collections.Generic;
using System.IO;
using IAI.Tutor;
using IAI.UI;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.XR.Interaction.Toolkit.UI;

public static class TutorPanelLayoutChecks
{
    static int checks;
    static void Check(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
    public static void Run()
    {
        checks=0;var panel=UnityEngine.Object.FindObjectOfType<TutorPanel>();
        Check(panel&&panel.StudyFlow,"Open the comparison scene in Play mode.");
        var handles=UnityEngine.Object.FindObjectsOfType<WorldSpacePanelDragHandle>();Check(handles.Length==2,"Both panels need a title drag handle.");
        var camera=Camera.main;
        foreach(var h in handles)
        {
            var initial=h.panelRoot.position;var rotation=h.panelRoot.rotation;
            var centre=h.transform.position;var screen=camera.WorldToScreenPoint(centre);
            try
            {
                var mouse=new PointerEventData(EventSystem.current){pointerId=-1,button=PointerEventData.InputButton.Left,position=new Vector2(screen.x,screen.y)};
                h.OnBeginDrag(mouse);Check(h.IsDragging,"Mouse must acquire title bar.");
                h.OnDrag(mouse);Check(Vector3.Distance(initial,h.panelRoot.position)<.005f,"Grab must not jump.");
                mouse.position+=new Vector2(28,20);h.OnDrag(mouse);Check(Vector3.Distance(initial,h.panelRoot.position)>.01f,"Mouse drag must move panel.");
                h.OnEndDrag(mouse);Check(!h.IsDragging,"Mouse release must stop movement.");h.panelRoot.position=initial;
                var origin=camera.transform.position;
                var xr=new TrackedDeviceEventData(EventSystem.current){pointerId=99,button=PointerEventData.InputButton.Left,rayPoints=new List<Vector3>{origin,origin+(centre-origin)*4}};
                h.OnBeginDrag(xr);Check(h.IsDragging,"XR ray must acquire title bar.");
                var target=centre+camera.transform.right*.08f+Vector3.up*.03f;
                xr.rayPoints=new List<Vector3>{origin,origin+(target-origin)*4};h.OnDrag(xr);
                Check(Vector3.Distance(initial,h.panelRoot.position)>.04f,"XR drag must move panel.");
                var held=h.panelRoot.position;xr.pointerId=100;h.OnDrag(xr);h.OnEndDrag(xr);
                Check(h.IsDragging&&Vector3.Distance(held,h.panelRoot.position)<.0001f,"A second pointer must not steal the drag.");xr.pointerId=99;
                target=centre-Vector3.up*3;xr.rayPoints=new List<Vector3>{origin,origin+(target-origin)*4};h.OnDrag(xr);
                var corners=new Vector3[4];h.panelBounds.GetWorldCorners(corners);
                foreach(var c in corners)Check(c.y>=h.minimumBottomY-.001f,"Bottom controls must remain above the table.");
                h.OnEndDrag(xr);Check(!h.IsDragging,"XR release must stop movement.");
                Check(Quaternion.Angle(rotation,h.panelRoot.rotation)<.001f,"Dragging must preserve chosen panel rotation.");
                h.panelRoot.position=initial;
                h.OnBeginDrag(mouse);h.enabled=false;Check(!h.IsDragging,"Disabling a handle must release capture.");h.enabled=true;
            }
            finally{h.panelRoot.position=initial;h.panelRoot.rotation=rotation;h.enabled=true;}
        }
        Directory.CreateDirectory("StudyData/manual/20261116-live-01");
        File.WriteAllText("StudyData/manual/20261116-live-01/layout-checks.json","{\"passed\":true,\"checks\":"+checks+",\"physical_vr_controller_tested\":false}");
        Debug.Log("TUTOR_PANEL_LAYOUT_CHECKS_PASSED "+checks);
    }
}
