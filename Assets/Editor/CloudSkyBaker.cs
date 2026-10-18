using System;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using Object=UnityEngine.Object;

public static class CloudSkyBaker
{
    const string CubePath="Assets/Project/Textures/Room/CloudSeaSky.asset";
    const string MaterialPath="Assets/Project/Materials/Room/CloudSeaSky.mat";
    public static void ApplyOrBake()
    {
        var m=AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
        if(m==null) Bake(); else RenderSettings.skybox=m;
        var clouds=GameObject.Find("06 Cloud Sea — exterior only");if(clouds!=null)clouds.gameObject.SetActive(false);
    }
    [MenuItem("AIAA4435/Room/Bake Cloud Sky")]
    public static void Bake()
    {
        var shader=Shader.Find("IAI/Cloud Sky Bake");var cubeShader=Shader.Find("Skybox/Cubemap");
        if(shader==null||cubeShader==null)throw new Exception("Required sky shader missing");
        var source=new Material(shader);var previous=RenderSettings.skybox;var go=new GameObject("Temporary Cloud Sky Baker");
        var cam=go.AddComponent<Camera>();cam.cullingMask=0;cam.clearFlags=CameraClearFlags.Skybox;cam.allowHDR=false;cam.nearClipPlane=.05f;cam.farClipPlane=2000;
        var cube=new Cubemap(1024,TextureFormat.RGBA32,true){name="CloudSeaSky",wrapMode=TextureWrapMode.Clamp,filterMode=FilterMode.Trilinear};
        try {
            RenderSettings.skybox=source;
            if(!cam.RenderToCubemap(cube))throw new Exception("Cloud sky render failed");
            cube.Apply(true,false);
            var old=AssetDatabase.LoadAssetAtPath<Cubemap>(CubePath);
            if(old==null)AssetDatabase.CreateAsset(cube,CubePath);else {EditorUtility.CopySerialized(cube,old);Object.DestroyImmediate(cube);cube=old;EditorUtility.SetDirty(cube);}
            var m=AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);if(m==null){m=new Material(cubeShader);AssetDatabase.CreateAsset(m,MaterialPath);}
            m.SetTexture("_Tex",cube);m.SetFloat("_Exposure",1);m.SetColor("_Tint",Color.gray);EditorUtility.SetDirty(m);RenderSettings.skybox=m;AssetDatabase.SaveAssets();
            EditorSceneManager.MarkSceneDirty(UnityEngine.SceneManagement.SceneManager.GetActiveScene());
        } catch {RenderSettings.skybox=previous;throw;}
        finally {Object.DestroyImmediate(go);Object.DestroyImmediate(source);}
    }
}
