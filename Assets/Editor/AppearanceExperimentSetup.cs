using System;
using System.IO;
using IAI.Appearance;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class AppearanceExperimentSetup
{
    public const string ScenePath="Assets/Project/Scenes/AppearanceExperiment.unity";
    [MenuItem("AIAA4435/Appearance/Create desktop experiment scene")]
    public static void CreateScene()
    {
        if(!Application.isBatchMode&&!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())return;
        var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var room=new GameObject("Controlled appearance studio").transform;
        var floor=AppearanceAvatar.Material("Sandstone",new Color(.37f,.41f,.40f));
        var wall=AppearanceAvatar.Material("Deep teal",new Color(.10f,.19f,.21f));
        var wood=AppearanceAvatar.Material("Oak",new Color(.40f,.27f,.17f));
        var brass=AppearanceAvatar.Material("Soft brass",new Color(.66f,.52f,.32f));
        var Shape=new Action<string,PrimitiveType,Vector3,Vector3,Material>((n,k,p,s,m)=>AppearanceAvatar.Shape(n,k,room,p,s,m));
        Shape("Floor",PrimitiveType.Cube,new Vector3(0,-.10f,0),new Vector3(12,.2f,12),floor);
        Shape("Back wall",PrimitiveType.Cube,new Vector3(0,3,2.3f),new Vector3(12,6,.2f),wall);
        for(int i=0;i<13;i++)Shape("Wall slat",PrimitiveType.Cube,new Vector3(-3+i*.5f,2,2.12f),new Vector3(.035f,4,.07f),brass);
        Shape("Display plinth",PrimitiveType.Cylinder,new Vector3(0,.05f,0),new Vector3(1.7f,.05f,1.7f),wood);
        Shape("Plinth rim",PrimitiveType.Cylinder,new Vector3(0,.007f,0),new Vector3(1.76f,.012f,1.76f),brass);
        for(int i=0;i<2;i++)
        {
            float x=i==0?-2:2;
            Shape("Plant pot",PrimitiveType.Cylinder,new Vector3(x,.35f,.9f),new Vector3(.55f,.35f,.55f),wood);
            var leaf=AppearanceAvatar.Material("Foliage",new Color(.12f,.27f,.20f));
            Shape("Plant",PrimitiveType.Capsule,new Vector3(x,1.15f,.9f),new Vector3(.65f,.55f,.60f),leaf);
        }
        var avatar=new GameObject("Companion").AddComponent<AppearanceAvatar>();
        avatar.transform.position=new Vector3(0,.1f,0);
        // Avatar is generated at runtime, keeping the editable scene and build deterministic.
        var client=new GameObject("Appearance experiment").AddComponent<AppearanceExperimentClient>();client.avatar=null;
        UnityEngine.Object.DestroyImmediate(avatar.gameObject);
        var camera=new GameObject("Appearance camera").AddComponent<Camera>();camera.tag="MainCamera";
        camera.transform.position=new Vector3(2.5f,2.05f,-5.5f);camera.transform.LookAt(new Vector3(0,1.10f,0));
        camera.fieldOfView=31;camera.rect=new Rect(.38f,0,.62f,1);camera.backgroundColor=new Color(.10f,.19f,.21f);
        camera.gameObject.AddComponent<AudioListener>();
        var key=new GameObject("Large soft key").AddComponent<Light>();key.type=LightType.Directional;key.intensity=1.25f;key.color=new Color(1,.94f,.84f);key.shadows=LightShadows.Soft;key.transform.rotation=Quaternion.Euler(35,-25,0);
        var fill=new GameObject("Cool fill").AddComponent<Light>();fill.type=LightType.Directional;fill.intensity=.55f;fill.color=new Color(.64f,.82f,1);fill.transform.rotation=Quaternion.Euler(25,145,0);
        RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.52f,.59f,.61f);RenderSettings.fog=false;
        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
        Debug.Log("Appearance scene saved: "+ScenePath);
    }

    [MenuItem("AIAA4435/Appearance/Build Linux desktop experiment")]
    public static void BuildLinux()
    {
        CreateScene();
        Directory.CreateDirectory("Builds/AppearanceLinux");
        var oldWidth=PlayerSettings.defaultScreenWidth;var oldHeight=PlayerSettings.defaultScreenHeight;
        var oldMode=PlayerSettings.fullScreenMode;
        var oldBackend=PlayerSettings.GetScriptingBackend(BuildTargetGroup.Standalone);
        try
        {
            PlayerSettings.defaultScreenWidth=1440;PlayerSettings.defaultScreenHeight=900;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone,ScriptingImplementation.Mono2x);
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName="Builds/AppearanceLinux/AppearanceLab.x86_64",target=BuildTarget.StandaloneLinux64,options=BuildOptions.Development});
            File.WriteAllText("Builds/AppearanceLinux/build-result.json","{\"result\":\""+report.summary.result+"\",\"errors\":"+report.summary.totalErrors+",\"warnings\":"+report.summary.totalWarnings+"}");
            if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Appearance Linux build failed: "+report.summary.result);
        }
        finally
        {
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Standalone,oldBackend);
            PlayerSettings.defaultScreenWidth=oldWidth;PlayerSettings.defaultScreenHeight=oldHeight;PlayerSettings.fullScreenMode=oldMode;
            AssetDatabase.SaveAssets();
        }
    }
}
