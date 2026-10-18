using System.IO;
using IAI.Interaction;
using IAI.UI;
using UnityEditor;
using UnityEditor.Events;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Rendering;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

public static class SettingsPanelSetup
{
    const string Root = "Assets/Project/Materials/Interaction";
    static readonly Color Ink = new Color(1f, .97f, .9f, 1f);
    static Sprite rounded;
    static Font font;

    [MenuItem("AIAA4435/Interaction/Install Settings Preview Panel")]
    public static void Install()
    {
        if (EditorApplication.isPlaying) throw new System.InvalidOperationException("Stop Play mode first.");
        var seat = Object.FindObjectOfType<ConversationSeat>();
        if (!seat) throw new System.InvalidOperationException("Install the chair interaction first.");
        if (Object.FindObjectOfType<SettingsPanelDemo>())
        {
            Debug.Log("Settings panel already exists; keeping the current layout.");
            return;
        }
        rounded = AssetDatabase.LoadAssetAtPath<Sprite>(Root + "/HintRounded.png");
        font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        var root = new GameObject("10 Settings Panel — warm curved preview");
        float radius = Mathf.Sqrt(.75f * .75f - .05f * .05f);
        float angle = Mathf.Atan2(.78f, .55f) + 20 * Mathf.Deg2Rad;
        root.transform.position = seat.seatAnchor.TransformPoint(new Vector3(Mathf.Sin(angle) * radius, 1.25f, Mathf.Cos(angle) * radius));
        root.transform.rotation = seat.seatAnchor.rotation * Quaternion.Euler(0, angle * Mathf.Rad2Deg, 0);
        var demo = root.AddComponent<SettingsPanelDemo>();
        demo.seat = seat;

        var surface = new GameObject("Curved glass and soft halo", typeof(MeshFilter), typeof(MeshRenderer));
        surface.transform.SetParent(root.transform, false);
        var mesh = CurvedMesh();
        AssetDatabase.CreateAsset(mesh, Root + "/SettingsPanelCurve.asset");
        surface.GetComponent<MeshFilter>().sharedMesh = mesh;
        var material = new Material(Shader.Find("IAI/Warm Curved Panel"));
        material.name = "Warm white translucent panel";
        material.SetColor("_Tint", new Color(1, .955f, .865f));
        material.SetFloat("_Visibility", 0);
        AssetDatabase.CreateAsset(material, Root + "/SettingsPanelGlass.mat");
        var renderer = surface.GetComponent<MeshRenderer>();
        renderer.sharedMaterial = material;
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;
        renderer.lightProbeUsage = LightProbeUsage.Off;
        renderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
        renderer.sortingOrder = -10;
        demo.backdrop = renderer;

        // The curved glass is physical geometry. Controls sit on a stable plane just in front of it,
        // so Unity's standard drag projection remains accurate for both desktop and XR pointers.
        var ui = Rect("Settings Canvas", root.transform, Vector2.zero, new Vector2(660, 500));
        ui.localPosition = new Vector3(0, 0, -.05f);
        ui.localScale = Vector3.one * .001f;
        var canvas = ui.gameObject.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.worldCamera = seat.origin.Camera;
        var xrRaycaster = ui.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>();
        xrRaycaster.checkFor3DOcclusion = true;
        xrRaycaster.checkFor2DOcclusion = false;
        ui.gameObject.AddComponent<DesktopPanelRaycaster>();
        demo.visibilityGroup = ui.gameObject.AddComponent<CanvasGroup>();
        demo.visibilityGroup.alpha = 0;
        demo.visibilityGroup.interactable = demo.visibilityGroup.blocksRaycasts = false;
        demo.pages = new CanvasGroup[5];
        string[] names = { "Overview", "Speech Rate", "Reply Length", "Tone", "Voice" };
        for (int i = 0; i < names.Length; i++)
        {
            var page = Rect("Page " + i + " — " + names[i], ui, Vector2.zero, new Vector2(660, 500));
            demo.pages[i] = page.gameObject.AddComponent<CanvasGroup>();
        }
        BuildHome(demo);
        BuildRate(demo);
        BuildLength(demo);
        BuildChoices(demo, true);
        BuildChoices(demo, false);
        for (int i = 1; i < demo.pages.Length; i++) demo.pages[i].gameObject.SetActive(false);

        var eventSystem = Object.FindObjectOfType<EventSystem>();
        if (!eventSystem)
        {
            var events = new GameObject("11 XR UI Event System", typeof(EventSystem), typeof(XRUIInputModule));
            eventSystem = events.GetComponent<EventSystem>();
        }
        var module = eventSystem.GetComponent<XRUIInputModule>();
        if (!module) throw new System.InvalidOperationException("Existing EventSystem needs XRUIInputModule configuration.");
        module.enableXRInput = true;
        module.enableMouseInput = true;
        module.enableTouchInput = false;
        module.enableGamepadInput = false;
        module.enableJoystickInput = false;
        module.enableBuiltinActionsAsFallback = true;
        eventSystem.sendNavigationEvents = false;
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
            GameObjectUtility.SetStaticEditorFlags(t.gameObject, 0);
        EditorSceneManager.MarkSceneDirty(root.scene);
        EditorSceneManager.SaveScene(root.scene);
        AssetDatabase.SaveAssets();
        Selection.activeGameObject = root;
        Debug.Log("Settings preview installed: overview + four pages, local-only values, XR trigger click/drag, seated visibility.");
    }

    static void BuildHome(SettingsPanelDemo demo)
    {
        var p = demo.pages[0].transform;
        Label(p, "Eyebrow", "CONVERSATION", -260, 200, 350, 24, 16, TextAnchor.MiddleLeft, .8f);
        Pill(p);
        Label(p, "Title", "Make it yours", -260, 148, 520, 48, 36, TextAnchor.MiddleLeft);
        Label(p, "Subtitle", "A little adjustment. A better conversation.", -260, 108, 520, 32, 20, TextAnchor.MiddleLeft, .88f);
        demo.homeValues = new Text[4];
        string[] titles = { "Speech rate", "Reply length", "Tone", "Voice" };
        string[] initial = { "1.00×", "Balanced", "Friendly", "Voice A" };
        for (int i = 0; i < 4; i++)
        {
            int col = i % 2, row = i / 2;
            var button = Button(p, "Open " + titles[i], new Vector2(col == 0 ? -139 : 139, row == 0 ? 24 : -104), new Vector2(260, 110));
            Label(button.transform, "Label", titles[i], -108, 26, 205, 28, 20, TextAnchor.MiddleLeft, .9f);
            demo.homeValues[i] = Label(button.transform, "Value", initial[i], -108, -14, 207, 42, 29, TextAnchor.MiddleLeft);
            Label(button.transform, "Arrow", "›", 91, -14, 22, 36, 30, TextAnchor.MiddleCenter, .85f);
            UnityEventTools.AddIntPersistentListener(button.onClick, demo.OpenPage, i + 1);
        }
        Label(p, "Footer", "Choose a setting to explore", -260, -207, 350, 28, 17, TextAnchor.MiddleLeft, .8f);
        Reset(p, demo, "Reset all");
    }

    static Transform Detail(SettingsPanelDemo demo, int index, string title, string description)
    {
        var p = demo.pages[index].transform;
        var back = Button(p, "Back", new Vector2(-215, 202), new Vector2(110, 42));
        Label(back.transform, "Label", "‹  Back", 0, 0, 110, 32, 20, TextAnchor.MiddleCenter);
        UnityEventTools.AddIntPersistentListener(back.onClick, demo.OpenPage, 0);
        Label(p, "Page count", "0" + index + " / 04", 180, 202, 90, 30, 16, TextAnchor.MiddleRight, .8f);
        Label(p, "Title", title, -260, 143, 520, 44, 34, TextAnchor.MiddleLeft);
        Label(p, "Description", description, -260, 102, 520, 30, 20, TextAnchor.MiddleLeft, .88f);
        Reset(p, demo, "Reset");
        return p;
    }

    static void BuildRate(SettingsPanelDemo demo)
    {
        var p = Detail(demo, 1, "Speech rate", "Find a pace that feels comfortable.");
        demo.rateValue = Label(p, "Rate value", "1.00×", 0, 37, 450, 58, 45, TextAnchor.MiddleCenter);
        demo.rateSlider = Slider(p, "Speech rate slider", -.0f, -35);
        demo.rateSlider.minValue = .7f;
        demo.rateSlider.maxValue = 1.3f;
        demo.rateSlider.SetValueWithoutNotify(1f);
        Label(p, "Slow label", "Slower · 0.70×", -245, -89, 190, 28, 18, TextAnchor.MiddleLeft, .9f);
        Label(p, "Fast label", "Faster · 1.30×", 150, -89, 190, 28, 18, TextAnchor.MiddleRight, .9f);
        Label(p, "Center label", "1.00× · Natural", 0, -125, 300, 28, 19, TextAnchor.MiddleCenter, .8f);
        Label(p, "Footer", "Drag the handle to adjust", -260, -207, 350, 28, 17, TextAnchor.MiddleLeft, .8f);
    }

    static void BuildLength(SettingsPanelDemo demo)
    {
        var p = Detail(demo, 2, "Reply length", "Choose how much detail you prefer.");
        demo.lengthValue = Label(p, "Length value", "Balanced", 0, 37, 470, 58, 42, TextAnchor.MiddleCenter);
        demo.lengthSlider = Slider(p, "Reply length slider", 0, -35);
        demo.lengthSlider.minValue = 0;
        demo.lengthSlider.maxValue = 2;
        demo.lengthSlider.wholeNumbers = true;
        demo.lengthSlider.SetValueWithoutNotify(1);
        Label(p, "Brief label", "Brief", -243, -88, 100, 28, 18, TextAnchor.MiddleLeft, .9f);
        Label(p, "Balanced label", "Balanced", 0, -88, 150, 28, 18, TextAnchor.MiddleCenter, .9f);
        Label(p, "Detailed label", "Detailed", 193, -88, 100, 28, 18, TextAnchor.MiddleRight, .9f);
        demo.lengthDescription = Label(p, "Length description", "Enough detail to keep the conversation flowing.", 0, -132, 520, 54, 19, TextAnchor.MiddleCenter, .85f);
        Label(p, "Footer", "Three levels of detail", -260, -207, 350, 28, 17, TextAnchor.MiddleLeft, .8f);
    }

    static void BuildChoices(SettingsPanelDemo demo, bool tone)
    {
        int index = tone ? 3 : 4;
        var p = Detail(demo, index, tone ? "Tone" : "Voice", tone ? "Set the feel of the conversation." : "Choose a voice profile.");
        string[] labels = tone ? new[] { "Professional", "Friendly", "Encouraging" } : new[] { "Voice A", "Voice B", "Voice C" };
        string[] details = tone ? new[] { "Clear and composed", "Warm and conversational", "Supportive and motivating" } : new[] { "Profile 01", "Profile 02", "Profile 03" };
        var options = new PanelControlFeedback[3];
        var checks = new GameObject[3];
        for (int i = 0; i < 3; i++)
        {
            var button = Button(p, (tone ? "Tone " : "Voice ") + i, new Vector2(0, 34 - i * 82), new Vector2(520, 70));
            options[i] = button.GetComponent<PanelControlFeedback>();
            Label(button.transform, "Label", labels[i], -237, 13, 420, 30, 23, TextAnchor.MiddleLeft);
            Label(button.transform, "Detail", details[i], -237, -15, 420, 25, 16, TextAnchor.MiddleLeft, .8f);
            var dot = Image("Selected", button.transform, new Vector2(222, 0), new Vector2(16, 16), new Color(1f, .98f, .91f, .95f));
            checks[i] = dot.gameObject;
            if (tone) UnityEventTools.AddIntPersistentListener(button.onClick, demo.ChooseTone, i);
            else UnityEventTools.AddIntPersistentListener(button.onClick, demo.ChooseVoice, i);
        }
        if (tone) { demo.toneOptions = options; demo.toneChecks = checks; }
        else { demo.voiceOptions = options; demo.voiceChecks = checks; }
        Label(p, "Footer", tone ? "Select a conversation style" : "Preview profiles", -260, -207, 350, 28, 17, TextAnchor.MiddleLeft, .8f);
    }

    static Slider Slider(Transform parent, string name, float x, float y)
    {
        var rect = Rect(name, parent, new Vector2(x, y), new Vector2(510, 76));
        var hit = rect.gameObject.AddComponent<Image>();
        hit.color = new Color(1, 1, 1, .001f);
        hit.raycastTarget = true;
        var slider = rect.gameObject.AddComponent<Slider>();
        slider.navigation = new Navigation { mode = Navigation.Mode.None };
        slider.transition = Selectable.Transition.None;
        Image("Track", rect, Vector2.zero, new Vector2(480, 5), new Color(1f, .96f, .88f, .24f));
        var fillArea = Rect("Fill area", rect, Vector2.zero, new Vector2(480, 5));
        var fill = Image("Fill", fillArea, Vector2.zero, new Vector2(480, 5), new Color(1f, .97f, .9f, .85f));
        var fillTransform = (RectTransform)fill.transform;
        fillTransform.anchorMin = Vector2.zero;
        fillTransform.anchorMax = Vector2.one;
        fillTransform.sizeDelta = Vector2.zero;
        var handles = Rect("Handle area", rect, Vector2.zero, new Vector2(480, 0));
        var handle = Image("Handle", handles, Vector2.zero, new Vector2(30, 30), Ink);
        handle.raycastTarget = true;
        Image("Handle glow", handle.transform, Vector2.zero, new Vector2(48, 48), new Color(1f, .94f, .82f, .12f));
        slider.fillRect = (RectTransform)fill.transform;
        slider.handleRect = (RectTransform)handle.transform;
        slider.targetGraphic = handle;
        var feedback = rect.gameObject.AddComponent<PanelControlFeedback>();
        feedback.isSlider = true;
        feedback.surface = handle;
        return slider;
    }

    static void Reset(Transform parent, SettingsPanelDemo demo, string caption)
    {
        var b = Button(parent, "Reset", new Vector2(206, -207), new Vector2(128, 42));
        Label(b.transform, "Label", caption, 0, 0, 128, 30, 18, TextAnchor.MiddleCenter);
        UnityEventTools.AddPersistentListener(b.onClick, demo.ResetCurrent);
    }
    static void Pill(Transform parent)
    {
        Image("Preview pill", parent, new Vector2(224, 200), new Vector2(92, 28), new Color(1f, .95f, .86f, .12f));
        Label(parent, "Preview", "PREVIEW", 224, 200, 92, 24, 13, TextAnchor.MiddleCenter, .9f);
    }
    static Button Button(Transform parent, string name, Vector2 position, Vector2 size)
    {
        var image = Image(name, parent, position, size, new Color(1f, .96f, .88f, .09f));
        image.raycastTarget = true;
        var button = image.gameObject.AddComponent<Button>();
        button.navigation = new Navigation { mode = Navigation.Mode.None };
        button.transition = Selectable.Transition.None;
        button.targetGraphic = image;
        image.gameObject.AddComponent<PanelControlFeedback>().surface = image;
        return button;
    }
    static Image Image(string name, Transform parent, Vector2 position, Vector2 size, Color color)
    {
        var r = Rect(name, parent, position, size);
        var image = r.gameObject.AddComponent<Image>();
        image.sprite = rounded;
        image.type = UnityEngine.UI.Image.Type.Sliced;
        image.pixelsPerUnitMultiplier = 1.6f;
        image.color = color;
        image.raycastTarget = false;
        return image;
    }
    static Text Label(Transform parent, string name, string value, float x, float y, float w, float h, int size, TextAnchor align, float alpha = 1f)
    {
        bool left = align == TextAnchor.MiddleLeft;
        var r = Rect(name, parent, new Vector2(x + (left ? w / 2 : 0), y), new Vector2(w, h));
        var text = r.gameObject.AddComponent<Text>();
        text.font = font;
        text.text = value;
        text.fontSize = size;
        text.alignment = align;
        text.color = new Color(Ink.r, Ink.g, Ink.b, alpha);
        text.raycastTarget = false;
        text.horizontalOverflow = HorizontalWrapMode.Wrap;
        text.verticalOverflow = VerticalWrapMode.Truncate;
        var shadow = r.gameObject.AddComponent<Shadow>();
        shadow.effectColor = new Color(.16f, .12f, .08f, .7f);
        shadow.effectDistance = new Vector2(.6f, -1.2f);
        shadow.useGraphicAlpha = true;
        return text;
    }
    static RectTransform Rect(string name, Transform parent, Vector2 position, Vector2 size)
    {
        var go = new GameObject(name, typeof(RectTransform));
        var rect = (RectTransform)go.transform;
        rect.SetParent(parent, false);
        rect.sizeDelta = size;
        rect.anchoredPosition = position;
        return rect;
    }
    static Mesh CurvedMesh()
    {
        const int segments = 40;
        const float radius = 1.6f;
        var vertices = new Vector3[(segments + 1) * 2];
        var uv = new Vector2[vertices.Length];
        var triangles = new int[segments * 6];
        for (int i = 0; i <= segments; i++)
        {
            float x = Mathf.Lerp(-.37f, .37f, i / (float)segments);
            float angle = x / radius;
            float curvedX = Mathf.Sin(angle) * radius;
            float z = (Mathf.Cos(angle) - 1) * radius;
            vertices[i * 2] = new Vector3(curvedX, -.29f, z);
            vertices[i * 2 + 1] = new Vector3(curvedX, .29f, z);
            uv[i * 2] = new Vector2(i / (float)segments, 0);
            uv[i * 2 + 1] = new Vector2(i / (float)segments, 1);
            if (i == segments) continue;
            int t = i * 6, v = i * 2;
            triangles[t] = v; triangles[t + 1] = v + 1; triangles[t + 2] = v + 2;
            triangles[t + 3] = v + 2; triangles[t + 4] = v + 1; triangles[t + 5] = v + 3;
        }
        var mesh = new Mesh { name = "Subtle curved panel — R1.6m" };
        mesh.vertices = vertices; mesh.uv = uv; mesh.triangles = triangles;
        mesh.RecalculateNormals(); mesh.RecalculateBounds();
        return mesh;
    }
}
