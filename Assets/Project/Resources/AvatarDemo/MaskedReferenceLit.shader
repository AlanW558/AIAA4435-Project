Shader "IAI/Avatar Demo/Masked Reference Lit"
{
    Properties
    {
        [MainTexture] _BaseMap("Reference albedo", 2D) = "white" {}
        [MainColor] _BaseColor("Requested appearance color", Color) = (1,1,1,1)
        _ReferenceColor("Color already present in albedo", Color) = (1,1,1,1)
        [NoScaleOffset] _TintMask("Tint mask (linear red channel)", 2D) = "black" {}
        _Metallic("Metallic", Range(0,1)) = 0
        _Smoothness("Smoothness", Range(0,1)) = 0.24
        [Toggle(_ALPHATEST_ON)] _AlphaClip("Alpha clipping", Float) = 0
        _Cutoff("Alpha cutoff", Range(0,1)) = 0.45
        [Enum(UnityEngine.Rendering.CullMode)] _Cull("Cull", Float) = 2
        [HideInInspector] _Surface("Surface type", Float) = 0
        [HideInInspector][NoScaleOffset] unity_Lightmaps("Lightmaps", 2DArray) = "" {}
        [HideInInspector][NoScaleOffset] unity_LightmapsInd("Directional lightmaps", 2DArray) = "" {}
        [HideInInspector][NoScaleOffset] unity_ShadowMasks("Shadow masks", 2DArray) = "" {}
    }

    SubShader
    {
        Tags
        {
            "RenderPipeline" = "UniversalPipeline"
            "RenderType" = "Opaque"
            "UniversalMaterialType" = "Lit"
            "IgnoreProjector" = "True"
        }
        LOD 300

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/SurfaceInput.hlsl"

        TEXTURE2D(_TintMask);
        SAMPLER(sampler_TintMask);

        // Shared layout for every pass keeps the material SRP-batcher compatible.
        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            half4 _ReferenceColor;
            half _Metallic;
            half _Smoothness;
            half _Cutoff;
            half _Surface;
        CBUFFER_END

        // LitForwardPass supplies the normal, view, shadow, GI and stereo inputs.
        // Override only its surface initializer; lighting remains URP's real PBR.
        void InitializeStandardLitSurfaceData(float2 uv, out SurfaceData surface)
        {
            half4 source = SampleAlbedoAlpha(uv, TEXTURE2D_ARGS(_BaseMap, sampler_BaseMap));
            half mask = saturate(SAMPLE_TEXTURE2D(_TintMask, sampler_TintMask, uv).r);
            surface = (SurfaceData)0;
            // Keep the reference appearance byte-for-byte, including its original hues.
            // Likewise, a zero mask must never alter skin, hair or fixed fabric.
            surface.albedo = source.rgb;
            if (mask > 0 && any(abs(_BaseColor.rgb - _ReferenceColor.rgb) > 0.0001h))
            {
                // Preserve linear-light brightness detail, not the source cloth's
                // residual blue hue. Neutral requests therefore become neutral.
                const half3 luminanceWeights = half3(0.2126h, 0.7152h, 0.0722h);
                half detail = dot(source.rgb, luminanceWeights) /
                    max(dot(_ReferenceColor.rgb, luminanceWeights), 0.0001h);
                half3 recolored = _BaseColor.rgb * detail;
                surface.albedo = lerp(source.rgb, recolored, mask);
            }
            surface.alpha = Alpha(source.a, _BaseColor, _Cutoff);
            surface.metallic = _Metallic;
            surface.smoothness = _Smoothness;
            surface.normalTS = half3(0,0,1);
            surface.occlusion = 1;
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForwardOnly" }
            ZWrite On
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex LitPassVertex
            #pragma fragment LitPassFragment
            #pragma shader_feature_local_fragment _ALPHATEST_ON
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ EVALUATE_SH_MIXED EVALUATE_SH_VERTEX
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fragment _ _LIGHT_COOKIES
            #pragma multi_compile _ _LIGHT_LAYERS
            #pragma multi_compile _ _FORWARD_PLUS
            #pragma multi_compile _ LIGHTMAP_SHADOW_MIXING
            #pragma multi_compile _ SHADOWS_SHADOWMASK
            #pragma multi_compile _ DIRLIGHTMAP_COMBINED
            #pragma multi_compile _ LIGHTMAP_ON
            #pragma multi_compile _ DYNAMICLIGHTMAP_ON
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #pragma instancing_options renderinglayer
            #include_with_pragmas "Packages/com.unity.render-pipelines.core/ShaderLibrary/FoveatedRenderingKeywords.hlsl"
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RenderingLayers.hlsl"
            // URP 14.0.12's vertex/fragment pair carries UNITY_*_STEREO macros
            // and calls UniversalFragmentPBR; do not replace it with an unlit pass.
            #include "Packages/com.unity.render-pipelines.universal/Shaders/LitForwardPass.hlsl"
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex ShadowPassVertex
            #pragma fragment ShadowPassFragment
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/Shaders/ShadowCasterPass.hlsl"
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex DepthOnlyVertex
            #pragma fragment DepthOnlyFragment
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/Shaders/DepthOnlyPass.hlsl"
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormalsOnly" }
            ZWrite On
            Cull [_Cull]
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex DepthNormalsVertex
            #pragma fragment DepthNormalsFragment
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing
            #pragma instancing_options renderinglayer
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RenderingLayers.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/Shaders/LitDepthNormalsPass.hlsl"
            ENDHLSL
        }
    }
    FallBack Off
}
