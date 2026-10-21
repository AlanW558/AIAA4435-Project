using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Security.Cryptography;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace IAI.Appearance
{
    [Serializable] public class AppearanceState { public int revision; public string jacket_color="blue", accessory="hat", avatar_id, outfit; public float scale=1; }
    [Serializable] public class Choice { public string id, label; }
    [Serializable] public class Question { public string text; public Choice[] options; }
    [Serializable] public class SessionView { public string session_id,decision,message,error,capability_profile; public AppearanceState state; public Question question; }
    [Serializable] public class CreateSession { public string participant_id,condition,phase,capability_profile="study-v1"; }
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

    // JsonUtility emits null string fields. Explicit study DTOs keep the frozen
    // three-field wire protocol exact, including nested reset histories and probes.
    public static class AppearanceWire
    {
        [Serializable] sealed class StudyState { public int revision; public string jacket_color,accessory; public float scale; }
        [Serializable] sealed class StudyCreate { public string participant_id,condition,phase; }
        [Serializable] sealed class StudyReset : Mutation { public StudyState state; public StudyState[] history; public string[] soft_preferences; public string task_id; }
        [Serializable] sealed class StudyRenderPayload { public int revision,probe_index; public float duration_ms; public StudyState state; public string screenshot,message; }
        [Serializable] sealed class StudyRenderEvent { public string @event; public StudyRenderPayload payload; }
        static StudyState State(AppearanceState state)=>state==null?null:new StudyState{revision=state.revision,jacket_color=state.jacket_color,accessory=state.accessory,scale=state.scale};
        public static string Serialize(object payload,bool demo)
        {
            if(!demo)
            {
                if(payload is CreateSession create)
                    payload=new StudyCreate{participant_id=create.participant_id,condition=create.condition,phase=create.phase};
                else if(payload is Reset reset)
                    payload=new StudyReset{request_id=reset.request_id,expected_revision=reset.expected_revision,state=State(reset.state),history=reset.history==null?null:Array.ConvertAll(reset.history,State),soft_preferences=reset.soft_preferences,task_id=reset.task_id};
                else if(payload is RenderEvent render)
                    payload=new StudyRenderEvent{@event=render.@event,payload=new StudyRenderPayload{revision=render.payload.revision,probe_index=render.payload.probe_index,duration_ms=render.payload.duration_ms,state=State(render.payload.state),screenshot=render.payload.screenshot,message=render.payload.message}};
            }
            return JsonUtility.ToJson(payload);
        }
    }

    public sealed class AppearanceExperimentClient : MonoBehaviour
    {
        public string endpoint="http://127.0.0.1:8765";
        public AppearanceAvatar avatar;
        public bool worldSpaceUI;
        public Font participantFont;
        public SessionView view = new SessionView();
        public bool Busy { get; private set; }
        public string Status { get; private set; } = "正在连接，请稍候。";
        public bool LastOk { get; private set; }
        public string participant="DEBUG01",phase="debug",condition="S",query="",answerText="";
        public string capabilityProfile="study-v1";
        bool controlledTask, trialActive, trialStarted, initialSent, finished, awaitingBlock,validating,capturedFirst,initialized,faulted,studyComplete;
        StudyTask[] tasks=Array.Empty<StudyTask>();
        List<TrialRow> schedule = new List<TrialRow>();
        int taskIndex,trialIndex=-1,fieldIndex;
        float started;
        string lastResponse="", studySessionId="";
        string scheduleText="", observedBuild="", captureError;
        AppearanceSessionConfig launch;
        readonly List<string> capturePaths=new List<string>();
        public bool Initialized => initialized;
        public bool CanOperate => initialized&&!string.IsNullOrEmpty(view.session_id)&&!Busy&&!validating&&!faulted&&!finished&&trialActive;
        public bool CanEditQuery => CanOperate&&(initialSent||!controlledTask);
        public bool CanFinish => CanOperate&&initialSent;
        public bool IsQuestion => view.decision=="ASK"&&view.question!=null;
        public bool IsFinished => finished;
        public bool WaitingForBlock => awaitingBlock;
        public bool StudyComplete => studyComplete;
        public bool Faulted => faulted;
        public bool Validating => validating;
        public bool ControlledTask => controlledTask;
        public bool IsDemo => capabilityProfile=="avatar-demo-v1";
        public string StudySessionId => studySessionId;
        public string ObservedBuild => observedBuild;
        public string[] EvidencePaths => capturePaths.ToArray();
        public int TrialNumber => trialIndex+1;
        public TrialRow CurrentTrial => trialIndex>=0&&trialIndex<schedule.Count?schedule[trialIndex]:null;
        public string CurrentTask => controlledTask&&taskIndex>=0&&taskIndex<tasks.Length?tasks[taskIndex].task_id:"free";
        static readonly string[] studyFields={"all","jacket_color","accessory","scale"};
        static readonly string[] demoFields={"all","jacket_color","accessory","scale","avatar_id","outfit"};
        string[] fields=>IsDemo?demoFields:studyFields;
        string[] policies={"E","A","N","S"};
        Font font;
        GUIStyle title,body,small,button,input,card;
        Texture2D panelTexture,cardTexture,buttonTexture;
        Vector2 scroll;
        const float Width=1440,Height=900;

        IEnumerator Start()
        {
            endpoint=System.Environment.GetEnvironmentVariable("APPEARANCE_BACKEND_URL")??endpoint;
            try
            {
                if(avatar==null) { var go=new GameObject("Appearance avatar");go.transform.position=Vector3.up*.1f; avatar=go.AddComponent<AppearanceAvatar>(); }
                avatar.Create();
            }
            catch(Exception e){Fail("Avatar creation failed: "+e.GetType().Name);}
            if(faulted)yield break;
            yield return ReadAsset("tasks.json", text=>tasks=JsonUtility.FromJson<TaskList>(text).tasks);
            yield return ReadAsset("trial_schedule.csv", text=>scheduleText=text);
            if(faulted||tasks==null||tasks.Length==0){Fail("Study assets unavailable.");yield break;}
            font=participantFont?participantFont:Font.CreateDynamicFontFromOSFont(new[]{"Noto Sans CJK SC","Noto Sans","DejaVu Sans","Arial"},20);
            observedBuild=System.Environment.GetEnvironmentVariable("APPEARANCE_BUILD_SHA256")??"";
#if UNITY_ANDROID && !UNITY_EDITOR
            string configPath=Path.Combine(Application.persistentDataPath,"appearance-session.json");
            try { launch=JsonUtility.FromJson<AppearanceSessionConfig>(File.ReadAllText(configPath));launch.Validate(); }
            catch(Exception e){Fail("Researcher configuration: "+e.GetType().Name+": "+e.Message);}
            if(faulted)yield break;
            if(!string.IsNullOrEmpty(launch.backend_url))endpoint=launch.backend_url;
            string apkPath=Application.dataPath;
            var hashTask=Task.Run(()=>{using(var hash=SHA256.Create())using(var stream=File.OpenRead(apkPath))return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant();});
            while(!hashTask.IsCompleted)yield return null;
            if(hashTask.IsFaulted){Fail("Cannot fingerprint installed APK.");yield break;}
            observedBuild=hashTask.Result;
            if(!string.IsNullOrEmpty(launch.expected_build_sha256)&&launch.expected_build_sha256!=observedBuild){Fail("Installed build fingerprint mismatch.");yield break;}
#endif
            if(Array.IndexOf(System.Environment.GetCommandLineArgs(),"-appearance-smoke")>=0)yield return Smoke();
            else yield return InitializeInteraction();
            initialized=LastOk&&!faulted;
        }

        IEnumerator ReadAsset(string name,Action<string> consume)
        {
            string path=Application.streamingAssetsPath+"/AppearanceStudy/"+name;
            if(!path.Contains("://"))path=new Uri(path).AbsoluteUri;
            using(var request=UnityWebRequest.Get(path))
            {
                request.timeout=20;yield return request.SendWebRequest();
                if(request.result!=UnityWebRequest.Result.Success){Fail("Cannot load study asset: "+name);yield break;}
                try{consume(request.downloadHandler.text);}catch(Exception e){Fail("Invalid study asset "+name+": "+e.GetType().Name);}
            }
        }
        void Fail(string diagnostic)
        {
            faulted=true;LastOk=false;Status="互动暂时无法继续，请研究者检查后重试。";
            Debug.LogError("APPEARANCE_FAULT "+diagnostic);
        }

        IEnumerator InitializeInteraction()
        {
            participant=launch?.participant_id??System.Environment.GetEnvironmentVariable("APPEARANCE_PARTICIPANT_ID")??"DEBUG01";
            phase=launch?.phase??System.Environment.GetEnvironmentVariable("APPEARANCE_PHASE")??"debug";
            capabilityProfile=launch?.capability_profile??System.Environment.GetEnvironmentVariable("APPEARANCE_CAPABILITY_PROFILE")??capabilityProfile;
            if(string.IsNullOrEmpty(capabilityProfile))capabilityProfile="study-v1";
            condition=string.IsNullOrEmpty(launch?.condition)?System.Environment.GetEnvironmentVariable("APPEARANCE_CONDITION")??"S":launch.condition;
            studySessionId=launch?.study_session_id??System.Environment.GetEnvironmentVariable("APPEARANCE_STUDY_SESSION_ID")??"";
            bool assigned=launch!=null?launch.assigned:System.Environment.GetEnvironmentVariable("APPEARANCE_ASSIGNED")=="1";
            string selectedTask=launch?.task_id??System.Environment.GetEnvironmentVariable("APPEARANCE_TASK_ID");
            if((phase!="debug"&&phase!="pilot"&&phase!="formal")||Array.IndexOf(policies,condition)<0||
               (phase!="debug"&&string.IsNullOrEmpty(studySessionId))||(phase=="formal"&&!assigned)||
               (capabilityProfile!="study-v1"&&!IsDemo)||(IsDemo&&(phase!="debug"||assigned||!string.IsNullOrEmpty(selectedTask))))
            {Fail("Invalid researcher launch configuration; use the launcher.");yield break;}
            try{avatar.EnableDemo(IsDemo);}
            catch(Exception e){Fail("Avatar initialization failed: "+e.GetType().Name);}
            if(faulted)yield break;
            query="";
            if(assigned) {yield return StartScheduled();yield break;}
            if(!string.IsNullOrEmpty(selectedTask))
            {
                taskIndex=Array.FindIndex(tasks,t=>t.task_id==selectedTask);
                if(taskIndex<0){Fail("Unknown task in researcher launch configuration.");yield break;}
                yield return NewSession(true);
            }
            else yield return NewSession(false);
        }

        string Id()=>Guid.NewGuid().ToString("N");
        int Revision=>view.state==null?0:view.state.revision;

        public IEnumerator Send(string route,object payload,bool update=true)
        {
            LastOk=false; Busy=true;
            bool completed=false;
            try
            {
            avatar.SetInteraction("thinking");
            using(var req=new UnityWebRequest(endpoint.TrimEnd('/')+route,"POST"))
            {
                req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(AppearanceWire.Serialize(payload,IsDemo)));
                req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json"); req.timeout=100;
                yield return req.SendWebRequest();
                lastResponse=req.downloadHandler.text;
                if(req.result!=UnityWebRequest.Result.Success)
                {
                    SessionView err=null;
                    try { err=JsonUtility.FromJson<SessionView>(lastResponse); } catch(Exception) { }
                    ApplyRequestFailure(req.responseCode,err);
                    Debug.LogWarning("Appearance request failed: HTTP "+req.responseCode+" result="+req.result+" error="+req.error);
                }
                else
                {
                    if(update)
                    {
                        try
                        {
                            var next=JsonUtility.FromJson<SessionView>(lastResponse);
                            if(!ValidView(next)||ViewProfile(next)!=capabilityProfile)throw new FormatException("Invalid session snapshot or capability profile.");
                            view=next; Status=next.decision=="READY"?"你可以告诉我想怎样修改外形。":next.message??"已收到。";
                            avatar.Apply(next.state);LastOk=true;
                        }
                        catch(Exception e){Fail("Invalid backend response: "+e.GetType().Name);}
                    }
                    else LastOk=true;
                }
            }
            if(LastOk&&update&&view.state!=null&&!string.IsNullOrEmpty(view.session_id))
            {
                // Record the values applied by the renderer, not an inferred API success.
                yield return null;
                bool observedMatches=SameAppearance(Observed(),view.state,IsDemo);
                string capture=null;
                if(view.decision=="ACT"&&!capturedFirst){yield return Capture("first-commit",path=>capture=path);capturedFirst=capture!=null;}
                var ack=new RenderEvent {payload=new RenderPayload {revision=Revision,state=Observed(),screenshot=capture}};
                using(var req=new UnityWebRequest(endpoint.TrimEnd('/')+"/sessions/"+view.session_id+"/events","POST"))
                {
                    req.uploadHandler=new UploadHandlerRaw(Encoding.UTF8.GetBytes(AppearanceWire.Serialize(ack,IsDemo)));
                    req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json"); req.timeout=10;
                    Busy=true; yield return req.SendWebRequest();
                    if(req.result!=UnityWebRequest.Result.Success) {Fail("Render acknowledgement was not persisted.");LastOk=false;}
                }
                if(!observedMatches){Fail("Renderer observations do not match the authoritative appearance state.");LastOk=false;}
            }
            if(LastOk&&payload is RenderEvent rendered&&!SameAppearance(rendered.payload.state,view.state,IsDemo))
                Fail("Renderer persistence probe does not match the authoritative appearance state.");
            completed=true;
            }
            finally
            {
                Busy=false;
                if(!completed){LastOk=false;Fail("Request interrupted unexpectedly; preserve this trial for operator review.");}
                try{if(avatar)avatar.SetInteraction(view.decision=="ASK"?"ask":view.decision=="ACT"?"act":"idle");}
                catch(Exception e){Fail("Avatar feedback failed: "+e.GetType().Name);}
            }
        }

        string Route(string action)=>"/sessions/"+view.session_id+"/"+action;
        void ApplyRequestFailure(long code,SessionView error)
        {
            Status=error!=null&&!string.IsNullOrEmpty(error.message)?error.message:"连接失败，请稍后重试。";
            // The backend may already have counted the initial request before the provider failed.
            // A new request ID would consume a repair and must never substitute for that initial gate.
            if(code==0||code>=500||error?.error=="model_error")
            {Fail("Request outcome or initial gate is unconfirmed; preserve this trial for operator review. HTTP "+code);return;}
            // API errors use an ERROR envelope even when an authoritative pending question remains.
            if(error?.question!=null&&!string.IsNullOrEmpty(error.question.text))error.decision="ASK";
            if(!ValidView(error)||ViewProfile(error)!=capabilityProfile){Fail("Rejected request did not contain a valid authoritative snapshot.");return;}
            view=error;
            try{avatar.Apply(error.state);}
            catch(Exception e){Fail("Rejected request state could not be rendered: "+e.GetType().Name);}
        }
        static bool ValidView(SessionView next)
        {
            var state=next?.state;
            string profile=ViewProfile(next);
            bool demo=profile=="avatar-demo-v1";
            if(state==null||string.IsNullOrEmpty(next.session_id)||string.IsNullOrEmpty(next.decision)||state.revision<0||
                (profile!="study-v1"&&!demo)||
                Array.IndexOf(demo?new[]{"blue","orange","green","gray","red","purple","yellow"}:new[]{"blue","orange","green","gray","red","purple"},state.jacket_color)<0||
                Array.IndexOf(new[]{"none","hat","glasses"},state.accessory)<0||float.IsNaN(state.scale)||float.IsInfinity(state.scale)||
                state.scale<.8499f||state.scale>1.1501f||Mathf.Abs(state.scale*20-Mathf.Round(state.scale*20))>.001f)return false;
            if(demo)
            {
                if(Array.IndexOf(new[]{"liang","nailong"},state.avatar_id)<0||Array.IndexOf(new[]{"suit","sport","none"},state.outfit)<0||
                   (state.avatar_id=="nailong"&&state.outfit!="none"))return false;
            }
            else if(!string.IsNullOrEmpty(state.avatar_id)||!string.IsNullOrEmpty(state.outfit))return false;
            return next.decision!="ASK"||(next.question!=null&&!string.IsNullOrEmpty(next.question.text)&&next.question.options!=null&&next.question.options.Length>0&&Array.TrueForAll(next.question.options,o=>o!=null&&!string.IsNullOrEmpty(o.id)&&!string.IsNullOrEmpty(o.label)));
        }
        static string ViewProfile(SessionView next)=>string.IsNullOrEmpty(next?.capability_profile)?"study-v1":next.capability_profile;
        public static bool SameAppearance(AppearanceState a,AppearanceState b,bool demo)=>a!=null&&b!=null&&a.jacket_color==b.jacket_color&&a.accessory==b.accessory&&
            !float.IsNaN(a.scale)&&!float.IsInfinity(a.scale)&&Mathf.Abs(a.scale-b.scale)<.001f&&(!demo||(a.avatar_id==b.avatar_id&&a.outfit==b.outfit));
        public AppearanceState Observed()=>new AppearanceState{revision=Revision,jacket_color=avatar.ObservedColor,accessory=avatar.ObservedAccessory,scale=avatar.ObservedScale,
            avatar_id=IsDemo?avatar.ObservedAvatar:null,outfit=IsDemo?avatar.ObservedOutfit:null};
        IEnumerator Capture(string label,Action<string> done)
        {
            string root=System.Environment.GetEnvironmentVariable("APPEARANCE_CAPTURE_DIR")??Path.Combine(Application.persistentDataPath,"appearance-captures");
            string path=Path.Combine(root,view.session_id+"-r"+Revision+"-"+label+".png");
            yield return new WaitForEndOfFrame();
            Texture2D texture=null;
            try
            {
                Directory.CreateDirectory(root);
                texture=ScreenCapture.CaptureScreenshotAsTexture();
                if(!texture)throw new IOException("Screenshot capture returned no texture.");
                File.WriteAllBytes(path,texture.EncodeToPNG());capturePaths.Add(path);done(path);
            }
            catch(Exception e){captureError=e.GetType().Name;Fail("Screenshot persistence failed: "+captureError);done(null);}
            finally{if(texture)Destroy(texture);}
        }
        IEnumerator NewSession(bool loadTask)
        {
            if(string.IsNullOrEmpty(studySessionId))studySessionId=phase+"_"+participant+"_"+Guid.NewGuid().ToString("N");
            yield return Send("/sessions",new CreateSession{participant_id=participant,condition=condition,phase=phase,capability_profile=capabilityProfile});
            if(!LastOk){Fail("Session creation failed.");yield break;}
            if(LastOk&&loadTask) yield return LoadTask();
            else if(LastOk)
            {
                controlledTask=false;taskIndex=-1;query="";answerText="";initialSent=false;trialStarted=false;finished=false;capturedFirst=false;capturePaths.Clear();trialActive=true;started=Time.realtimeSinceStartup;
                yield return Marker("interaction_ready","");
            }
        }
        IEnumerator LoadTask()
        {
            if(taskIndex<0||taskIndex>=tasks.Length) yield break;
            var t=tasks[taskIndex];var c=t.model_visible;
            yield return Send(Route("reset"),new Reset{request_id=Id(),expected_revision=Revision,state=c.state,history=c.visible_history,soft_preferences=c.soft_preferences,task_id=t.task_id});
            if(!LastOk){Fail("Task reset failed; this trial cannot be skipped.");yield break;}
            controlledTask=true;query=c.initial_query;answerText="";initialSent=false;trialStarted=false;trialActive=true;finished=false;capturedFirst=false;capturePaths.Clear();started=Time.realtimeSinceStartup;
            yield return Marker("task_ready","");
        }
        IEnumerator Marker(string kind,string value)
        {
            var row=trialIndex>=0&&trialIndex<schedule.Count?schedule[trialIndex]:null;
            yield return Send(Route("events"),new MarkerEvent{payload=new MarkerPayload{kind=kind,value=value,study_session_id=studySessionId,observed_build_sha256=observedBuild,trial_id=row?.trialId??"debug",task_id=CurrentTask,block=row?.block??0,within_block=row?.withinBlock??0,elapsed_seconds=Time.realtimeSinceStartup-started}},false);
            if(!LastOk)Fail("Required client marker was not persisted: "+kind);
        }
        IEnumerator Submit()
        {
            if(!trialStarted) {started=Time.realtimeSinceStartup;yield return Marker("trial_start","");if(!LastOk)yield break;trialStarted=true;}
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
            if(!LastOk){Fail("Completion marker failed.");validating=false;yield break;}
            yield return Send(Route("finish"),new Mutation{request_id=Id(),expected_revision=Revision});
            if(!LastOk){Fail("Trial finish failed.");validating=false;yield break;}
            string[] turns={"修改已完成。","你可以看看现在的外形。","外形会保持当前状态。"};
            for(int i=0;i<turns.Length;i++)
            {
                float probeStarted=Time.realtimeSinceStartup;Status=turns[i];yield return new WaitForSeconds(1.5f);
                string capture=null;yield return Capture("probe-"+(i+1),path=>capture=path);
                if(faulted){validating=false;yield break;}
                yield return Send(Route("events"),new RenderEvent{@event="probe",payload=new RenderPayload{revision=Revision,state=Observed(),probe_index=i+1,duration_ms=(Time.realtimeSinceStartup-probeStarted)*1000,message=turns[i],screenshot=capture}},false);
                if(!LastOk){Fail("Persistence probe failed.");validating=false;yield break;}
            }
            validating=false;finished=true;Status="本次修改已结束。";Debug.Log("APPEARANCE_READY_FOR_NEXT block="+(trialIndex>=0?schedule[trialIndex].block:0)+" within="+(trialIndex>=0?schedule[trialIndex].withinBlock:0));
            avatar.SetInteraction("done");
        }
        IEnumerator StartScheduled()
        {
            if(phase!="formal"){Status="互动尚未准备好，请稍候。";Debug.LogError("Assigned schedule requires formal phase.");yield break;}
            schedule.Clear();trialIndex=-1;
            try{schedule=AppearanceSchedule.Parse(scheduleText,participant,tasks);}
            catch(ArgumentException e){Fail(e.Message);}
            if(faulted)yield break;
            trialIndex=0;yield return ScheduledTrial();
        }
        IEnumerator ScheduledTrial()
        {
            var row=schedule[trialIndex]; condition=row.condition;
            taskIndex=Array.FindIndex(tasks,t=>t.task_id==row.taskId);
            if(taskIndex<0) {Fail("Scheduled task is missing.");yield break;}
            if(row.withinBlock==1) yield return NewSession(true);else yield return LoadTask();
        }
        IEnumerator Next()
        {
            if(trialIndex<0) {if(controlledTask)yield return LoadTask();else yield return NewSession(false);yield break;}
            var step=AppearanceSchedule.Next(schedule,trialIndex);
            if(step==ScheduleStep.Complete) {Status="本次互动已结束，谢谢。";studyComplete=true;yield break;}
            if(step==ScheduleStep.Pause){awaitingBlock=true;Status="请稍作休息，准备好后我们继续。";yield return Marker("block_pause","");yield break;}
            trialIndex++;awaitingBlock=false;yield return ScheduledTrial();
        }

        public bool RequestSubmit(string text=null)
        {
            if(!CanOperate||IsQuestion)return false;
            if(text!=null){if(!CanEditQuery)return false;query=text;}
            if(string.IsNullOrWhiteSpace(query))return false;
            StartCoroutine(Submit());return true;
        }
        public bool RequestAnswer(string option,string text="")
        {
            if(!CanOperate||!IsQuestion||view.question.options==null||!Array.Exists(view.question.options,o=>o.id==option)||(option=="other"&&string.IsNullOrWhiteSpace(text)))return false;
            answerText=text;StartCoroutine(SubmitAnswer(option));return true;
        }
        public bool RequestUndo(string field)
        {
            if(!CanOperate||Array.IndexOf(fields,field)<0)return false;
            StartCoroutine(Send(Route("undo"),new Undo{request_id=Id(),expected_revision=Revision,field=field}));return true;
        }
        public bool RequestFinish()
        {
            if(!CanFinish)return false;StartCoroutine(Finish("participant_done"));return true;
        }
        public bool RequestNext()
        {
            if(!initialized||Busy||validating||faulted||!finished||awaitingBlock||studyComplete)return false;
            StartCoroutine(Next());return true;
        }
        public bool RequestResume()
        {
            if(Busy||validating||faulted||!awaitingBlock||trialIndex<0||trialIndex+1>=schedule.Count)return false;
            awaitingBlock=false;trialIndex++;StartCoroutine(ScheduledTrial());return true;
        }

        void Update()
        {
            // Researcher advances the frozen schedule between interactions; no study panel is rendered.
            if(UnityEngine.InputSystem.Keyboard.current!=null&&UnityEngine.InputSystem.Keyboard.current.f8Key.wasPressedThisFrame&&finished&&!awaitingBlock&&!Busy&&!validating)
                RequestNext();
            if(trialActive&&trialStarted&&!Busy&&!validating&&!faulted&&Time.realtimeSinceStartup-started>=(IsDemo?600:120)) StartCoroutine(Finish("timeout"));
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
            if(worldSpaceUI)return;
            Styles();GUI.matrix=Matrix4x4.Scale(new Vector3(Screen.width/Width,Screen.height/Height,1));
            GUI.DrawTexture(new Rect(0,0,548,Height),panelTexture);
            GUILayout.BeginArea(new Rect(32,28,484,844));
            GUILayout.Label("外形调整",title);
            GUILayout.Space(14);
            scroll=GUILayout.BeginScrollView(scroll);
            GUILayout.Label(Busy?"正在处理…":Status,body);GUILayout.Space(12);
            GUI.enabled=CanOperate;
            if(view.decision=="ASK"&&view.question!=null)
            {
                GUILayout.BeginVertical(card);GUILayout.Label(view.question.text,body);
                if(view.question.options!=null) foreach(var option in view.question.options)
                {
                    if(option.id=="other")continue;
                    var captured=option.id;if(Button(option.label))RequestAnswer(captured);
                }
                GUILayout.Label("也可以补充你的想法",small);answerText=GUILayout.TextArea(answerText,input,GUILayout.Height(68));
                GUI.enabled=CanOperate&&!string.IsNullOrWhiteSpace(answerText);if(Button("发送补充说明"))RequestAnswer("other",answerText);
                GUI.enabled=CanOperate;GUILayout.EndVertical();
            }
            else
            {
                GUILayout.Label("你想怎样修改？",small);
                // Controlled first request is fixed; repairs are free text.
                GUI.enabled=CanEditQuery;
                query=GUILayout.TextArea(query,input,GUILayout.Height(100));
                GUI.enabled=CanOperate&&!string.IsNullOrWhiteSpace(query);
                if(Button("发送"))RequestSubmit();
            }
            GUILayout.Space(12);GUI.enabled=CanOperate;
            fieldIndex=Mathf.Clamp(fieldIndex,0,fields.Length-1);
            GUILayout.BeginHorizontal();fieldIndex=GUILayout.SelectionGrid(fieldIndex,IsDemo?new[]{"全部","颜色","配饰","大小","形象","服装"}:new[]{"全部","颜色","配饰","大小"},IsDemo?3:4,button);GUILayout.EndHorizontal();
            if(Button("撤销上次修改"))RequestUndo(fields[fieldIndex]);
            GUI.enabled=CanFinish;if(trialStarted&&Button("完成修改"))RequestFinish();
            GUI.enabled=initialized&&!Busy&&!validating&&!faulted;
            if(finished&&trialIndex<0&&Button("继续修改"))RequestNext();
            GUI.enabled=true;GUILayout.EndScrollView();
            GUILayout.EndArea();
            GUI.Label(new Rect(620,42,700,44),"看看现在的样子",title);
            GUI.Label(new Rect(620,90,700,50),IsDemo?"形象    /    服装    /    颜色    /    配饰    /    大小":"衣服颜色    /    配饰    /    大小",small);

        }

        [Serializable] class SmokeResult { public bool passed; public string error; public List<string> checks=new List<string>(); }
        void Check(bool value,string label,SmokeResult r) {if(!value)throw new Exception(label+" failed");r.checks.Add(label);}
        IEnumerator Smoke()
        {
            var r=new SmokeResult();
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
                yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query="Make your appearance more formal."});
                if(LastOk&&view.decision=="ASK")r.checks.Add("S materially ambiguous request ASK");else r.error="Selective ambiguous request: "+view.decision;
            }
            if(r.error==null)
            {
                yield return NewSession(false);
                yield return Send(Route("request"),new Request{request_id=Id(),expected_revision=Revision,query="Set jacket to purple, wear glasses and set scale=1.10."});
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
