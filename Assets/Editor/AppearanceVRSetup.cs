using System;
using System.IO;
using System.Linq;
using IAI.Appearance;
using IAI.Interaction;
using IAI.UI;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class AppearanceVRSetup
{
    const string Source="Assets/Project/Scenes/CloudConversationRoom.unity";
    const string Scene="Assets/Project/Scenes/AppearanceVR.unity";
    const string Output="Builds/Pico/AppearanceVR.apk";
    [Serializable] sealed class Result
    {
        public string result,apk,package,startedUtc,finishedUtc;
        public ulong bytes;
        public double seconds;
        public int errors,warnings;
        public string[] messages;
    }

    [MenuItem("AIAA4435/Appearance/Create VR Scene")]
    public static void CreateScene()
    {
        if(EditorApplication.isPlayingOrWillChangePlaymode)throw new InvalidOperationException("Stop play mode first.");
        var scene=EditorSceneManager.OpenScene(Source);
        // Save the clone before changing it; the authored room remains the source of future builds.
        EditorSceneManager.SaveScene(scene,Scene);
        foreach(var old in UnityEngine.Object.FindObjectsOfType<SettingsPanelDemo>())UnityEngine.Object.DestroyImmediate(old.gameObject);
        foreach(var hint in UnityEngine.Object.FindObjectsOfType<SeatInteractionHint>())hint.gameObject.SetActive(false);
        var tutorChair=GameObject.Find("Tutor Chair");if(tutorChair)UnityEngine.Object.DestroyImmediate(tutorChair);
        var seat=UnityEngine.Object.FindObjectOfType<ConversationSeat>();
        if(!seat)throw new InvalidOperationException("The cloud room is missing its seating rig.");
        var font=AssetDatabase.LoadAssetAtPath<Font>("Assets/Project/Fonts/NotoSansCJKsc-Regular.otf");
        if(!font)throw new InvalidOperationException("Bundled CJK font has not imported.");
        var root=new GameObject("12 Appearance interaction");
        var client=root.AddComponent<AppearanceExperimentClient>();client.worldSpaceUI=true;client.participantFont=font;
        var avatarRoot=new GameObject("Shared expressive character");avatarRoot.transform.SetParent(root.transform,false);
        avatarRoot.transform.position=seat.seatAnchor.TransformPoint(new Vector3(-.45f,0,2.05f));
        avatarRoot.transform.rotation=seat.seatAnchor.rotation;
        client.avatar=avatarRoot.AddComponent<AppearanceAvatar>();
        var panelRoot=new GameObject("Appearance conversation panel");panelRoot.transform.SetParent(root.transform,false);
        panelRoot.transform.position=seat.seatAnchor.TransformPoint(new Vector3(.69f,1.25f,1.06f));
        Vector3 eye=seat.seatAnchor.position+Vector3.up*seat.seatedEyeHeight;
        panelRoot.transform.rotation=Quaternion.LookRotation(panelRoot.transform.position-eye,Vector3.up);
        var panel=panelRoot.AddComponent<AppearanceXRPanel>();panel.client=client;panel.seat=seat;panel.font=font;
        panel.rounded=AssetDatabase.LoadAssetAtPath<Sprite>("Assets/Project/Materials/Interaction/HintRounded.png");
        root.AddComponent<AppearanceDeviceBridge>().client=client;
        root.AddComponent<AppearanceVRStart>().seat=seat;
        EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
        Debug.Log("APPEARANCE_VR_SCENE_READY "+Scene);
    }

    [MenuItem("AIAA4435/Appearance/Build PICO APK")]
    public static void BuildAndroid()
    {
        Directory.CreateDirectory("Builds/Pico");
        var result=new Result{startedUtc=DateTime.UtcNow.ToString("o"),apk=Path.GetFullPath(Output),package="com.iai.aiaa4435.appearance"};
        try
        {
            ProjectFoundationSetup.Validate();
            AppearanceVRChecks.Run();
            CreateScene();
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android,result.package);
            PlayerSettings.productName="Appearance Room";
            PlayerSettings.bundleVersion="0.3.0";PlayerSettings.Android.bundleVersionCode=30;
            PlayerSettings.Android.forceInternetPermission=true;
            PlayerSettings.insecureHttpOption=InsecureHttpOption.AlwaysAllowed;
            PlayerSettings.Android.targetSdkVersion=AndroidSdkVersions.AndroidApiLevel34;
            EditorUserBuildSettings.buildAppBundle=false;EditorUserBuildSettings.exportAsGoogleAndroidProject=false;EditorUserBuildSettings.development=false;
            AssetDatabase.SaveAssets();
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{Scene},locationPathName=Output,target=BuildTarget.Android,options=BuildOptions.None});
            var summary=report.summary;result.result=summary.result.ToString();result.bytes=summary.totalSize;
            result.seconds=summary.totalTime.TotalSeconds;result.errors=(int)summary.totalErrors;result.warnings=(int)summary.totalWarnings;
            result.messages=report.steps.SelectMany(s=>s.messages).Where(m=>m.type==LogType.Error||m.type==LogType.Exception||m.type==LogType.Warning).Select(m=>m.content).Distinct().ToArray();
            if(summary.result!=BuildResult.Succeeded)throw new InvalidOperationException("Appearance Android build failed.");
        }
        catch(Exception e){result.result="Failed";result.messages=(result.messages??Array.Empty<string>()).Concat(new[]{e.ToString()}).ToArray();throw;}
        finally{result.finishedUtc=DateTime.UtcNow.ToString("o");File.WriteAllText("Builds/Pico/AppearanceBuildStatus.json",JsonUtility.ToJson(result,true));}
    }
}
