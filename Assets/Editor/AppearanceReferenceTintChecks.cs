using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

// Run with graphics enabled: -executeMethod AppearanceReferenceTintChecks.Run
// This creates only a temporary scene and reviewer artifacts, never participant data.
public static class AppearanceReferenceTintChecks
{
    const int Size = 256;
    const float OracleTolerance = .002f;
    static readonly RectInt MaskZeroRegion = new RectInt(40, 40, 80, 176);
    static readonly RectInt MaskOneRegion = new RectInt(136, 40, 80, 176);

    [Serializable] sealed class ShaderMessage
    {
        public string shader, severity, message, file, platform;
        public int line;
    }
    [Serializable] sealed class ImageReceipt
    {
        public string filename;
        public Color maskZeroCenter, maskOneCenter;
    }
    [Serializable] sealed class Comparison
    {
        public string check;
        public int pixels;
        public float maxChannelDifference, meanChannelDifference;
    }
    [Serializable] sealed class ToneMetrics
    {
        public string image;
        public float maxRgbSpread, meanSaturation, lowerBandLuminance, upperBandLuminance;
    }
    [Serializable] sealed class Report
    {
        public bool passed;
        public string startedUtc, unityVersion, graphicsDeviceType, graphicsDeviceName,
            graphicsDeviceVendor, graphicsDeviceVersion, colorSpace, pipeline, renderer,
            renderTextureFormat, readbackTextureFormat, failure;
        public string method = "URP.SingleCameraRequest; RGBAFloat GPU readback; standard URP/Lit GPU oracle";
        public string source = "32x32 linear albedo: skin left, two different blue hues with reference-equivalent luminance right, two brightness bands; linear R8 mask 0 left / 1 right";
        public string shadowValidation = "Temporary in-memory PicoURP clone with the same renderer; main-light shadows enabled only for the shadow check";
        public float oracleTolerance = OracleTolerance;
        public string maskZeroRoi = "x=[40,120), y=[40,216)", maskOneRoi = "x=[136,216), y=[40,216)";
        public List<string> assertions = new List<string>();
        public List<ImageReceipt> images = new List<ImageReceipt>();
        public List<Comparison> comparisons = new List<Comparison>();
        public List<ToneMetrics> tones = new List<ToneMetrics>();
        public List<ShaderMessage> shaderMessages = new List<ShaderMessage>();
    }

    public static void Run()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            throw new InvalidOperationException("Stop play mode before running the GPU check.");
        string output = Path.GetFullPath("StudyData/avatar-v3/shader-checks");
        Directory.CreateDirectory(output);
        var report = new Report {
            startedUtc = DateTime.UtcNow.ToString("O"), unityVersion = Application.unityVersion,
            graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
            graphicsDeviceName = SystemInfo.graphicsDeviceName,
            graphicsDeviceVendor = SystemInfo.graphicsDeviceVendor,
            graphicsDeviceVersion = SystemInfo.graphicsDeviceVersion,
            colorSpace = QualitySettings.activeColorSpace.ToString()
        };
        var previousTarget = RenderTexture.active;
        bool previousAsync = ShaderUtil.allowAsyncCompilation;
        Scene scene = default;
        RenderTexture target = null;
        Shader shader = null, litShader = null;
        var owned = new List<Object>();
        try
        {
            Require(SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null,
                "A real graphics device is active (no -nographics).", report);
            var pipeline = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            Require(pipeline != null, "The project's existing Universal Render Pipeline is active.", report);
            report.pipeline = AssetDatabase.GetAssetPath(pipeline);
            report.renderer = pipeline.scriptableRenderer.GetType().FullName;
            Require(QualitySettings.activeColorSpace == ColorSpace.Linear,
                "The project's Linear color space is active.", report);
            Require(SystemInfo.SupportsRenderTextureFormat(RenderTextureFormat.ARGBFloat),
                "The GPU supports float render targets.", report);
            ShaderUtil.allowAsyncCompilation = false;
            shader = Resources.Load<Shader>("AvatarDemo/MaskedReferenceLit");
            litShader = Shader.Find("Universal Render Pipeline/Lit");
            Require(shader != null && shader.isSupported && litShader != null && litShader.isSupported,
                "Both the masked shader and standard URP/Lit are supported.", report);

            // Preview scenes also work when batch Unity starts with an untitled scene.
            // Leave the project's environment untouched; every draw uses the same one.
            scene = EditorSceneManager.NewPreviewScene();

            var camera = new GameObject("Reference tint check camera").AddComponent<Camera>();
            SceneManager.MoveGameObjectToScene(camera.gameObject, scene);
            camera.enabled = false;
            camera.scene = scene;
            camera.transform.position = new Vector3(0, 0, -3);
            camera.orthographic = true;
            camera.orthographicSize = 1;
            camera.aspect = 1;
            camera.nearClipPlane = .1f;
            camera.farClipPlane = 10;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.stereoTargetEye = StereoTargetEyeMask.None;
            camera.allowHDR = true;
            camera.allowMSAA = false;
            camera.useOcclusionCulling = false;
            var cameraData = camera.GetUniversalAdditionalCameraData();
            cameraData.renderPostProcessing = false;
            cameraData.renderShadows = true;
            cameraData.antialiasing = AntialiasingMode.None;
            cameraData.volumeLayerMask = 0;
            cameraData.dithering = false;
            cameraData.stopNaN = false;

            var light = new GameObject("White PBR key light").AddComponent<Light>();
            SceneManager.MoveGameObjectToScene(light.gameObject, scene);
            light.type = LightType.Directional;
            light.color = Color.white;
            light.intensity = .9f;
            light.shadows = LightShadows.None;
            light.transform.rotation = Quaternion.identity;
            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            SceneManager.MoveGameObjectToScene(quad, scene);
            quad.name = "Known two-region albedo and mask";
            quad.transform.localScale = new Vector3(1.6f, 1.6f, 1);
            Object.DestroyImmediate(quad.GetComponent<Collider>());
            var surface = quad.GetComponent<Renderer>();
            surface.lightProbeUsage = LightProbeUsage.Off;
            surface.reflectionProbeUsage = ReflectionProbeUsage.Off;

            ColorUtility.TryParseHtmlString("#2358B8", out var blue);
            ColorUtility.TryParseHtmlString("#EF8B22", out var orange);
            ColorUtility.TryParseHtmlString("#B58D72", out var skin);
            ColorUtility.TryParseHtmlString("#7B8793", out var uiGray);
            var neutralGray = new Color(.5f, .5f, .5f, 1);
            // Two strongly blue source hues share the reference's luminance.
            // The independent oracle contains only requested colors and brightness bands.
            var albedo = Albedo(skin.linear, blue.linear, owned, true);
            var expectedOrange = Albedo(skin.linear, orange.linear, owned);
            var expectedNeutralGray = Albedo(skin.linear, neutralGray.linear, owned);
            var expectedUiGray = Albedo(skin.linear, uiGray.linear, owned);
            var mask = new Texture2D(32, 32, TextureFormat.R8, false, true) {
                name = "Known linear 0/1 mask", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp
            };
            owned.Add(mask);
            var maskBytes = new byte[32 * 32];
            for (int y = 0; y < 32; y++)
                for (int x = 16; x < 32; x++) maskBytes[y * 32 + x] = 255;
            mask.LoadRawTextureData(maskBytes);
            mask.Apply(false, false);
            var material = new Material(shader) { name = "Masked reference GPU check", mainTexture = albedo, color = blue };
            owned.Add(material);
            material.SetColor("_ReferenceColor", blue);
            material.SetTexture("_TintMask", mask);
            material.SetFloat("_Metallic", 0);
            material.SetFloat("_Smoothness", .24f);
            var oracle = new Material(litShader) { name = "Standard URP Lit GPU oracle", mainTexture = albedo, color = Color.white };
            owned.Add(oracle);
            oracle.SetFloat("_Metallic", 0);
            oracle.SetFloat("_Smoothness", .24f);
            target = new RenderTexture(Size, Size, 24, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear) {
                name = "Reference tint float GPU readback", antiAliasing = 1, filterMode = FilterMode.Point
            };
            Require(target.Create(), "Float render target was created.", report);
            camera.targetTexture = target;
            report.renderTextureFormat = target.graphicsFormat.ToString();
            report.readbackTextureFormat = TextureFormat.RGBAFloat.ToString();
            var request = new UniversalRenderPipeline.SingleCameraRequest { destination = target };
            Require(RenderPipeline.SupportsRenderRequest(camera, request), "The current URP renderer supports camera render requests.", report);

            surface.sharedMaterial = oracle;
            var original = Render(camera, target, "00-urp-lit-original.png", output, report);
            surface.sharedMaterial = material;
            var baseline = Render(camera, target, "01-masked-default-blue.png", output, report);
            material.color = orange; // Same public Material.color path used by AppearanceAvatar.Apply.
            Require(material.color == orange, "Material.color reports the requested orange unchanged.", report);
            var changed = Render(camera, target, "02-masked-requested-orange.png", output, report);
            surface.sharedMaterial = oracle;
            oracle.mainTexture = expectedOrange;
            var expected = Render(camera, target, "03-urp-lit-expected-orange.png", output, report);
            surface.sharedMaterial = material;
            material.color = blue;
            light.intensity = 0;
            var unlit = Render(camera, target, "04-masked-key-light-off.png", output, report);
            light.intensity = .9f;
            material.color = neutralGray;
            var gray = Render(camera, target, "05-masked-neutral-gray.png", output, report);
            surface.sharedMaterial = oracle;
            oracle.mainTexture = expectedNeutralGray;
            var expectedGray = Render(camera, target, "06-urp-lit-expected-neutral-gray.png", output, report);
            surface.sharedMaterial = material;
            material.color = uiGray;
            Require(material.color == uiGray, "Material.color preserves the existing UI gray palette value.", report);
            var actualUiGray = Render(camera, target, "07-masked-ui-gray.png", output, report);
            surface.sharedMaterial = oracle;
            oracle.mainTexture = expectedUiGray;
            var uiGrayOracle = Render(camera, target, "08-urp-lit-expected-ui-gray.png", output, report);
            surface.sharedMaterial = material;
            material.color = orange;
            for (int y = 0; y < 32; y++)
                for (int x = 16; x < 32; x++) maskBytes[y * 32 + x] = 128;
            mask.LoadRawTextureData(maskBytes); mask.Apply(false, false);
            var halfMasked = Render(camera, target, "09-masked-orange-half-mask.png", output, report);
            var halfExpected = new Color[baseline.Length];
            for (int i = 0; i < baseline.Length; i++)
                halfExpected[i] = Color.Lerp(baseline[i], changed[i], 128f / 255);
            for (int y = 0; y < 32; y++)
                for (int x = 16; x < 32; x++) maskBytes[y * 32 + x] = 255;
            mask.LoadRawTextureData(maskBytes); mask.Apply(false, false);

            var originalZero = Compare("default_vs_original_mask0", original, baseline, MaskZeroRegion, report);
            var originalOne = Compare("default_vs_original_mask1", original, baseline, MaskOneRegion, report);
            var unchanged = Compare("blue_vs_orange_mask0", baseline, changed, MaskZeroRegion, report);
            var recolored = Compare("blue_vs_orange_mask1", baseline, changed, MaskOneRegion, report);
            var ratio = Compare("orange_vs_expected_urp_lit_mask1", changed, expected, MaskOneRegion, report);
            var illumination = Compare("key_light_on_vs_off_mask1", baseline, unlit, MaskOneRegion, report);
            var grayUnchanged = Compare("blue_vs_neutral_gray_mask0", baseline, gray, MaskZeroRegion, report);
            var grayOracle = Compare("neutral_gray_vs_expected_urp_lit_mask1", gray, expectedGray, MaskOneRegion, report);
            var uiUnchanged = Compare("blue_vs_ui_gray_mask0", baseline, actualUiGray, MaskZeroRegion, report);
            var uiOracle = Compare("ui_gray_vs_expected_urp_lit_mask1", actualUiGray, uiGrayOracle, MaskOneRegion, report);
            var halfUnchanged = Compare("blue_vs_half_mask_orange_mask0", baseline, halfMasked, MaskZeroRegion, report);
            var halfBlend = Compare("half_mask_vs_blended_gpu_endpoints_mask1", halfMasked, halfExpected, MaskOneRegion, report);
            var originalTone = MeasureTone("01-masked-default-blue.png", baseline, report);
            var grayTone = MeasureTone("05-masked-neutral-gray.png", gray, report);
            var uiTone = MeasureTone("07-masked-ui-gray.png", actualUiGray, report);
            Require(originalZero.maxChannelDifference == 0 && originalOne.maxChannelDifference == 0,
                "Default blue matches the original albedo rendered by standard URP/Lit in both regions.", report);
            Require(unchanged.maxChannelDifference == 0 && grayUnchanged.maxChannelDifference == 0 &&
                uiUnchanged.maxChannelDifference == 0 && halfUnchanged.maxChannelDifference == 0,
                "Every sampled mask=0 RGB channel is bit-identical for orange, both grays, and the half-mask request.", report);
            Require(recolored.meanChannelDifference > .03f,
                "The sampled mask=1 region visibly changes under the orange request.", report);
            Require(ratio.maxChannelDifference <= OracleTolerance,
                "The recolored region matches an independently textured orange URP/Lit GPU oracle, including source brightness bands.", report);
            Require(illumination.meanChannelDifference > .02f,
                "Switching the real directional light off changes the output; the shader is lit.", report);
            Require(originalTone.meanSaturation > .7f && grayTone.maxRgbSpread <= .00001f,
                "Pure gray removes the strongly saturated source blue: every sampled mask=1 pixel has equal RGB channels.", report);
            Require(grayOracle.maxChannelDifference <= OracleTolerance && uiOracle.maxChannelDifference <= OracleTolerance,
                "Both gray requests match independently textured standard URP/Lit GPU oracles.", report);
            Require(grayTone.upperBandLuminance > grayTone.lowerBandLuminance * 1.25f,
                "Neutral recoloring preserves the source texture's bright and dark bands.", report);
            Require(uiTone.meanSaturation < .4f && uiTone.meanSaturation < originalTone.meanSaturation * .55f,
                "The unchanged UI blue-gray palette renders as low-saturation gray instead of source blue.", report);
            Require(halfBlend.maxChannelDifference <= OracleTolerance,
                "The fractional mask blends the independently rendered GPU endpoints in linear light.", report);
            material.color = neutralGray;
            CheckShadows(pipeline, scene, camera, light, material, target, output, report);
            CaptureMessages(shader, litShader, report);
            Require(!ShaderUtil.ShaderHasError(shader) && !ShaderUtil.ShaderHasError(litShader),
                "ShaderUtil reports no shader compile errors after the actual GPU draws.", report);
            report.passed = true;
            Debug.Log("APPEARANCE_REFERENCE_TINT_CHECKS passed on " + report.graphicsDeviceName + " (" + report.graphicsDeviceType + ").");
        }
        catch (Exception error)
        {
            report.failure = error.ToString();
            throw;
        }
        finally
        {
            CaptureMessages(shader, litShader, report);
            File.WriteAllText(Path.Combine(output, "checks.json"), JsonUtility.ToJson(report, true));
            RenderTexture.active = previousTarget;
            ShaderUtil.allowAsyncCompilation = previousAsync;
            if (target) { target.Release(); Object.DestroyImmediate(target); }
            foreach (var item in owned) if (item) Object.DestroyImmediate(item);
            if (scene.IsValid()) EditorSceneManager.ClosePreviewScene(scene);
        }
    }

    static float Luminance(Color color) => color.r * .2126f + color.g * .7152f + color.b * .0722f;

    static Texture2D Albedo(Color left, Color right, List<Object> owned, bool varyRightHue = false)
    {
        var texture = new Texture2D(32, 32, TextureFormat.RGBAFloat, false, true) {
            name = "Known two-region linear albedo", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp
        };
        owned.Add(texture);
        var pixels = new Color[32 * 32];
        for (int y = 0; y < 32; y++)
            for (int x = 0; x < 32; x++)
            {
                var color = x < 16 ? left : right;
                if (varyRightHue && x >= 16)
                {
                    color.r *= x < 24 ? .25f : 2;
                    color.g *= x < 24 ? .6f : .8f;
                    color.b = (Luminance(right) - color.r * .2126f - color.g * .7152f) / .0722f;
                }
                color *= y < 16 ? .55f : .85f;
                color.a = 1;
                pixels[y * 32 + x] = color;
            }
        texture.SetPixels(pixels);
        texture.Apply(false, false);
        return texture;
    }

    static ToneMetrics MeasureTone(string filename, Color[] pixels, Report report)
    {
        var result = new ToneMetrics { image = filename };
        double saturation = 0, lower = 0, upper = 0;
        int lowerCount = 0, upperCount = 0;
        for (int y = MaskOneRegion.yMin; y < MaskOneRegion.yMax; y++)
            for (int x = MaskOneRegion.xMin; x < MaskOneRegion.xMax; x++)
            {
                var pixel = pixels[y * Size + x];
                float maximum = Mathf.Max(pixel.r, Mathf.Max(pixel.g, pixel.b));
                float minimum = Mathf.Min(pixel.r, Mathf.Min(pixel.g, pixel.b));
                result.maxRgbSpread = Mathf.Max(result.maxRgbSpread, maximum - minimum);
                saturation += maximum > .000001f ? (maximum - minimum) / maximum : 0;
                if (y < Size / 2) { lower += Luminance(pixel); lowerCount++; }
                else { upper += Luminance(pixel); upperCount++; }
            }
        result.meanSaturation = (float)(saturation / (MaskOneRegion.width * MaskOneRegion.height));
        result.lowerBandLuminance = (float)(lower / lowerCount);
        result.upperBandLuminance = (float)(upper / upperCount);
        report.tones.Add(result);
        return result;
    }

    static void CheckShadows(UniversalRenderPipelineAsset pipeline, Scene scene, Camera camera, Light light,
        Material material, RenderTexture target, string output, Report report)
    {
        // PicoURP normally disables shadows. Clone only the asset in memory and keep
        // its existing renderer; never save or change the project's pipeline asset.
        var previousPipeline = QualitySettings.renderPipeline;
        var shadowPipeline = Object.Instantiate(pipeline);
        shadowPipeline.name = "Temporary reference tint shadow check";
        shadowPipeline.hideFlags = HideFlags.HideAndDontSave;
        GameObject caster = null;
        try
        {
            var settings = new SerializedObject(shadowPipeline);
            settings.FindProperty("m_MainLightShadowsSupported").boolValue = true;
            settings.FindProperty("m_AnyShadowsSupported").boolValue = true;
            settings.FindProperty("m_MainLightShadowmapResolution").intValue = 2048;
            settings.FindProperty("m_ShadowCascadeCount").intValue = 1;
            settings.FindProperty("m_ShadowDistance").floatValue = 10;
            settings.ApplyModifiedPropertiesWithoutUndo();
            QualitySettings.renderPipeline = shadowPipeline;
            Require(shadowPipeline.supportsMainLightShadows, "The temporary pipeline supports actual main-light shadows.", report);
            light.shadows = LightShadows.Hard;
            light.shadowStrength = 1;
            light.shadowBias = .001f;
            light.shadowNormalBias = 0;
            caster = GameObject.CreatePrimitive(PrimitiveType.Cube);
            SceneManager.MoveGameObjectToScene(caster, scene);
            caster.name = "Shadow-only masked-shader occluder";
            caster.transform.position = new Vector3(.4f, 0, -.2f);
            caster.transform.localScale = new Vector3(.6f, .6f, .1f);
            var renderer = caster.GetComponent<Renderer>();
            renderer.sharedMaterial = material; // Exercise this shader's ShadowCaster pass too.
            renderer.shadowCastingMode = ShadowCastingMode.ShadowsOnly;
            var shadowed = Render(camera, target, "10-masked-real-shadow.png", output, report);
            renderer.enabled = false;
            var clear = Render(camera, target, "11-masked-shadow-caster-off.png", output, report);
            var shadow = Compare("masked_shader_casts_and_receives_shadow", shadowed, clear,
                new RectInt(160, 104, 40, 48), report);
            Require(shadow.meanChannelDifference > .02f,
                "A real shadow-only occluder using this shader darkens the same shader's receiver.", report);
        }
        finally
        {
            light.shadows = LightShadows.None;
            if (caster) Object.DestroyImmediate(caster);
            QualitySettings.renderPipeline = previousPipeline;
            Object.DestroyImmediate(shadowPipeline);
        }
    }

    static Color[] Render(Camera camera, RenderTexture target, string filename, string output, Report report)
    {
        var request = new UniversalRenderPipeline.SingleCameraRequest { destination = target };
        RenderPipeline.SubmitRenderRequest(camera, request);
        RenderTexture.active = target;
        var readback = new Texture2D(Size, Size, TextureFormat.RGBAFloat, false, true);
        var preview = new Texture2D(Size, Size, TextureFormat.RGBA32, false, false);
        try
        {
            readback.ReadPixels(new Rect(0, 0, Size, Size), 0, 0);
            readback.Apply(false, false);
            var pixels = readback.GetPixels();
            var display = new Color[pixels.Length];
            for (int i = 0; i < pixels.Length; i++)
            {
                var pixel = pixels[i];
                if (float.IsNaN(pixel.r + pixel.g + pixel.b) || float.IsInfinity(pixel.r + pixel.g + pixel.b))
                    throw new InvalidOperationException("GPU produced a non-finite pixel: " + filename);
                display[i] = pixel.gamma;
            }
            preview.SetPixels(display);
            preview.Apply(false, false);
            File.WriteAllBytes(Path.Combine(output, filename), preview.EncodeToPNG());
            report.images.Add(new ImageReceipt { filename = filename,
                maskZeroCenter = pixels[Size * 96 + 80], maskOneCenter = pixels[Size * 96 + 176] });
            return pixels;
        }
        finally { Object.DestroyImmediate(readback); Object.DestroyImmediate(preview); }
    }

    static Comparison Compare(string name, Color[] first, Color[] second, RectInt region, Report report)
    {
        var result = new Comparison { check = name, pixels = region.width * region.height };
        double sum = 0;
        for (int y = region.yMin; y < region.yMax; y++)
            for (int x = region.xMin; x < region.xMax; x++)
                for (int channel = 0; channel < 3; channel++)
                {
                    float difference = Mathf.Abs(first[y * Size + x][channel] - second[y * Size + x][channel]);
                    result.maxChannelDifference = Mathf.Max(result.maxChannelDifference, difference);
                    sum += difference;
                }
        result.meanChannelDifference = (float)(sum / (result.pixels * 3));
        report.comparisons.Add(result);
        return result;
    }

    static void Require(bool success, string description, Report report)
    {
        if (!success) throw new InvalidOperationException(description);
        report.assertions.Add(description);
    }

    static void CaptureMessages(Shader shader, Shader oracle, Report report)
    {
        report.shaderMessages.Clear();
        foreach (var item in new[] { shader, oracle })
            if (item)
                foreach (var message in ShaderUtil.GetShaderMessages(item))
                    report.shaderMessages.Add(new ShaderMessage { shader = item.name,
                        severity = message.severity.ToString(), message = message.message,
                        file = message.file, line = message.line, platform = message.platform.ToString() });
    }
}
