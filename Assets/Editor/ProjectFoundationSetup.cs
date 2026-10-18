using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.XR.Management;
using Unity.XR.PXR;

// Explicit setup command: does not rebuild or replace any scene.
public static class ProjectFoundationSetup
{
    private const string Root = "Assets/Project/Settings";

    [MenuItem("AIAA4435/Configure Project Foundation")]
    public static void Configure()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            throw new InvalidOperationException("Stop Play mode before configuring the project.");
        Directory.CreateDirectory(Root);
        AssetDatabase.Refresh();

        var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(Root + "/PicoRenderer.asset");
        if (renderer == null)
        {
            renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
            AssetDatabase.CreateAsset(renderer, Root + "/PicoRenderer.asset");
        }
        renderer.renderingMode = RenderingMode.Forward;
        renderer.depthPrimingMode = DepthPrimingMode.Disabled;
        ResourceReloader.ReloadAllNullIn(renderer, UniversalRenderPipelineAsset.packagePath);
        var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(Root + "/PicoURP.asset");
        if (pipeline == null)
        {
            pipeline = UniversalRenderPipelineAsset.Create(renderer);
            AssetDatabase.CreateAsset(pipeline, Root + "/PicoURP.asset");
        }
        pipeline.supportsHDR = false;
        pipeline.msaaSampleCount = 4;
        pipeline.renderScale = 1f;
        pipeline.supportsCameraDepthTexture = false;
        pipeline.supportsCameraOpaqueTexture = false;
        var pipelineSerialized = new SerializedObject(pipeline);
        pipelineSerialized.FindProperty("m_MainLightShadowsSupported").boolValue = true;
        pipelineSerialized.FindProperty("m_MainLightShadowmapResolution").intValue = 1024;
        pipelineSerialized.FindProperty("m_AdditionalLightsRenderingMode").intValue = (int)LightRenderingMode.PerVertex;
        pipelineSerialized.ApplyModifiedPropertiesWithoutUndo();
        pipeline.shadowDistance = 15f;
        pipeline.shadowCascadeCount = 1;
        GraphicsSettings.defaultRenderPipeline = pipeline;
        int originalQuality = QualitySettings.GetQualityLevel();
        for (int i = 0; i < QualitySettings.names.Length; i++)
        {
            QualitySettings.SetQualityLevel(i, false);
            QualitySettings.renderPipeline = pipeline;
        }
        QualitySettings.SetQualityLevel(originalQuality, false);
        PlayerSettings.colorSpace = ColorSpace.Linear;

        XRGeneralSettingsPerBuildTarget perTarget;
        if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out perTarget))
        {
            perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
            AssetDatabase.CreateAsset(perTarget, Root + "/XRGeneralSettings.asset");
            EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
        }
        var general = perTarget.SettingsForBuildTarget(BuildTargetGroup.Android);
        if (general == null)
        {
            perTarget.CreateDefaultSettingsForBuildTarget(BuildTargetGroup.Android);
            general = perTarget.SettingsForBuildTarget(BuildTargetGroup.Android);
        }
        if (general.Manager == null)
        {
            general.Manager = ScriptableObject.CreateInstance<XRManagerSettings>();
            general.Manager.name = "Android XR Manager";
            AssetDatabase.AddObjectToAsset(general.Manager, perTarget);
        }
        general.InitManagerOnStart = true;
        general.Manager.automaticLoading = true;
        general.Manager.automaticRunning = true;
        if (!XRPackageMetadataStore.AssignLoader(general.Manager, "Unity.XR.PXR.PXR_Loader", BuildTargetGroup.Android))
            throw new InvalidOperationException("PICO loader assignment failed.");

        PXR_Settings pico;
        if (!EditorBuildSettings.TryGetConfigObject("Unity.XR.PXR.Settings", out pico))
        {
            pico = ScriptableObject.CreateInstance<PXR_Settings>();
            AssetDatabase.CreateAsset(pico, Root + "/PicoSettings.asset");
            EditorBuildSettings.AddConfigObject("Unity.XR.PXR.Settings", pico, true);
        }
        pico.stereoRenderingModeAndroid = PXR_Settings.StereoRenderingModeAndroid.Multiview;
        pico.systemDisplayFrequency = PXR_Settings.SystemDisplayFrequency.RefreshRate90;
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevelAuto;
        PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.iai.aiaa4435.project");
        // PICO SDK 3.4 validation disallows Vulkan Development Builds on Unity 2022.
        EditorUserBuildSettings.development = false;
        var player = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);
        player.FindProperty("activeInputHandler").intValue = 1;
        player.ApplyModifiedPropertiesWithoutUndo();

        foreach (var obj in new UnityEngine.Object[] {renderer, pipeline, perTarget, general, general.Manager, pico})
            EditorUtility.SetDirty(obj);
        AssetDatabase.SaveAssets();
        Debug.Log("[AIAA4435] Foundation configured. Restart the Editor to activate the Input System backend.");
    }

    [MenuItem("AIAA4435/Validate Project Foundation")]
    public static void Validate()
    {
        var pipeline = GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
        var xr = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Android);
        if (pipeline == null || pipeline.supportsHDR || pipeline.msaaSampleCount != 4)
            throw new InvalidOperationException("URP configuration is incomplete.");
        if (xr == null || xr.Manager == null || !xr.Manager.activeLoaders.Any(l => l is PXR_Loader))
            throw new InvalidOperationException("Android PICO loader is missing.");
        if (PlayerSettings.GetScriptingBackend(BuildTargetGroup.Android) != ScriptingImplementation.IL2CPP ||
            PlayerSettings.Android.targetArchitectures != AndroidArchitecture.ARM64)
            throw new InvalidOperationException("Android IL2CPP / ARM64 configuration is incomplete.");
        PXR_Settings pico;
        if (!EditorBuildSettings.TryGetConfigObject("Unity.XR.PXR.Settings", out pico) ||
            pico.stereoRenderingModeAndroid != PXR_Settings.StereoRenderingModeAndroid.Multiview ||
            pico.systemDisplayFrequency != PXR_Settings.SystemDisplayFrequency.RefreshRate90)
            throw new InvalidOperationException("PICO Multiview / 90 Hz configuration is incomplete.");
        if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android))
            throw new InvalidOperationException("Android Build Support is unavailable.");
        var player = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);
        if (player.FindProperty("activeInputHandler").intValue != 1 ||
            PlayerSettings.GetGraphicsAPIs(BuildTarget.Android)[0] != GraphicsDeviceType.Vulkan)
            throw new InvalidOperationException("Input System / Vulkan configuration is incomplete.");
        Debug.Log("[AIAA4435] Foundation validation passed (configuration only; device performance remains untested).");
    }
}
