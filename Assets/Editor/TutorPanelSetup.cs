using System;
using System.IO;
using IAI.Appearance;
using IAI.Interaction;
using IAI.Tutor;
using IAI.UI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class TutorPanelSetup
{
    public const string DesktopScene = "Assets/Project/Scenes/TutorPersonalizationDesktop.unity";
    public const string VRScene = "Assets/Project/Scenes/TutorPersonalizationVR.unity";

    [MenuItem("AIAA4435/Tutor/Create Integration Scenes")]
    public static void CreateScenes()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Stop Play mode first.");
        if (EditorSceneManager.GetActiveScene().isDirty) throw new InvalidOperationException("Save current scene edits before creating integration scenes.");
        Create("Assets/Project/Scenes/AppearanceDesktopDemo.unity", DesktopScene, true);
        Create("Assets/Project/Scenes/AppearanceVR.unity", VRScene, false);
        EditorSceneManager.OpenScene(DesktopScene);
        AssetDatabase.SaveAssets();
        Debug.Log("TUTOR_SCENES_READY: original room and appearance scenes were preserved.");
    }

    static void Create(string source, string destination, bool desktop)
    {
        if (File.Exists(destination)) { Debug.Log("Keeping existing tutor integration scene: " + destination); return; }
        var scene = EditorSceneManager.OpenScene(source);
        EditorSceneManager.SaveScene(scene, destination);
        var oldClient = UnityEngine.Object.FindObjectOfType<AppearanceExperimentClient>();
        var oldPanel = UnityEngine.Object.FindObjectOfType<AppearanceXRPanel>();
        if (!oldClient || !oldPanel || !oldClient.avatar) throw new InvalidOperationException("Appearance scene needs the shared avatar and panel anchors.");
        var avatar = oldClient.avatar;
        var position = oldPanel.transform.position;
        var rotation = oldPanel.transform.rotation;
        UnityEngine.Object.DestroyImmediate(oldPanel.gameObject);
        foreach (var bridge in UnityEngine.Object.FindObjectsOfType<AppearanceDeviceBridge>(true)) UnityEngine.Object.DestroyImmediate(bridge);
        foreach (var preview in UnityEngine.Object.FindObjectsOfType<SettingsPanelDemo>(true)) UnityEngine.Object.DestroyImmediate(preview.gameObject);
        UnityEngine.Object.DestroyImmediate(oldClient);
        var root = new GameObject("Tutor personalization client");
        var client = root.AddComponent<TutorClient>(); client.avatar = avatar;
        var panelRoot = new GameObject("Adaptive Conversational Agent — warm glass");
        panelRoot.transform.SetParent(root.transform, false); panelRoot.transform.SetPositionAndRotation(position, rotation);
        var panel = panelRoot.AddComponent<TutorPanel>();
        panel.client = client; panel.desktopDebugInput = desktop;
        panel.seat = desktop ? null : UnityEngine.Object.FindObjectOfType<ConversationSeat>();
        panel.font = AssetDatabase.LoadAssetAtPath<Font>("Assets/Project/Fonts/NotoSansCJKsc-Regular.otf");
        panel.rounded = AssetDatabase.LoadAssetAtPath<Sprite>("Assets/Project/Materials/Interaction/HintRounded.png");
        panel.glassMaterial = AssetDatabase.LoadAssetAtPath<Material>("Assets/Project/Materials/Interaction/SettingsPanelGlass.mat");
        EditorSceneManager.MarkSceneDirty(scene); EditorSceneManager.SaveScene(scene);
    }

    [MenuItem("AIAA4435/Tutor/Open Desktop Integration")]
    public static void OpenDesktop() { EditorSceneManager.OpenScene(DesktopScene); }
    [MenuItem("AIAA4435/Tutor/Open VR Integration")]
    public static void OpenVR() { EditorSceneManager.OpenScene(VRScene); }

    [MenuItem("AIAA4435/Tutor/Run Local Fixture Checks (Play mode)")]
    public static void RunFixtureChecks()
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput)
            throw new InvalidOperationException("Enter Play mode in the desktop integration scene first.");
        if (client.Connected || client.Busy || client.GetComponent<TutorIntegrationChecks>())
            throw new InvalidOperationException("Use a fresh disconnected session and wait for any connection attempt to finish.");
        client.endpoint = "http://127.0.0.1:8766"; client.condition = "S";
        client.Connect(); client.gameObject.AddComponent<TutorIntegrationChecks>();
    }

    [MenuItem("AIAA4435/Tutor/Run Fault Acceptance (Play mode)")]
    public static void RunFaultAcceptance() { RunAcceptance(false); }
    [MenuItem("AIAA4435/Tutor/Run Live Acceptance (Play mode)")]
    public static void RunLiveAcceptance() { RunAcceptance(true); }
    static void RunAcceptance(bool live)
    {
        var client = UnityEngine.Object.FindObjectOfType<TutorClient>();
        var panel = UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if (!EditorApplication.isPlaying || !client || !panel || !panel.desktopDebugInput)
            throw new InvalidOperationException("Enter Play mode in the desktop integration scene first.");
        if (client.Connected || client.Busy || client.GetComponent<TutorAcceptanceChecks>())
            throw new InvalidOperationException("Use a fresh disconnected session and wait for any connection attempt to finish.");
        client.endpoint = "http://127.0.0.1:8767"; client.condition = "S";
        client.Connect(); client.gameObject.AddComponent<TutorAcceptanceChecks>().live = live;
    }
}
