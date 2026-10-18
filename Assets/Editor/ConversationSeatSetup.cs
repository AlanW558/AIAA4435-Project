using System.IO;
using System.Linq;
using IAI.Environment;
using IAI.Interaction;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.Locomotion;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Turning;
using UnityEngine.XR.Interaction.Toolkit.Samples.StarterAssets;

public static class ConversationSeatSetup
{
    const string AssetRoot = "Assets/Project/Materials/Interaction";

    [MenuItem("AIAA4435/Interaction/Install Chair Interaction")]
    public static void Install()
    {
        if (EditorApplication.isPlaying) throw new System.InvalidOperationException("Stop Play mode first.");
        var room = Object.FindObjectOfType<RoomReferences>();
        var origin = Object.FindObjectOfType<XROrigin>();
        if (!room || !origin) throw new System.InvalidOperationException("Open CloudConversationRoom first.");
        if (Object.FindObjectOfType<ConversationSeat>())
        {
            Debug.Log("Chair interaction is already installed; keeping existing settings.");
            return;
        }
        Directory.CreateDirectory(AssetRoot);
        AssetDatabase.Refresh();
        var root = new GameObject("09 Chair Interaction");
        var seat = root.AddComponent<ConversationSeat>();
        seat.origin = origin;
        seat.seatAnchor = room.userSeat;
        var exit = new GameObject("Standing Exit — behind user chair").transform;
        exit.SetParent(root.transform);
        exit.position = room.userSeat.TransformPoint(new Vector3(0, 0, -1.55f));
        exit.rotation = room.userSeat.rotation;
        seat.exitAnchor = exit;

        // Enable only the intended locomotion pair. The chair saves/restores this configuration.
        foreach (var provider in origin.GetComponentsInChildren<LocomotionProvider>(true)) provider.enabled = false;
        var move = origin.GetComponentInChildren<ContinuousMoveProvider>(true);
        move.moveSpeed = 1.15f;
        move.enabled = true;
        var snap = origin.GetComponentInChildren<SnapTurnProvider>(true);
        snap.turnAmount = 30;
        snap.enableTurnAround = false;
        snap.enabled = true;
        foreach (var manager in origin.GetComponentsInChildren<ControllerInputActionManager>(true))
        {
            manager.smoothMotionEnabled = manager.name.Contains("Left");
            manager.smoothTurnEnabled = false;
        }
        origin.name = "08 XR Origin — walk and seated conversation";
        origin.transform.position = room.userSeat.TransformPoint(new Vector3(0, 0, -2.2f));
        origin.transform.rotation = room.userSeat.rotation;
        origin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
        origin.CameraYOffset = 1.65f;
        origin.CameraFloorOffsetObject.transform.localPosition = Vector3.up * 1.65f;
        var character = origin.GetComponent<CharacterController>();
        character.radius = .2f;
        character.stepOffset = .15f;

        var fadeMaterial = new Material(Shader.Find("IAI/Seat Fade")) { name = "Seat Transition Black" };
        fadeMaterial.SetColor("_Color", Color.clear);
        AssetDatabase.CreateAsset(fadeMaterial, AssetRoot + "/SeatTransition.mat");
        var overlay = GameObject.CreatePrimitive(PrimitiveType.Quad);
        overlay.name = "Seat Transition — stereo fade";
        Object.DestroyImmediate(overlay.GetComponent<Collider>());
        overlay.transform.SetParent(origin.Camera.transform, false);
        overlay.transform.localPosition = Vector3.forward * (origin.Camera.nearClipPlane + .025f);
        overlay.transform.localScale = Vector3.one * 2;
        var renderer = overlay.GetComponent<MeshRenderer>();
        renderer.sharedMaterial = fadeMaterial;
        // XRI's ray SortingGroups use order 30005; the fade must cover those too.
        renderer.sortingOrder = 32767;
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;
        renderer.lightProbeUsage = LightProbeUsage.Off;
        renderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
        renderer.enabled = false;
        seat.viewFade = overlay.AddComponent<SeatViewFade>();
        seat.viewFade.overlay = renderer;

        var hintObject = new GameObject("Seat Hint — warm white", typeof(RectTransform), typeof(Canvas), typeof(CanvasGroup));
        hintObject.transform.SetParent(root.transform, false);
        hintObject.transform.position = room.userSeat.position + new Vector3(0, 1.18f, -.12f);
        hintObject.transform.localScale = Vector3.one * .001f;
        var canvas = hintObject.GetComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.worldCamera = origin.Camera;
        ((RectTransform)hintObject.transform).sizeDelta = new Vector2(500, 190);
        var group = hintObject.GetComponent<CanvasGroup>();
        group.alpha = 0;
        group.interactable = false;
        group.blocksRaycasts = false;
        var hint = hintObject.AddComponent<SeatInteractionHint>();
        hint.seat = seat;
        hint.group = group;

        var plate = new GameObject("Soft backdrop", typeof(RectTransform), typeof(Image));
        plate.transform.SetParent(hintObject.transform, false);
        var plateRect = (RectTransform)plate.transform;
        plateRect.sizeDelta = new Vector2(500, 190);
        var image = plate.GetComponent<Image>();
        image.sprite = RoundedSprite();
        image.type = Image.Type.Sliced;
        image.color = new Color(.15f, .14f, .12f, .72f);
        image.raycastTarget = false;
        // High source font resolution, then scaled in world space; no scene lights or bloom required.
        hint.title = Label("Heading", hintObject.transform, 46, 33, new Color(1f, .88f, .68f));
        hint.action = Label("Action", hintObject.transform, 1, 43, new Color(1f, .97f, .90f));
        hint.detail = Label("Detail", hintObject.transform, -51, 24, new Color(.94f, .91f, .84f));

        var ringObject = new GameObject("Seat proximity halo");
        ringObject.transform.SetParent(root.transform, false);
        var ring = ringObject.AddComponent<LineRenderer>();
        ring.useWorldSpace = true;
        ring.loop = true;
        ring.positionCount = 80;
        ring.widthMultiplier = .008f;
        ring.numCornerVertices = 2;
        ring.shadowCastingMode = ShadowCastingMode.Off;
        ring.receiveShadows = false;
        ring.lightProbeUsage = LightProbeUsage.Off;
        ring.reflectionProbeUsage = ReflectionProbeUsage.Off;
        ring.alignment = LineAlignment.TransformZ;
        ring.transform.rotation = Quaternion.Euler(90, 0, 0);
        for (int i = 0; i < ring.positionCount; i++)
        {
            float angle = i * 2 * Mathf.PI / ring.positionCount;
            ring.SetPosition(i, room.userSeat.position + new Vector3(Mathf.Cos(angle) * .5f, .018f, Mathf.Sin(angle) * .5f));
        }
        var ringMaterial = new Material(Shader.Find("IAI/Interaction Line")) { name = "Seat Warm Halo" };
        AssetDatabase.CreateAsset(ringMaterial, AssetRoot + "/SeatHalo.mat");
        ring.sharedMaterial = ringMaterial;
        ring.enabled = false;
        hint.floorRing = ring;

        foreach (var t in root.GetComponentsInChildren<Transform>(true))
            GameObjectUtility.SetStaticEditorFlags(t.gameObject, 0);
        EditorUtility.SetDirty(origin);
        EditorSceneManager.MarkSceneDirty(origin.gameObject.scene);
        EditorSceneManager.SaveScene(origin.gameObject.scene);
        AssetDatabase.SaveAssets();
        Selection.activeGameObject = root;
        Debug.Log("Chair interaction installed. Left stick: walk. Right stick: snap turn. A/X: sit nearby. B/Y: leave. Editor: Enter/Backspace.");
    }

    static Text Label(string name, Transform parent, float y, int size, Color color)
    {
        var go = new GameObject(name, typeof(RectTransform), typeof(Text));
        go.transform.SetParent(parent, false);
        var rect = (RectTransform)go.transform;
        rect.sizeDelta = new Vector2(470, 58);
        rect.anchoredPosition = new Vector2(0, y);
        var text = go.GetComponent<Text>();
        text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        text.fontSize = size;
        text.alignment = TextAnchor.MiddleCenter;
        text.color = color;
        text.raycastTarget = false;
        return text;
    }

    static Sprite RoundedSprite()
    {
        string path = AssetRoot + "/HintRounded.png";
        const int size = 128;
        var texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                Vector2 p = new Vector2(Mathf.Abs(x - 63.5f), Mathf.Abs(y - 63.5f));
                Vector2 q = new Vector2(Mathf.Max(p.x - 39.5f, 0), Mathf.Max(p.y - 39.5f, 0));
                float alpha = Mathf.Clamp01(24 - q.magnitude);
                texture.SetPixel(x, y, new Color(1, 1, 1, alpha));
            }
        texture.Apply();
        File.WriteAllBytes(path, texture.EncodeToPNG());
        Object.DestroyImmediate(texture);
        AssetDatabase.ImportAsset(path);
        var importer = (TextureImporter)AssetImporter.GetAtPath(path);
        importer.textureType = TextureImporterType.Sprite;
        importer.spriteBorder = new Vector4(26, 26, 26, 26);
        importer.mipmapEnabled = false;
        importer.alphaIsTransparency = true;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Sprite>(path);
    }
}
