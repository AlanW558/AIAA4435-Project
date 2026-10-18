using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Appearance
{
    [Serializable] public class AppearanceState { public int revision; public string jacket_color="blue", accessory="hat"; public float scale=1; }
    [Serializable] public class Choice { public string id, label; }
    [Serializable] public class Question { public string text; public Choice[] options; }
    [Serializable] public class SessionView { public string session_id,decision,message,error; public AppearanceState state; public Question question; }
    [Serializable] public class CreateSession { public string participant_id,condition,phase; }
    [Serializable] public class Mutation { public string request_id; public int expected_revision; }
    [Serializable] public class Request : Mutation { public string query; }
    [Serializable] public class Answer : Mutation { public string option_id,free_text; }
    [Serializable] public class Undo : Mutation { public string field; }
    [Serializable] public class Reset : Mutation { public AppearanceState state; public AppearanceState[] history; public string[] soft_preferences; public string task_id; }
    [Serializable] public class RenderPayload { public int revision,probe_index; public float duration_ms; public AppearanceState state; public string screenshot,message; }
    [Serializable] public class RenderEvent { public string @event="render_ack"; public RenderPayload payload; }
    [Serializable] public class MarkerPayload { public string trial_id,task_id,kind,value,study_session_id,observed_build_sha256; public int block,within_block; public float elapsed_seconds; }
    [Serializable] public class MarkerEvent { public string @event="client_marker"; public MarkerPayload payload; }
    [Serializable] public class ModelContext { public string initial_query; public AppearanceState state; public AppearanceState[] visible_history; public string[] soft_preferences; }
    [Serializable] public class StudyTask { public string task_id,participant_goal; public ModelContext model_visible; }
    [Serializable] public class TaskList { public StudyTask[] tasks; }
    public class TrialRow { public string trialId,taskId,condition; public int block,withinBlock; }

    public sealed class AppearanceExperimentClient : MonoBehaviour
    {
        public string endpoint="http://127.0.0.1:8765";
        public AppearanceAvatar avatar;
        public SessionView view = new SessionView();
        public bool Busy { get; private set; }
        public string Status { get; private set; } = "Start a session to connect.";
        public bool LastOk { get; private set; }
        public string participant="DEBUG01",phase="debug",condition="S",query="把外衣改成橙色，帽子和大小保持不变。",answerText="";
        bool researcher=true, trialActive, initialSent, finished, awaitingBlock,validating,capturedFirst;
        StudyTask[] tasks=Array.Empty<StudyTask>();
        List<TrialRow> schedule = new List<TrialRow>();
        int taskIndex,trialIndex=-1,fieldIndex;
        float started;
        string taskGoal="Try changing the jacket, accessory, or size.", lastResponse="", studySessionId="";
        string[] fields={"all","jacket_color","accessory","scale"};
        string[] policies={"E","A","N","S"};
        Font font;
        GUIStyle title,body,small,button,input,card;
        Texture2D panelTexture,cardTexture,buttonTexture;
        Vector2 scroll;
        const float Width=1440,Height=900;

        void Start()
        {
            endpoint=System.Environment.GetEnvironmentVariable("APPEARANCE_BACKEND_URL")??endpoint;
            if(avatar==null) { var go=new GameObject("Appearance avatar");go.transform.position=Vector3.up*.1f; avatar=go.AddComponent<AppearanceAvatar>(); avatar.Create(); }
            var path=Path.Combine(Application.streamingAssetsPath,"AppearanceStudy/tasks.json");
            if(File.Exists(path)) tasks=JsonUtility.FromJson<TaskList>(File.ReadAllText(path)).tasks;
            font=Font.CreateDynamicFontFromOSFont(new[]{"Noto Sans CJK SC","Noto Sans","DejaVu Sans","Arial"},20);
            if(Array.IndexOf(System.Environment.GetCommandLineArgs(),"-appearance-smoke")>=0) StartCoroutine(Smoke());
        }

        string Id()=>Guid.NewGuid().ToString("N");
        int Revision=>view.state==null?0:view.state.revision;

        public IEnumerator Send(string route,object payload,bool update=true)
        {
            LastOk=false; Busy=true;
            using(var req=new UnityWebRequest(endpoint.TrimEnd('/')+route,"POST"))
            {
                req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(payload)));
                req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json"); req.timeout=100;
                yield return req.SendWebRequest();
                lastResponse=req.downloadHandler.text;
                if(req.result!=UnityWebRequest.Result.Success)
                {
                    SessionView err=null;
                    try { err=JsonUtility.FromJson<SessionView>(lastResponse); } catch(Exception) { }
                    Status=err!=null&&!string.IsNullOrEmpty(err.message)?err.message:"Connection failed ("+req.responseCode+"). Check the backend.";
                    // A revision conflict is recovered explicitly from the authoritative snapshot.
                    if(err!=null&&err.state!=null&&err.state.scale>0) { view=err; avatar.Apply(err.state); }
                    Debug.LogWarning("Appearance request failed: HTTP "+req.responseCode);
                }
                else
                {
                    LastOk=true;
                    if(update)
                    {
                        var next=JsonUtility.FromJson<SessionView>(lastResponse);
                        view=next; Status=next.message??next.decision;
                        if(next.state!=null) avatar.Apply(next.state);
                    }
                }
            }
            if(LastOk&&update&&view.state!=null&&!string.IsNullOrEmpty(view.session_id))
            {
                // Record the values applied by the renderer, not an inferred API success.
                yield return null;
                string capture=null;
                if(view.decision=="ACT"&&!capturedFirst){capture=Capture("first-commit");capturedFirst=true;}
                var ack=new RenderEvent {payload=new RenderPayload {revision=Revision,state=Observed(),screenshot=capture}};
                using(var req=new UnityWebRequest(endpoint.TrimEnd('/')+"/sessions/"+view.session_id+"/events","POST"))
                {
                    req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(ack)));
                    req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json"); req.timeout=10;
                    Busy=true; yield return req.SendWebRequest();
                    if(req.result!=UnityWebRequest.Result.Success) {Status="State rendered, but the render log could not be saved. Stop this trial.";LastOk=false;}
                }
            }
            Busy=false;
        }

        string Route(string action)=>"/sessions/"+view.session_id+"/"+action;
        AppearanceState Observed()=>new AppearanceState{revision=Revision,jacket_color=avatar.ObservedColor,accessory=avatar.ObservedAccessory,scale=avatar.ObservedScale};
        string Capture(string label)
        {
            string root=System.Environment.GetEnvironmentVariable("APPEARANCE_CAPTURE_DIR")??Path.Combine(Application.persistentDataPath,"appearance-captures");
            Directory.CreateDirectory(root);
            string path=Path.Combine(root,view.session_id+"-r"+Revision+"-"+label+".png");
            ScreenCapture.CaptureScreenshot(path);return path;
        }
        IEnumerator NewSession(bool loadTask)
        {
            if(string.IsNullOrEmpty(studySessionId))studySessionId=participant+"_"+DateTime.UtcNow.ToString("yyyyMMddTHHmmss");
            yield return Send("/sessions",new CreateSession{participant_id=participant,condition=condition,phase=phase});
            if(LastOk&&loadTask) yield return LoadTask();
        }
        IEnumerator LoadTask()
        {
            if(tasks.Length==0) yield break;
            var t=tasks[taskIndex];var c=t.model_visible;
            yield return Send(Route("reset"),new Reset{request_id=Id(),expected_revision=Revision,state=c.state,history=c.visible_history,soft_preferences=c.soft_preferences,task_id=t.task_id});
            if(!LastOk) yield break;
            query=c.initial_query;taskGoal=t.participant_goal;answerText="";initialSent=false;trialActive=true;finished=false;capturedFirst=false;started=Time.realtimeSinceStartup;
            yield return Marker("task_ready","");
        }
        IEnumerator Marker(string kind,string value)
        {
            var row=trialIndex>=0&&trialIndex<schedule.Count?schedule[trialIndex]:null;
            yield return Send(Route("events"),new MarkerEvent{payload=new MarkerPayload{kind=kind,value=value,study_session_id=studySessionId,observed_build_sha256=System.Environment.GetEnvironmentVariable("APPEARANCE_BUILD_SHA256")??"",trial_id=row?.trialId??"debug",task_id=tasks.Length>0?tasks[taskIndex].task_id:"free",block=row?.block??0,within_block=row?.withinBlock??0,elapsed_seconds=Time.realtimeSinceStartup-started}},false);
        }
        IEnumerator Submit()
        {
            if(!initialSent) {started=Time.realtimeSinceStartup;yield return Marker("trial_start","");if(!LastOk)yield break;initialSent=true;}
            yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query=query});
            if(LastOk) {initialSent=true; query="";}
        }
        IEnumerator SubmitAnswer(string option)
        {
            yield return Send(Route("answer"),new Answer{request_id=Id(),expected_revision=Revision,option_id=option,free_text=answerText});
            if(LastOk) answerText="";
        }
        IEnumerator Finish(string reason)
        {
            trialActive=false;validating=true;
            yield return Marker("completion",reason);
            if(!LastOk){validating=false;yield break;}
            yield return Send(Route("finish"),new Mutation{request_id=Id(),expected_revision=Revision});
            if(!LastOk){validating=false;yield break;}
            string[] turns={"Tutor: We can continue when you are ready.","Tutor: Take a moment to review the character.","Tutor: The next task will begin after this check."};
            for(int i=0;i<turns.Length;i++)
            {
                float probeStarted=Time.realtimeSinceStartup;Status=turns[i];yield return new WaitForSeconds(1.5f);
                yield return Send(Route("events"),new RenderEvent{@event="probe",payload=new RenderPayload{revision=Revision,state=Observed(),probe_index=i+1,duration_ms=(Time.realtimeSinceStartup-probeStarted)*1000,message=turns[i],screenshot=Capture("probe-"+(i+1))}},false);
                if(!LastOk){validating=false;yield break;}
            }
            validating=false;finished=true;Status="Task complete. Thank you.";
        }
        IEnumerator StartScheduled()
        {
            if(phase!="formal"){Status="Assigned sessions require formal mode. For engineering or pilot checks use a manual session.";yield break;}
            schedule.Clear();trialIndex=-1;studySessionId=participant+"_"+DateTime.UtcNow.ToString("yyyyMMddTHHmmss");
            string path=Path.Combine(Application.streamingAssetsPath,"AppearanceStudy/trial_schedule.csv");
            foreach(var line in File.ReadAllLines(path))
            {
                var c=line.Split(',');if(c.Length<6||c[0]!=participant) continue;
                schedule.Add(new TrialRow {trialId=c[1],block=int.Parse(c[2]),withinBlock=int.Parse(c[3]),condition=c[4],taskId=c[5]});
            }
            if(schedule.Count!=16) {Status="Use a scheduled ID P001–P020. Pilot IDs use manual debug/pilot tasks.";yield break;}
            trialIndex=0;researcher=false;yield return ScheduledTrial();
        }
        IEnumerator ScheduledTrial()
        {
            var row=schedule[trialIndex]; condition=row.condition;
            taskIndex=Array.FindIndex(tasks,t=>t.task_id==row.taskId);
            if(taskIndex<0) {Status="Missing task configuration.";yield break;}
            if(row.withinBlock==1) yield return NewSession(true);else yield return LoadTask();
        }
        IEnumerator Next()
        {
            if(trialIndex<0) {yield return LoadTask();yield break;}
            if(trialIndex==schedule.Count-1) {Status="All four blocks are complete. Please complete the final questionnaire.";awaitingBlock=true;yield break;}
            trialIndex++;awaitingBlock=false;yield return ScheduledTrial();
        }

        void Update()
        {
            if(UnityEngine.InputSystem.Keyboard.current!=null&&UnityEngine.InputSystem.Keyboard.current.f1Key.wasPressedThisFrame) researcher=!researcher;
            if(trialActive&&initialSent&&!Busy&&Time.realtimeSinceStartup-started>=120) StartCoroutine(Finish("timeout"));
        }
        Texture2D Tex(Color c) {var t=new Texture2D(1,1);t.SetPixel(0,0,c);t.Apply();return t;}
        void Styles()
        {
            if(body!=null)return;
            panelTexture=Tex(new Color(.055f,.075f,.10f,.98f));cardTexture=Tex(new Color(.105f,.135f,.17f));buttonTexture=Tex(new Color(.18f,.27f,.31f));
            title=new GUIStyle(GUI.skin.label){font=font,fontSize=30,wordWrap=true,normal={textColor=new Color(.91f,.95f,.94f)}};
            body=new GUIStyle(GUI.skin.label){font=font,fontSize=18,wordWrap=true,normal={textColor=new Color(.88f,.92f,.94f)}};
            small=new GUIStyle(body){fontSize=14,normal={textColor=new Color(.57f,.69f,.74f)}};
            button=new GUIStyle(GUI.skin.button){font=font,fontSize=17,wordWrap=true,padding=new RectOffset(12,12,10,10),normal={background=buttonTexture,textColor=Color.white},hover={textColor=Color.white},active={textColor=Color.white}};
            input=new GUIStyle(GUI.skin.textArea){font=font,fontSize=19,padding=new RectOffset(12,12,12,12),wordWrap=true};
            card=new GUIStyle(GUI.skin.box){normal={background=cardTexture},padding=new RectOffset(18,18,16,16)};
        }
        bool Button(string text,int height=44)=>GUILayout.Button(text,button,GUILayout.MinHeight(height));
        void OnGUI()
        {
            Styles();GUI.matrix=Matrix4x4.Scale(new Vector3(Screen.width/Width,Screen.height/Height,1));
            GUI.DrawTexture(new Rect(0,0,548,Height),panelTexture);
            GUILayout.BeginArea(new Rect(32,28,484,844));
            GUILayout.Label("APPEARANCE LAB",small);GUILayout.Space(6);GUILayout.Label("Shape your companion",title);
            GUILayout.Space(14);
            scroll=GUILayout.BeginScrollView(scroll);
            if(researcher)
            {
                GUILayout.BeginVertical(card);GUILayout.Label("Researcher setup  ·  F1 to hide",small);
                bool configure=trialIndex<0||(finished&&awaitingBlock);GUI.enabled=!Busy&&!validating&&configure;
                GUILayout.BeginHorizontal();participant=GUILayout.TextField(participant,input,GUILayout.Width(220));
                foreach(var p in new[]{"debug","pilot","formal"}) if(GUILayout.Toggle(phase==p,p,button))phase=p;
                GUILayout.EndHorizontal();
                GUILayout.BeginHorizontal();foreach(var p in policies)if(GUILayout.Toggle(condition==p,p,button))condition=p;GUILayout.EndHorizontal();
                GUILayout.Label("Manual condition: E execute / A ask / N native gate / S selective",small);
                GUI.enabled=!Busy&&!validating&&configure;
                if(Button("Start manual session")) {trialIndex=-1;studySessionId="";schedule.Clear();StartCoroutine(NewSession(true));}
                if(Button("Start assigned 16-task session"))StartCoroutine(StartScheduled());
                if(tasks.Length>0)
                {
                    GUILayout.BeginHorizontal();
                    if(Button("Previous",35))taskIndex=(taskIndex+tasks.Length-1)%tasks.Length;
                    GUILayout.Label(tasks[taskIndex].task_id,body,GUILayout.Width(90));
                    if(Button("Next",35))taskIndex=(taskIndex+1)%tasks.Length;
                    GUILayout.EndHorizontal();
                    GUI.enabled=!Busy&&!validating&&configure&&!string.IsNullOrEmpty(view.session_id);
                    if(Button("Load selected task",35))StartCoroutine(LoadTask());
                }
                GUI.enabled=true;GUILayout.EndVertical();GUILayout.Space(12);
            }
            if(trialIndex>=0) GUILayout.Label("Block "+schedule[trialIndex].block+" / 4    ·    Task "+schedule[trialIndex].withinBlock+" / 4",small);
            GUILayout.BeginVertical(card);GUILayout.Label("YOUR GOAL",small);GUILayout.Label(taskGoal,body);
            if(tasks.Length>0&&trialActive)
            {
                var context=tasks[taskIndex].model_visible;
                if(context.visible_history!=null&&context.visible_history.Length>0)
                {GUILayout.Label("PUBLIC HISTORY (earliest first)",small);foreach(var h in context.visible_history)GUILayout.Label(h.jacket_color+" / "+h.accessory+" / "+h.scale.ToString("0.00"),small);}
                if(context.soft_preferences!=null)foreach(var p in context.soft_preferences)GUILayout.Label("Preference: "+p,small);
            }
            GUILayout.EndVertical();GUILayout.Space(14);
            GUILayout.Label(Busy?"Working…":Status,body);GUILayout.Space(12);
            GUI.enabled=!Busy&&!validating&&!string.IsNullOrEmpty(view.session_id)&&!finished;
            if(view.decision=="ASK"&&view.question!=null)
            {
                GUILayout.BeginVertical(card);GUILayout.Label(view.question.text,body);
                if(view.question.options!=null) foreach(var option in view.question.options)
                {
                    if(option.id=="other")continue;
                    var captured=option.id;if(Button(option.label))StartCoroutine(SubmitAnswer(captured));
                }
                GUILayout.Label("Or describe what you mean",small);answerText=GUILayout.TextArea(answerText,input,GUILayout.Height(68));
                GUI.enabled=!Busy&&!validating&&!string.IsNullOrWhiteSpace(answerText);if(Button("Use this explanation"))StartCoroutine(SubmitAnswer("other"));
                GUI.enabled=!Busy&&!validating;GUILayout.EndVertical();
            }
            else
            {
                GUILayout.Label(initialSent?"REPAIR / FOLLOW-UP":"YOUR REQUEST",small);
                // Controlled first request is fixed; repairs are free text.
                bool editable=initialSent||researcher;GUI.enabled=!Busy&&!validating&&editable&&!finished;
                query=GUILayout.TextArea(query,input,GUILayout.Height(100));
                GUI.enabled=!Busy&&!validating&&!string.IsNullOrWhiteSpace(query)&&!string.IsNullOrEmpty(view.session_id)&&!finished;
                if(Button(initialSent?"Send repair":"Send request"))StartCoroutine(Submit());
            }
            GUILayout.Space(12);GUI.enabled=!Busy&&!validating&&!string.IsNullOrEmpty(view.session_id)&&!finished;
            GUILayout.BeginHorizontal();fieldIndex=GUILayout.SelectionGrid(fieldIndex,new[]{"All","Color","Accessory","Size"},4,button);GUILayout.EndHorizontal();
            if(Button(fieldIndex==0?"Undo last change":"Undo "+fields[fieldIndex]+" change"))StartCoroutine(Send(Route("undo"),new Undo{request_id=Id(),expected_revision=Revision,field=fields[fieldIndex]}));
            if(initialSent&&Button("Finish this task"))StartCoroutine(Finish("participant_done"));
            GUI.enabled=!Busy&&!validating;
            if(finished)
            {
                bool blockEnd=trialIndex>=0&&schedule[trialIndex].withinBlock==4;
                if(blockEnd)GUILayout.Label("Please complete the post-block questionnaire before continuing. Use block "+schedule[trialIndex].block+" and the session ID below.",body);
                if(!awaitingBlock&&Button(blockEnd?"Questionnaire complete · continue":"Next task"))StartCoroutine(Next());
            }
            GUI.enabled=true;GUILayout.EndScrollView();GUILayout.Space(10);
            GUILayout.Label("Study: "+studySessionId+(phase=="debug"?"  ·  DEBUG":""),small);
            if(researcher)GUILayout.Label("Backend: "+(view.session_id??"not started"),small);
            GUILayout.Label("F1  researcher controls    ·    Changes remain undoable",small);
            GUILayout.EndArea();
            GUI.Label(new Rect(620,42,700,44),"A familiar face. A different look.",title);
            GUI.Label(new Rect(620,90,700,50),"JACKET COLOR    /    ACCESSORY    /    SIZE",small);
            if(view.state!=null)GUI.Label(new Rect(620,820,750,50),view.state.jacket_color.ToUpperInvariant()+"     ·     "+view.state.accessory.ToUpperInvariant()+"     ·     "+view.state.scale.ToString("0.00")+"×",body);
        }

        [Serializable] class SmokeResult { public bool passed; public string error; public List<string> checks=new List<string>(); }
        void Check(bool value,string label,SmokeResult r) {if(!value)throw new Exception(label+" failed");r.checks.Add(label);}
        IEnumerator Smoke()
        {
            researcher=false;var r=new SmokeResult();
            // Same HTTP client, avatar application and acknowledgement path as the participant UI.
            foreach(string p in policies)
            {
                condition=p;participant="ENGINEERING_"+p;phase="debug";
                yield return Send("/sessions",new CreateSession{participant_id=participant,condition=p,phase=phase});
                if(!LastOk) {r.error="Session "+p+": "+Status;break;}
                yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query="Set the jacket to orange. Keep the accessory and size unchanged."});
                if(!LastOk) {r.error="Request "+p+": "+Status;break;}
                bool asked=view.decision=="ASK";
                if(asked)
                {
                    string option=null;foreach(var o in view.question.options)if(o.id!="cancel"&&o.id!="other"){option=o.id;break;}
                    yield return Send(Route("answer"),new Answer{request_id=Id(),expected_revision=Revision,option_id=option,free_text=""});
                }
                if(!LastOk||avatar.ObservedColor!="orange") {r.error="Rendered orange "+p;break;}
                if((p=="E"&&asked)||(p=="A"&&!asked)) {r.error="Gate semantics "+p;break;}
                r.checks.Add(p+" request/clarification/render: "+(asked?"ASK":"ACT"));
                yield return Send(Route("undo"),new Undo{request_id=Id(),expected_revision=Revision,field="jacket_color"});
                if(!LastOk||avatar.ObservedColor!="blue") {r.error="Undo "+p;break;}
                r.checks.Add(p+" field undo rendered blue");
            }
            if(r.error==null)
            {
                condition="S";
                yield return NewSession(false);
                yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query="Make your appearance warmer."});
                if(LastOk&&view.decision=="ASK")r.checks.Add("S materially ambiguous request ASK");else r.error="Selective ambiguous request: "+view.decision;
            }
            if(r.error==null)
            {
                yield return NewSession(false);
                yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query="Set jacket to purple, wear glasses and set scale to 1.10."});
                if(!LastOk||avatar.ObservedColor!="purple"||avatar.ObservedAccessory!="glasses"||Mathf.Abs(avatar.ObservedScale-1.1f)>.001f)r.error="Three-field edit";
                else r.checks.Add("Three appearance fields rendered");
                yield return Send(Route("undo"),new Undo{request_id=Id(),expected_revision=Revision,field="accessory"});
                if(!LastOk||avatar.ObservedAccessory!="none"||avatar.ObservedColor!="purple"||Mathf.Abs(avatar.ObservedScale-1.1f)>.001f)r.error="Partial undo preserved other fields";
                else r.checks.Add("Accessory-only undo preserves color and scale");
                yield return Send(Route("undo"),new Undo{request_id=Id(),expected_revision=Revision,field="all"});
                if(!LastOk||avatar.ObservedColor!="blue"||Mathf.Abs(avatar.ObservedScale-1)>.001f)r.error="Undo remaining edit";
                else r.checks.Add("Undo all remaining fields");
                taskIndex=0;yield return LoadTask();yield return Submit();
                if(!LastOk||avatar.ObservedColor!="orange"||avatar.ObservedAccessory!="hat")r.error="Controlled task reset and submit";
                else {r.checks.Add("Controlled task reset and submit");yield return Finish("engineering_done");if(!LastOk||!finished)r.error="Finish and probes";else r.checks.Add("Finish plus three actual renderer probes");}
            }
            r.passed=r.error==null;
            string dir=System.Environment.GetEnvironmentVariable("APPEARANCE_SMOKE_DIR")??Path.Combine(Application.persistentDataPath,"appearance-smoke");Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir,"unity-smoke.json"),JsonUtility.ToJson(r,true));
            yield return new WaitForEndOfFrame();ScreenCapture.CaptureScreenshot(Path.Combine(dir,"unity-smoke.png"));yield return new WaitForSeconds(2);
            Debug.Log("APPEARANCE_SMOKE "+JsonUtility.ToJson(r));Application.Quit(r.passed?0:1);
        }
    }
}
