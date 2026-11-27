using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using IAI.Tutor;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Builds the authored Tutor scenes without regenerating room/UI assets.</summary>
public static class TutorDeviceBuild
{
    public const string StudyPackage = "com.iai.aiaa4435.project";
    public const string FreePackage = "com.iai.aiaa4435.tutor.free";
    const string Endpoint = "http://127.0.0.1:8765";

    [Serializable] sealed class Result
    {
        public string state, kind, scene, package, apk, startedUtc, finishedUtc, sha256;
        public string unityVersion, endpoint, graphics, httpPolicy, dataCollection;
        public bool development, headsetTested;
        public int minSdk, targetSdk, errors, warnings;
        public ulong bytes;
        public double seconds;
        public string[] messages;
    }

    static void RequireIdle()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer)
            throw new InvalidOperationException("Stop Play mode and wait for the current build first.");
        for (int i = 0; i < SceneManager.sceneCount; i++)
            if (SceneManager.GetSceneAt(i).isDirty)
                throw new InvalidOperationException("Save the current scene changes before configuring/building Tutor.");
    }

    [MenuItem("AIAA4435/Tutor/Device/Configure Study USB Build")]
    public static void ConfigureStudyUsb() { Configure(true); }

    static void Configure(bool study)
    {
        RequireIdle();
        ProjectFoundationSetup.Validate();
        string scene = study ? TutorComparisonSetup.VRScene : TutorComparisonSetup.FreeVRScene;
        ValidateScene(scene, study);
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, study ? StudyPackage : FreePackage);
        PlayerSettings.productName = study ? "AIAA4435 Tutor Study" : "AIAA4435 Tutor Free";
        PlayerSettings.bundleVersion = "0.4.0";
        PlayerSettings.Android.bundleVersionCode = 40;
        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel34;
        PlayerSettings.Android.forceInternetPermission = true;
        // PICO SDK 3.4 forbids Unity 2022 Vulkan Development builds. This explicit
        // USB test profile therefore permits HTTP in its non-Development Player.
        PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
        EditorUserBuildSettings.connectProfiler = false;
        EditorUserBuildSettings.buildAppBundle = false;
        EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(scene, true) };
        AssetDatabase.SaveAssets();
        Debug.Log("TUTOR_USB_BUILD_CONFIGURED " + scene + " / " + Endpoint);
    }

    static void ValidateScene(string path, bool study)
    {
        if (!File.Exists(path)) throw new FileNotFoundException("Authored Tutor VR scene is missing.", path);
        var previous = EditorSceneManager.GetSceneManagerSetup();
        try
        {
            var scene = EditorSceneManager.OpenScene(path);
            var panels = scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<TutorPanel>(true)).ToArray();
            if (panels.Length != 1) throw new InvalidOperationException("Expected one Tutor panel in " + path);
            var panel = panels[0];
            if (!panel.comparison || panel.durableStudy != study || panel.freeTesting == study || panel.desktopDebugInput)
                throw new InvalidOperationException("Tutor VR scene mode does not match the requested build: " + path);
            if (panel.comparison.connectOnStart || panel.comparison.endpoint != Endpoint)
                throw new InvalidOperationException("USB build requires explicit connection to " + Endpoint);
            foreach (var resource in new[] { "Tutor/StudyTaskSequence", "Tutor/StudyQuestionnaires" })
                if (!Resources.Load<TextAsset>(resource))
                    throw new InvalidOperationException("Required study resource is missing: " + resource);
        }
        finally
        {
            // A fresh batch Editor can have no active saved scene to restore.
            if (previous.Any(s => s.isActive && !string.IsNullOrEmpty(s.path)))
                EditorSceneManager.RestoreSceneManagerSetup(previous);
        }
    }

    [MenuItem("AIAA4435/Tutor/Device/Build Both USB Test APKs")]
    public static void BuildBothUsb()
    {
        RequireIdle();
        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            throw new InvalidOperationException("Switch the active platform to Android first.");
        string output = Environment.GetEnvironmentVariable("TUTOR_BUILD_OUT");
        if (string.IsNullOrWhiteSpace(output)) output = "Builds/Tutor/usb-" + DateTime.Now.ToString("yyyyMMdd-HHmmss");
        output = Path.GetFullPath(output);
        if (Directory.Exists(output) && Directory.EnumerateFileSystemEntries(output).Any())
            throw new InvalidOperationException("Use a new output directory; existing build evidence will not be overwritten.");
        Directory.CreateDirectory(output);
        string originalArgs = PlayerSettings.GetAdditionalIl2CppArgs();
        if (!Regex.IsMatch(originalArgs ?? "", @"(^|\s)--jobs(?:=|\s)"))
            PlayerSettings.SetAdditionalIl2CppArgs(((originalArgs ?? "") + " --jobs=2").Trim());
        try { Build(false, output); Build(true, output); }
        finally
        {
            PlayerSettings.SetAdditionalIl2CppArgs(originalArgs);
            Configure(true);
        }
    }

    static void Build(bool study, string output)
    {
        Configure(study);
        var result = new Result
        {
            state = "Building", kind = study ? "study" : "free",
            scene = study ? TutorComparisonSetup.VRScene : TutorComparisonSetup.FreeVRScene,
            package = study ? StudyPackage : FreePackage,
            apk = Path.Combine(output, study ? "TutorStudyUSB.apk" : "TutorFreeUSB.apk"),
            startedUtc = DateTime.UtcNow.ToString("o"), unityVersion = Application.unityVersion,
            endpoint = Endpoint, graphics = "Vulkan", httpPolicy = "AlwaysAllowed (USB test profile)",
            development = false, headsetTested = false, minSdk = 29, targetSdk = 34,
            dataCollection = study ? "engineering" : "free_testing"
        };
        string status = Path.Combine(output, result.kind + "-build.json");
        File.WriteAllText(status, JsonUtility.ToJson(result, true));
        try
        {
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { result.scene }, locationPathName = result.apk,
                target = BuildTarget.Android, options = BuildOptions.None
            });
            result.state = report.summary.result.ToString();
            result.bytes = report.summary.totalSize;
            result.seconds = report.summary.totalTime.TotalSeconds;
            result.errors = (int)report.summary.totalErrors;
            result.warnings = (int)report.summary.totalWarnings;
            result.messages = report.steps.SelectMany(s => s.messages)
                .Where(m => m.type == LogType.Error || m.type == LogType.Exception || m.type == LogType.Warning)
                .Select(m => m.content).Distinct().ToArray();
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException("Tutor " + result.kind + " Android build failed; inspect " + status);
            using (var sha = SHA256.Create())
            using (var file = File.OpenRead(result.apk))
                result.sha256 = BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
        }
        catch (Exception error)
        {
            result.state = "Failed";
            result.messages = (result.messages ?? Array.Empty<string>()).Concat(new[] { error.Message }).ToArray();
            throw;
        }
        finally
        {
            result.finishedUtc = DateTime.UtcNow.ToString("o");
            File.WriteAllText(status, JsonUtility.ToJson(result, true));
        }
    }
}
