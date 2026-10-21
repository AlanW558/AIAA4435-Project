using UnityEditor;

// Explicit mobile import settings for only the newly authored demo assets.
public sealed class AppearanceAvatarImport : AssetPostprocessor
{
    void OnPreprocessModel()
    {
        if (!assetPath.StartsWith("Assets/Project/Resources/AvatarDemo/")) return;
        var importer = (ModelImporter)assetImporter;
        importer.importCameras = false;
        importer.importLights = false;
        importer.importAnimation = false;
        importer.animationType = ModelImporterAnimationType.Generic;
        importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        importer.isReadable = true; // Real geometry-budget checks query imported triangles.
        importer.meshCompression = ModelImporterMeshCompression.Off;
        importer.importBlendShapes = true;
    }
    void OnPreprocessTexture()
    {
        if (!assetPath.StartsWith("Assets/Project/Resources/AvatarDemo/")) return;
        var importer = (TextureImporter)assetImporter;
        importer.maxTextureSize = 2048;
        importer.alphaIsTransparency = true;
        importer.mipmapEnabled = true;
        if (assetPath.EndsWith("_Mask.png", System.StringComparison.Ordinal))
        {
            importer.textureType = TextureImporterType.SingleChannel;
            var settings = new TextureImporterSettings();
            importer.ReadTextureSettings(settings);
            settings.singleChannelComponent = TextureImporterSingleChannelComponent.Red;
            importer.SetTextureSettings(settings);
            importer.sRGBTexture = false;
            importer.alphaIsTransparency = false;
        }
    }
}
