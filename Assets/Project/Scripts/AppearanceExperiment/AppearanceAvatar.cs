using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace IAI.Appearance
{
    // Frozen study renderer and debug-only mesh avatars share the same observation interface.
    public sealed class AppearanceAvatar : MonoBehaviour
    {
        AppearanceLegacyAvatar legacy;
        Transform demoRoot;
        GameObject liang, nailong;
        Transform liangHead, nailongHead;
        bool demo;
        readonly List<Material> owned = new List<Material>();
        readonly Dictionary<Material, Material> converted = new Dictionary<Material, Material>();
        readonly Dictionary<Transform, Quaternion> neutral = new Dictionary<Transform, Quaternion>();
        string interaction = "idle";
        float elapsed, gestureAge;
        static readonly string[] Names = { "blue", "orange", "green", "gray", "red", "purple", "yellow" };
        static readonly string[] Hex = { "#2358B8", "#EF8B22", "#319B6B", "#7B8793", "#CE3549", "#8954C1", "#F9C92B" };
        public static Material Material(string name, Color color) => AppearanceLegacyAvatar.Material(name, color);
        public static GameObject Shape(string name, PrimitiveType kind, Transform parent, Vector3 pos, Vector3 size, Material mat)
            => AppearanceLegacyAvatar.Shape(name, kind, parent, pos, size, mat);

        public void Create()
        {
            if (legacy) return;
            var node = new GameObject("Study v1 renderer");
            node.transform.SetParent(transform, false);
            legacy = node.AddComponent<AppearanceLegacyAvatar>();
            legacy.Create();
        }
        public void EnableDemo(bool enabled)
        {
            Create();
            if (enabled && !demoRoot)
            {
                try
                {
                    demoRoot = new GameObject("Demo foot anchor").transform;
                    demoRoot.SetParent(transform, false);
                    liang = Load("Liang", demoRoot);
                    nailong = Load("Nailong", demoRoot);
                    liangHead = Find(liang, "head"); nailongHead = Find(nailong, "head");
                    foreach (var t in demoRoot.GetComponentsInChildren<Transform>(true)) neutral[t] = t.localRotation;
                }
                catch
                {
                    if (demoRoot) { if (Application.isPlaying) Destroy(demoRoot.gameObject); else DestroyImmediate(demoRoot.gameObject); }
                    demoRoot = null; liang = null; nailong = null; liangHead = nailongHead = null;
                    ReleaseMaterials(); neutral.Clear();
                    throw;
                }
            }
            demo = enabled;
            legacy.gameObject.SetActive(!demo);
            if (demoRoot) demoRoot.gameObject.SetActive(demo);
            if (demo) Apply(new AppearanceState { avatar_id = "liang", outfit = "suit", jacket_color = "blue", accessory = "glasses", scale = 1 });
        }
        GameObject Load(string name, Transform parent)
        {
            var source = Resources.Load<GameObject>("AvatarDemo/" + name);
            if (!source) throw new InvalidOperationException("Missing mesh avatar: " + name);
            var instance = Instantiate(source, parent, false);
            instance.name = name;
            // FBX imports face +Z; the shared room places the viewer toward -Z.
            instance.transform.localRotation = Quaternion.Euler(0, 180, 0) * instance.transform.localRotation;
            foreach (var r in instance.GetComponentsInChildren<Renderer>(true))
            {
                var materials = r.sharedMaterials;
                for (int i = 0; i < materials.Length; i++)
                {
                    var original = materials[i];
                    if (!original) throw new InvalidOperationException("Missing avatar material: " + r.name);
                    if (!converted.TryGetValue(original, out var replacement))
                    {
                        if (original.name.EndsWith("_Reference", StringComparison.Ordinal))
                        {
                            bool nailongReference = original.name == "Tint_Nailong_Reference";
                            if (!nailongReference && original.name != "Tint_LiangSuit_Reference" &&
                                original.name != "Tint_LiangSport_Reference" && original.name != "Tint_LiangBare_Reference")
                                throw new InvalidOperationException("Unknown reference avatar material: " + original.name);
                            var maskPath = "AvatarDemo/Textures/" + original.name + "_Mask";
                            var mask = Resources.Load<Texture2D>(maskPath);
                            if (!mask) throw new InvalidOperationException("Missing avatar tint mask: " + maskPath);
                            var texture = original.mainTexture;
                            if (!texture) throw new InvalidOperationException("Missing reference avatar albedo: " + original.name);
                            var shader = Resources.Load<Shader>("AvatarDemo/MaskedReferenceLit");
                            if (!shader || !shader.isSupported)
                                throw new InvalidOperationException("Missing or unsupported avatar shader: AvatarDemo/MaskedReferenceLit");
                            ColorUtility.TryParseHtmlString(Hex[nailongReference ? 6 : 0], out var referenceColor);
                            replacement = new Material(shader) { name = original.name, color = referenceColor, enableInstancing = true };
                            replacement.SetColor("_ReferenceColor", referenceColor);
                            replacement.SetTexture("_TintMask", mask);
                            replacement.mainTexture = texture;
                            replacement.mainTextureScale = original.mainTextureScale;
                            replacement.mainTextureOffset = original.mainTextureOffset;
                        }
                        else
                        {
                            replacement = Material(original.name, original.color);
                            if (original.name == "Belly_cream")
                            {
                                ColorUtility.TryParseHtmlString("#F4D99B", out var cream);
                                replacement.color = cream;
                            }
                            if (original.name == "Warm_olive_extremities")
                            {
                                ColorUtility.TryParseHtmlString("#88732E", out var olive);
                                replacement.color = olive;
                            }
                            var texture = original.mainTexture;
                            if (texture) { replacement.mainTexture = texture; replacement.SetTexture("_BaseMap", texture); }
                        }
                        if (original.name.Contains("Cutout"))
                        {
                            replacement.SetFloat("_AlphaClip", 1);
                            replacement.SetFloat("_Cutoff", .45f);
                            replacement.SetFloat("_Cull", 0);
                            replacement.EnableKeyword("_ALPHATEST_ON");
                            replacement.SetOverrideTag("RenderType", "TransparentCutout");
                            replacement.renderQueue = 2450;
                        }
                        replacement.SetFloat("_Smoothness", original.name.Contains("Eye") ? .68f : original.name.Contains("Metal") ? .65f : .24f);
                        if (original.name.Contains("Metal")) replacement.SetFloat("_Metallic", .45f);
                        converted.Add(original, replacement); owned.Add(replacement);
                    }
                    materials[i] = replacement;
                }
                r.sharedMaterials = materials;
            }
            return instance;
        }
        GameObject ActiveModel => liang && liang.activeSelf ? liang : nailong && nailong.activeSelf ? nailong : null;
        static Transform Find(GameObject root, string name) => root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == name);
        static bool IsActive(GameObject root, string name) { var t = Find(root, name); return t && t.gameObject.activeInHierarchy; }
        static void Toggle(GameObject root, string name, bool value)
        {
            var t = Find(root, name);
            if (!t) throw new InvalidOperationException("Missing avatar assembly: " + name);
            t.gameObject.SetActive(value);
        }
        public string ObservedAvatar => !demo ? null : liang.activeSelf == nailong.activeSelf ? "invalid" : liang.activeSelf ? "liang" : "nailong";
        public string ObservedOutfit
        {
            get
            {
                if (!demo) return null;
                var active = ActiveModel;
                if (!active) return "invalid";
                var found = new[] { "suit", "sport", "none" }.Where(x => IsActive(active, "Outfit_" + x)).ToArray();
                return found.Length == 1 ? found[0] : "invalid";
            }
        }
        public string ObservedColor
        {
            get
            {
                if (!demo) return legacy.ObservedColor;
                var active = ActiveModel;
                if (!active) return "unrecognized";
                var colors = active.GetComponentsInChildren<Renderer>().Where(r => r.enabled)
                    .SelectMany(r => r.sharedMaterials).Where(m => m && m.name.StartsWith("Tint", StringComparison.Ordinal))
                    .Select(m => m.color).ToArray();
                if (colors.Length == 0) return "unrecognized";
                for (int i = 0; i < Names.Length; i++)
                {
                    ColorUtility.TryParseHtmlString(Hex[i], out var expected);
                    if (colors.All(c => Vector4.Distance(c, expected) < .005f)) return Names[i];
                }
                return "unrecognized";
            }
        }
        public string ObservedAccessory => !demo ? legacy.ObservedAccessory :
            !ActiveModel ? "invalid" : IsActive(ActiveModel, "Accessory_hat") ?
            (IsActive(ActiveModel, "Accessory_glasses") ? "invalid_multiple" : "hat") :
            IsActive(ActiveModel, "Accessory_glasses") ? "glasses" : "none";
        public float ObservedScale => demo ? demoRoot.localScale.x : legacy.ObservedScale;
        public void Apply(AppearanceState state)
        {
            if (state == null) return;
            Create();
            if (!demo) { legacy.Apply(state); return; }
            if (state.avatar_id != "liang" && state.avatar_id != "nailong") throw new ArgumentException("Unknown avatar.");
            if (Array.IndexOf(new[] { "suit", "sport", "none" }, state.outfit) < 0 ||
                (state.avatar_id == "nailong" && state.outfit != "none")) throw new ArgumentException("Unsupported outfit.");
            int color = Array.IndexOf(Names, state.jacket_color);
            if (color < 0) throw new ArgumentException("Unsupported color.");
            liang.SetActive(state.avatar_id == "liang"); nailong.SetActive(state.avatar_id == "nailong");
            var active = ActiveModel;
            foreach (string outfit in new[] { "suit", "sport", "none" })
            {
                var group = Find(active, "Outfit_" + outfit);
                if (group) group.gameObject.SetActive(outfit == state.outfit);
            }
            Toggle(active, "Accessory_hat", state.accessory == "hat");
            Toggle(active, "Accessory_glasses", state.accessory == "glasses");
            ColorUtility.TryParseHtmlString(Hex[color], out var tint);
            foreach (var m in active.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Distinct())
                if (m && m.name.StartsWith("Tint", StringComparison.Ordinal)) m.color = tint;
            demoRoot.localScale = Vector3.one * state.scale;
        }
        public void SetInteraction(string mode)
        {
            Create();
            if (!demo) { legacy.SetInteraction(mode); return; }
            if (interaction == mode) return;
            interaction = mode; gestureAge = 0;
        }
        void LateUpdate()
        {
            if (!demo || !ActiveModel) return;
            float dt = Mathf.Min(Time.unscaledDeltaTime, .1f);
            elapsed += dt; gestureAge += dt;
            float gesture = Mathf.Sin(Mathf.Clamp01(gestureAge / 1.4f) * Mathf.PI);
            var head = liang.activeSelf ? liangHead : nailongHead;
            if (head && neutral.TryGetValue(head, out var rest))
                head.localRotation = rest * Quaternion.Euler(
                    interaction == "done" ? Mathf.Sin(gestureAge * 6) * gesture * 3 : Mathf.Sin(elapsed * .65f) * .7f,
                    Mathf.Sin(elapsed * .4f) * 1.6f, interaction == "ask" ? gesture * 3 : 0);
        }
        void ReleaseMaterials()
        {
            foreach (var m in owned)
                if (m) { if (Application.isPlaying) Destroy(m); else DestroyImmediate(m); }
            owned.Clear(); converted.Clear();
        }
        void OnDestroy() => ReleaseMaterials();
    }
}
