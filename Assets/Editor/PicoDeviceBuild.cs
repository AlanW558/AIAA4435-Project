using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class PicoDeviceBuild
{
    const string Scene = "Assets/Project/Scenes/CloudConversationRoom.unity";
    const string Output = "Builds/Pico/AIAA4435Project.apk";
    const string Status = "Builds/Pico/BuildStatus.json";

    [Serializable]
    sealed class Result
    {
        public string state, startedUtc, finishedUtc, apk, result;
        public ulong bytes;
        public double seconds;
        public int errors, warnings;
        public string[] messages;
    }

    [MenuItem("AIAA4435/Build/Build Pico APK")]
    public static void QueueBuild()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer)
            throw new InvalidOperationException("Stop Play mode and wait for any existing build first.");
        ProjectFoundationSetup.Validate();
        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            throw new InvalidOperationException("Switch the active platform to Android first.");
        if (EditorSceneManager.GetActiveScene().path != Scene)
            throw new InvalidOperationException("Open CloudConversationRoom before building.");
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene());
        AssetDatabase.SaveAssets();
        Directory.CreateDirectory("Builds/Pico");
        var result = new Result { state = "Queued", startedUtc = DateTime.UtcNow.ToString("o"), apk = Path.GetFullPath(Output) };
        File.WriteAllText(Status, JsonUtility.ToJson(result, true));
        EditorApplication.delayCall += () => Build(result);
    }

    static void Build(Result result)
    {
        result.state = "Building";
        File.WriteAllText(Status, JsonUtility.ToJson(result, true));
        try
        {
            // PICO's Unity 2022 Vulkan configuration uses a non-Development APK.
            EditorUserBuildSettings.buildAppBundle = false;
            EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
            EditorUserBuildSettings.development = false;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { Scene },
                locationPathName = Output,
                target = BuildTarget.Android,
                options = BuildOptions.None
            });
            var summary = report.summary;
            result.result = summary.result.ToString();
            result.state = summary.result == BuildResult.Succeeded ? "Succeeded" : "Failed";
            result.bytes = summary.totalSize;
            result.seconds = summary.totalTime.TotalSeconds;
            result.errors = (int)summary.totalErrors;
            result.warnings = (int)summary.totalWarnings;
            result.messages = report.steps.SelectMany(s => s.messages)
                .Where(m => m.type == LogType.Error || m.type == LogType.Exception || m.type == LogType.Warning)
                .Select(m => m.content).Distinct().ToArray();
        }
        catch (Exception error)
        {
            result.state = "Failed";
            result.result = "Exception";
            result.messages = new[] { error.ToString() };
            Debug.LogException(error);
        }
        finally
        {
            result.finishedUtc = DateTime.UtcNow.ToString("o");
            File.WriteAllText(Status, JsonUtility.ToJson(result, true));
        }
    }
}
