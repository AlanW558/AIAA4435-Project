using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using MCPForUnity.Editor.Services;

[InitializeOnLoad]
public static class IAIUnityMcpSetup
{
    static IAIUnityMcpSetup()
    {
        if (Application.isBatchMode) return;
        string runtimeBin = Path.GetFullPath(Path.Combine(Application.dataPath, "../../Tools/python-env/bin"));
        string currentPath = Environment.GetEnvironmentVariable("PATH") ?? "";
        if (Directory.Exists(runtimeBin) && !currentPath.StartsWith(runtimeBin + ":", StringComparison.Ordinal))
            Environment.SetEnvironmentVariable("PATH", runtimeBin + ":" + currentPath);
        // StdioBridgeHost starts itself. Do not start another bridge during reload.
        EditorApplication.delayCall += () =>
        {
            var uvx = Path.Combine(runtimeBin, "uvx");
            if (File.Exists(uvx)) EditorConfigurationCache.Instance.SetUvxPathOverride(uvx);
        };
    }
}
