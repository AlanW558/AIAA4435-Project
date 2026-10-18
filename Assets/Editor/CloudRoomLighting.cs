using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using IAI.Environment;
using Object = UnityEngine.Object;

[InitializeOnLoad]
public static class CloudRoomLighting
{
    const string Root = "Assets/Project/";
    static double started;
    static CloudRoomLighting()
    {
        Lightmapping.bakeCompleted -= Completed;
        Lightmapping.bakeCompleted += Completed;
    }

    [MenuItem("AIAA4435/Room/Lighting/Prepare Mobile Baked Lighting")]
    public static void Prepare()
    {
        if (Lightmapping.isRunning) throw new InvalidOperationException("Wait for the current bake.");
        if (EditorSceneManager.GetActiveScene().path != CloudRoomBuilder.ScenePath)
            throw new InvalidOperationException("Open CloudConversationRoom first.");
        Lightmapping.Clear();
        Lightmapping.ClearLightingDataAsset();
        foreach (var r in Object.FindObjectsOfType<MeshRenderer>())
        {
            var flags = GameObjectUtility.GetStaticEditorFlags(r.gameObject);
            if ((flags & StaticEditorFlags.ContributeGI) == 0) continue;
            bool large = r.name.EndsWith("Wall") || r.name.StartsWith("Ceiling —") || r.name.StartsWith("Roof Slab") || r.name == "Floor Slab";
            r.receiveGI = large ? ReceiveGI.Lightmaps : ReceiveGI.LightProbes;
            r.scaleInLightmap = large ? .65f : 0;
            r.stitchLightmapSeams = true;
            if (large) ReplaceArchitecturalMesh(r);
            bool furniture = r.name == "Rounded Oak Top" || r.name == "Tailored Linen Cushion" || r.name == "Curved Timber Back Shell" || r.name == "Curved Upholstered Back Pad" || r.name == "Rounded Seat Frame";
            if (furniture)
            {
                var filter = r.GetComponent<MeshFilter>();
                string meshName = filter.sharedMesh.name.StartsWith("Lighting_Furniture_") ? filter.sharedMesh.name : "Lighting_Furniture_" + filter.sharedMesh.name;
                string path = Root + "Models/Room/" + meshName + ".asset";
                var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(path);
                if (!mesh)
                {
                    mesh = Object.Instantiate(filter.sharedMesh);
                    mesh.name = Path.GetFileNameWithoutExtension(path);
                    UnwrapParam p; UnwrapParam.SetDefaults(out p); p.packMargin = .06f; p.hardAngle = 88;
                    Unwrapping.GenerateSecondaryUVSet(mesh,p);
                    AssetDatabase.CreateAsset(mesh,path);
                }
                filter.sharedMesh=mesh; r.receiveGI=ReceiveGI.Lightmaps; r.scaleInLightmap=4;
            }
        }
        foreach (var r in Object.FindObjectsOfType<MeshRenderer>().Where(r=>r.name.StartsWith("Notebook") || r.name=="Paper Block" || r.name=="Book Spine" || r.name.StartsWith("Pen ")))
        {
            GameObjectUtility.SetStaticEditorFlags(r.gameObject, StaticEditorFlags.ContributeGI | StaticEditorFlags.BatchingStatic | StaticEditorFlags.ReflectionProbeStatic);
            r.receiveGI=ReceiveGI.LightProbes; r.scaleInLightmap=0;
        }
        PrepareFloor();
        foreach (var l in Object.FindObjectsOfType<Light>())
        {
            l.lightmapBakeType = LightmapBakeType.Baked;
            if (l.type == LightType.Directional)
            {
                l.color = new Color(1f, .8784f, .6745f);
                l.intensity = 1.45f;
                l.shadowStrength = 1;
                l.bounceIntensity = 1;
            }
            else if (l.type == LightType.Area) l.intensity = 1.2f;
        }
        // Surround the two seated people as well as the small furniture pieces.
        var group = Object.FindObjectOfType<LightProbeGroup>();
        var points = new System.Collections.Generic.List<Vector3>();
        foreach (float x in new[] {-3f,-.9f,0,.9f,3f})
        foreach (float z in new[] {-3f,-1f,0,1f,3f})
        foreach (float y in new[] {.15f,.6f,1.2f,1.9f,3f}) points.Add(new Vector3(x,y,z));
        if (group) group.probePositions = points.ToArray();
        RenderSettings.ambientMode = AmbientMode.Skybox;
        RenderSettings.ambientIntensity = .65f;
        var ls = Lightmapping.lightingSettings;
        ls.autoGenerate = false; ls.bakedGI = true; ls.realtimeGI = false;
        ls.realtimeEnvironmentLighting = false;
        ls.lightmapper = LightingSettings.Lightmapper.ProgressiveCPU;
        ls.lightmapResolution = 16; ls.lightmapMaxSize = 1024; ls.lightmapPadding = 4;
        ls.directionalityMode = LightmapsMode.CombinedDirectional;
        ls.directSampleCount = 64; ls.indirectSampleCount = 256; ls.environmentSampleCount = 128;
        ls.lightProbeSampleCountMultiplier = 2; ls.maxBounces = 3; ls.minBounces = 2;
        ls.prioritizeView = false;
        ls.ao = true; ls.aoMaxDistance = .18f; ls.aoExponentIndirect = .6f;
        // This Intel Mac supports CPU Open Image Denoise, but not NVIDIA OptiX.
        // Denoise indirect illumination only, preserving direct shadow edges.
        ls.filteringMode = LightingSettings.FilterMode.Advanced;
        ls.denoiserTypeDirect = LightingSettings.DenoiserType.None;
        ls.denoiserTypeIndirect = LightingSettings.DenoiserType.OpenImage;
        ls.denoiserTypeAO = LightingSettings.DenoiserType.None;
        ls.filteringGaussianRadiusDirect = 1; ls.filteringGaussianRadiusIndirect = 2;
        ls.filteringGaussianRadiusAO = 1;
        ls.lightmapCompression = LightmapCompression.HighQuality;
        var pipeline=AssetDatabase.LoadAssetAtPath<UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset>(Root+"Settings/PicoURP.asset");
        if(pipeline)
        {
            var serialized=new SerializedObject(pipeline);
            serialized.FindProperty("m_MainLightShadowsSupported").boolValue=false;
            serialized.FindProperty("m_AdditionalLightShadowsSupported").boolValue=false;
            serialized.FindProperty("m_SoftShadowsSupported").boolValue=false;
            serialized.FindProperty("m_AdditionalLightsRenderingMode").intValue=0;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            pipeline.supportsCameraDepthTexture=false; pipeline.supportsCameraOpaqueTexture=false;
            pipeline.supportsHDR=false; pipeline.useSRPBatcher=true;
            EditorUtility.SetDirty(pipeline);
        }
        EditorUtility.SetDirty(ls);
        AssetDatabase.SaveAssets();
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene());
    }

    static void ReplaceArchitecturalMesh(MeshRenderer r)
    {
        string path = Root + "Models/Room/Lighting_" + r.name.Replace(' ', '_') + ".asset";
        var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if (!existing)
        {
            var old = r.GetComponent<MeshFilter>().sharedMesh;
            var temp = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var mesh = Object.Instantiate(temp.GetComponent<MeshFilter>().sharedMesh);
            Object.DestroyImmediate(temp);
            mesh.name = "Lighting_" + r.name;
            var vertices = mesh.vertices;
            for (int i=0; i<vertices.Length; i++) vertices[i] = Vector3.Scale(vertices[i], old.bounds.size) + old.bounds.center;
            mesh.vertices = vertices;
            mesh.RecalculateBounds();
            UnwrapParam p; UnwrapParam.SetDefaults(out p); p.packMargin = .04f;
            Unwrapping.GenerateSecondaryUVSet(mesh, p);
            AssetDatabase.CreateAsset(mesh,path); existing = mesh;
        }
        r.GetComponent<MeshFilter>().sharedMesh = existing;
    }

    static void PrepareFloor()
    {
        var floor = Object.FindObjectsOfType<MeshRenderer>().First(r=>r.name.StartsWith("Oak Floor —"));
        var binding = floor.GetComponent<FloorLightmapBinding>();
        if (!binding) binding = floor.gameObject.AddComponent<FloorLightmapBinding>();
        // Keep both meshes out of static batching: it can bake the proxy's atlas
        // transform into UV2, which would invalidate the shared lightmap binding.
        // They still use the SRP Batcher.
        GameObjectUtility.SetStaticEditorFlags(floor.gameObject, StaticEditorFlags.ReflectionProbeStatic);
        floor.receiveGI = ReceiveGI.Lightmaps;
        floor.scaleInLightmap = 0;
        if (!binding.bakeSurface)
        {
            var go = new GameObject("Continuous Floor Lighting Surface");
            go.transform.SetParent(floor.transform.parent, false);
            var mesh = new Mesh {name="ContinuousFloorLightmap"};
            float w=CloudRoomBuilder.RoomWidth/2, z=CloudRoomBuilder.RoomLength/2;
            mesh.vertices = new[] {new Vector3(-w,0,-z),new Vector3(-w,0,z),new Vector3(w,0,z),new Vector3(w,0,-z)};
            mesh.uv = new[] {Vector2.zero,Vector2.up,Vector2.one,Vector2.right};
            mesh.uv2 = new[] {new Vector2(.01f,.01f),new Vector2(.01f,.99f),new Vector2(.99f,.99f),new Vector2(.99f,.01f)};
            mesh.triangles = new[] {0,1,2,0,2,3}; mesh.RecalculateNormals(); mesh.RecalculateTangents(); mesh.RecalculateBounds();
            string path=Root+"Models/Room/ContinuousFloorLightmap.asset";
            var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (!old) AssetDatabase.CreateAsset(mesh,path); else {Object.DestroyImmediate(mesh);mesh=old;}
            go.AddComponent<MeshFilter>().sharedMesh=mesh;
            binding.bakeSurface=go.AddComponent<MeshRenderer>();
            binding.bakeSurface.sharedMaterial=floor.sharedMaterials[2];
        }
        GameObjectUtility.SetStaticEditorFlags(binding.bakeSurface.gameObject, StaticEditorFlags.ContributeGI);
        binding.bakeSurface.receiveGI=ReceiveGI.Lightmaps;
        binding.bakeSurface.scaleInLightmap=2.5f;
        binding.visibleFloor=floor; binding.baking=false; binding.Apply();
    }

    [MenuItem("AIAA4435/Room/Lighting/Bake Production Lighting")]
    public static void Bake() { StartBake(false); }
    [MenuItem("AIAA4435/Room/Lighting/Bake Diagnostic Lighting")]
    public static void DiagnosticBake() { StartBake(true); }

    static void StartBake(bool diagnostic)
    {
        if (Lightmapping.isRunning) throw new InvalidOperationException("Bake already running.");
        var ls=Lightmapping.lightingSettings;
        ls.lightmapResolution=diagnostic?8:16;
        ls.directSampleCount=diagnostic?16:64;
        ls.indirectSampleCount=diagnostic?32:256;
        ls.environmentSampleCount=diagnostic?16:128;
        foreach(var b in Object.FindObjectsOfType<FloorLightmapBinding>())
        {b.baking=true; b.visibleFloor.enabled=false; b.bakeSurface.shadowCastingMode=ShadowCastingMode.On;}
        EditorUtility.SetDirty(ls); AssetDatabase.SaveAssets();
        started=EditorApplication.timeSinceStartup;
        SessionState.SetBool("CloudRoomBakeRequested",true);
        SessionState.SetBool("CloudRoomBakeDiagnostic",diagnostic);
        SessionState.SetString("CloudRoomBakeStart",DateTime.UtcNow.ToString("o"));
        if (!Lightmapping.BakeAsync()) { SessionState.SetBool("CloudRoomBakeRequested",false); RestoreFloor(); throw new InvalidOperationException("Unity did not start baking."); }
    }

    [MenuItem("AIAA4435/Room/Lighting/Cancel Bake And Restore Floor")]
    public static void CancelBake()
    {
        SessionState.SetBool("CloudRoomBakeRequested",false);
        Lightmapping.Cancel(); RestoreFloor();
        Debug.Log("Room bake cancelled; visible floor restored. The previous report does not describe this cancelled attempt.");
    }

    static void RestoreFloor()
    {
        foreach(var b in Object.FindObjectsOfType<FloorLightmapBinding>()) {b.baking=false;b.Apply();EditorUtility.SetDirty(b);}
    }
    static void Completed()
    {
        if(!SessionState.GetBool("CloudRoomBakeRequested",false)) return;
        SessionState.SetBool("CloudRoomBakeRequested",false);
        RestoreFloor();
        // Recapture reflections with the detailed floor visible, after transferring its lighting.
        foreach(var probe in Object.FindObjectsOfType<ReflectionProbe>())
        {
            string path=AssetDatabase.GetAssetPath(probe.bakedTexture);
            if(probe.mode==ReflectionProbeMode.Baked && !string.IsNullOrEmpty(path)) Lightmapping.BakeReflectionProbe(probe,path);
        }
        AssetDatabase.SaveAssets();
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene());
        var result = new BakeReport { completedUtc=DateTime.UtcNow.ToString("o"), startedUtc=SessionState.GetString("CloudRoomBakeStart",""), diagnostic=SessionState.GetBool("CloudRoomBakeDiagnostic",true), seconds=EditorApplication.timeSinceStartup-started, maps=LightmapSettings.lightmaps.Length, lightingData=AssetDatabase.GetAssetPath(Lightmapping.lightingDataAsset), lightmaps=LightmapSettings.lightmaps.Select(x=>AssetDatabase.GetAssetPath(x.lightmapColor)).ToArray() };
        File.WriteAllText("RoomLightingBakeReport.json",JsonUtility.ToJson(result,true));
        Debug.Log("Cloud room bake completed: "+result.maps+" lightmaps, "+result.seconds.ToString("F1")+" seconds.");
    }
    [Serializable] class BakeReport {public string startedUtc,completedUtc,lightingData; public bool diagnostic;public double seconds;public int maps;public string[] lightmaps;}
}
