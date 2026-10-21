using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using IAI.Appearance;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

// Editor-only offline materials. No private target JSON is copied into Assets or a build.
public static class AppearanceTaskCards
{
    [Serializable] sealed class Settings
    {
        public int width, height;
        public float orthographic_size;
        public float[] camera_position, camera_target;
    }
    [Serializable] sealed class Job { public string id, image; public AppearanceState state; }
    [Serializable] sealed class Manifest
    {
        public string schema_version, source_sha256, avatar_source_sha256, renderer_source_sha256;
        public Settings render_settings;
        public Job[] jobs;
    }
    [Serializable] sealed class ImageReceipt
    {
        public string id, image, sha256;
        public AppearanceState observed;
    }
    [Serializable] sealed class Receipt
    {
        public string schema_version = "appearance-task-card-render-v1";
        public string manifest_sha256, unity_version, render_mode;
        public ImageReceipt[] images;
    }

    // Use -executeMethod AppearanceTaskCards.RenderFromCommandLine
    //     -appearanceTaskCardManifest <absolute StudyData/pico/.../render-jobs.json>.
    public static void RenderFromCommandLine()
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i + 1 < args.Length; ++i)
            if (args[i] == "-appearanceTaskCardManifest") { RenderManifest(args[i + 1]); return; }
        throw new ArgumentException("Supply -appearanceTaskCardManifest with the prepared job manifest path.");
    }

    public static void RenderManifest(string manifestPath)
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || BuildPipeline.isBuildingPlayer)
            throw new InvalidOperationException("Stop Play mode and finish the active build before rendering materials.");
        string project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string boundary = Path.Combine(project, "StudyData", "pico") + Path.DirectorySeparatorChar;
        manifestPath = Path.GetFullPath(manifestPath);
        var comparison = Application.platform == RuntimePlatform.WindowsEditor ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!manifestPath.StartsWith(boundary, comparison) || Path.GetFileName(manifestPath) != "render-jobs.json")
            throw new ArgumentException("Render jobs must stay under the project's StudyData/pico folder.");
        string output = Path.GetDirectoryName(manifestPath);
        var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(manifestPath));
        if (manifest == null || manifest.schema_version != "appearance-task-card-jobs-v1" || manifest.jobs == null
            || manifest.jobs.Length < 32 || manifest.jobs.Length > 528)
            throw new ArgumentException("Invalid task-card job manifest.");
        if (manifest.source_sha256 != Hash(Path.Combine(project, "Docs/AppearanceExperiment/Study/materials/tasks_private.json"))
            || manifest.avatar_source_sha256 != Hash(Path.Combine(project, "Assets/Project/Scripts/AppearanceExperiment/AppearanceAvatar.cs"))
            || manifest.renderer_source_sha256 != Hash(Path.Combine(project, "Assets/Editor/AppearanceTaskCards.cs")))
            throw new ArgumentException("Task or renderer sources changed. Prepare the materials again.");
        ValidateSettings(manifest.render_settings);
        Directory.CreateDirectory(Path.Combine(output, "images"));
        // Avoid writing through a directory link into Assets or another bundle.
        for (var directory = new DirectoryInfo(Path.Combine(output, "images")); directory != null; directory = directory.Parent)
        {
            if ((directory.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new ArgumentException("Material output directories must not be symbolic links.");
            if (string.Equals(directory.FullName, project, comparison)) break;
        }
        var ids = new HashSet<string>();
        foreach (var job in manifest.jobs)
        {
            if (job == null || string.IsNullOrEmpty(job.id) || !ids.Add(job.id)
                || job.image != "images/" + job.id + ".png"
                || !Regex.IsMatch(job.id, @"^[A-D]_T[1-4]_(initial|target_[0-9]{2})$"))
                throw new ArgumentException("Invalid or duplicate render job path.");
            ValidateState(job.state);
            string image = Path.Combine(output, job.image);
            if (File.Exists(image) && (File.GetAttributes(image) & FileAttributes.ReparsePoint) != 0)
                throw new ArgumentException("Rendered image must not be a symbolic link.");
        }
        string receiptPath = Path.Combine(output, "render-receipt.json");
        if (File.Exists(receiptPath)) File.Delete(receiptPath);
        var scene = EditorSceneManager.NewPreviewScene();
        RenderTexture texture = null;
        var previousTarget = RenderTexture.active;
        try
        {
            var stage = new GameObject("Offline task card preview only");
            SceneManager.MoveGameObjectToScene(stage, scene);
            var avatarObject = Child("Shared AppearanceAvatar", stage.transform, scene);
            var avatar = avatarObject.AddComponent<AppearanceAvatar>();
            avatar.Create();
            avatar.enabled = false; // Freeze the common neutral pose; never rescale the camera per job.
            var camera = Child("Fixed offline camera", stage.transform, scene).AddComponent<Camera>();
            camera.enabled = false;
            camera.scene = scene; // Isolated preview, never the open researcher scene.
            camera.transform.position = new Vector3(0, 1.25f, -5);
            camera.transform.LookAt(new Vector3(0, 1.25f, 0));
            camera.orthographic = true;
            camera.orthographicSize = 1.45f;
            camera.aspect = 768f / 1024f;
            camera.nearClipPlane = .1f;
            camera.farClipPlane = 20;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.94f, .96f, .94f, 1);
            camera.allowHDR = false;
            camera.allowMSAA = false;
            camera.useOcclusionCulling = false;
            camera.stereoTargetEye = StereoTargetEyeMask.None;
            var cameraData = camera.GetUniversalAdditionalCameraData();
            cameraData.renderPostProcessing = false;
            cameraData.renderShadows = false;
            cameraData.antialiasing = AntialiasingMode.None;
            LightFor("Neutral key", stage.transform, scene, new Vector3(25, -30, 0), 1.1f);
            LightFor("Neutral fill", stage.transform, scene, new Vector3(15, 145, 0), .65f);
            texture = new RenderTexture(768, 1024, 24, RenderTextureFormat.ARGB32) { antiAliasing = 1 };
            texture.Create();
            camera.targetTexture = texture;
            bool urp = GraphicsSettings.currentRenderPipeline != null;
            if (urp && !(GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset))
                throw new NotSupportedException("Task card renderer supports the project's URP or the built-in pipeline.");
            var receipts = new List<ImageReceipt>();
            foreach (var job in manifest.jobs)
            {
                avatar.Apply(job.state);
                var observed = new AppearanceState { revision = 0, jacket_color = avatar.ObservedColor,
                    accessory = avatar.ObservedAccessory, scale = avatar.ObservedScale };
                if (observed.jacket_color != job.state.jacket_color || observed.accessory != job.state.accessory
                    || Mathf.Abs(observed.scale - job.state.scale) > .0001f)
                    throw new InvalidOperationException("Shared Avatar did not apply requested appearance: " + job.id);
                if (urp)
                {
                    var request = new UniversalRenderPipeline.SingleCameraRequest { destination = texture };
                    if (!RenderPipeline.SupportsRenderRequest(camera, request))
                        throw new InvalidOperationException("URP camera render requests are unavailable. Run with graphics enabled.");
                    RenderPipeline.SubmitRenderRequest(camera, request);
                }
                else camera.Render();
                RenderTexture.active = texture;
                var pixels = new Texture2D(768, 1024, TextureFormat.RGBA32, false);
                try
                {
                    pixels.ReadPixels(new Rect(0, 0, 768, 1024), 0, 0);
                    pixels.Apply(false, false);
                    CheckVisibleAvatar(pixels);
                    string imagePath = Path.Combine(output, job.image);
                    File.WriteAllBytes(imagePath, pixels.EncodeToPNG());
                    receipts.Add(new ImageReceipt { id = job.id, image = job.image, sha256 = Hash(imagePath), observed = observed });
                }
                finally { Object.DestroyImmediate(pixels); }
            }
            var receipt = new Receipt { manifest_sha256 = Hash(manifestPath), unity_version = Application.unityVersion,
                render_mode = urp ? "URP.SingleCameraRequest" : "Camera.Render", images = receipts.ToArray() };
            File.WriteAllText(receiptPath, JsonUtility.ToJson(receipt, true));
            Debug.Log("Offline task card rendering complete: " + receipts.Count + " genuine shared Avatar images. "
                + "Publish with generate_pico_task_cards.py publish; inspect PNGs before participant use.");
        }
        finally
        {
            RenderTexture.active = previousTarget;
            if (texture != null) { texture.Release(); Object.DestroyImmediate(texture); }
            EditorSceneManager.ClosePreviewScene(scene);
        }
    }

    static GameObject Child(string name, Transform parent, Scene scene)
    {
        var go = new GameObject(name);
        SceneManager.MoveGameObjectToScene(go, scene);
        go.transform.SetParent(parent, false);
        return go;
    }
    static void LightFor(string name, Transform parent, Scene scene, Vector3 rotation, float intensity)
    {
        var light = Child(name, parent, scene).AddComponent<Light>();
        light.type = LightType.Directional; light.color = Color.white;
        light.intensity = intensity; light.shadows = LightShadows.None;
        light.transform.rotation = Quaternion.Euler(rotation);
    }
    static void ValidateSettings(Settings s)
    {
        if (s == null || s.width != 768 || s.height != 1024 || Mathf.Abs(s.orthographic_size - 1.45f) > .0001f
            || s.camera_position == null || s.camera_position.Length != 3 || s.camera_target == null || s.camera_target.Length != 3
            || s.camera_position[0] != 0 || s.camera_position[1] != 1.25f || s.camera_position[2] != -5
            || s.camera_target[0] != 0 || s.camera_target[1] != 1.25f || s.camera_target[2] != 0)
            throw new ArgumentException("Fixed camera settings differ from the material protocol.");
    }
    static void ValidateState(AppearanceState s)
    {
        if (s == null || Array.IndexOf(new[] { "blue", "orange", "green", "gray", "red", "purple" }, s.jacket_color) < 0
            || Array.IndexOf(new[] { "none", "hat", "glasses" }, s.accessory) < 0
            || float.IsNaN(s.scale) || float.IsInfinity(s.scale))
            throw new ArgumentException("Invalid shared Avatar target state.");
        float nearest = Mathf.Round(s.scale * 20) / 20;
        if (nearest < .85f || nearest > 1.15f || Mathf.Abs(s.scale - nearest) > .00001f)
            throw new ArgumentException("Target scale must be on the 0.85–1.15 grid with 0.05 increments.");
    }
    static void CheckVisibleAvatar(Texture2D image)
    {
        Color32[] pixels = image.GetPixels32();
        Color32 background = pixels[0];
        int foreground = 0, magenta = 0;
        for (int y = 180; y < 920; y += 3)
            for (int x = 220; x < 548; x += 3)
            {
                var p = pixels[y * 768 + x];
                if (Math.Abs(p.r - background.r) + Math.Abs(p.g - background.g) + Math.Abs(p.b - background.b) < 35) continue;
                foreground++;
                if (p.r > 220 && p.g < 60 && p.b > 220) magenta++;
            }
        if (foreground < 100 || magenta > foreground / 4)
            throw new InvalidOperationException("Blank or missing-shader camera output; no successful receipt written.");
    }
    static string Hash(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
}
