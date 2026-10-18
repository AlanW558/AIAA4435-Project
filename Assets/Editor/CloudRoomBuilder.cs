using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEditor;
using UnityEditor.SceneManagement;
using Unity.XR.CoreUtils;
using UnityEngine.XR.Interaction.Toolkit;
using IAI.Environment;
using Object = UnityEngine.Object;

// All generated assets live in dedicated Room subfolders. Rebuild explicitly from the menu.
public static class CloudRoomBuilder
{
    const string Root="Assets/Project/";
    public const float RoomWidth=11.5f, RoomLength=64f/3f, RoomHeight=6.75f;
    public const string ScenePath=Root+"Scenes/CloudConversationRoom.unity";
    static readonly Dictionary<string,Mesh> meshes=new Dictionary<string,Mesh>();
    static Material wall, ceiling, slabEdge, oak, linen, metal, shadow, floor;
    static readonly HashSet<string> importedTextures=new HashSet<string>();
    static Transform architecture;
    static Color Hex(string h) { Color c; ColorUtility.TryParseHtmlString("#"+h,out c);return c; }
    static T Save<T>(T asset,string path) where T:Object
    {
        var old=AssetDatabase.LoadAssetAtPath<T>(path);
        if(old!=null) {
            // Mesh serialization alone can leave stale GPU index buffers after a topology change.
            if(asset is Mesh source && old is Mesh target) {
                target.Clear();target.indexFormat=source.indexFormat;target.vertices=source.vertices;target.normals=source.normals;target.tangents=source.tangents;target.uv=source.uv;target.uv2=source.uv2;target.triangles=source.triangles;target.RecalculateBounds();target.UploadMeshData(false);
            } else EditorUtility.CopySerialized(asset,old);
            Object.DestroyImmediate(asset); EditorUtility.SetDirty(old);return old;
        }
        AssetDatabase.CreateAsset(asset,path);return asset;
    }
    static Material Mat(string name,string color,float smooth=0.2f,float metallic=0)
    {
        var m=new Material(Shader.Find("Universal Render Pipeline/Lit")){name=name};
        m.SetColor("_BaseColor",Hex(color));m.SetFloat("_Smoothness",smooth);m.SetFloat("_Metallic",metallic);
        m.enableInstancing=true;return Save(m,Root+"Materials/Room/"+name+".mat");
    }
    static void Texture(Material m,string stem,string suffix,string property,bool normal=false)
    {
        string path=Root+"Textures/Room/"+stem+suffix+".png";
        var imp=AssetImporter.GetAtPath(path) as TextureImporter;
        if(imp==null) throw new Exception("Missing texture "+path);
        bool needsImport=imp.anisoLevel!=16 || imp.filterMode!=FilterMode.Trilinear || imp.textureType!=(normal?TextureImporterType.NormalMap:TextureImporterType.Default) || !imp.GetPlatformTextureSettings("Android").overridden;
        imp.textureType=normal?TextureImporterType.NormalMap:TextureImporterType.Default;
        imp.sRGBTexture=!normal && property!="_MetallicGlossMap";
        imp.maxTextureSize=stem.StartsWith("Oak")?4096:1024;
        imp.mipmapEnabled=true;imp.anisoLevel=16;imp.filterMode=FilterMode.Trilinear;
        imp.wrapMode=TextureWrapMode.Repeat;imp.textureCompression=TextureImporterCompression.CompressedHQ;
        var android=imp.GetPlatformTextureSettings("Android"); android.overridden=true;android.maxTextureSize=imp.maxTextureSize;
        android.format=TextureImporterFormat.ASTC_4x4;android.compressionQuality=100;imp.SetPlatformTextureSettings(android);
        if(importedTextures.Add(path) && needsImport)imp.SaveAndReimport();m.SetTexture(property,AssetDatabase.LoadAssetAtPath<Texture2D>(path));
        if(normal) {m.EnableKeyword("_NORMALMAP");m.SetFloat("_BumpScale",.32f);}
        if(property=="_MetallicGlossMap") {m.EnableKeyword("_METALLICSPECGLOSSMAP");m.SetFloat("_Smoothness",1);}
        EditorUtility.SetDirty(m);
    }
    static void ScannedOak(Material m)
    {
        foreach(var channel in new[]{"diff","nor_gl"}) {
            string path=Root+"Textures/Room/PolyHaven/oak_veneer_01_"+channel+"_4k.jpg";
            var imp=(TextureImporter)AssetImporter.GetAtPath(path);if(imp==null)throw new Exception("Scanned oak texture missing: "+path);
            bool normal=channel=="nor_gl";
            bool needs=imp.anisoLevel!=16 || !imp.GetPlatformTextureSettings("Android").overridden;
            if(needs && importedTextures.Add(path)) {
                imp.textureType=normal?TextureImporterType.NormalMap:TextureImporterType.Default;imp.sRGBTexture=!normal;imp.maxTextureSize=4096;
                imp.mipmapEnabled=true;imp.anisoLevel=16;imp.filterMode=FilterMode.Trilinear;imp.wrapMode=TextureWrapMode.Repeat;
                var settings=imp.GetPlatformTextureSettings("Android");settings.overridden=true;settings.maxTextureSize=4096;settings.format=TextureImporterFormat.ASTC_4x4;settings.compressionQuality=50;imp.SetPlatformTextureSettings(settings);imp.SaveAndReimport();
            }
            m.SetTexture(normal?"_BumpMap":"_BaseMap",AssetDatabase.LoadAssetAtPath<Texture2D>(path));
        }
        m.EnableKeyword("_NORMALMAP");m.SetFloat("_BumpScale",.18f);EditorUtility.SetDirty(m);
    }
    static void Materials()
    {
        importedTextures.Clear();
        wall=Mat("Warm Greige Plaster","DED8CC",.13f);ceiling=Mat("Matte Warm Charcoal Ceiling","484A48",.08f);slabEdge=Mat("Warm White Slab Edge","F1EEE7",.1f);
        oak=Mat("Natural Oak Furniture","E2C5A3",.26f);floor=Mat("Pale Oak Floor","FFF2DB",.22f);
        foreach(var m in new[]{oak,floor}) ScannedOak(m);
        oak.SetColor("_BaseColor",new Color(1.04f,1.07f,1.12f));floor.SetColor("_BaseColor",new Color(1.15f,1.25f,1.45f));floor.SetFloat("_BumpScale",.1f);
        linen=Mat("Sand Linen","D6CBB8",.08f);Texture(linen,"Linen_","Albedo_1K","_BaseMap");Texture(linen,"Linen_","Normal_1K","_BumpMap",true);
        metal=Mat("Satin Champagne Aluminium","B7AC97",.38f,.65f);
        shadow=Mat("Recess Shadow","57534B",.1f);
    }
    static Transform Group(string name,Transform parent=null) {var g=new GameObject(name);g.transform.SetParent(parent,false);return g.transform;}
    static void Static(GameObject g) {GameObjectUtility.SetStaticEditorFlags(g,StaticEditorFlags.ContributeGI|StaticEditorFlags.BatchingStatic|StaticEditorFlags.ReflectionProbeStatic|StaticEditorFlags.OccluderStatic|StaticEditorFlags.OccludeeStatic);}
    static GameObject MeshObject(string name,Mesh mesh,Material mat,Transform parent,Vector3 position,bool bake=true)
    {
        var go=new GameObject(name);go.transform.SetParent(parent,false);go.transform.localPosition=position;
        go.AddComponent<MeshFilter>().sharedMesh=mesh;var r=go.AddComponent<MeshRenderer>();r.sharedMaterial=mat;
        if(bake) {Static(go);r.receiveGI=ReceiveGI.Lightmaps;}return go;
    }
    static Mesh AssetMesh(string name,Mesh m,bool uv2=true)
    {
        m.name=name;m.RecalculateNormals();m.RecalculateBounds();m.RecalculateTangents();
        if(uv2) Unwrapping.GenerateSecondaryUVSet(m);
        return Save(m,Root+"Models/Room/"+name+".asset");
    }
    // Rounded rectangle extruded through several bevel rings; dimensions are real metres.
    static Mesh Rounded(string id,float w,float h,float d,float radius,float bevel,float uvScale=1,bool turnGrain=false)
    {
        if(meshes.ContainsKey(id))return meshes[id];
        var v=new List<Vector3>();var uv=new List<Vector2>();var tris=new List<int>();
        int segments=id.StartsWith("Plank_")?1:12, steps=id.StartsWith("Plank_")?1:4, n=4*(segments+1);var rings=new List<Vector2>();
        for(int i=0;i<=steps;i++){float a=i*Mathf.PI/(2*steps);rings.Add(new Vector2(-h/2+bevel*(1-Mathf.Cos(a)),bevel*(1-Mathf.Sin(a))));}
        for(int i=0;i<=steps;i++){float a=i*Mathf.PI/(2*steps);rings.Add(new Vector2(h/2-bevel+bevel*Mathf.Sin(a),bevel*(1-Mathf.Cos(a))));}
        foreach(var ring in rings)
        {
            float rw=w/2-ring.y,rd=d/2-ring.y,rr=Mathf.Max(.001f,radius-ring.y);
            for(int c=0;c<4;c++)for(int j=0;j<=segments;j++)
            {
                float a=(c*90+j*90f/segments)*Mathf.Deg2Rad;
                float cx=(c==0||c==3?1:-1)*(rw-rr),cz=(c<2?1:-1)*(rd-rr);
                var p=new Vector3(cx+rr*Mathf.Cos(a),ring.x,cz+rr*Mathf.Sin(a));v.Add(p);
                uv.Add(turnGrain?new Vector2(p.z/.85f,p.x/1.8f):new Vector2(p.x*uvScale,p.z*uvScale));
            }
        }
        for(int r=0;r<rings.Count-1;r++)for(int j=0;j<n;j++)
        {int a=r*n+j,b=r*n+(j+1)%n,c=b+n,e=a+n;tris.AddRange(new[]{a,e,c,a,c,b});}
        int bottom=v.Count;v.Add(new Vector3(0,-h/2,0));uv.Add(Vector2.zero);
        int top=v.Count;v.Add(new Vector3(0,h/2,0));uv.Add(Vector2.zero);
        for(int j=0;j<n;j++){int k=(j+1)%n;tris.AddRange(new[]{bottom,j,k,top,(rings.Count-1)*n+k,(rings.Count-1)*n+j});}
        var m=new Mesh();m.SetVertices(v);m.SetUVs(0,uv);m.SetTriangles(tris,0);m=AssetMesh(id,m);meshes[id]=m;return m;
    }
    static GameObject Box(string name,Vector3 p,Vector3 size,Material m,Transform parent,float bevel=.006f,float radius=.01f,bool collider=false,float uvScale=1,bool grain=false)
    {
        bevel=Mathf.Min(bevel,Mathf.Min(size.y/3,Mathf.Min(size.x,size.z)/4));radius=Mathf.Min(radius,Mathf.Min(size.x,size.z)/2);
        string id=name.Replace(" ","_")+"_"+size.x.ToString("F3")+"_"+size.y.ToString("F3")+"_"+size.z.ToString("F3");
        var go=MeshObject(name,Rounded(id,size.x,size.y,size.z,radius,bevel,uvScale,grain),m,parent,p);
        if(collider){var c=go.AddComponent<BoxCollider>();c.size=size;}return go;
    }
    static void Beam(string name,Vector3 a,Vector3 b,float radiusA,float radiusB,Material mat,Transform parent)
    {
        const int seg=24;float length=Vector3.Distance(a,b);string id=name.Replace(" ","_")+"_"+length.ToString("F3")+"_"+radiusA.ToString("F3")+"_"+radiusB.ToString("F3");
        Mesh m;
        if(!meshes.TryGetValue(id,out m)) {
        var vs=new List<Vector3>();var uv=new List<Vector2>();var ts=new List<int>();
        for(int r=0;r<4;r++)for(int i=0;i<=seg;i++) {float t=i*2*Mathf.PI/seg;float rr=r<2?radiusA:radiusB;float y=r==0?0:r==1?.003f:r==2?length-.003f:length; if(r==0||r==3)rr-=.003f;vs.Add(new Vector3(Mathf.Cos(t)*rr,y,Mathf.Sin(t)*rr));uv.Add(new Vector2(i/(float)seg,y/.8f));}
        for(int r=0;r<3;r++)for(int j=0;j<seg;j++){int a0=r*(seg+1)+j;ts.AddRange(new[]{a0,a0+seg+1,a0+seg+2,a0,a0+seg+2,a0+1});}
        int cb=vs.Count;vs.Add(Vector3.zero);uv.Add(Vector2.zero);int ct=vs.Count;vs.Add(Vector3.up*length);uv.Add(Vector2.zero);
        for(int i=0;i<seg;i++)ts.AddRange(new[]{cb,i,i+1,ct,3*(seg+1)+i+1,3*(seg+1)+i});
        m=new Mesh();m.SetVertices(vs);m.SetUVs(0,uv);m.SetTriangles(ts,0);m=AssetMesh(id,m);meshes[id]=m;}
        var go=MeshObject(name,m,mat,parent,a);go.transform.localRotation=Quaternion.FromToRotation(Vector3.up,b-a);
    }
    static void Architecture()
    {
        float w=RoomWidth,l=RoomLength,h=RoomHeight,hw=w/2,hl=l/2;
        architecture=Group("01 Architecture — 21.33m × 11.5m × 6.75m");
        Box("Floor Slab",new Vector3(-.3f,-.18f,0),new Vector3(w+.6f,.32f,l+.4f),slabEdge,architecture,.012f,.02f,true);
        Box("Front Wall",new Vector3(0,h/2,hl+.12f),new Vector3(w+.4f,h,.24f),wall,architecture,.008f,.01f,true);
        Box("Rear Wall",new Vector3(0,h/2,-hl-.12f),new Vector3(w+.4f,h,.24f),wall,architecture,.008f,.01f,true);
        Box("Right Wall",new Vector3(hw+.12f,h/2,0),new Vector3(.24f,h,l+.25f),wall,architecture,.008f,.01f,true);
        Box("Roof Slab — 600mm Overhang",new Vector3(-.3f,h+.18f,0),new Vector3(w+.6f,.36f,l+.4f),ceiling,architecture,.012f,.02f,true);
        Box("Ceiling — Matte Warm Charcoal Plane",new Vector3(0,h+.025f,0),new Vector3(w-.06f,.05f,l-.06f),ceiling,architecture,.006f,.01f);
        Box("Ceiling Shadow Gap",new Vector3(0,h+.06f,0),new Vector3(w+.02f,.02f,l+.02f),shadow,architecture,.001f,.002f);
        foreach(float z in new[]{-hl+.005f,hl-.005f})Box("Flush Oak Skirting",new Vector3(0,.045f,z),new Vector3(w,.09f,.012f),oak,architecture,.002f,.003f);
        Box("Flush Oak Skirting",new Vector3(hw-.005f,.045f,0),new Vector3(.012f,.09f,l),oak,architecture,.002f,.003f);
        var underlay=Box("Dark Recess Below Board Joints",new Vector3(0,-.01f,0),new Vector3(w,.01f,l),shadow,architecture,.001f,.002f);
        GameObjectUtility.SetStaticEditorFlags(underlay,StaticEditorFlags.BatchingStatic);underlay.GetComponent<MeshRenderer>().receiveGI=ReceiveGI.LightProbes;
        Flooring();
        var glazing=Group("02 Glazing — 8 bays, recessed 600mm");
        var glass=Mat("Low Iron Architectural Glass","E5F1F0",.88f);
        glass.SetFloat("_Surface",1);glass.SetFloat("_Blend",0);glass.SetFloat("_SrcBlend",(int)BlendMode.SrcAlpha);glass.SetFloat("_DstBlend",(int)BlendMode.OneMinusSrcAlpha);glass.SetFloat("_ZWrite",0);
        glass.SetColor("_BaseColor",new Color(.88f,.95f,.95f,.045f));glass.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");glass.renderQueue=3000;glass.SetOverrideTag("RenderType","Transparent");glass.SetShaderPassEnabled("ShadowCaster",false);EditorUtility.SetDirty(glass);
        const int bays=8;float bay=l/bays;
        for(int i=0;i<bays;i++) {
            var g=Box("Glass Pane "+(i+1),new Vector3(-hw,h/2,-hl+(i+.5f)*bay),new Vector3(.012f,h-.08f,bay-.04f),glass,glazing,.001f,.002f,true);
            g.GetComponent<Renderer>().shadowCastingMode=ShadowCastingMode.Off;GameObjectUtility.SetStaticEditorFlags(g,StaticEditorFlags.BatchingStatic);
        }
        for(int i=0;i<=bays;i++)Box("Slender Vertical Mullion",new Vector3(-hw,h/2,-hl+i*bay),new Vector3(.065f,h,.038f),metal,glazing,.004f,.007f);
        foreach(float y in new[]{.025f,h-.025f})Box("Recessed Glazing Track",new Vector3(-hw,y,0),new Vector3(.09f,.05f,l+.1f),metal,glazing,.004f,.008f);
    }
    static void Flooring()
    {
        // A continuous, non-overlapping world-space lightmap UV layout. Physical
        // board gaps remain, without thousands of tiny underside lightmap charts.
        var group=Group("Oak Planks — staggered, 2m grain repeat",architecture);var rand=new System.Random(4435);
        var vertices=new List<Vector3>();var uv=new List<Vector2>();var lightUV=new List<Vector2>();
        var triangles=new List<int>[6];var materials=new Material[6];for(int i=0;i<6;i++)triangles[i]=new List<int>();
        int columns=Mathf.CeilToInt(RoomWidth/.22f);float width=RoomWidth/columns;
        for(int col=0;col<columns;col++) {
            float z=-RoomLength/2-(col%3)*.66f;
            while(z<RoomLength/2) {
                float start=Mathf.Max(z,-RoomLength/2)+.00075f,end=Mathf.Min(z+2,RoomLength/2)-.00075f;z+=2;if(end-start<.01f)continue;
                float x0=-RoomWidth/2+col*width+.00075f,x1=x0+width-.0015f;int first=vertices.Count;
                float u=(float)rand.NextDouble(),v=(float)rand.NextDouble();
                foreach(var pt in new[]{new Vector3(x0,0,start),new Vector3(x0,0,end),new Vector3(x1,0,end),new Vector3(x1,0,start)}) {
                    vertices.Add(pt);uv.Add(new Vector2((pt.x-x0)/1.8f+u,(pt.z-start)/2+v));
                    lightUV.Add(new Vector2(.01f+.98f*(pt.x/RoomWidth+.5f),.01f+.98f*(pt.z/RoomLength+.5f)));
                }
                triangles[rand.Next(6)].AddRange(new[]{first,first+1,first+2,first,first+2,first+3});
            }
        }
        for(int i=0;i<6;i++) {
            var mat=new Material(floor){name="Oak Plank Tone "+i};mat.SetColor("_BaseColor",new Color(1.15f,1.25f,1.45f)*(.96f+i*.012f));
            materials[i]=Save(mat,Root+"Materials/Room/Oak Plank Tone "+i+".mat");
        }
        var mesh=new Mesh{name="Oak Floor Surface"};mesh.SetVertices(vertices);mesh.SetUVs(0,uv);mesh.SetUVs(1,lightUV);mesh.subMeshCount=6;
        for(int i=0;i<6;i++)mesh.SetTriangles(triangles[i],i);
        mesh.RecalculateNormals();mesh.RecalculateTangents();mesh.RecalculateBounds();
        // A distinct asset keeps all six submeshes intact and avoids the generic single-submesh helper.
        string path=Root+"Models/Room/OakFloorSurface.asset";var old=AssetDatabase.LoadAssetAtPath<Mesh>(path);
        if(old==null)AssetDatabase.CreateAsset(mesh,path);else {
            old.Clear();old.vertices=mesh.vertices;old.normals=mesh.normals;old.tangents=mesh.tangents;old.uv=mesh.uv;old.uv2=mesh.uv2;old.subMeshCount=6;
            for(int i=0;i<6;i++)old.SetTriangles(mesh.GetTriangles(i),i);old.RecalculateBounds();old.UploadMeshData(false);Object.DestroyImmediate(mesh);mesh=old;EditorUtility.SetDirty(old);
        }
        var go=MeshObject("Oak Floor — six plank tones",mesh,materials[0],group,Vector3.zero);go.GetComponent<MeshRenderer>().sharedMaterials=materials;
        var collision=group.gameObject.AddComponent<BoxCollider>();collision.center=new Vector3(0,-.025f,0);collision.size=new Vector3(RoomWidth,.05f,RoomLength);
    }
    static Transform Table()
    {
        var t=Group("Meeting Table — 1800 × 850 × 740mm");
        Box("Rounded Oak Top",new Vector3(0,.72f,0),new Vector3(1.8f,.04f,.85f),oak,t,.009f,.09f,true,1,true);
        Box("Underframe Long",new Vector3(0,.663f,0),new Vector3(1.45f,.08f,.52f),oak,t,.008f,.045f);
        foreach(float x in new[]{-.68f,.68f})foreach(float z in new[]{-.27f,.27f})
            Beam("Tapered Oak Leg",new Vector3(x*1.06f,.006f,z*1.12f),new Vector3(x,.697f,z),.023f,.036f,oak,t);
        return t;
    }
    static Mesh CurvedBack(string id,float width,float bottom,float top,float thickness,float outset)
    {
        if(meshes.ContainsKey(id))return meshes[id];
        const int seg=48;var vs=new List<Vector3>();var uv=new List<Vector2>();var ts=new List<int>();
        // Closed bent timber/foam shell, front faces towards +Z.
        for(int side=0;side<2;side++)for(int row=0;row<2;row++)for(int i=0;i<=seg;i++) {
            float u=i/(float)seg,angle=(u-.5f)*1.9f;
            float x=Mathf.Sin(angle)*width/(2*Mathf.Sin(.95f));float z=-.075f-Mathf.Cos(angle)*.18f+side*thickness+outset;
            float y=row==0?bottom:top-.025f*Mathf.Pow(Mathf.Abs(u-.5f)*2,4);
            vs.Add(new Vector3(x,y,z));uv.Add(id.Contains("Linen")?new Vector2(x/.12f,y/.12f):new Vector2(x/1.8f,y/2));
        }
        int n=seg+1;
        for(int i=0;i<seg;i++) {ts.AddRange(new[]{i,n+i+1,n+i,i,i+1,n+i+1});int j=2*n+i;ts.AddRange(new[]{j,j+n,j+n+1,j,j+n+1,j+1});ts.AddRange(new[]{i,2*n+i,2*n+i+1,i,2*n+i+1,i+1});j=n+i;ts.AddRange(new[]{j,j+1,j+2*n+1,j,j+2*n+1,j+2*n});}
        ts.AddRange(new[]{0,n,3*n,0,3*n,2*n,seg,3*n-1,4*n-1,seg,4*n-1,2*n-1});
        for(int i=0;i<ts.Count;i+=3){int tmp=ts[i+1];ts[i+1]=ts[i+2];ts[i+2]=tmp;}
        var m=new Mesh();m.SetVertices(vs);m.SetUVs(0,uv);m.SetTriangles(ts,0);m=AssetMesh(id,m);meshes[id]=m;return m;
    }
    static Transform Chair(string name,Vector3 pos,float yaw)
    {
        var t=Group(name);t.localPosition=pos;t.localRotation=Quaternion.Euler(0,yaw,0);
        Box("Rounded Seat Frame",new Vector3(0,.413f,0),new Vector3(.53f,.045f,.52f),oak,t,.008f,.075f);
        Box("Tailored Linen Cushion",new Vector3(0,.459f,.008f),new Vector3(.485f,.07f,.465f),linen,t,.022f,.08f,true,1/.12f);
        // Thin piping catches light without a thick cartoon outline.
        var piping=Mat("Linen Piping","C7BAA3",.11f);
        Box("Cushion Welt Seam",new Vector3(0,.449f,.008f),new Vector3(.491f,.004f,.471f),piping,t,.001f,.081f);
        foreach(float x in new[]{-.205f,.205f})foreach(float z in new[]{-.185f,.185f})
            Beam("Splayed Timber Chair Leg",new Vector3(x*1.17f,.005f,z*1.15f),new Vector3(x,.415f,z),.016f,.024f,oak,t);
        MeshObject("Curved Timber Back Shell",CurvedBack("Bent_Oak_Back",.52f,.57f,.99f,.023f,0),oak,t,Vector3.zero);
        MeshObject("Curved Upholstered Back Pad",CurvedBack("Curved_Linen_Back",.455f,.605f,.955f,.023f,.028f),linen,t,Vector3.zero);
        foreach(float x in new[]{-.255f,.255f}) {
            Beam("Rear Back Support",new Vector3(x*.76f,.405f,-.185f),new Vector3(x*.91f,.865f,-.19f),.018f,.016f,oak,t);
            Beam("Arm Upright",new Vector3(x*.83f,.42f,.13f),new Vector3(x,.64f,.13f),.014f,.014f,oak,t);
            Box("Softly Rounded Armrest",new Vector3(x,.662f,-.015f),new Vector3(.055f,.033f,.41f),oak,t,.012f,.026f);
        }
        return t;
    }
    static void Furniture()
    {
        var group=Group("03 Furniture — one table, two chairs");
        var table=Table();table.SetParent(group,true);
        var user=Chair("User Chair",new Vector3(0,0,-.80f),0);user.SetParent(group,true);
        var tutor=Chair("Tutor Chair",new Vector3(0,0,.80f),180);tutor.SetParent(group,true);
        foreach(var r in group.GetComponentsInChildren<MeshRenderer>()){var so=new SerializedObject(r);so.FindProperty("m_ScaleInLightmap").floatValue=2;so.ApplyModifiedPropertiesWithoutUndo();}
        PrefabUtility.SaveAsPrefabAsset(table.gameObject,Root+"Prefabs/Room/OakMeetingTable.prefab");
        PrefabUtility.SaveAsPrefabAsset(user.gameObject,Root+"Prefabs/Room/OakLinenArmchair.prefab");
        var decor=Group("04 Optional Table Decor");
        var book=Group("Closed Notebook",decor);book.localPosition=new Vector3(-.59f,.742f,-.23f);book.localRotation=Quaternion.Euler(0,-8,0);
        var cover=Mat("Notebook Sand Cover","B4A78D",.09f);var pages=Mat("Warm Ivory Paper","ECE6D8",.05f);
        Box("Paper Block",new Vector3(0,.009f,0),new Vector3(.133f,.014f,.196f),pages,book,.002f,.004f);
        foreach(float y in new[]{.001f,.018f})Box("Notebook Cover",new Vector3(0,y,0),new Vector3(.14f,.003f,.204f),cover,book,.001f,.005f);
        Box("Book Spine",new Vector3(-.068f,.01f,0),new Vector3(.005f,.019f,.204f),cover,book,.001f,.002f);
        var pen=Mat("Graphite Pen","464944",.32f,.35f);
        Beam("Pen Barrel",new Vector3(-.43f,.748f,-.31f),new Vector3(-.43f,.748f,-.19f),.0038f,.0038f,pen,decor);
        Beam("Pen Tip",new Vector3(-.43f,.748f,-.33f),new Vector3(-.43f,.748f,-.31f),.0007f,.0038f,metal,decor);
        foreach(var r in decor.GetComponentsInChildren<MeshRenderer>()){GameObjectUtility.SetStaticEditorFlags(r.gameObject,StaticEditorFlags.BatchingStatic|StaticEditorFlags.ReflectionProbeStatic);r.receiveGI=ReceiveGI.LightProbes;}
        var anchors=Group("05 Study Anchors");var refs=anchors.gameObject.AddComponent<RoomReferences>();refs.interiorSize=new Vector3(RoomWidth,RoomHeight,RoomLength);
        refs.userSeat=Group("User Seat Origin",anchors);refs.userSeat.position=new Vector3(0,0,-.80f);
        refs.tutorSeat=Group("Tutor Seat Origin",anchors);refs.tutorSeat.position=new Vector3(0,0,.80f);refs.tutorSeat.rotation=Quaternion.Euler(0,180,0);
        refs.tutorEye=Group("Tutor Eye — seated 1.2m",refs.tutorSeat);refs.tutorEye.localPosition=Vector3.up*1.2f;
        refs.tableSurface=Group("Table Surface",anchors);refs.tableSurface.position=new Vector3(0,.74f,0);refs.tableDecor=decor.gameObject;
    }
    static float CloudHeight(float x,float z)
    {
        float a=Mathf.PerlinNoise(x*.014f+31,z*.014f+61),b=Mathf.PerlinNoise(x*.04f+11,z*.04f+21),c=Mathf.PerlinNoise(x*.11f+7,z*.11f+3);
        return -23+Mathf.Pow(a,1.2f)*13+b*3+c*.8f;
    }
    static void Clouds()
    {
        var root=Group("06 Cloud Sea — exterior only");
        var cm=new Material(Shader.Find("IAI/Cloud Sea")){name="Cloud Sea"};cm=Save(cm,Root+"Materials/Room/Cloud Sea.mat");
        // Dense horizon layer plus a finer nearby layer. No transparent particle stacks.
        foreach(int layer in new[]{0,1}) {
            int n=layer==0?160:160;float span=layer==0?320:2400;
            var v=new Vector3[(n+1)*(n+1)];var uv=new Vector2[v.Length];var tr=new List<int>();
            for(int z=0;z<=n;z++)for(int x=0;x<=n;x++){float px=(x/(float)n-.5f)*span,pz=(z/(float)n-.5f)*span;int i=z*(n+1)+x;v[i]=new Vector3(px,CloudHeight(px,pz)-(layer==1?4:0),pz);uv[i]=new Vector2(px/30,pz/30);if(x<n&&z<n){int j=i;tr.AddRange(new[]{j,j+n+1,j+1,j+1,j+n+1,j+n+2});}}
            var m=new Mesh{indexFormat=IndexFormat.UInt32};m.vertices=v;m.uv=uv;m.SetTriangles(tr,0);m=AssetMesh("Cloud_Sea_Layer_"+layer,m,false);
            var go=MeshObject("Cloud Layer "+layer,m,cm,root,Vector3.zero,false);go.GetComponent<Renderer>().shadowCastingMode=ShadowCastingMode.Off;
        }
    }
    static void Lighting()
    {
        var root=Group("07 Afternoon Lighting");var sun=new GameObject("Afternoon Sun — through left glazing");sun.transform.SetParent(root);sun.transform.rotation=Quaternion.LookRotation(new Vector3(1,-.65f,-.45f));
        var l=sun.AddComponent<Light>();l.type=LightType.Directional;l.color=Hex("FFE0AC");l.intensity=1.45f;l.shadows=LightShadows.Soft;l.shadowStrength=.8f;l.shadowBias=.035f;l.shadowNormalBias=.15f;l.lightmapBakeType=LightmapBakeType.Mixed;RenderSettings.sun=l;
        var sky=new Material(Shader.Find("IAI/Afternoon Sky")){name="Afternoon Sky"};sky=Save(sky,Root+"Materials/Room/Afternoon Sky.mat");RenderSettings.skybox=sky;
        RenderSettings.ambientMode=AmbientMode.Trilight;RenderSettings.ambientSkyColor=Hex("C3D2DC");RenderSettings.ambientEquatorColor=Hex("BDB4A5");RenderSettings.ambientGroundColor=Hex("A59880");RenderSettings.ambientIntensity=1;
        RenderSettings.reflectionIntensity=.55f;RenderSettings.fog=false;
        // Soft indirect daylight is baked into the room; no real-time area lights.
        var fill=new GameObject("Window Daylight — baked area");fill.transform.SetParent(root);fill.transform.position=new Vector3(-RoomWidth/2+.12f,RoomHeight*.55f,0);fill.transform.rotation=Quaternion.LookRotation(Vector3.right);
        var f=fill.AddComponent<Light>();f.type=LightType.Area;f.lightmapBakeType=LightmapBakeType.Baked;f.areaSize=new Vector2(RoomLength-2,RoomHeight-.8f);f.color=Hex("E9F0F4");f.intensity=1.8f;f.range=15;
        var ls=new LightingSettings{name="CloudRoomLighting"};ls.autoGenerate=false;ls.realtimeGI=false;ls.bakedGI=true;ls.lightmapper=LightingSettings.Lightmapper.ProgressiveCPU;ls.lightmapResolution=8;ls.lightmapMaxSize=512;ls.directSampleCount=16;ls.indirectSampleCount=32;ls.environmentSampleCount=16;ls.maxBounces=2;ls.ao=true;ls.aoMaxDistance=.35f;ls.aoExponentIndirect=.75f;ls.mixedBakeMode=MixedLightingMode.Shadowmask;
        ls=Save(ls,Root+"Settings/CloudRoomLighting.asset");Lightmapping.lightingSettings=ls;
        var probes=new GameObject("Seated Conversation Light Probes");probes.transform.SetParent(root);var lp=probes.AddComponent<LightProbeGroup>();var points=new List<Vector3>();
        foreach(float x in new[]{-3f,0,3})foreach(float z in new[]{-3f,0,3})foreach(float y in new[]{.3f,1.2f,2.2f})points.Add(new Vector3(x,y,z));lp.probePositions=points.ToArray();
        var probe=new GameObject("Room Reflection Probe");probe.transform.SetParent(root);probe.transform.position=new Vector3(0,1.7f,0);var p=probe.AddComponent<ReflectionProbe>();p.mode=ReflectionProbeMode.Baked;p.size=new Vector3(RoomWidth,RoomHeight,RoomLength);p.center=new Vector3(0,RoomHeight/2-1.7f,0);p.boxProjection=true;p.resolution=128;p.intensity=.65f;p.hdr=false;
        QualitySettings.anisotropicFiltering=AnisotropicFiltering.ForceEnable;
    }
    static void Rig()
    {
        const string path="Assets/Samples/XR Interaction Toolkit/3.0.8/Starter Assets/Prefabs/XR Origin (XR Rig).prefab";
        var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(path);if(prefab==null)throw new Exception("XRI Starter Assets rig missing");
        var rig=(GameObject)PrefabUtility.InstantiatePrefab(prefab);rig.name="08 XR Origin — seated conversation";rig.transform.position=new Vector3(0,0,-.80f);
        var origin=rig.GetComponent<XROrigin>();origin.RequestedTrackingOriginMode=XROrigin.TrackingOriginMode.Device;origin.CameraYOffset=1.2f;origin.CameraFloorOffsetObject.transform.localPosition=Vector3.up*1.2f;
        var cam=rig.GetComponentInChildren<Camera>(true);cam.nearClipPlane=.05f;cam.farClipPlane=1600;cam.allowHDR=false;cam.backgroundColor=Hex("CCD5DD");cam.fieldOfView=72;
        // Fixed seated task: keep head/controller tracking, disable locomotion providers.
        foreach(var b in rig.GetComponentsInChildren<Behaviour>(true)) if(b.GetType().Name.EndsWith("MoveProvider")||b.GetType().Name.EndsWith("TurnProvider")||b.GetType().Name=="TeleportationProvider")b.enabled=false;
        if(Object.FindObjectOfType<XRInteractionManager>()==null)new GameObject("XR Interaction Manager").AddComponent<XRInteractionManager>();
        var simPrefab=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Samples/XR Interaction Toolkit/3.0.8/XR Device Simulator/XR Device Simulator.prefab");
        if(simPrefab!=null){var sim=(GameObject)PrefabUtility.InstantiatePrefab(simPrefab);sim.name="Editor Only — XR Device Simulator";sim.tag="EditorOnly";}
    }
    [MenuItem("AIAA4435/Room/Build Cloud Conversation Room")]
    public static void Build()
    {
        if(EditorApplication.isPlayingOrWillChangePlaymode)throw new Exception("Stop Play mode first");
        foreach(var dir in new[]{"Materials/Room","Models/Room","Prefabs/Room","Scenes","Settings"})Directory.CreateDirectory(Root+dir);
        var current=EditorSceneManager.GetActiveScene();
        if(current.isDirty && !EditorSceneManager.SaveScene(current,AssetDatabase.GenerateUniqueAssetPath(Root+"Scenes/BeforeRoomBuild.unity"),true))throw new Exception("Scene backup failed");
        if(File.Exists(ScenePath)) {Directory.CreateDirectory("SetupBackups/Room");File.Copy(ScenePath,"SetupBackups/Room/CloudConversationRoom_"+DateTime.Now.ToString("yyyyMMdd_HHmmss")+".unity",false);}
        meshes.Clear();EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);AssetDatabase.Refresh();Materials();Architecture();Furniture();Lighting();CloudSkyBaker.ApplyOrBake();Rig();
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),ScenePath);AssetDatabase.SaveAssets();
        var scenes=EditorBuildSettings.scenes.Where(s=>s.path!=ScenePath).ToList();scenes.Insert(0,new EditorBuildSettingsScene(ScenePath,true));EditorBuildSettings.scenes=scenes.ToArray();
        Selection.activeGameObject=GameObject.Find("03 Furniture — one table, two chairs");SceneView.RepaintAll();
        Debug.Log("[AIAA4435] Cloud Conversation Room built and saved. Bake lighting, then capture previews.");
    }
    [MenuItem("AIAA4435/Room/Capture Room Previews")]
    public static void Capture()
    {
        Directory.CreateDirectory("Captures");
        var rig=Object.FindObjectOfType<XROrigin>();var hidden=rig==null?new Renderer[0]:rig.GetComponentsInChildren<Renderer>().Where(r=>r.enabled).ToArray();
        foreach(var r in hidden)r.enabled=false;
        try {
        Shot("01_Seated_View",new Vector3(0,1.2f,-.80f),new Vector3(0,1.10f,1),85);
        Shot("02_Room_Overview",new Vector3(RoomWidth/2-.65f,2.8f,-RoomLength/2+1.5f),new Vector3(-.65f,2.15f,.7f),78);
        Shot("03_Materials_Closeup",new Vector3(1.15f,1.35f,-1.45f),new Vector3(-.05f,.6f,0),55);
        Shot("04_Window_Clouds",new Vector3(1.6f,1.6f,4.7f),new Vector3(-5,.9f,0),72);
        Shot("06_Seated_Window_View",new Vector3(0,1.2f,-.8f),new Vector3(-RoomWidth/2,1.2f,0),80);
        Shot("05_Cloud_Sea_Detail",new Vector3(-RoomWidth/2+.8f,1.5f,0),new Vector3(-35,-16,5),75);
        } finally {foreach(var r in hidden)if(r!=null)r.enabled=true;}
        AssetDatabase.Refresh();
    }
    static void Shot(string name,Vector3 pos,Vector3 look,float fov)
    {
        var go=new GameObject("Temporary Preview Camera");var cam=go.AddComponent<Camera>();go.transform.position=pos;go.transform.LookAt(look);cam.fieldOfView=fov;cam.nearClipPlane=.04f;cam.farClipPlane=1600;cam.allowHDR=false;
        var rt=new RenderTexture(1920,1200,24,RenderTextureFormat.ARGB32){antiAliasing=4};rt.Create();var previous=RenderTexture.active;
        try {cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;var texture=new Texture2D(1920,1200,TextureFormat.RGB24,false);texture.ReadPixels(new Rect(0,0,1920,1200),0,0);texture.Apply();File.WriteAllBytes("Captures/"+name+".png",texture.EncodeToPNG());Object.DestroyImmediate(texture);}
        finally {RenderTexture.active=previous;cam.targetTexture=null;rt.Release();Object.DestroyImmediate(rt);Object.DestroyImmediate(go);}
    }
}
