using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

namespace IAI.Tutor
{
    /// <summary>New-contract participant flow. All advancement is receipt-gated.</summary>
    public sealed class TutorStudyFlowPanel : MonoBehaviour
    {
        public TutorStudyDataClient Data { get; private set; }
        public TutorSpeechInput Speech { get; private set; }
        public JObject State { get; private set; }
        public string RunId => State?.Value<string>("study_run_id");
        public bool Visible { get; private set; } = true;
        public bool Running { get; private set; }
        public bool InstructionsOpen => State == null || ShowingIntro || State.Value<string>("lifecycle") != "active" || !Data.Ready;
        public bool CanRecordComment => State?.Value<string>("lifecycle")=="active" && !Running && Data.Ready && (CurrentQuestionnaire != null || PreferenceScope != null) && Visible;
        public string CommentContext => CanRecordComment ? RunId + ":" + Revision + ":" + (CurrentQuestionnaire?.Value<string>("questionnaire_id") ?? PreferenceScope) : null;
        public string CommentTarget => PreferenceScope ?? CurrentQuestionnaire?.Value<string>("questionnaire_id");
        public string CommentCondition => PreferenceScope!=null?"preference":naturalModule!=null?"S":selected;
        public int Revision => State?.Value<int>("revision") ?? 0;
        public string Error { get; private set; } = "";
        public string PriorParticipation = "not_reported";
        TutorPanel owner; TutorComparisonClient comparison; TutorClient single;
        TutorTaskManifest tasks; JObject catalog, config;
        JObject currentTask, naturalModule;
        string selected="E", currentItem="A0", lastRuntime="", attachedKind="", itemKey="", pendingRestore;
        bool failed, ShowingIntro=true, questionnaireOpen, exitRequested, showReasons, reviewComment, showComment;
        JObject localAnswers, localExtras;
        readonly Dictionary<string,JObject> drafts=new Dictionary<string,JObject>();
        readonly HashSet<string> preferred=new HashSet<string>();
        string preferenceKind="", preferenceComment="", loadedPreferenceScope="";
        GameObject content; RectTransform canvasRoot; Canvas canvas; CanvasGroup group;
        IAI.UI.WorldSpacePanelDragHandle dragHandle;
        static readonly Vector2 ExpandedPanelSize = new Vector2(920,1050);
        static readonly Vector2 CollapsedPanelSize = new Vector2(250,52);
        static readonly Vector2 TogglePosition = new Vector2(280,-485);
        Button toggle; Text header, status;
        Font font;
        readonly Color paper=new Color(.96f,.94f,.88f,1), ink=new Color(.14f,.20f,.22f,1), accent=new Color(.17f,.38f,.40f,1);
        JObject CurrentQuestionnaire => State==null || !questionnaireOpen ? null : ((JObject)State["questionnaires"]).Properties().Select(p=>(JObject)p.Value).FirstOrDefault(q=>q.Value<string>("target_id")==TargetId && q.Value<string>("condition")== (naturalModule!=null?"S":selected));
        public TutorTaskCard CurrentCard => currentTask==null?null:tasks.modules.SelectMany(m=>m.tasks).FirstOrDefault(t=>t.task_code==currentTask.Value<string>("task_code"));
        public bool MaterialAvailable => naturalModule==null && !InstructionsOpen && !questionnaireOpen && Visible;
        string TargetId => naturalModule?.Value<string>("module_instance_id") ?? currentTask?.Value<string>("task_id");
        string PreferenceScope
        {
            get
            {
                if(State==null || naturalModule!=null || currentTask==null || currentTask["submission_id"].Type==JTokenType.Null)return null;
                string domain=currentTask.Value<string>("domain");
                var done=((JObject)State["tasks"]).Properties().Select(p=>p.Value).Where(t=>t["submission_id"].Type!=JTokenType.Null).ToArray();
                int planned=tasks.modules.First(m=>m.direction==domain).tasks.Length;
                if(done.Count(t=>t.Value<string>("domain")==domain)==planned && State["preferences"]?[domain]==null)return domain;
                if(done.Length==tasks.modules.Sum(m=>m.tasks.Length) && State["preferences"]?["comparison_overall"]==null)return "comparison_overall";
                return null;
            }
        }
        public void Initialize(TutorPanel panel)
        {
            owner=panel; comparison=panel.comparison; comparison.studyManaged=true; font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tasks=TutorTaskManifest.Parse(Resources.Load<TextAsset>("Tutor/StudyTaskSequence").text);
            catalog=JObject.Parse(Resources.Load<TextAsset>("Tutor/StudyQuestionnaires").text);
            Data=gameObject.AddComponent<TutorStudyDataClient>();Data.endpoint=System.Environment.GetEnvironmentVariable("TUTOR_BACKEND_URL")??comparison.endpoint;comparison.endpoint=Data.endpoint;
            Speech=gameObject.AddComponent<TutorSpeechInput>();Speech.panel=owner;Speech.flowPanel=this;
            Speech.Changed+=Render;comparison.Changed+=RuntimeChanged;
            var eye=panel.seat?panel.seat.seatAnchor.position+Vector3.up*panel.seat.seatedEyeHeight:Camera.main.transform.position;
            var forward=Vector3.ProjectOnPlane(panel.seat?panel.seat.seatAnchor.forward:Camera.main.transform.forward,Vector3.up).normalized;
            if(forward.sqrMagnitude<.1f)forward=Vector3.forward;
            transform.position=eye+Quaternion.LookRotation(forward)*panel.studySeatOffset;
            // Turn clockwise by 5 degrees from above, around the panel's own vertical axis.
            transform.rotation=Quaternion.AngleAxis(5f,Vector3.up)*Quaternion.LookRotation(transform.position-eye,Vector3.up);
            canvasRoot=Rect("Study flow canvas",transform,Vector2.zero,ExpandedPanelSize);canvasRoot.localScale=Vector3.one*.0012f;
            canvas=canvasRoot.gameObject.AddComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;canvas.worldCamera=Camera.main;
            canvasRoot.gameObject.AddComponent<CanvasScaler>();canvasRoot.gameObject.AddComponent<IAI.UI.DesktopPanelRaycaster>();canvasRoot.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>();
            group=canvasRoot.gameObject.AddComponent<CanvasGroup>();canvasRoot.gameObject.AddComponent<Image>().color=paper;
            // Floor clearance is computed from the actual canvas, including its tilt.
            var corners=new Vector3[4];canvasRoot.GetWorldCorners(corners);
            float bottom=corners.Min(c=>c.y);if(bottom<panel.panelMinimumBottomY)transform.position+=Vector3.up*(panel.panelMinimumBottomY-bottom);
            dragHandle=IAI.UI.WorldSpacePanelDragHandle.Attach(canvasRoot,transform,new Vector2(0,480),new Vector2(900,80),font,ink,panel.panelMinimumBottomY);
            header=Label(canvasRoot,"Research session",new Vector2(0,480),new Vector2(840,40),24);
            status=Label(canvasRoot,"",new Vector2(0,-434),new Vector2(840,28),20);
            toggle=Button(canvasRoot,"Hide panel",TogglePosition,new Vector2(250,40),ToggleVisibility,22);
            if(Data.Journal!=null)
            {
                var receipt=Data.Journal.LatestReceipt;
                if(!string.IsNullOrEmpty(receipt))pendingRestore=JObject.Parse(receipt).Value<string>("study_run_id");
            }
            Render();
        }
        void Update()
        {
            if(owner==null)return;
            bool seated=!owner.seat || owner.seat.IsSeated;group.alpha=seated?1:0;group.blocksRaycasts=group.interactable=seated;
            bool locked=InstructionsOpen || Running || exitRequested || PreferenceScope!=null || (naturalModule??currentTask)?["submission_id"]?.Type==JTokenType.String || (naturalModule!=null && naturalModule.Value<bool>("frozen"));
            comparison.studyLocked=locked;comparison.instructionsOpen=InstructionsOpen;
            if(single)single.studyLocked=locked;
            if(!canvas.worldCamera)canvas.worldCamera=Camera.main;
            status.text=Running?"Saving / synchronizing…":Error.Length>0?Error:Data.Error.Length>0?Data.Error:IdleStatus();
        }
        void OnDisable(){if(Speech)Speech.Cancel();}
        void RuntimeChanged(){if(naturalModule==null && comparison.Connected)selected=comparison.Selected;Render();}
        void OnDestroy(){if(Speech)Speech.Changed-=Render;if(comparison)comparison.Changed-=RuntimeChanged;if(single)single.Changed-=Render;}
        void Begin(IEnumerator action)
        {
            if(Running)return;Error="";failed=false;StartCoroutine(Work(action));
        }
        IEnumerator Work(IEnumerator action)
        {
            Running=true;Render();
            try {yield return action;}
            finally {Running=false;Render();owner.Render();}
        }
        IEnumerator Get(string route,Action<JObject> accept)
        {
            using(var r=UnityWebRequest.Get(Data.endpoint.TrimEnd('/')+route))
            {
                r.timeout=20;yield return r.SendWebRequest();
                if(r.result!=UnityWebRequest.Result.Success){failed=true;Error="Connection interrupted. Saved data are retained; retry synchronization.";yield break;}
                try{accept(JObject.Parse(r.downloadHandler.text));}
                catch(Exception e){failed=true;Error="The saved study response could not be verified ("+e.GetType().Name+").";}
            }
        }
        IEnumerator Refresh()
        {
            string id=RunId ?? pendingRestore;if(string.IsNullOrEmpty(id)){failed=true;yield break;}
            yield return Get("/study/runs/"+id+"/snapshot",r=>
            {
                if(r["state"]?.Value<string>("study_run_id")!=id || r["state"]?.Value<string>("data_contract_version")!="study-data-contract-v1" || r.Value<bool>("replay_model_calls"))throw new InvalidOperationException();
                State=(JObject)r["state"];Data.Journal.SaveLocal("run:"+id,r.ToString(Formatting.None),true);pendingRestore=id;
                var all=((JObject)State["tasks"]).Properties().Select(p=>(JObject)p.Value).ToArray();
                currentTask=all.OrderBy(t=>Array.FindIndex(tasks.modules.SelectMany(m=>m.tasks).ToArray(),c=>c.task_code==t.Value<string>("task_code"))).LastOrDefault();
                naturalModule=((JObject)State["modules"]).Properties().Select(p=>(JObject)p.Value).FirstOrDefault(m=>m.Value<string>("module_type")=="natural_selective");
            });
        }
        IEnumerator Command(string op,JObject payload)
        {
            string request=null;
            try{request=Data.Send(op,RunId,Revision,payload.ToString(Formatting.None));}
            catch(Exception){failed=true;Error="Saving is blocked. Resolve the pending request first.";}
            if(failed)yield break;
            while(Data.Busy)yield return null;
            if(Data.Journal.PendingCount>0 || Data.StorageFault || Data.RejectedRequestId==request){failed=true;Error=Data.Error;yield break;}
            var ack=JObject.Parse(Data.LastReceiptJson);
            if(ack.Value<string>("request_id")!=request){failed=true;Error="Submission receipt mismatch.";yield break;}
            if(op=="create_run")pendingRestore=ack.Value<string>("study_run_id");
            if(op!="register_participant")yield return Refresh();
        }
        public void StartStudy(){Begin(StartNew());}
        IEnumerator StartNew()
        {
            yield return Get("/study/config",v=>config=v);if(failed)yield break;
            yield return Command("register_participant",new JObject{["prior_participation"]=PriorParticipation});if(failed)yield break;
            var participant=JObject.Parse(Data.LastReceiptJson)["result"].Value<string>("participant_id");
            var manifest=new JObject{["protocol_version"]="study-protocol-v1.7",["task_manifest_version"]=tasks.materials_version,
                ["task_manifest_sha256"]=tasks.catalog_sha256,["questionnaire_manifest_sha256"]=TutorStudyJournal.Hash(Resources.Load<TextAsset>("Tutor/StudyQuestionnaires").text),
                ["app_build_id"]="unity-study-flow-v1",["backend_build_id"]=config["backend_build_id"],["configuration_sha256"]=TutorStudyJournal.Hash(config.ToString(Formatting.None)),
                ["execution_sequence"]=JObject.Parse(JsonUtility.ToJson(TutorTaskNavigation.PublicSequence(tasks))),
                ["tasks"]=new JArray(tasks.modules.SelectMany(m=>m.tasks.Select(t=>new JObject{["task_code"]=t.task_code,["domain"]=m.direction,["scenario"]=t.scenario})))};
            yield return Command("create_run",new JObject{["participant_id"]=participant,["collection_kind"]="engineering",["execution_mode"]=config["mode"],["manifest"]=manifest});
            if(!failed)yield return OpenNextTask();
        }
        IEnumerator OpenNextTask()
        {
            var saved=((JObject)State["tasks"]).Properties().Select(p=>p.Value.Value<string>("task_code")).ToArray();
            var task=State["manifest"]["tasks"].FirstOrDefault(t=>!saved.Contains(t.Value<string>("task_code")));
            if(task==null){ShowingIntro=true;yield break;}
            string domain=task.Value<string>("domain");
            var module=((JObject)State["modules"]).Properties().Select(p=>p.Value).FirstOrDefault(m=>m.Value<string>("domain")==domain);
            if(module==null)
            {
                yield return Command("open_module",new JObject{["module_type"]="attribute_comparison",["domain"]=domain});if(failed)yield break;
                module=((JObject)State["modules"]).Properties().Select(p=>p.Value).First(m=>m.Value<string>("domain")==domain);
            }
            yield return Command("open_task",new JObject{["module_instance_id"]=module["module_instance_id"],["task_code"]=task["task_code"]});if(failed)yield break;
            yield return LaunchCurrent();ShowingIntro=true;questionnaireOpen=false;
        }
        IEnumerator LaunchCurrent()
        {
            var target=naturalModule??currentTask;if(target==null)yield break;
            if(target["runtime_id"]==null)
            {yield return Command("launch_runtime",new JObject{["target_id"]=TargetId});if(failed)yield break;target=naturalModule??currentTask;}
            comparison.studyJournal=Data.Journal;comparison.studyRunId=RunId;
            string id=target.Value<string>("runtime_id");
            if(id==lastRuntime)yield break;
            if(naturalModule!=null)
            {
                if(!single){single=owner.gameObject.AddComponent<TutorClient>();single.avatar=comparison.avatar;single.endpoint=Data.endpoint;single.studyManaged=true;single.connectOnStart=false;single.Changed+=Render;}
                single.studyJournal=Data.Journal;single.studyRunId=RunId;owner.UseNaturalClient(single);single.AttachStudyRuntime(id);attachedKind="sessions";
            }
            else {comparison.AttachStudyRuntime(id);attachedKind="comparisons";}
            lastRuntime=id;
            float until=Time.realtimeSinceStartup+25;
            while(Time.realtimeSinceStartup<until && (naturalModule!=null ? !single.Connected : !comparison.Connected))yield return null;
            if(naturalModule!=null ? !single.Connected : !comparison.Connected){failed=true;lastRuntime="";Error="Execution could not be restored. Keep the saved run; retry or exit without submitting.";}
        }
        IEnumerator RecoverRuntimeReceipts()
        {
            var missing=Data.Journal.Entries.Where(e=>e.kind=="draft" && e.scope.StartsWith("runtime:") && Data.Journal.RestoreLocal("runtime-ack:"+e.scope.Substring(8))==null).ToArray();
            foreach(var entry in missing)
            {
                var packet=JObject.Parse(entry.payload);if(packet.Value<string>("study_run_id")!=RunId)continue;
                using(var r=new UnityWebRequest(Data.endpoint.TrimEnd('/')+"/study/runs/"+RunId+"/runtime-receipt","POST"))
                {
                    r.uploadHandler=new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(entry.payload));r.downloadHandler=new DownloadHandlerBuffer();r.timeout=20;r.SetRequestHeader("Content-Type","application/json");
                    yield return r.SendWebRequest();
                    if(r.result!=UnityWebRequest.Result.Success){failed=true;Error="An earlier tutor operation needs inspection. Its original input is saved; no model call was replayed. Retry synchronization or exit without submitting.";yield break;}
                    try
                    {
                        var receipt=JObject.Parse(r.downloadHandler.text);
                        if(!receipt.Value<bool>("recorded") || receipt.Value<bool>("replay_model_calls") || receipt.Value<string>("study_run_id")!=RunId || receipt.Value<string>("runtime_id")!=packet.Value<string>("runtime_id") || receipt.Value<string>("request_id")!=packet["body"].Value<string>("request_id"))throw new InvalidOperationException();
                        TutorStudyRuntimeEvidence.Acknowledge(Data.Journal,entry.scope,receipt["response"]["body"].ToString(Formatting.None));
                    }
                    catch(Exception){failed=true;Error="The recovered tutor receipt could not be saved or verified.";}
                    if(failed)yield break;
                }
            }
        }
        public void RestoreStudy(){Begin(Restore());}
        IEnumerator Restore()
        {
            if(comparison.Busy || single && single.Busy){failed=true;Error="Wait for the current connection attempt before synchronizing.";yield break;}
            if(Data.Journal.PendingCount>0)
            {
                Data.Retry();while(Data.Busy)yield return null;
                if(Data.Journal.PendingCount>0){failed=true;Error=Data.Error;yield break;}
                pendingRestore=JObject.Parse(Data.LastReceiptJson).Value<string>("study_run_id");
            }
            yield return Refresh();if(failed)yield break;
            if(State.Value<string>("lifecycle")!="ended"){yield return RecoverRuntimeReceipts();if(failed)yield break;}
            lastRuntime="";
            yield return Get("/study/config",v=>config=v);if(failed)yield break;
            if(State.Value<string>("lifecycle")=="ended")yield break;
            if(naturalModule?["submission_id"]?.Type==JTokenType.String)
            {yield return Command("end_run",new JObject{["end_reason"]="normal_completion"});yield break;}
            if(naturalModule==null && (currentTask==null || (currentTask["submission_id"]?.Type==JTokenType.String && PreferenceScope==null)))
            {yield return OpenNextTask();yield break;}
            if((naturalModule??currentTask)["submission_id"]?.Type!=JTokenType.String)yield return LaunchCurrent();
            questionnaireOpen=(naturalModule!=null && naturalModule.Value<bool>("frozen")) || currentTask?["evaluation"]?.Type==JTokenType.Object;
            ShowingIntro=!questionnaireOpen;
        }
        public void CaptureEvaluation(){Begin(Capture());}
        IEnumerator Capture()
        {
            yield return Command(naturalModule==null?"capture_evaluation":"finish_natural",new JObject{[naturalModule==null?"task_id":"module_instance_id"]=TargetId});
            if(!failed){questionnaireOpen=true;ShowingIntro=false;currentItem=naturalModule==null?"A0":"N0";itemKey="";}
        }
        string EvaluationBasis(JObject q)
        {
            var target=(JObject)(q["task_id"].Type==JTokenType.Null?State["modules"][q.Value<string>("module_instance_id")]:State["tasks"][q.Value<string>("task_id")]);
            var binding=q["task_id"].Type==JTokenType.Null?target["evaluation"]:target["evaluation"]?["branches"]?[q.Value<string>("condition")];
            return q.Value<string>("target_id")+":"+q.Value<string>("condition")+":"+(q["task_id"].Type==JTokenType.Null?target.Value<int>("evaluation_revision").ToString():binding?["branch_revision"]+":"+binding?["state_revision"]);
        }
        JObject EnsureDraft(JObject q)
        {
            string qid=q.Value<string>("questionnaire_id"),basis=EvaluationBasis(q);
            if(!drafts.TryGetValue(qid,out var draft))
            {
                string local=Data.Journal.RestoreLocal("draft:"+qid);
                if(local!=null)draft=JObject.Parse(local);
                else
                {
                    var answers=(JObject)q["answers"].DeepClone();
                    if(q.Value<string>("evaluation_status")=="stale")foreach(var p in answers.Properties().ToArray())answers[p.Name]=new JObject{["status"]="unanswered",["value"]=JValue.CreateNull()};
                    draft=new JObject{["answers"]=answers,["extras"]=q["extras"].DeepClone(),["evaluation_basis"]=basis};
                }
                drafts[qid]=draft;
            }
            if(draft.Value<string>("evaluation_basis")!=basis)
            {
                var answers=(JObject)draft["answers"];
                foreach(var p in answers.Properties().ToArray())answers[p.Name]=new JObject{["status"]="unanswered",["value"]=JValue.CreateNull()};
                draft["extras"]=new JObject{["reasons"]=new JArray(),["comment"]="",["comment_confirmed"]=false};draft["evaluation_basis"]=basis;
                Data.SaveDraft(qid,draft.ToString(Formatting.None));
            }
            return draft;
        }
        JObject Draft()
        {
            var q=CurrentQuestionnaire;if(q==null)return null;
            var draft=EnsureDraft(q);localAnswers=(JObject)draft["answers"];localExtras=(JObject)draft["extras"];return draft;
        }
        public void Choose(string item,string statusValue,JToken value,string reason=null)
        {
            if(Running || !Data.Ready || Draft()==null)return;
            var answer=new JObject{["status"]=statusValue,["value"]=value??JValue.CreateNull()};if(reason!=null)answer["reason"]=reason;
            localAnswers[item]=answer;
            if(item=="A0" && (string)value=="fully_met")localExtras["reasons"]=new JArray();
            PersistDraft();Render();
        }
        void PersistDraft()
        {
            var q=CurrentQuestionnaire;if(q!=null && !Data.SaveDraft(q.Value<string>("questionnaire_id"),drafts[q.Value<string>("questionnaire_id")].ToString(Formatting.None)))Error=Data.Error;
        }
        public void ConfirmComment(string text)
        {
            if(!CanRecordComment || string.IsNullOrWhiteSpace(text))return;
            if(PreferenceScope!=null){preferenceComment=text;Data.SaveLocalDraft("preference:"+RunId+":"+PreferenceScope,PreferenceAnswers().ToString(Formatting.None));}
            else{Draft();localExtras["comment"]=text;localExtras["comment_confirmed"]=true;PersistDraft();}Render();
        }
        bool AnsweredAll(JObject q)
        {
            var a=(JObject)EnsureDraft(q)["answers"];
            return a.Properties().All(p=>new[]{"answered","unable_to_judge","not_applicable"}.Contains(p.Value.Value<string>("status")) || (p.Name.StartsWith("S") || p.Name.StartsWith("U")) && p.Value.Value<string>("status")=="skipped");
        }
        public void SaveQuestionnaire(){Begin(SaveCurrent());}
        IEnumerator SaveCurrent()
        {
            var q=CurrentQuestionnaire;if(q==null || !AnsweredAll(q)){failed=true;Error="Answer each item before saving this evaluation.";yield break;}
            var draft=Draft();var target=naturalModule??currentTask;
            yield return Command("save_feedback",new JObject{["module_instance_id"]=q["module_instance_id"],["task_id"]=q["task_id"],["condition"]=q["condition"],
                ["questionnaire_version"]=q["questionnaire_version"],["evaluation_revision"]=target["evaluation_revision"],["answers"]=draft["answers"].DeepClone(),["extras"]=draft["extras"].DeepClone()});
        }
        public bool ReadyToSubmit
        {
            get
            {
                if(State==null || !questionnaireOpen)return false;
                var qs=((JObject)State["questionnaires"]).Properties().Select(p=>(JObject)p.Value).Where(q=>q.Value<string>("target_id")==TargetId).ToArray();
                return qs.Length==(naturalModule!=null?1:4) && qs.All(AnsweredAll);
            }
        }
        public void SubmitAndNext(){Begin(SubmitNext());}
        IEnumerator SubmitNext()
        {
            var qs=((JObject)State["questionnaires"]).Properties().Select(p=>(JObject)p.Value).Where(q=>q.Value<string>("target_id")==TargetId).ToArray();
            if(!ReadyToSubmit){failed=true;Error="Complete every required evaluation before continuing.";yield break;}
            foreach(var q in qs)
            {
                var draft=drafts.TryGetValue(q.Value<string>("questionnaire_id"),out var found)?found:new JObject{["answers"]=q["answers"].DeepClone(),["extras"]=q["extras"].DeepClone()};
                yield return Command("save_feedback",new JObject{["module_instance_id"]=q["module_instance_id"],["task_id"]=q["task_id"],["condition"]=q["condition"],
                    ["questionnaire_version"]=q["questionnaire_version"],["evaluation_revision"]=(naturalModule??currentTask)["evaluation_revision"],["answers"]=draft["answers"].DeepClone(),["extras"]=draft["extras"].DeepClone()});
                if(failed)yield break;
            }
            if(naturalModule!=null)
            {
                yield return Command("submit_natural",new JObject{["module_instance_id"]=TargetId,["evaluation_revision"]=naturalModule["evaluation_revision"]});if(failed)yield break;
                yield return Command("end_run",new JObject{["end_reason"]="normal_completion"});yield break;
            }
            yield return Command("submit_task",new JObject{["task_id"]=TargetId,["evaluation_revision"]=currentTask["evaluation_revision"]});if(failed)yield break;
            questionnaireOpen=false;
            if(PreferenceScope==null)yield return OpenNextTask();
        }
        JObject PreferenceAnswers()=>new JObject{["choice_kind"]=preferenceKind,["selected_conditions"]=new JArray(preferred),["comment"]=preferenceComment,["comment_confirmed"]=preferenceComment.Length>0};
        public void SelectApproach(string condition)
        {if(!"EANS".Contains(condition)||condition.Length!=1||Running)return;selected=condition;showReasons=false;showComment=false;currentItem="A0";if(Speech)Speech.Cancel();comparison.Select(condition);Render();}
        public void ChoosePreference(string kind, params string[] conditions)
        {
            if(PreferenceScope==null||Running)return;preferenceKind=kind;preferred.Clear();foreach(string c in conditions)preferred.Add(c);
            Data.SaveLocalDraft("preference:"+RunId+":"+PreferenceScope,PreferenceAnswers().ToString(Formatting.None));Render();
        }
        public void ContinueInteraction(){ShowingIntro=false;questionnaireOpen=false;Render();owner.Render();}
        public void SubmitPreference(){Begin(SavePreference());}
        IEnumerator SavePreference()
        {
            var scope=PreferenceScope;
            yield return Command("preference",new JObject{["scope"]=scope=="comparison_overall"?"comparison_overall":"attribute",["domain"]=scope=="comparison_overall"?JValue.CreateNull():new JValue(scope),["answers"]=PreferenceAnswers()});
            if(failed)yield break;preferred.Clear();preferenceKind="";preferenceComment="";
            if(PreferenceScope==null)yield return OpenNextTask();
        }
        public void StartNatural(){Begin(Natural());}
        IEnumerator Natural()
        {
            if(config==null){yield return Get("/study/config",v=>config=v);if(failed)yield break;}
            yield return Command("open_module",new JObject{["module_type"]="natural_selective",["domain"]=JValue.CreateNull(),["initial_state"]=config["defaults"]});if(failed)yield break;
            yield return LaunchCurrent();ShowingIntro=true;questionnaireOpen=false;
        }
        public void PauseResume(){Begin(Command(State.Value<string>("lifecycle")=="paused"?"resume":"pause",new JObject()));if(owner.Speech)owner.Speech.Cancel();if(owner.Playback)owner.Playback.Stop(reason:"study_pause");}
        public void ExitStudy()
        {
            exitRequested=true;if(owner.Speech)owner.Speech.Cancel();if(Speech)Speech.Cancel();
            if(owner.Playback)owner.Playback.Stop(reason:"study_exit");
            Data.SaveLocalDraft("exit:"+RunId,new JObject{["end_reason"]="participant_exit"}.ToString(Formatting.None));
            if(!Running && Data.Ready)Begin(Command("end_run",new JObject{["end_reason"]="participant_exit"}));
            else{Error="Exit intent saved locally. Synchronize pending data, then confirm exit.";Render();}
        }
        public void ToggleVisibility()
        {
            Visible=!Visible;
            if(!Visible && Speech)Speech.Cancel();
            Render();
        }
        void ApplyPanelVisibility()
        {
            // Keep the show button where the hide button was, without leaving a full-size raycast surface.
            canvasRoot.sizeDelta=Visible?ExpandedPanelSize:CollapsedPanelSize;
            canvasRoot.localPosition=Visible?Vector3.zero:Vector3.Scale(new Vector3(TogglePosition.x,TogglePosition.y,0),canvasRoot.localScale);
            canvasRoot.GetComponent<Image>().enabled=Visible;
            header.gameObject.SetActive(Visible);status.gameObject.SetActive(Visible);
            dragHandle.gameObject.SetActive(Visible);
            var rect=(RectTransform)toggle.transform;
            rect.anchoredPosition=Visible?TogglePosition:Vector2.zero;
            rect.sizeDelta=Visible?new Vector2(250,40):CollapsedPanelSize;
            var label=toggle.GetComponentInChildren<Text>();
            label.text=Visible?"Hide panel":"Show panel";
            label.rectTransform.sizeDelta=rect.sizeDelta-new Vector2(12,4);
        }
        public void Render()
        {
            if(!canvasRoot)return;
            if(content){content.SetActive(false);Destroy(content);}
            ApplyPanelVisibility();
            if(!Visible)return;
            content=new GameObject("Study page",typeof(RectTransform));content.transform.SetParent(canvasRoot,false);
            var root=(RectTransform)content.transform;root.sizeDelta=new Vector2(880,1020);
            header.text=State==null?"Research session · local preview":$"{State.Value<string>("participant_id")} · {(naturalModule!=null?"Natural conversation":(currentTask?.Value<string>("domain")??"Setup").Replace('_',' '))}";
            if(State==null)
            {
                Label(root,"Four communication attributes, followed by a natural conversation.\n\nUse your own words.\n\nEngineering preview · not formal participant collection.",new Vector2(0,180),new Vector2(820,210),25);
                Button(root,"Earlier participation: "+PriorParticipation,new Vector2(0,20),new Vector2(740,52),()=>{PriorParticipation=PriorParticipation=="not_reported"?"yes":PriorParticipation=="yes"?"no":"not_reported";Render();});
                Button(root,"Start new session",new Vector2(0,-55),new Vector2(740,56),StartStudy);
                if(!string.IsNullOrEmpty(pendingRestore)||Data.Journal?.PendingCount>0)Button(root,"Restore saved session / retry",new Vector2(0,-130),new Vector2(740,56),RestoreStudy);
                return;
            }
            Button(root,"Sync / retry",new Vector2(-280,-485),new Vector2(250,40),RestoreStudy,20);
            Button(root,State.Value<string>("lifecycle")=="paused"?"Resume":"Pause",new Vector2(0,-485),new Vector2(250,40),PauseResume,20);
            if(State.Value<string>("lifecycle")=="ended")
            {Label(root,"Session ended\n"+State.Value<string>("end_reason")+"\n\nPreviously submitted results are retained.\nYou may now remove the headset.",Vector2.zero,new Vector2(800,350),30);return;}
            if(State.Value<string>("lifecycle")=="paused"){Label(root,"Paused\nYour saved answers are retained.",Vector2.zero,new Vector2(800,300),30);return;}
            if(reviewComment && Speech.CanSend)
            {
                Label(root,"Review your optional comment",new Vector2(0,270),new Vector2(810,60),28);
                var viewport=Rect("Transcript review",root,new Vector2(0,25),new Vector2(810,380));
                viewport.gameObject.AddComponent<Image>().color=paper;viewport.gameObject.AddComponent<RectMask2D>();
                var scroll=viewport.gameObject.AddComponent<ScrollRect>();scroll.horizontal=false;scroll.viewport=viewport;
                var text=Label(viewport,Speech.Transcript,Vector2.zero,new Vector2(780,380),23);text.alignment=TextAnchor.UpperLeft;
                var tr=text.rectTransform;tr.anchorMin=new Vector2(.5f,1);tr.anchorMax=new Vector2(.5f,1);tr.pivot=new Vector2(.5f,1);tr.anchoredPosition=Vector2.zero;tr.sizeDelta=new Vector2(780,Mathf.Max(380,text.preferredHeight+20));scroll.content=tr;
                Button(root,"Confirm this text",new Vector2(0,-245),new Vector2(790,55),()=>{reviewComment=false;Speech.Submit();Render();});
                Button(root,"Discard transcript",new Vector2(0,-305),new Vector2(790,45),()=>{reviewComment=false;Speech.Cancel();Render();});return;
            }
            if(showComment){RenderComment(root);return;}
            if(PreferenceScope!=null)
            {
                string scope=PreferenceScope;
                if(loadedPreferenceScope!=scope)
                {
                    loadedPreferenceScope=scope;preferred.Clear();preferenceKind="";preferenceComment="";
                    string saved=Data.Journal.RestoreLocal("preference:"+RunId+":"+scope);
                    if(saved!=null){var p=JObject.Parse(saved);preferenceKind=p.Value<string>("choice_kind");preferenceComment=p.Value<string>("comment");foreach(var c in (JArray)p["selected_conditions"])preferred.Add((string)c);}
                }
                Label(root,scope=="comparison_overall"?"Considering the four attributes, which approach would you prefer overall?":"For "+scope.Replace('_',' ')+" adjustments, which approach would you prefer?",new Vector2(0,230),new Vector2(800,140),27);
                for(int i=0;i<4;i++)
                {
                    string c="EANS"[i].ToString();
                    Button(root,(preferred.Contains(c)?"✓ ":"")+c,new Vector2(-300+i*200,110),new Vector2(175,55),()=>{if(preferenceKind!="selected")preferred.Clear();preferenceKind="selected";if(!preferred.Remove(c)&&preferred.Count<3)preferred.Add(c);ChoosePreference(preferenceKind,preferred.ToArray());});
                }
                string[] kinds={"no_clear_preference","none_acceptable","unable_to_compare"};string[] labels={"No clear preference","I would not want to use any of them","Unable to compare"};
                for(int i=0;i<3;i++){int j=i;Button(root,(preferenceKind==kinds[i]?"✓ ":"")+labels[i],new Vector2(0,35-i*60),new Vector2(790,48),()=>{ChoosePreference(kinds[j]);});}
                Notes(root,-165);
                var save=Button(root,"Save preference and continue",new Vector2(0,-290),new Vector2(790,52),SubmitPreference);save.interactable&=preferenceKind.Length>0&&(preferenceKind!="selected"||preferred.Count>0);
                return;
            }
            if(naturalModule==null && State["preferences"]?["comparison_overall"]!=null)
            {
                Label(root,"Attribute comparisons complete\n\nTake a break when needed. Next, you will use a tutor in one continuous conversation, with Selective only.",new Vector2(0,160),new Vector2(800,250),28);
                Button(root,"Start natural conversation",new Vector2(0,-90),new Vector2(760,60),StartNatural);return;
            }
            if(ShowingIntro)
            {
                string text;
                if(naturalModule!=null)text="Imagine you are getting to know a tutor that you would be comfortable continuing to use. Start a conversation about a topic or question of your choice. As you talk, explore how the tutor communicates and how it looks, and make any adjustments that suit you. You may change its speaking rate, voice, tone, level of detail, or appearance at any time. Keep talking and revise your choices whenever you wish. There is no single correct final setup.";
                else
                {
                    var card=tasks.modules.SelectMany(m=>m.tasks).FirstOrDefault(t=>t.task_code==currentTask?.Value<string>("task_code"));
                    text=(card?.title??"Task instructions")+"\n\n"+(card?.instructions??"")+"\n\n"+(card?.context_text??"")+"\n\nUse your own words. Speak to the tutor.";
                }
                Label(root,text,new Vector2(0,85),new Vector2(820,490),25);
                Button(root,"Begin / continue interaction",new Vector2(0,-240),new Vector2(790,60),ContinueInteraction);return;
            }
            if(!questionnaireOpen)
            {
                Label(root,naturalModule!=null?"Natural conversation · Selective\n\nAdjust the tutor's communication and appearance whenever you wish.\n\nFinish or cancel any pending clarification before opening the questionnaire.":"Compare the four results\n\nAnswer any clarification questions first. Results are shown together. You may continue adjusting and comparing before rating.",new Vector2(0,160),new Vector2(800,270),27);
                if(naturalModule==null)
                {
                    var card=tasks.modules.SelectMany(m=>m.tasks).First(t=>t.task_code==currentTask.Value<string>("task_code"));
                    if(card.materials!=null)for(int i=0;i<card.materials.Length && i<3;i++)
                    {int j=i;Button(root,"Play · "+card.materials[i].label,new Vector2(0,-30-i*55),new Vector2(790,48),()=>owner.Playback.ToggleMaterial(j));}
                }
                var rate=Button(root,naturalModule!=null?"Finish conversation · open questionnaire":"Open questionnaire",new Vector2(0,-240),new Vector2(790,60),CaptureEvaluation);
                rate.interactable&=naturalModule!=null?single&&single.Connected&&!single.Busy&&!single.HasQuestion&&!single.HasQueuedAnswer:comparison.Connected&&!comparison.Busy&&comparison.State.results_visible&&TutorComparisonClient.Conditions.All(c=>new[]{"ready","stopped"}.Contains(comparison.State.branches.Get(c).status));
                return;
            }
            if(naturalModule==null)
                for(int i=0;i<4;i++){string c="EANS"[i].ToString();ChoiceButton(root,ApproachName(c),new Vector2(-315+i*210,435),new Vector2(196,42),()=>SelectApproach(c),selected==c,22);}
            var q=CurrentQuestionnaire;if(q==null){Label(root,"Synchronize to recover this questionnaire.",Vector2.zero,new Vector2(800,200),28);return;}
            Draft();
            if(naturalModule==null){RenderAttribute(root,q);return;}
            var items=((JArray)catalog["items"]).OfType<JObject>().Where(i=>naturalModule!=null?!i.Value<string>("id").StartsWith("A"):i.Value<string>("id").StartsWith("A")).ToArray();
            int index=Array.FindIndex(items,i=>i.Value<string>("id")==currentItem);if(index<0){index=0;currentItem=items[0].Value<string>("id");}
            var item=items[index];string scale=item.Value<string>("scale");
            Label(root,(naturalModule==null?"Current approach · "+selected:"Natural conversation only")+" · "+(index+1)+" / "+items.Length,new Vector2(0,245),new Vector2(810,48),22);
            string context=currentItem.StartsWith("S")||currentItem.StartsWith("U")?"System means the VR tutor used in the natural conversation.\n":"";
            Label(root,context+item.Value<string>("text")+(item["help"]!=null?"\n"+item.Value<string>("help"):""),new Vector2(0,145),new Vector2(820,145),26);
            var answer=localAnswers[currentItem];
            if(scale=="category")
            {
                string[] values={"fully_met","partly_met","not_met","unable_to_judge"};string[] labels={"Fully met","Partly met","Not met","Unable to judge"};
                if(currentItem=="N0")labels=new[]{"Fully","Partly","Not at all","Unable to judge"};
                for(int i=0;i<4;i++){int j=i;Button(root,(answer?.Value<string>("value")==values[i]||answer?.Value<string>("status")==values[i]?"✓ ":"")+labels[i],new Vector2(-300+i*200,30),new Vector2(185,58),()=>Choose(currentItem,j==3?"unable_to_judge":"answered",j==3?JValue.CreateNull():new JValue(values[j])));}
            }
            else
            {
                int count=scale=="agreement5"?5:7;
                string left=scale=="ease7"?"Very difficult":scale=="demand7"?"Very low":scale=="bipolar7"?item.Value<string>("left"):"Strongly disagree";
                string right=scale=="ease7"?"Very easy":scale=="demand7"?"Very high":scale=="bipolar7"?item.Value<string>("right"):"Strongly agree";
                Label(root,left+"                         "+right,new Vector2(0,60),new Vector2(800,55),22);
                for(int i=1;i<=count;i++){int value=i;Button(root,(answer?.Value<string>("status")=="answered" && answer.Value<int?>("value")==i?"● ":"")+i,new Vector2(-330+(i-1)*660f/(count-1),0),new Vector2(90,52),()=>Choose(currentItem,"answered",new JValue(value)));}
                string special=item.Value<string>("special");
                Button(root,(answer?.Value<string>("status")==special?"✓ ":"")+(special=="skipped"?"Skip this item":"Unable to judge"),new Vector2(0,-65),new Vector2(740,43),()=>Choose(currentItem,special,JValue.CreateNull()));
                if(currentItem=="N5")Button(root,"No clarification questions occurred",new Vector2(0,-112),new Vector2(740,43),()=>Choose(currentItem,"not_applicable",JValue.CreateNull(),"no_clarification_questions"));
            }
            Button(root,"Previous item",new Vector2(-220,-175),new Vector2(350,44),()=>{currentItem=items[Math.Max(0,index-1)].Value<string>("id");Render();});
            Button(root,"Next item",new Vector2(220,-175),new Vector2(350,44),()=>{currentItem=items[Math.Min(items.Length-1,index+1)].Value<string>("id");Render();});
            Notes(root,-230);
            Button(root,"Save this evaluation",new Vector2(-215,-305),new Vector2(390,48),SaveQuestionnaire).interactable&=AnsweredAll(q);
            Button(root,naturalModule!=null?"Submit and finish":"Submit ratings · next task",new Vector2(215,-305),new Vector2(390,48),SubmitAndNext).interactable&=ReadyToSubmit;
        }
        void RenderAttribute(RectTransform root,JObject q)
        {
            if(showReasons)
            {
                Label(root,"Optional reasons · "+selected,new Vector2(0,245),new Vector2(800,55),26);
                string[] codes={"target_mismatch","unwanted_change","not_maintained","hard_to_verify","interaction_problem","other"};
                string[] names={"The requested change did not meet the requirements.","Something that should have stayed unchanged was changed.","The change was not maintained during later interaction.","I could not tell whether the change met the requirements.","A speech, playback, or interaction problem affected my judgement.","Another reason."};
                for(int i=0;i<codes.Length;i++)
                {
                    string code=codes[i];bool later=comparison.Connected && comparison.Branch.result?.state?.conversation?.Length>comparison.FirstConversationCount(selected);
                    if(code=="not_maintained"&&!later)continue;
                    var b=Button(root,(((JArray)localExtras["reasons"]).Any(v=>(string)v==code)?"✓ ":"")+names[i],new Vector2(0,170-i*60),new Vector2(820,50),()=>
                    {var a=(JArray)localExtras["reasons"];var found=a.FirstOrDefault(v=>(string)v==code);if(found==null)a.Add(code);else found.Remove();PersistDraft();Render();});b.GetComponentInChildren<Text>().fontSize=20;
                }
                Button(root,"Back to five questions",new Vector2(0,-220),new Vector2(790,52),()=>{showReasons=false;Render();});return;
            }
            var items=((JArray)catalog["items"]).OfType<JObject>().Where(i=>i.Value<string>("id").StartsWith("A")).ToArray();
            for(int row=0;row<items.Length;row++)
            {
                var item=items[row];string id=item.Value<string>("id");float y=361-row*136;
                var question=Label(root,(row+1)+". "+item.Value<string>("text"),new Vector2(0,y),new Vector2(840,62),26);
                question.alignment=TextAnchor.MiddleLeft;
                var answer=localAnswers[id];
                if(row==0)
                {
                    string[] codes={"fully_met","partly_met","not_met","unable_to_judge"};string[] names={"Fully met","Partly met","Not met","Cannot judge"};
                    for(int i=0;i<4;i++)
                    {
                        int j=i;bool chosen=answer.Value<string>("value")==codes[i]||answer.Value<string>("status")==codes[i];
                        ChoiceButton(root,names[i],new Vector2(-315+i*210,y-58),new Vector2(196,46),()=>Choose(id,j==3?"unable_to_judge":"answered",j==3?JValue.CreateNull():new JValue(codes[j])),chosen,23);
                    }
                    Label(root,item.Value<string>("help"),new Vector2(0,y-94),new Vector2(840,24),17);
                }
                else
                {
                    for(int i=1;i<=7;i++)
                    {
                        int value=i;bool chosen=answer.Value<string>("status")=="answered"&&answer.Value<int?>("value")==i;
                        ChoiceButton(root,i.ToString(),new Vector2(-383+(i-1)*90,y-58),new Vector2(74,46),()=>Choose(id,"answered",new JValue(value)),chosen,28);
                    }
                    ChoiceButton(root,"Cannot judge",new Vector2(318,y-58),new Vector2(204,46),()=>Choose(id,"unable_to_judge",JValue.CreateNull()),answer.Value<string>("status")=="unable_to_judge",23);
                    Label(root,row==1?"1 = Very difficult     ·     7 = Very easy":"1 = Strongly disagree     ·     7 = Strongly agree",new Vector2(-105,y-94),new Vector2(630,24),19);
                }
            }
            var reasons=Button(root,"Explain unmet goals",new Vector2(-285,-322),new Vector2(270,40),()=>{showReasons=true;Render();},21);
            reasons.interactable&=localAnswers["A0"].Value<string>("status")!="unanswered" && localAnswers["A0"].Value<string>("value")!="fully_met";
            Button(root,"Re-evaluate latest results",new Vector2(0,-322),new Vector2(270,40),CaptureEvaluation,21);
            Button(root,"Add spoken comment",new Vector2(285,-322),new Vector2(270,40),()=>{showComment=true;Render();},21);
            Button(root,"Save this evaluation",new Vector2(-215,-382),new Vector2(410,48),SaveQuestionnaire,24).interactable&=AnsweredAll(q);
            Button(root,"Submit all & next task",new Vector2(215,-382),new Vector2(410,48),SubmitAndNext,24).interactable&=ReadyToSubmit;
        }
        static string ApproachName(string c)
        {return c=="E"?"Always act":c=="A"?"Always ask":c=="N"?"Native":"Selective";}
        string IdleStatus()
        {
            var q=CurrentQuestionnaire;
            if(q!=null && localAnswers!=null)
            {
                bool saved=q.Value<int>("feedback_revision")>0 && JToken.DeepEquals(localAnswers,q["answers"]) && JToken.DeepEquals(localExtras,q["extras"]);
                if(saved)return naturalModule==null?"Saved for "+ApproachName(selected)+" · finish all four evaluations to continue.":"Evaluation saved · submit when ready.";
                return "Answers kept locally · use Save this evaluation to save to the study record.";
            }
            return "Changes are saved before continuing.";
        }
        void RenderComment(RectTransform root)
        {
            Label(root,"Optional spoken comment",new Vector2(0,345),new Vector2(840,55),32);
            Label(root,"Explain your rating or describe a problem. Record your comment, review the transcript, then confirm the text.",new Vector2(0,255),new Vector2(800,100),27);
            string confirmed=PreferenceScope!=null?preferenceComment:localExtras?.Value<string>("comment");
            var viewport=Rect("Saved comment",root,new Vector2(0,45),new Vector2(800,240));
            viewport.gameObject.AddComponent<RectMask2D>();
            var scroll=viewport.gameObject.AddComponent<ScrollRect>();scroll.horizontal=false;scroll.viewport=viewport;
            var text=Label(viewport,string.IsNullOrEmpty(confirmed)?"No comment confirmed yet.":"Confirmed comment:\n"+confirmed,Vector2.zero,new Vector2(780,240),26);text.alignment=TextAnchor.UpperLeft;
            var tr=text.rectTransform;tr.anchorMin=tr.anchorMax=new Vector2(.5f,1);tr.pivot=new Vector2(.5f,1);tr.anchoredPosition=Vector2.zero;tr.sizeDelta=new Vector2(780,Mathf.Max(240,text.preferredHeight+20));scroll.content=tr;
            Notes(root,-160);
            Button(root,"Back to questionnaire",new Vector2(0,-300),new Vector2(600,52),()=>{if(Speech.Recording||Speech.Working)Speech.Cancel();showComment=false;Render();},24);
        }
        void Notes(RectTransform root,float y)
        {
            Button(root,Speech.Recording?"Stop recording":"Optional spoken comment",new Vector2(-160,y),new Vector2(440,42),()=>Speech.PressRecord());
            Button(root,"Review transcript",new Vector2(250,y),new Vector2(270,42),()=>{reviewComment=true;Render();}).interactable&=Speech.CanSend;
            Label(root,string.IsNullOrEmpty(Speech.Transcript)?Speech.Status:"Transcript ready · review before confirming.",new Vector2(0,y-36),new Vector2(810,24),16);
        }
        RectTransform Rect(string name,Transform parent,Vector2 pos,Vector2 size)
        {var go=new GameObject(name,typeof(RectTransform));var r=(RectTransform)go.transform;r.SetParent(parent,false);r.sizeDelta=size;r.anchoredPosition=pos;return r;}
        Text Label(Transform parent,string text,Vector2 pos,Vector2 size,int fontSize)
        {var r=Rect("Label",parent,pos,size);var t=r.gameObject.AddComponent<Text>();t.text=text;t.font=font;t.fontSize=fontSize;t.color=ink;t.alignment=TextAnchor.MiddleCenter;t.raycastTarget=false;t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Truncate;return t;}
        Button Button(Transform parent,string label,Vector2 pos,Vector2 size,Action action,int fontSize=22)
        {
            var r=Rect(label,parent,pos,size);r.gameObject.AddComponent<Image>().color=new Color(.83f,.86f,.81f,1);
            var b=r.gameObject.AddComponent<Button>();b.navigation=new Navigation{mode=Navigation.Mode.None};b.interactable=!Running&&!Data.StorageFault;b.onClick.AddListener(()=>action());
            var text=Label(r,label,Vector2.zero,new Vector2(size.x-12,size.y-4),fontSize);
            text.horizontalOverflow=HorizontalWrapMode.Overflow;
            return b;
        }
        Button ChoiceButton(Transform parent,string label,Vector2 pos,Vector2 size,Action action,bool chosen,int fontSize)
        {
            var b=Button(parent,label,pos,size,action,fontSize);
            if(chosen){b.GetComponent<Image>().color=accent;var text=b.GetComponentInChildren<Text>();text.color=Color.white;text.fontStyle=FontStyle.Bold;}
            return b;
        }
    }
}
