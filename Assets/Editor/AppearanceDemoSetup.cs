using System;
using System.IO;
using IAI.Appearance;
using IAI.Interaction;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEngine;

// A fixed desktop camera for recording the shared VR room. Never included in the PICO APK.
public static class AppearanceDemoSetup
{
    const string Scene="Assets/Project/Scenes/AppearanceDesktopDemo.unity";
    [MenuItem("AIAA4435/Appearance/Build desktop room demo")]
    public static void BuildLinux()
    {
        AppearanceVRSetup.CreateScene();
        var scene=EditorSceneManager.GetActiveScene();EditorSceneManager.SaveScene(scene,Scene);
        var seat=UnityEngine.Object.FindObjectOfType<ConversationSeat>();
        var anchor=seat.seatAnchor;
        Vector3 cameraPosition=anchor.TransformPoint(new Vector3(0,1.35f,-.5f));
        Vector3 lookAt=anchor.TransformPoint(new Vector3(.05f,1.25f,1.8f));
        foreach(var start in UnityEngine.Object.FindObjectsOfType<AppearanceVRStart>())UnityEngine.Object.DestroyImmediate(start);
        foreach(var origin in UnityEngine.Object.FindObjectsOfType<XROrigin>())UnityEngine.Object.DestroyImmediate(origin.gameObject);
        UnityEngine.Object.DestroyImmediate(seat);
        var camera=new GameObject("Desktop demo camera").AddComponent<Camera>();camera.tag="MainCamera";
        camera.transform.position=cameraPosition;camera.transform.LookAt(lookAt);camera.fieldOfView=58;
        camera.nearClipPlane=.05f;camera.farClipPlane=100;camera.gameObject.AddComponent<AudioListener>();
        var panel=UnityEngine.Object.FindObjectOfType<AppearanceXRPanel>();panel.seat=null;
        panel.transform.rotation=Quaternion.LookRotation(panel.transform.position-cameraPosition,Vector3.up);
        EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
        string product=PlayerSettings.productName;int width=PlayerSettings.defaultScreenWidth,height=PlayerSettings.defaultScreenHeight;
        var mode=PlayerSettings.fullScreenMode;var scripting=PlayerSettings.GetScriptingBackend(BuildTargetGroup.Standalone);
        var xr=XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Standalone);
        bool xrStarted=xr&&xr.InitManagerOnStart;
        try
        {
            PlayerSettings.productName="Appearance Desktop Demo";
            PlayerSettings.defaultScreenWidth=1920;PlayerSettings.defaultScreenHeight=1080;
            PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone,ScriptingImplementation.Mono2x);
            if(xr)xr.InitManagerOnStart=false;
            Directory.CreateDirectory("Builds/AppearanceDemo");
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{Scene},locationPathName="Builds/AppearanceDemo/AppearanceDemo.x86_64",target=BuildTarget.StandaloneLinux64,options=BuildOptions.None});
            var s=report.summary;
            File.WriteAllText("Builds/AppearanceDemo/build-report.txt",$"{DateTime.UtcNow:o}\n{s.result}\nErrors: {s.totalErrors}\nWarnings: {s.totalWarnings}\n");
            if(s.result!=BuildResult.Succeeded)throw new InvalidOperationException("Desktop room demo build failed.");
        }
        finally
        {
            PlayerSettings.productName=product;PlayerSettings.defaultScreenWidth=width;PlayerSettings.defaultScreenHeight=height;
            PlayerSettings.fullScreenMode=mode;PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone,scripting);
            if(xr)xr.InitManagerOnStart=xrStarted;
            AssetDatabase.SaveAssets();
        }
    }
}
