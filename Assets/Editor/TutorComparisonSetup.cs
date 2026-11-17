using System;
using System.IO;
using IAI.Tutor;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class TutorComparisonSetup
{
    public const string DesktopScene = "Assets/Project/Scenes/TutorComparisonDesktop.unity";
    public const string VRScene = "Assets/Project/Scenes/TutorComparisonVR.unity";

    public const string FreeDesktopScene = "Assets/Project/Scenes/TutorFreeTestDesktop.unity";
    public const string FreeVRScene = "Assets/Project/Scenes/TutorFreeTestVR.unity";
    [MenuItem("AIAA4435/Tutor/Free Testing/Create Scenes")]
    public static void CreateFreeScenes()
    {
        if(EditorApplication.isPlayingOrWillChangePlaymode || EditorSceneManager.GetActiveScene().isDirty)
            throw new InvalidOperationException("Save current edits and stop Play mode first.");
        var original=EditorSceneManager.GetActiveScene().path;
        foreach(var pair in new[]{new[]{DesktopScene,FreeDesktopScene},new[]{VRScene,FreeVRScene}})
        {
            if(File.Exists(pair[1]))continue;
            var scene=EditorSceneManager.OpenScene(pair[0]);
            EditorSceneManager.SaveScene(scene,pair[1]);
            var p=UnityEngine.Object.FindObjectOfType<TutorPanel>();p.freeTesting=true;p.durableStudy=false;
            p.comparison.studyManaged=false;p.comparison.connectOnStart=false;
            EditorSceneManager.MarkSceneDirty(scene);EditorSceneManager.SaveScene(scene);
        }
        if(!string.IsNullOrEmpty(original))EditorSceneManager.OpenScene(original);
    }
    [MenuItem("AIAA4435/Tutor/Free Testing/Open Desktop")]
    public static void OpenFreeDesktop(){EditorSceneManager.OpenScene(FreeDesktopScene);}
    [MenuItem("AIAA4435/Tutor/Free Testing/Open VR")]
    public static void OpenFreeVR(){EditorSceneManager.OpenScene(FreeVRScene);}

    [MenuItem("AIAA4435/Tutor/Comparison/Run Study Materials Checks (Play mode)")]
    public static void RunStudyMaterialsChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        if (!EditorApplication.isPlaying || !client || client.Connected || client.Busy || client.GetComponent<TutorStudyMaterialsChecks>())
            throw new InvalidOperationException("Use a fresh disconnected comparison in Play mode.");
        client.gameObject.AddComponent<TutorStudyMaterialsChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Use 32-task Study Preview (Play mode)")]
    public static void UseStudyPreview() { SelectMaterials(true); }
    [MenuItem("AIAA4435/Tutor/Comparison/Use 8-task Practice (Play mode)")]
    public static void UsePractice() { SelectMaterials(false); }
    static void SelectMaterials(bool study)
    {
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !panel) throw new InvalidOperationException("Use a disconnected comparison in Play mode.");
        panel.LoadStudyPreview(study);
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Create Scenes")]
    public static void CreateScenes()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || EditorSceneManager.GetActiveScene().isDirty)
            throw new InvalidOperationException("Save current edits and stop Play mode before creating comparison scenes.");
        Create(TutorPanelSetup.DesktopScene, DesktopScene);
        Create(TutorPanelSetup.VRScene, VRScene);
        EditorSceneManager.OpenScene(DesktopScene);
        AssetDatabase.SaveAssets();
        Debug.Log("TUTOR_COMPARISON_SCENES_READY");
    }
    static void Create(string source, string destination)
    {
        if (File.Exists(destination)) { Debug.Log("Keeping existing comparison scene: " + destination); return; }
        var scene = EditorSceneManager.OpenScene(source);
        EditorSceneManager.SaveScene(scene, destination);
        var single = UnityEngine.Object.FindObjectOfType<TutorClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!single || !panel) throw new InvalidOperationException("Source must be a tutor integration scene.");
        var comparison = single.gameObject.AddComponent<TutorComparisonClient>();
        comparison.avatar = single.avatar; comparison.endpoint = single.endpoint;
        // No automatic API use when opening Play mode; Connect is explicit.
        comparison.connectOnStart = false;
        panel.comparison = comparison; panel.client = null;
        UnityEngine.Object.DestroyImmediate(single);
        EditorSceneManager.MarkSceneDirty(scene); EditorSceneManager.SaveScene(scene);
    }
    [MenuItem("AIAA4435/Tutor/Comparison/Open Desktop")]
    public static void OpenDesktop() { EditorSceneManager.OpenScene(DesktopScene); }
    [MenuItem("AIAA4435/Tutor/Comparison/Open VR")]
    public static void OpenVR() { EditorSceneManager.OpenScene(VRScene); }
    [MenuItem("AIAA4435/Tutor/Comparison/Run Local Checks (Play mode)")]
    public static void RunChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput || client.Connected || client.Busy)
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        if (client.GetComponent<TutorComparisonChecks>()) throw new InvalidOperationException("Checks already running.");
        client.endpoint = "http://127.0.0.1:8768";
        client.gameObject.AddComponent<TutorComparisonChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Controls Checks (Play mode)")]
    public static void RunControlsChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput || client.Connected || client.Busy || client.GetComponent<TutorControlsChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.endpoint = "http://127.0.0.1:8771";
        client.gameObject.AddComponent<TutorControlsChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Preparation Checks (Play mode)")]
    public static void RunPreparationChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || client.Connected || client.Busy || client.GetComponent<TutorPreparationChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.gameObject.AddComponent<TutorPreparationChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Preference Checks (Play mode)")]
    public static void RunPreferenceChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        if (!EditorApplication.isPlaying || !client || client.Connected || client.Busy || client.GetComponent<TutorPreferenceChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.gameObject.AddComponent<TutorPreferenceChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Questionnaire Checks (Play mode)")]
    public static void RunQuestionnaireChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        if (!EditorApplication.isPlaying || !client || client.Connected || client.Busy || client.GetComponent<TutorQuestionnaireChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.gameObject.AddComponent<TutorQuestionnaireChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Navigation Checks (Play mode)")]
    public static void RunNavigationChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        if (!EditorApplication.isPlaying || !client || client.Connected || client.Busy || client.GetComponent<TutorNavigationChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.gameObject.AddComponent<TutorNavigationChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Comparison/Run Fault Acceptance (Play mode)")]
    public static void RunFaultAcceptance() { RunAcceptance(false); }
    [MenuItem("AIAA4435/Tutor/Comparison/Run Appearance Checks (Play mode)")]
    public static void RunAppearanceChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput || client.Connected || client.Busy || client.GetComponent<TutorAppearanceComparisonChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.endpoint = "http://127.0.0.1:8770";
        client.gameObject.AddComponent<TutorAppearanceComparisonChecks>();
    }
    [MenuItem("AIAA4435/Tutor/Comparison/Run Live Acceptance (Play mode)")]
    public static void RunLiveAcceptance() { RunAcceptance(true); }
    static void RunAcceptance(bool live)
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorComparisonClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput || client.Connected || client.Busy || client.GetComponent<TutorComparisonAcceptanceChecks>())
            throw new InvalidOperationException("Use a fresh disconnected desktop comparison in Play mode.");
        client.endpoint = "http://127.0.0.1:8769";
        client.gameObject.AddComponent<TutorComparisonAcceptanceChecks>().live = live;
    }
}
