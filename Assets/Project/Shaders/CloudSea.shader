Shader "IAI/Cloud Sea"
{
 Properties { _TopColor("Sunlit cloud", Color)=(0.94,0.91,0.86,1) _ShadeColor("Cloud shadow",Color)=(0.60,0.68,0.73,1) }
 SubShader {
 Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="Geometry" }
 Pass {
 HLSLPROGRAM
 #pragma vertex vert
 #pragma fragment frag
 #pragma multi_compile_instancing
 #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
 CBUFFER_START(UnityPerMaterial)
 half4 _TopColor; half4 _ShadeColor;
 CBUFFER_END
 struct A { float4 positionOS:POSITION; float3 normalOS:NORMAL; UNITY_VERTEX_INPUT_INSTANCE_ID };
 struct V { float4 positionCS:SV_POSITION; float3 world:TEXCOORD0; half3 normal:TEXCOORD1; UNITY_VERTEX_OUTPUT_STEREO };
 V vert(A i) { V o; UNITY_SETUP_INSTANCE_ID(i); UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o); o.world=TransformObjectToWorld(i.positionOS.xyz); o.positionCS=TransformWorldToHClip(o.world); o.normal=TransformObjectToWorldNormal(i.normalOS); return o; }
 half4 frag(V i):SV_Target {
 UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
 half light=saturate(dot(normalize(i.normal),normalize(float3(-.7,1,.3)))*.5+.5);
 half valley=saturate((i.world.y+26)/18);
 half3 col=lerp(_ShadeColor.rgb,_TopColor.rgb, saturate(light*.68+valley*.32));
 float dist=length(i.world.xz-_WorldSpaceCameraPos.xz);
 col=lerp(col,half3(.78,.83,.86),saturate(1-exp(-dist*.0018)));
 return half4(col,1); }
 ENDHLSL
 }
 }
}
