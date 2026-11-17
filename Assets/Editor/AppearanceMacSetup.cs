using System;
using System.IO;
using IAI.Appearance;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class AppearanceMacSetup
{
    public static void OpenDemo()
    {
        EditorSceneManager.OpenScene("Assets/Project/Scenes/AppearanceDesktopDemo.unity");
        Debug.Log("Mac desktop demo ready. Start a backend, then press Play. Profile is configured by macos.sh.");
    }

    public static void Verify()
    {
        AppearanceVRChecks.Run();
        if (!Resources.Load<GameObject>("AvatarDemo/Liang") || !Resources.Load<GameObject>("AvatarDemo/Nailong"))
            throw new Exception("Avatar FBX import failed.");
        if (!AssetDatabase.LoadAssetAtPath<Font>("Assets/Project/Fonts/NotoSansCJKsc-Regular.otf"))
            throw new Exception("CJK font import failed.");
        var root = new GameObject("Mac resource verification");
        try
        {
            var avatar = root.AddComponent<AppearanceAvatar>();
            avatar.EnableDemo(true);
            avatar.Apply(new AppearanceState {avatar_id="nailong", outfit="none", jacket_color="yellow", accessory="hat", scale=1.05f});
            if (avatar.ObservedAccessory != "hat" || Mathf.Abs(avatar.ObservedScale - 1.05f) > .0001f)
                throw new Exception("Avatar state application failed.");
            avatar.EnableDemo(false);
        }
        finally { UnityEngine.Object.DestroyImmediate(root); }
        Directory.CreateDirectory("StudyData/macos");
        File.WriteAllText("StudyData/macos/unity-resources.json", "{\"passed\":true,\"scope\":\"Editor import and runtime component checks; no live API or headset test\"}");
        Debug.Log("MAC_APPEARANCE_VERIFIED");
    }
}
