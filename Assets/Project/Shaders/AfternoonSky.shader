Shader "IAI/Afternoon Sky" {
 Properties { _Zenith("Zenith",Color)=(.37,.58,.74,1) _Horizon("Horizon",Color)=(.80,.84,.87,1) }
 SubShader { Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" } Cull Off ZWrite Off
 Pass { HLSLPROGRAM
 #pragma vertex vert
 #pragma fragment frag
 #pragma multi_compile_instancing
 #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
 CBUFFER_START(UnityPerMaterial)
 half4 _Zenith; half4 _Horizon;
 CBUFFER_END
 struct A {float4 vertex:POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID};
 struct V {float4 positionCS:SV_POSITION; float3 dir:TEXCOORD0; UNITY_VERTEX_OUTPUT_STEREO};
 V vert(A i){V o; UNITY_SETUP_INSTANCE_ID(i); UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o); o.positionCS=TransformObjectToHClip(i.vertex.xyz);o.dir=i.vertex.xyz;return o;}
 half4 frag(V i):SV_Target { UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i); float3 d=normalize(i.dir); half3 c=lerp(_Horizon.rgb,_Zenith.rgb,pow(saturate(d.y),.6)); float sun=pow(saturate(dot(d,normalize(float3(-1,.65,.45)))),180); c+=half3(.35,.23,.09)*sun; return half4(c,1);}
 ENDHLSL }
 }
}
