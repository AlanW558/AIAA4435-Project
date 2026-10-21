using System;
using UnityEngine;

namespace IAI.Appearance
{
    // Appearance state lives on body/jacket/accessories; expression only poses their children.
    public sealed class AppearanceLegacyAvatar : MonoBehaviour
    {
        Material jacket;
        Material[] ownedMaterials;
        Transform body, chest, head, leftArm, rightArm, leftEye, rightEye, leftBrow, rightBrow;
        GameObject hat, glasses;
        Camera viewer;
        float cameraRefreshAt, animationTime, interactionTime, gazePitch, gazeYaw;
        Interaction interaction;
        enum Interaction { Idle, Thinking, Ask, Act, Done }
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

        static Transform Pivot(string name, Transform parent, Vector3 position)
        {
            var pivot = new GameObject(name).transform;
            pivot.SetParent(parent, false);
            pivot.localPosition = position;
            return pivot;
        }

        public void Create()
        {
            // A second call preserves both the current appearance and existing renderers/materials.
            if (body != null) return;
            body = Pivot("Foot anchored avatar", transform, Vector3.zero);
            jacket = Material("Editable jacket", new Color(.23f,.51f,.96f));
            var skin = Material("Warm ivory", new Color(.86f,.74f,.61f));
            var dark = Material("Graphite", new Color(.065f,.1f,.14f));
            var pale = Material("Warm white", new Color(.94f,.94f,.88f));
            var metal = Material("Accessory brass", new Color(.85f,.63f,.28f));
            var hair = Material("Chestnut hair", new Color(.19f,.105f,.065f));
            var blush = Material("Soft cheek", new Color(.84f,.49f,.41f));
            var sole = Material("Shoe sole", new Color(.25f,.29f,.31f));
            ownedMaterials = new[] { jacket, skin, dark, pale, metal, hair, blush, sole };

            Shape("Trouser seat", PrimitiveType.Sphere, body, new Vector3(0,.83f,.015f), new Vector3(.47f,.29f,.33f), dark);
            for (int s=-1;s<=1;s+=2)
            {
                Shape("Trouser", PrimitiveType.Capsule, body, new Vector3(s*.145f,.52f,.01f), new Vector3(.22f,.32f,.25f), dark);
                // These fixed soles put the neutral feet exactly at y=0.
                Shape("Shoe sole", PrimitiveType.Cube, body, new Vector3(s*.145f,.035f,-.065f), new Vector3(.24f,.07f,.37f), sole);
                Shape("Shoe", PrimitiveType.Cube, body, new Vector3(s*.145f,.12f,-.065f), new Vector3(.225f,.17f,.345f), dark);
                Shape("Shoe welt", PrimitiveType.Cube, body, new Vector3(s*.145f,.10f,-.239f), new Vector3(.19f,.025f,.012f), sole);
            }

            chest = Pivot("Breathing torso", body, new Vector3(0,.98f,0));
            Shape("Jacket torso", PrimitiveType.Capsule, chest, new Vector3(0,.14f,0), new Vector3(.60f,.35f,.38f), jacket);
            Shape("Jacket hem", PrimitiveType.Cube, chest, new Vector3(0,-.085f,-.005f), new Vector3(.48f,.065f,.33f), jacket);
            Shape("Shirt inset", PrimitiveType.Cube, chest, new Vector3(0,.365f,-.155f), new Vector3(.17f,.19f,.055f), pale);
            Shape("Jacket placket", PrimitiveType.Cube, chest, new Vector3(0,.115f,-.194f), new Vector3(.032f,.38f,.012f), dark);
            for (int s=-1;s<=1;s+=2)
            {
                var lapel=Shape("Lapel", PrimitiveType.Cube, chest, new Vector3(s*.092f,.325f,-.175f), new Vector3(.075f,.19f,.035f), jacket);
                lapel.transform.localRotation=Quaternion.Euler(0,0,s*24);
                Shape("Pocket opening", PrimitiveType.Cube, chest, new Vector3(s*.155f,.04f,-.174f), new Vector3(.11f,.018f,.014f), dark);
                Shape("Pocket piping", PrimitiveType.Cube, chest, new Vector3(s*.155f,.026f,-.18f), new Vector3(.11f,.012f,.014f), jacket);
                var arm=Pivot(s<0?"Left shoulder":"Right shoulder", chest, new Vector3(s*.345f,.36f,0));
                if(s<0) leftArm=arm; else rightArm=arm;
                Shape("Jacket sleeve", PrimitiveType.Capsule, arm, new Vector3(0,-.235f,0), new Vector3(.19f,.255f,.21f), jacket);
                Shape("Shirt cuff", PrimitiveType.Cylinder, arm, new Vector3(0,-.46f,0), new Vector3(.155f,.028f,.165f), pale);
                Shape("Hand", PrimitiveType.Sphere, arm, new Vector3(0,-.55f,-.012f), new Vector3(.155f,.19f,.16f), skin);
                Shape("Thumb", PrimitiveType.Sphere, arm, new Vector3(-s*.064f,-.52f,-.048f), new Vector3(.07f,.10f,.075f), skin);
            }
            for(int i=0;i<3;i++) Shape("Button", PrimitiveType.Sphere, chest, new Vector3(0,.23f-i*.115f,-.21f), Vector3.one*.026f, metal);
            Shape("Neck", PrimitiveType.Cylinder, chest, new Vector3(0,.51f,0), new Vector3(.17f,.10f,.17f), skin);

            // Face and accessories face local -Z and share a neck pivot so they remain aligned.
            head = Pivot("Head expression", chest, new Vector3(0,.55f,0));
            Shape("Head", PrimitiveType.Sphere, head, new Vector3(0,.23f,0), new Vector3(.46f,.51f,.43f), skin);
            Shape("Hair cap", PrimitiveType.Sphere, head, new Vector3(0,.385f,.045f), new Vector3(.465f,.21f,.435f), hair);
            for(int s=-1;s<=1;s+=2)
            {
                Shape("Ear", PrimitiveType.Sphere, head, new Vector3(s*.225f,.225f,.005f), new Vector3(.075f,.12f,.09f), skin);
                Shape("Side hair", PrimitiveType.Capsule, head, new Vector3(s*.199f,.315f,.025f), new Vector3(.055f,.072f,.12f), hair);
                Shape("Cheek", PrimitiveType.Sphere, head, new Vector3(s*.135f,.19f,-.18f), new Vector3(.062f,.027f,.018f), blush);
                var eye=Pivot("Blinking eye", head, new Vector3(s*.085f,.265f,-.207f));
                if(s<0) leftEye=eye; else rightEye=eye;
                Shape("Eye white", PrimitiveType.Sphere, eye, Vector3.zero, new Vector3(.075f,.061f,.03f), pale);
                Shape("Pupil", PrimitiveType.Sphere, eye, new Vector3(0,0,-.017f), new Vector3(.03f,.041f,.017f), dark);
                Shape("Catchlight", PrimitiveType.Sphere, eye, new Vector3(-.007f,.01f,-.025f), Vector3.one*.009f, pale);
                var brow=Shape("Brow", PrimitiveType.Capsule, head, new Vector3(s*.087f,.318f,-.186f), new Vector3(.015f,.035f,.017f), hair).transform;
                brow.localRotation=Quaternion.Euler(0,0,90+s*7);
                if(s<0) leftBrow=brow; else rightBrow=brow;
                var smile=Shape("Smile corner", PrimitiveType.Capsule, head, new Vector3(s*.035f,.135f,-.202f), new Vector3(.012f,.024f,.014f), dark);
                smile.transform.localRotation=Quaternion.Euler(0,0,-s*55);
            }
            var fringe=Shape("Swept fringe", PrimitiveType.Capsule, head, new Vector3(-.06f,.405f,-.13f), new Vector3(.09f,.13f,.08f), hair);
            fringe.transform.localRotation=Quaternion.Euler(0,0,65);
            Shape("Nose", PrimitiveType.Sphere, head, new Vector3(0,.205f,-.219f), new Vector3(.064f,.075f,.067f), skin);
            Shape("Smile center", PrimitiveType.Capsule, head, new Vector3(0,.12f,-.197f), new Vector3(.012f,.027f,.014f), dark).transform.localRotation=Quaternion.Euler(0,0,90);

            hat = Pivot("Hat", head, Vector3.zero).gameObject;
            Shape("Hat brim", PrimitiveType.Cylinder, hat.transform, new Vector3(0,.44f,0), new Vector3(.64f,.022f,.56f), dark);
            Shape("Hat crown", PrimitiveType.Cylinder, hat.transform, new Vector3(0,.535f,0), new Vector3(.41f,.085f,.38f), dark);
            Shape("Hat band", PrimitiveType.Cylinder, hat.transform, new Vector3(0,.475f,0), new Vector3(.42f,.025f,.39f), metal);
            Shape("Hat badge", PrimitiveType.Cube, hat.transform, new Vector3(.115f,.477f,-.18f), new Vector3(.038f,.035f,.018f), pale);
            glasses = Pivot("Glasses", head, Vector3.zero).gameObject;
            for(int s=-1;s<=1;s+=2)
            {
                for(int i=0;i<2;i++) Shape("Frame horizontal",PrimitiveType.Cube,glasses.transform,new Vector3(s*.09f,.215f+i*.10f,-.237f),new Vector3(.145f,.018f,.025f),dark);
                for(int i=0;i<2;i++) Shape("Frame vertical",PrimitiveType.Cube,glasses.transform,new Vector3(s*(.025f+i*.13f),.265f,-.237f),new Vector3(.018f,.118f,.025f),dark);
                Shape("Temple",PrimitiveType.Cube,glasses.transform,new Vector3(s*.165f,.285f,-.09f),new Vector3(.018f,.018f,.29f),dark);
            }
            Shape("Bridge",PrimitiveType.Cube,glasses.transform,new Vector3(0,.265f,-.245f),new Vector3(.055f,.018f,.025f),metal);
            Apply(new AppearanceState {jacket_color="blue",accessory="hat",scale=1});
            Pose(0);
        }

        public void Apply(AppearanceState state)
        {
            if(state==null) return;
            if(body==null) Create();
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

        // Optional: all conditions use these same short, neutral acknowledgement gestures.
        // Repeating a mode is harmless; idle followed by a mode explicitly retriggers it.
        public void SetInteraction(string mode)
        {
            if(body==null) Create();
            Interaction next=Interaction.Idle;
            if(string.Equals(mode,"thinking",StringComparison.OrdinalIgnoreCase)) next=Interaction.Thinking;
            else if(string.Equals(mode,"ask",StringComparison.OrdinalIgnoreCase)) next=Interaction.Ask;
            else if(string.Equals(mode,"act",StringComparison.OrdinalIgnoreCase)) next=Interaction.Act;
            else if(string.Equals(mode,"done",StringComparison.OrdinalIgnoreCase)) next=Interaction.Done;
            if(interaction==next) return;
            interaction=next;
            interactionTime=0;
            Pose(0);
        }

        void LateUpdate()
        {
            if(body==null) return;
            float dt=Mathf.Min(Time.unscaledDeltaTime,.1f);
            animationTime+=dt;
            interactionTime+=dt;
            if(Time.unscaledTime>=cameraRefreshAt)
            {
                viewer=Camera.main;
                cameraRefreshAt=Time.unscaledTime+.8f;
            }
            Pose(dt);
        }

        void OnDestroy()
        {
            if(ownedMaterials==null) return;
            for(int i=0;i<ownedMaterials.Length;i++)
            {
                if(ownedMaterials[i]==null) continue;
                if(Application.isPlaying) Destroy(ownedMaterials[i]);
                else DestroyImmediate(ownedMaterials[i]);
            }
        }

        void Pose(float dt)
        {
            // Chest-only breathing leaves the experimental scale and both soles untouched.
            float breath=Mathf.Sin(animationTime*1.6f);
            chest.localScale=new Vector3(1+breath*.003f,1+breath*.004f,1+breath*.005f);
            float pitch=0, yaw=0;
            if(viewer!=null && viewer.isActiveAndEnabled)
            {
                Vector3 toward=body.InverseTransformPoint(viewer.transform.position)-new Vector3(0,1.795f,0);
                // A camera behind the avatar does not cause a turn away from the participant.
                if(toward.z<-.05f && toward.sqrMagnitude>.04f)
                {
                    yaw=Mathf.Clamp(Mathf.Atan2(-toward.x,-toward.z)*Mathf.Rad2Deg,-13,13);
                    pitch=Mathf.Clamp(Mathf.Atan2(toward.y,Mathf.Sqrt(toward.x*toward.x+toward.z*toward.z))*Mathf.Rad2Deg,-8,8);
                }
            }
            float follow=1-Mathf.Exp(-5*dt);
            gazeYaw=Mathf.Lerp(gazeYaw,yaw,follow);
            gazePitch=Mathf.Lerp(gazePitch,pitch,follow);
            float duration=interaction==Interaction.Thinking?1.7f:interaction==Interaction.Ask?1.4f:interaction==Interaction.Act?.9f:1.2f;
            float progress=Mathf.Clamp01(interactionTime/duration);
            float gesture=interaction==Interaction.Idle?0:Mathf.Sin(progress*Mathf.PI);
            float nod=interaction==Interaction.Done?Mathf.Sin(progress*Mathf.PI*2)*5*gesture:0;
            float tilt=interaction==Interaction.Thinking?4*gesture:interaction==Interaction.Ask?-3*gesture:0;
            head.localRotation=Quaternion.Euler(gazePitch+nod,gazeYaw,tilt);
            leftArm.localRotation=Quaternion.Euler(6+(interaction==Interaction.Thinking?22:interaction==Interaction.Act?12:0)*gesture,0,-9);
            rightArm.localRotation=Quaternion.Euler(6+(interaction==Interaction.Ask?32:interaction==Interaction.Done?18:interaction==Interaction.Act?12:0)*gesture,0,9);
            float browLift=(interaction==Interaction.Ask?.008f:interaction==Interaction.Thinking?.004f:0)*gesture;
            leftBrow.localPosition=new Vector3(-.087f,.318f+browLift,-.186f);
            rightBrow.localPosition=new Vector3(.087f,.318f+browLift,-.186f);
            // Deterministic cadence avoids random-state coupling to any experimental condition.
            float blinkPhase=Mathf.Repeat(animationTime+1.25f,4.6f);
            float openness=blinkPhase<.16f?Mathf.Lerp(.08f,1,Mathf.Abs(blinkPhase-.08f)/.08f):1;
            leftEye.localScale=rightEye.localScale=new Vector3(1,openness,1);
        }
    }
}
