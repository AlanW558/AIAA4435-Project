// Editor-baked sky source. The shipping scene samples a static cubemap;
// this ray marcher is never needed per eye at runtime.
Shader "IAI/Cloud Sky Bake" {
 SubShader { Tags {"Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox"} Cull Off ZWrite Off
 Pass { HLSLPROGRAM
 #pragma target 3.5
 #pragma vertex vert
 #pragma fragment frag
 #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
 struct A {float4 vertex:POSITION;};
 struct V {float4 pos:SV_POSITION;float3 dir:TEXCOORD0;};
 V vert(A i){V o;o.pos=TransformObjectToHClip(i.vertex.xyz);o.dir=i.vertex.xyz;return o;}
 float hash(float3 p){p=frac(p*.1031);p+=dot(p,p.yzx+33.33);return frac((p.x+p.y)*p.z);}
 float noise(float3 p){float3 i=floor(p),f=frac(p);f=f*f*(3-2*f);
 return lerp(lerp(lerp(hash(i),hash(i+float3(1,0,0)),f.x),lerp(hash(i+float3(0,1,0)),hash(i+float3(1,1,0)),f.x),f.y),lerp(lerp(hash(i+float3(0,0,1)),hash(i+float3(1,0,1)),f.x),lerp(hash(i+float3(0,1,1)),hash(i+float3(1,1,1)),f.x),f.y),f.z);}
 float density(float3 p){
 float n=noise(p*.032+float3(17,2,31))*.62+noise(p*.085+float3(6,19,4))*.26+noise(p*.19)*.12;
 float top=-19+noise(p.xzz*.018+17)*18;
 float height=saturate((top-p.y)*.32)*saturate((p.y+60)*.14);
 return saturate((n-.43)*5.0)*height;
 }
 half4 frag(V i):SV_Target {
 float3 d=normalize(i.dir);float3 horizon=float3(.70,.78,.84);float3 sky=lerp(horizon,float3(.26,.46,.65),pow(saturate(d.y),.6));
 float sun=pow(saturate(dot(d,normalize(float3(-1,.65,.45)))),200);sky+=float3(.33,.22,.1)*sun;
 if(d.y>=-.002)return half4(sky,1);
 float3 origin=float3(0,25.2,0);float t0=(-2-origin.y)/d.y;float t1=min((-59-origin.y)/d.y,1600);
 if(t0>=t1)return half4(horizon,1);
 float dt=(t1-t0)/384;float trans=1;float3 total=0;
 [loop] for(int step=0;step<384;step++) {
 float t=t0+(step+.5)*dt;float3 p=origin+d*t;float den=density(p);
 float shade=exp(-density(p+float3(-1,1.1,.5))*3.8-density(p+float3(-3,3.3,1.5))*1.8);
 float3 colour=lerp(float3(.32,.41,.53),float3(1.05,.98,.86),shade*.85+.12);
 colour=lerp(colour,horizon,saturate(t/2500));
 float alpha=1-exp(-den*dt*.22);total+=trans*alpha*colour;trans*=1-alpha;
 if(trans<.012)break;
 }
 return half4(total+trans*horizon,1);
 }
 ENDHLSL }
 }
}
