using UnityEngine;

namespace IAI.Appearance
{
    // A deliberately fixed avatar: only the three experimental attributes vary.
    public sealed class AppearanceAvatar : MonoBehaviour
    {
        Material jacket;
        Transform body;
        GameObject hat, glasses;
        static readonly string[] ColorNames={"blue","orange","green","gray","red","purple"};
        static readonly string[] ColorHex={"#3B82F6","#F59E0B","#22C55E","#80858F","#EF4444","#8B5CF6"};
        public string ObservedColor {
            get { for(int i=0;i<ColorNames.Length;i++){Color c;ColorUtility.TryParseHtmlString(ColorHex[i],out c);if(Vector4.Distance(jacket.color,c)<.005f)return ColorNames[i];}return "unrecognized"; }
        }
        public string ObservedAccessory => hat.activeInHierarchy?(glasses.activeInHierarchy?"invalid_multiple":"hat"):(glasses.activeInHierarchy?"glasses":"none");
        public float ObservedScale => body.localScale.x;

        public static Material Material(string name, Color color)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var result = new Material(shader) { name = name, color = color };
            result.SetFloat("_Smoothness", .3f);
            return result;
        }

        public static GameObject Shape(string name, PrimitiveType kind, Transform parent, Vector3 pos, Vector3 size, Material mat)
        {
            var go = GameObject.CreatePrimitive(kind);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = size;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            var collider = go.GetComponent<Collider>();
            if (collider) { if(Application.isPlaying) Destroy(collider); else DestroyImmediate(collider); }
            return go;
        }

        public void Create()
        {
            body = new GameObject("Foot anchored avatar").transform;
            body.SetParent(transform, false);
            jacket = Material("Editable jacket", new Color(.23f,.51f,.96f));
            var skin = Material("Warm ivory", new Color(.86f,.74f,.61f));
            var dark = Material("Graphite", new Color(.065f,.1f,.14f));
            var pale = Material("Warm white", new Color(.94f,.94f,.88f));
            var metal = Material("Accessory brass", new Color(.85f,.63f,.28f));
            Shape("Jacket torso", PrimitiveType.Capsule, body, new Vector3(0,1.12f,0), new Vector3(.62f,.40f,.38f), jacket);
            for (int s=-1;s<=1;s+=2)
            {
                Shape("Trouser", PrimitiveType.Capsule, body, new Vector3(s*.155f,.43f,0), new Vector3(.22f,.32f,.24f), dark);
                Shape("Shoe", PrimitiveType.Cube, body, new Vector3(s*.155f,.095f,-.07f), new Vector3(.23f,.17f,.37f), dark);
                var arm=Shape("Jacket sleeve", PrimitiveType.Capsule, body, new Vector3(s*.39f,1.02f,0), new Vector3(.19f,.29f,.21f), jacket);
                arm.transform.localRotation=Quaternion.Euler(0,0,s*10);
                Shape("Hand", PrimitiveType.Sphere, body, new Vector3(s*.44f,.73f,0), new Vector3(.17f,.21f,.17f), skin);
            }
            Shape("Collar", PrimitiveType.Cube, body, new Vector3(0,1.42f,-.17f), new Vector3(.19f,.12f,.05f), pale);
            for(int i=0;i<3;i++) Shape("Button", PrimitiveType.Sphere, body, new Vector3(0,1.23f-i*.12f,-.197f), Vector3.one*.028f, metal);
            Shape("Neck", PrimitiveType.Cylinder, body, new Vector3(0,1.5f,0), new Vector3(.17f,.1f,.17f), skin);
            Shape("Head", PrimitiveType.Sphere, body, new Vector3(0,1.72f,0), new Vector3(.43f,.49f,.40f), skin);
            for(int s=-1;s<=1;s+=2)
            {
                Shape("Ear", PrimitiveType.Sphere, body, new Vector3(s*.215f,1.72f,0), new Vector3(.075f,.12f,.09f), skin);
                Shape("Eye", PrimitiveType.Sphere, body, new Vector3(s*.08f,1.75f,-.187f), Vector3.one*.038f, dark);
            }
            Shape("Nose", PrimitiveType.Sphere, body, new Vector3(0,1.68f,-.2f), new Vector3(.065f,.08f,.065f), skin);
            Shape("Smile", PrimitiveType.Capsule, body, new Vector3(0,1.61f,-.172f), new Vector3(.025f,.04f,.025f), dark).transform.localRotation=Quaternion.Euler(0,0,90);
            hat = new GameObject("Hat"); hat.transform.SetParent(body,false);
            Shape("Hat brim", PrimitiveType.Cylinder, hat.transform, new Vector3(0,1.94f,0), new Vector3(.62f,.025f,.54f), dark);
            Shape("Hat crown", PrimitiveType.Cylinder, hat.transform, new Vector3(0,2.04f,0), new Vector3(.40f,.10f,.37f), dark);
            Shape("Hat band", PrimitiveType.Cylinder, hat.transform, new Vector3(0,1.98f,0), new Vector3(.41f,.025f,.38f), metal);
            glasses = new GameObject("Glasses"); glasses.transform.SetParent(body,false);
            for(int s=-1;s<=1;s+=2)
            {
                foreach(float y in new[]{1.695f,1.80f}) Shape("Frame horizontal",PrimitiveType.Cube,glasses.transform,new Vector3(s*.09f,y,-.21f),new Vector3(.14f,.018f,.024f),dark);
                foreach(float x in new[]{s*.025f,s*.155f}) Shape("Frame vertical",PrimitiveType.Cube,glasses.transform,new Vector3(x,1.75f,-.21f),new Vector3(.018f,.12f,.024f),dark);
                Shape("Temple",PrimitiveType.Cube,glasses.transform,new Vector3(s*.165f,1.76f,-.08f),new Vector3(.018f,.018f,.26f),dark);
            }
            Shape("Bridge",PrimitiveType.Cube,glasses.transform,new Vector3(0,1.75f,-.218f),new Vector3(.055f,.018f,.025f),dark);
            Apply(new AppearanceState {jacket_color="blue",accessory="hat",scale=1});
        }

        public void Apply(AppearanceState state)
        {
            string hex;
            switch(state.jacket_color) {
                case "orange": hex="#F59E0B";break; case "green":hex="#22C55E";break;
                case "gray":hex="#80858F";break; case "red":hex="#EF4444";break;
                case "purple":hex="#8B5CF6";break; default:hex="#3B82F6";break;
            }
            Color color; ColorUtility.TryParseHtmlString(hex,out color); jacket.color=color;
            hat.SetActive(state.accessory=="hat"); glasses.SetActive(state.accessory=="glasses");
            body.localScale=Vector3.one*state.scale;

        }
    }
}
