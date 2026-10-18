Shader "IAI/Warm Curved Panel"
{
    Properties
    {
        _Tint ("Warm white", Color) = (1,0.94,0.83,1)
        _Visibility ("Visibility", Range(0,1)) = 1
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" }
        Pass
        {
            Tags { "LightMode"="SRPDefaultUnlit" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off Cull Off
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS:POSITION; float2 uv:TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; UNITY_VERTEX_OUTPUT_STEREO };
            CBUFFER_START(UnityPerMaterial)
                half4 _Tint;
                half _Visibility;
            CBUFFER_END
            Varyings Vert(Attributes input)
            {
                Varyings output;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                output.positionCS = TransformObjectToHClip(input.positionOS.xyz);
                output.uv = input.uv;
                return output;
            }
            half4 Frag(Varyings input):SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                float2 p = (input.uv - .5) * float2(.74, .58);
                float2 q = abs(p) - float2(.305, .225);
                float d = length(max(q, 0)) + min(max(q.x, q.y), 0) - .025;
                float inside = 1 - smoothstep(-.001, .002, d);
                // Broad, soft halo rather than an outline; no HDR or post-processing required.
                float halo = exp(-max(d, 0) * 100) * .045;
                float alpha = (inside * .115 + halo) * _Visibility;
                return half4(_Tint.rgb, alpha);
            }
            ENDHLSL
        }
    }
}
