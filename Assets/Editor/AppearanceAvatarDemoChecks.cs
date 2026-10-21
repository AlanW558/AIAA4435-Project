using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using IAI.Appearance;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

// Real Unity mesh/material/observation checks and reviewer images, never participant data.
public static class AppearanceAvatarDemoChecks
{
    static readonly Color NeutralAmbientLinear = new Color(.3f, .3f, .3f);
    [Serializable] sealed class ReviewLight
    {
        public float intensity;
        public Vector3 rotationEuler;
        public Color color = Color.white;
    }
    [Serializable] sealed class Lighting
    {
        public string scope = "Preview geometry review; independent of the production room.";
        public string ambientProbeMode = "CustomProvided";
        public string ambientProbeMethod = "SphericalHarmonicsL2.AddAmbientLight";
        public Color ambientLinear = NeutralAmbientLinear;
        public ReviewLight[] directionalLights = {
            new ReviewLight { intensity = 1.15f, rotationEuler = new Vector3(25, -30, 0) },
            new ReviewLight { intensity = .5f, rotationEuler = new Vector3(15, 45, 0) },
            new ReviewLight { intensity = .5f, rotationEuler = new Vector3(15, 160, 0) }
        };
    }
    [Serializable] sealed class Item
    {
        public string image;
        public AppearanceState observed;
        public int activeRenderers, activeTriangles;
        public Vector3 boundsMin, boundsMax;
        public Vector3 cameraPosition, cameraForward;
        public float orthographicSize;
    }
    [Serializable] sealed class Report
    {
        public bool passed;
        public string profile = "avatar-demo-v1", unityVersion;
        public Lighting lighting = new Lighting();
        public List<Item> states = new List<Item>();
        public List<Item> detailViews = new List<Item>();
    }
    static void ApplyReviewAmbient(Renderer[] renderers)
    {
        // Preview scenes may have no ambient sky probe. Use the same explicit
        // neutral linear SH probe verified by the isolated ambient diagnostic.
        var probe = new SphericalHarmonicsL2();
        probe.AddAmbientLight(NeutralAmbientLinear);
        foreach (var renderer in renderers)
        {
            renderer.lightProbeUsage = LightProbeUsage.CustomProvided;
            var block = new MaterialPropertyBlock();
            renderer.GetPropertyBlock(block); // Preserve existing material overrides.
            block.CopySHCoefficientArraysFrom(new[] { probe });
            renderer.SetPropertyBlock(block);
        }
    }
    static GameObject Child(string name, Transform parent, Scene scene)
    {
        var go = new GameObject(name); SceneManager.MoveGameObjectToScene(go, scene);
        if (parent) go.transform.SetParent(parent, false);
        return go;
    }
    static Bounds VisibleMeshBounds(Renderer[] renderers)
    {
        // Imported skinned culling bounds extend beyond the visible surface.
        // Evaluate the bind-pose skinning matrices for the actual current pose.
        Bounds bounds = default;
        bool first = true;
        foreach (var renderer in renderers)
        {
            var skin = renderer as SkinnedMeshRenderer;
            var mesh = skin ? skin.sharedMesh : renderer.GetComponent<MeshFilter>().sharedMesh;
            var vertices = mesh.vertices;
            var weights = skin ? mesh.boneWeights : null;
            var matrices = skin ? mesh.bindposes.Select((bind, i) => skin.bones[i].localToWorldMatrix * bind).ToArray() : null;
            foreach (int index in mesh.triangles.Distinct())
            {
                var vertex = vertices[index];
                Vector3 point;
                if (skin)
                {
                    var w = weights[index];
                    point = matrices[w.boneIndex0].MultiplyPoint3x4(vertex) * w.weight0 +
                        matrices[w.boneIndex1].MultiplyPoint3x4(vertex) * w.weight1 +
                        matrices[w.boneIndex2].MultiplyPoint3x4(vertex) * w.weight2 +
                        matrices[w.boneIndex3].MultiplyPoint3x4(vertex) * w.weight3;
                }
                else point = renderer.transform.TransformPoint(vertex);
                if (first) { bounds = new Bounds(point, Vector3.zero); first = false; }
                else bounds.Encapsulate(point);
            }
        }
        return bounds;
    }
    static Item Capture(AppearanceAvatar character, AppearanceState expected, Camera camera,
        RenderTexture texture, string filename, string output)
    {
        character.Apply(expected); character.Create(); character.SetInteraction("ask");
        var actual = new AppearanceState { avatar_id=character.ObservedAvatar, outfit=character.ObservedOutfit,
            jacket_color=character.ObservedColor, accessory=character.ObservedAccessory, scale=character.ObservedScale };
        if (actual.avatar_id != expected.avatar_id || actual.outfit != expected.outfit ||
            actual.jacket_color != expected.jacket_color || actual.accessory != expected.accessory ||
            Mathf.Abs(actual.scale-expected.scale) > .0001f) throw new Exception("Avatar observation mismatch: " + filename);
        var renderers = character.GetComponentsInChildren<Renderer>().Where(r=>r.enabled).ToArray();
        int triangles = renderers.Sum(r => r is SkinnedMeshRenderer skin ? skin.sharedMesh.triangles.Length/3 :
            r.GetComponent<MeshFilter>() ? r.GetComponent<MeshFilter>().sharedMesh.triangles.Length/3 : 0);
        // Current debug import-precheck budget preserves the reference head texture;
        // this is not a PICO performance approval. Device frame rate is unmeasured.
        if (renderers.Length == 0 || renderers.Length > 120 || triangles > 200000)
            throw new Exception("Unexpected avatar geometry budget: " + renderers.Length + " / " + triangles);
        var bounds = VisibleMeshBounds(renderers);
        if (bounds.size.y < 1.70f * expected.scale || bounds.size.y > 2.10f * expected.scale ||
            Mathf.Abs(bounds.min.y) > .06f * expected.scale)
            throw new Exception("Avatar must stand upright with feet at the anchor: " + bounds);
        ApplyReviewAmbient(renderers);
        var request = new UniversalRenderPipeline.SingleCameraRequest { destination = texture };
        if (GraphicsSettings.currentRenderPipeline) RenderPipeline.SubmitRenderRequest(camera, request); else camera.Render();
        RenderTexture.active = texture;
        var image = new Texture2D(texture.width, texture.height, TextureFormat.RGBA32, false);
        try
        {
            image.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0); image.Apply();
            File.WriteAllBytes(Path.Combine(output, filename), image.EncodeToPNG());
            return new Item { image=filename, observed=actual, activeRenderers=renderers.Length,
                activeTriangles=triangles, boundsMin=bounds.min, boundsMax=bounds.max,
                cameraPosition=camera.transform.position, cameraForward=camera.transform.forward,
                orthographicSize=camera.orthographicSize };
        }
        finally { Object.DestroyImmediate(image); }
    }
    static Bounds ItemBounds(Item item)
    {
        return new Bounds((item.boundsMin + item.boundsMax) * .5f, item.boundsMax - item.boundsMin);
    }
    static void FullView(Camera camera, Bounds bounds, Vector3 direction)
    {
        camera.transform.position = bounds.center + direction.normalized * 5;
        camera.transform.LookAt(bounds.center);
        // Fit the complete geometry in this projection, including the side-view tail.
        var right = camera.transform.right;
        var up = camera.transform.up;
        var extents = bounds.extents;
        float horizontal = Mathf.Abs(right.x) * extents.x + Mathf.Abs(right.y) * extents.y + Mathf.Abs(right.z) * extents.z;
        float vertical = Mathf.Abs(up.x) * extents.x + Mathf.Abs(up.y) * extents.y + Mathf.Abs(up.z) * extents.z;
        camera.orthographicSize = Mathf.Max(vertical, horizontal / camera.aspect) * 1.15f;
    }
    public static void Run()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Stop play mode.");
        var report = new Report { unityVersion = Application.unityVersion };
        string output = "StudyData/avatar-v3/unity-preview";
        var args = Environment.GetCommandLineArgs();
        int outputFlag = Array.IndexOf(args, "-appearanceAvatarOutput");
        if (outputFlag >= 0)
        {
            if (outputFlag + 1 >= args.Length || args[outputFlag + 1].StartsWith("-", StringComparison.Ordinal))
                throw new ArgumentException("-appearanceAvatarOutput requires an output directory.");
            output = args[outputFlag + 1];
        }
        output = Path.GetFullPath(output);
        Directory.CreateDirectory(output);
        File.WriteAllText(Path.Combine(output, "checks.json"), JsonUtility.ToJson(report, true));
        var scene = EditorSceneManager.NewPreviewScene();
        RenderTexture texture = null;
        var previous = RenderTexture.active;
        try
        {
            var stage = Child("Avatar review stage", null, scene);
            var character = Child("Shared renderer", stage.transform, scene).AddComponent<AppearanceAvatar>();
            character.Create(); character.EnableDemo(true); character.enabled = false;
            var camera = Child("Review camera", stage.transform, scene).AddComponent<Camera>();
            camera.enabled = false; camera.scene = scene;
            camera.transform.position = new Vector3(0, 1.15f, -5);
            camera.transform.LookAt(new Vector3(0, 1.0f, 0));
            camera.orthographic = true; camera.orthographicSize = 1.2f; camera.aspect = 768f / 1024;
            camera.nearClipPlane = .05f; camera.farClipPlane = 20;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(.82f, .87f, .9f);
            camera.stereoTargetEye = StereoTargetEyeMask.None;
            camera.allowHDR = false; camera.allowMSAA = false;
            camera.GetUniversalAdditionalCameraData().renderPostProcessing = false;
            for (int i = 0; i < report.lighting.directionalLights.Length; i++)
            {
                var config = report.lighting.directionalLights[i];
                var light = Child("Review light " + i, stage.transform, scene).AddComponent<Light>();
                light.type = LightType.Directional; light.intensity = config.intensity; light.color = config.color;
                light.transform.rotation = Quaternion.Euler(config.rotationEuler);
            }
            texture = new RenderTexture(768, 1024, 24) { antiAliasing = 1 }; texture.Create(); camera.targetTexture = texture;
            var states = new[] {
                new AppearanceState { avatar_id="liang", outfit="suit", jacket_color="blue", accessory="glasses", scale=1 },
                new AppearanceState { avatar_id="liang", outfit="suit", jacket_color="purple", accessory="hat", scale=1.1f },
                new AppearanceState { avatar_id="liang", outfit="sport", jacket_color="red", accessory="none", scale=1 },
                new AppearanceState { avatar_id="liang", outfit="none", jacket_color="gray", accessory="none", scale=1 },
                new AppearanceState { avatar_id="nailong", outfit="none", jacket_color="yellow", accessory="none", scale=1 },
                new AppearanceState { avatar_id="nailong", outfit="none", jacket_color="green", accessory="hat", scale=.85f },
                new AppearanceState { avatar_id="liang", outfit="suit", jacket_color="blue", accessory="glasses", scale=1 }
            };
            for (int i = 0; i < states.Length; i++)
            {
                var expected = states[i];
                string filename = i.ToString("00") + "-" + expected.avatar_id + "-" + expected.outfit + ".png";
                report.states.Add(Capture(character, expected, camera, texture, filename, output));
            }
            // The original seven front-view state checks remain unchanged above.
            // Extra images use the same Apply/observed-state/geometry validation.
            var liangBounds = ItemBounds(report.states[0]);
            var faceTarget = new Vector3(liangBounds.center.x,
                liangBounds.min.y + liangBounds.size.y * .83f, liangBounds.center.z);
            camera.transform.position = faceTarget + Vector3.back * 5;
            camera.transform.LookAt(faceTarget);
            camera.orthographicSize = liangBounds.size.y * .205f; // Face, glasses, hair and collar.
            report.detailViews.Add(Capture(character, states[0], camera, texture, "07-liang-default-face-closeup.png", output));
            FullView(camera, liangBounds, new Vector3(-1, 0, -1));
            report.detailViews.Add(Capture(character, states[0], camera, texture, "08-liang-default-three-quarter.png", output));
            var nailongBounds = ItemBounds(report.states[4]);
            FullView(camera, nailongBounds, Vector3.back);
            report.detailViews.Add(Capture(character, states[4], camera, texture, "09-nailong-default-front.png", output));
            FullView(camera, nailongBounds, Vector3.right);
            report.detailViews.Add(Capture(character, states[4], camera, texture, "10-nailong-default-side.png", output));
            // Keep the four original detail views, then inspect accessory fit
            // from an oblique view and the actual Nailong eye line.
            FullView(camera, ItemBounds(report.states[1]), new Vector3(-1, 0, -1));
            report.detailViews.Add(Capture(character, states[1], camera, texture, "11-liang-hat-three-quarter.png", output));
            FullView(camera, ItemBounds(report.states[5]), new Vector3(-1, 0, -1));
            report.detailViews.Add(Capture(character, states[5], camera, texture, "12-nailong-hat-three-quarter.png", output));
            var nailongGlasses = new AppearanceState {
                avatar_id="nailong", outfit="none", jacket_color="yellow", accessory="glasses", scale=1
            };
            var nailongFaceTarget = new Vector3(nailongBounds.center.x,
                nailongBounds.min.y + nailongBounds.size.y * .90f, nailongBounds.center.z);
            camera.transform.position = nailongFaceTarget + Vector3.back * 5;
            camera.transform.LookAt(nailongFaceTarget);
            camera.orthographicSize = nailongBounds.size.y * .205f;
            report.detailViews.Add(Capture(character, nailongGlasses, camera, texture,
                "13-nailong-glasses-face-closeup.png", output));
            // Expose bare neck bridges that collars can hide: shoulder silhouette
            // in three-quarter view, then the chin/neck profile at close range.
            var bareBounds = ItemBounds(report.states[3]);
            FullView(camera, bareBounds, new Vector3(-1, 0, -1));
            report.detailViews.Add(Capture(character, states[3], camera, texture,
                "14-liang-bare-three-quarter.png", output));
            var bareNeckTarget = new Vector3(bareBounds.center.x,
                bareBounds.min.y + bareBounds.size.y * .83f, bareBounds.center.z);
            camera.transform.position = bareNeckTarget + Vector3.right * 5;
            camera.transform.LookAt(bareNeckTarget);
            camera.orthographicSize = .40f;
            report.detailViews.Add(Capture(character, states[3], camera, texture,
                "15-liang-bare-neck-side.png", output));
            character.EnableDemo(false);
            character.Apply(new AppearanceState { jacket_color="orange", accessory="hat", scale=.95f });
            if (character.ObservedAvatar != null || character.ObservedOutfit != null || character.ObservedColor != "orange")
                throw new Exception("Returning to the frozen study renderer failed.");
            report.passed = true;
            File.WriteAllText(Path.Combine(output, "checks.json"), JsonUtility.ToJson(report, true));
            Debug.Log("APPEARANCE_AVATAR_DEMO_CHECKS passed: " + report.states.Count + " mesh states, " +
                report.detailViews.Count + " detail views plus study restore.");
        }
        finally
        {
            RenderTexture.active = previous;
            if (texture) { texture.Release(); Object.DestroyImmediate(texture); }
            EditorSceneManager.ClosePreviewScene(scene);
        }
    }
}
