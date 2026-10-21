using System;
using IAI.Interaction;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.Appearance
{
    // A shared participant interface for all policies. Study metadata is never rendered here.
    public sealed class AppearanceXRPanel : MonoBehaviour
    {
        public AppearanceExperimentClient client;
        public Font font;
        public Sprite rounded;
        public ConversationSeat seat;
        readonly Color ink=new Color(.10f,.20f,.23f),muted=new Color(.32f,.41f,.43f);
        readonly Color accent=new Color(.06f,.39f,.42f),paper=new Color(.97f,.95f,.90f),light=new Color(.87f,.90f,.87f);
        readonly string[] fields={"all","jacket_color","accessory","scale","avatar_id","outfit"};
        Text status,entryHint,subtitle,eyebrow,examples;
        InputField requestInput,answerInput;
        RectTransform requestGroup,questionGroup,doneGroup,choices;
        Button send,answerSend,undo,finish,next;
        Button[] fieldButtons;
        Button[] choiceButtons=Array.Empty<Button>();
        string questionKey="";
        int selectedField;
        Canvas canvas;
        bool? demoLayout;

        void Start()
        {
            if(!client||!font){Debug.LogError("Appearance XR panel requires a client and bundled font.");enabled=false;return;}
            client.worldSpaceUI=true;
            var root=Rect("Appearance canvas",transform,Vector2.zero,new Vector2(960,880));
            root.localScale=Vector3.one*.0012f;
            canvas=root.gameObject.AddComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;canvas.worldCamera=Camera.main;
            var ray=root.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>();ray.checkFor3DOcclusion=false;ray.checkFor2DOcclusion=false;
            var background=Surface("Ivory surface",root,Vector2.zero,new Vector2(960,880),paper);
            background.transform.SetAsFirstSibling();background.raycastTarget=true;
            Surface("Accent rule",root,new Vector2(-430,340),new Vector2(5,102),accent);
            eyebrow=Label("Eyebrow",root,"衣服  ·  配饰  ·  大小",new Vector2(0,382),new Vector2(828,32),21,muted);
            Label("Title",root,"一起调整外形",new Vector2(0,332),new Vector2(828,64),38,ink);
            Surface("Status surface",root,new Vector2(0,230),new Vector2(856,106),light);
            status=Label("Status",root,"正在准备…",new Vector2(0,230),new Vector2(800,90),24,ink);

            requestGroup=Rect("Request",root,Vector2.zero,Vector2.zero);
            entryHint=Label("Input label",requestGroup,"你想怎样修改？",new Vector2(0,147),new Vector2(856,32),22,muted);
            requestInput=Input("Request text",requestGroup,new Vector2(0,48),new Vector2(856,140),"点击这里输入你的想法");
            requestInput.onValueChanged.AddListener(text=>{if(client.CanEditQuery)client.query=text;});
            send=ActionButton("Send",requestGroup,"发送",new Vector2(287,-65),new Vector2(282,66),true,()=>client.RequestSubmit());
            subtitle=Label("Guidance",requestGroup,"选中输入框即可输入文字",new Vector2(-150,-65),new Vector2(520,60),20,muted);
            examples=Label("Examples",requestGroup,"可以调整颜色、配饰或大小，也可以撤销。",new Vector2(0,-150),new Vector2(856,64),21,muted);

            questionGroup=Rect("Clarification",root,Vector2.zero,Vector2.zero);
            choices=Rect("Choices",questionGroup,Vector2.zero,Vector2.zero);
            answerInput=Input("Other answer",questionGroup,new Vector2(-118,-166),new Vector2(620,64),"也可以补充你的想法");
            answerInput.onValueChanged.AddListener(text=>client.answerText=text);
            answerSend=ActionButton("Other submit",questionGroup,"发送补充",new Vector2(324,-166),new Vector2(208,64),true,()=>client.RequestAnswer("other",answerInput.text));
            doneGroup=Rect("Done",root,Vector2.zero,Vector2.zero);
            Label("Done title",doneGroup,"看看现在的样子",new Vector2(0,60),new Vector2(856,70),32,ink);
            Label("Done detail",doneGroup,"你的修改已经保留。",new Vector2(0,-8),new Vector2(856,54),23,muted);
            next=ActionButton("Continue",doneGroup,"继续修改",new Vector2(0,-112),new Vector2(340,66),true,()=>client.RequestNext());

            Surface("Divider",root,new Vector2(0,-236),new Vector2(856,2),new Color(.74f,.78f,.73f));
            fieldButtons=new Button[fields.Length];
            string[] names={"全部","颜色","配饰","大小","形象","服装"};
            for(int i=0;i<fields.Length;i++)
            {
                int index=i;
                fieldButtons[i]=ActionButton("Undo field "+fields[i],root,names[i],new Vector2(-324+i*216,-283),new Vector2(208,54),false,()=>SelectField(index));
            }
            undo=ActionButton("Undo",root,"撤销上次修改",new Vector2(-220,-363),new Vector2(416,72),false,()=>client.RequestUndo(fields[selectedField]));
            finish=ActionButton("Finish",root,"完成修改",new Vector2(220,-363),new Vector2(416,72),true,()=>client.RequestFinish());
            UpdateProfile();
            SelectField(0);
            if(!FindObjectOfType<EventSystem>())
            {
                var events=new GameObject("Appearance XR events",typeof(EventSystem),typeof(XRUIInputModule));
                var module=events.GetComponent<XRUIInputModule>();module.enableXRInput=true;module.enableMouseInput=true;
                module.enableBuiltinActionsAsFallback=true;events.GetComponent<EventSystem>().sendNavigationEvents=false;
            }
        }

        void Update()
        {
            if(!status)return;
            UpdateProfile();
            if(!canvas.worldCamera)canvas.worldCamera=Camera.main;
            bool ask=client.IsQuestion&&!client.IsFinished&&!client.Faulted;
            status.text=client.Faulted?client.Status:client.Busy?"正在理解你的想法…":ask?client.view.question.text:client.Status;
            requestGroup.gameObject.SetActive(!ask&&!client.IsFinished);
            questionGroup.gameObject.SetActive(ask);
            doneGroup.gameObject.SetActive(client.IsFinished);
            next.gameObject.SetActive(client.TrialNumber==0&&!client.StudyComplete);
            next.interactable=client.IsFinished&&!client.Busy&&!client.Validating&&!client.Faulted;
            if(!requestInput.isFocused&&requestInput.text!=client.query)requestInput.SetTextWithoutNotify(client.query);
            requestInput.readOnly=!client.CanEditQuery;
            requestInput.interactable=client.CanEditQuery;
            entryHint.text=client.ControlledTask&&!client.CanEditQuery?"确认下面的请求":"你想怎样修改？";
            subtitle.text=client.ControlledTask&&!client.CanEditQuery?"确认后选择“发送”":"选中输入框即可输入文字";
            send.interactable=client.CanOperate&&!string.IsNullOrWhiteSpace(client.query);
            if(!answerInput.isFocused&&answerInput.text!=client.answerText)answerInput.SetTextWithoutNotify(client.answerText);
            answerInput.interactable=client.CanOperate;
            answerSend.interactable=client.CanOperate&&!string.IsNullOrWhiteSpace(answerInput.text);
            undo.interactable=client.CanOperate;
            finish.interactable=client.CanFinish;
            foreach(var b in fieldButtons)b.interactable=client.CanOperate;
            if(ask)
            {
                string key=JsonUtility.ToJson(client.view.question);
                if(key!=questionKey){questionKey=key;BuildChoices(client.view.question);}
            }
            else questionKey="";
            foreach(var b in choiceButtons)if(b)b.interactable=client.CanOperate;
        }

        void UpdateProfile()
        {
            bool demo=client.IsDemo;
            if(demoLayout==demo)return;
            demoLayout=demo;
            int count=demo?6:4;
            float step=864f/count;
            for(int i=0;i<fieldButtons.Length;i++)
            {
                fieldButtons[i].gameObject.SetActive(i<count);
                var rect=fieldButtons[i].GetComponent<RectTransform>();
                rect.anchoredPosition=new Vector2(-432+step*(i+.5f),-283);
                rect.sizeDelta=new Vector2(step-8,54);
                fieldButtons[i].GetComponentInChildren<Text>().rectTransform.sizeDelta=rect.sizeDelta-new Vector2(28,8);
            }
            if(selectedField>=count)SelectField(0);
            eyebrow.text=demo?"形象  ·  服装  ·  颜色  ·  配饰  ·  大小":"衣服  ·  配饰  ·  大小";
            examples.text=demo?"可以换装、改颜色或大小，也可以换成奶龙。":"可以调整颜色、配饰或大小，也可以撤销。";
        }

        void BuildChoices(Question question)
        {
            foreach(Transform child in choices)Destroy(child.gameObject);
            var options=new System.Collections.Generic.List<Choice>();
            foreach(var option in question.options??Array.Empty<Choice>())if(option.id!="other")options.Add(option);
            choiceButtons=new Button[options.Count];
            // The shared backend emits <=3 candidates plus cancellation. Keep every option visible.
            float height=Mathf.Min(64,280f/Mathf.Max(1,options.Count)-8);
            for(int i=0;i<options.Count;i++)
            {
                string id=options[i].id;
                choiceButtons[i]=ActionButton("Choice "+id,choices,options[i].label,new Vector2(0,138-i*(height+8)),new Vector2(856,height),id!="cancel",()=>client.RequestAnswer(id));
            }
        }
        void SelectField(int index)
        {
            selectedField=index;
            for(int i=0;i<fieldButtons.Length;i++)
            {
                fieldButtons[i].GetComponent<Image>().color=i==index?accent:light;
                fieldButtons[i].GetComponentInChildren<Text>().color=i==index?Color.white:ink;
            }
        }
        RectTransform Rect(string name,Transform parent,Vector2 position,Vector2 size)
        {
            var go=new GameObject(name,typeof(RectTransform));var rect=go.GetComponent<RectTransform>();
            rect.SetParent(parent,false);rect.anchorMin=rect.anchorMax=new Vector2(.5f,.5f);rect.sizeDelta=size;rect.anchoredPosition=position;return rect;
        }
        Image Surface(string name,Transform parent,Vector2 position,Vector2 size,Color color)
        {
            var rect=Rect(name,parent,position,size);var img=rect.gameObject.AddComponent<Image>();img.color=color;img.raycastTarget=false;
            if(rounded){img.sprite=rounded;img.type=Image.Type.Sliced;}return img;
        }
        Text Label(string name,Transform parent,string text,Vector2 position,Vector2 size,int fontSize,Color color)
        {
            var rect=Rect(name,parent,position,size);var label=rect.gameObject.AddComponent<Text>();
            label.font=font;label.fontSize=fontSize;label.text=text;label.color=color;label.raycastTarget=false;
            label.alignment=TextAnchor.MiddleLeft;label.horizontalOverflow=HorizontalWrapMode.Wrap;label.verticalOverflow=VerticalWrapMode.Truncate;
            return label;
        }
        Button ActionButton(string name,Transform parent,string text,Vector2 position,Vector2 size,bool primary,Action action)
        {
            var image=Surface(name,parent,position,size,primary?accent:light);image.raycastTarget=true;
            var button=image.gameObject.AddComponent<Button>();button.targetGraphic=image;
            var colors=button.colors;colors.highlightedColor=new Color(.83f,.94f,.92f);colors.pressedColor=new Color(.62f,.80f,.78f);colors.disabledColor=new Color(.68f,.70f,.68f,.55f);button.colors=colors;
            button.navigation=new Navigation{mode=Navigation.Mode.None};button.onClick.AddListener(()=>action());
            var label=Label("Label",image.transform,text,Vector2.zero,size-new Vector2(28,8),23,primary?Color.white:ink);
            label.alignment=TextAnchor.MiddleCenter;label.resizeTextForBestFit=true;label.resizeTextMinSize=17;label.resizeTextMaxSize=23;
            return button;
        }
        InputField Input(string name,Transform parent,Vector2 position,Vector2 size,string hint)
        {
            var image=Surface(name,parent,position,size,Color.white);image.raycastTarget=true;
            var input=image.gameObject.AddComponent<InputField>();input.targetGraphic=image;
            var text=Label("Text",image.transform,"",Vector2.zero,size-new Vector2(32,16),24,ink);
            var placeholder=Label("Placeholder",image.transform,hint,Vector2.zero,size-new Vector2(32,16),23,muted);
            input.textComponent=text;input.placeholder=placeholder;input.lineType=InputField.LineType.MultiLineNewline;
            input.characterLimit=2000;input.caretColor=accent;input.selectionColor=new Color(.2f,.6f,.6f,.3f);
            input.navigation=new Navigation{mode=Navigation.Mode.None};return input;
        }
    }
}
