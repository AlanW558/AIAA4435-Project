#if UNITY_ANDROID
using System;
using System.IO;
using System.Linq;
using System.Xml;
using UnityEditor;
using UnityEditor.Android;

/// <summary>Explicit Android network policy for the two USB test build profiles.</summary>
public sealed class TutorUsbAndroidManifest : IPostGenerateGradleAndroidProject
{
    public int callbackOrder => int.MaxValue;
    public void OnPostGenerateGradleAndroidProject(string path)
    {
        string package = PlayerSettings.GetApplicationIdentifier(BuildTargetGroup.Android);
        var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        bool study = package == TutorDeviceBuild.StudyPackage && scenes.SequenceEqual(new[] { TutorComparisonSetup.VRScene });
        bool free = package == TutorDeviceBuild.FreePackage && scenes.SequenceEqual(new[] { TutorComparisonSetup.FreeVRScene });
        if (!study && !free) return;
        if (PlayerSettings.insecureHttpOption != InsecureHttpOption.AlwaysAllowed)
            throw new InvalidOperationException("Configure the Tutor USB build profile before generating its Android manifest.");
        const string android = "http://schemas.android.com/apk/res/android";
        string manifest = Path.Combine(path, "src/main/AndroidManifest.xml");
        var document = new XmlDocument(); document.Load(manifest);
        var application = document.SelectSingleNode("/manifest/application") as XmlElement;
        if (application == null || application.HasAttribute("networkSecurityConfig", android))
            throw new InvalidOperationException("Unexpected Android network security configuration; review it before building the USB profile.");
        // PlayerSettings controls UnityWebRequest; Android's merged manifest must
        // also permit the local HTTP backend for target SDK 34.
        application.SetAttribute("usesCleartextTraffic", android, "true");
        document.Save(manifest);
    }
}
#endif
