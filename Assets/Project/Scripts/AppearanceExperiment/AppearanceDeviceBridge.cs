using System;
using System.IO;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using IAI.Interaction;

namespace IAI.Appearance
{
    [Serializable] public sealed class DeviceCommand
    {
        public string id, study_session_id, action, value, text;
    }
    [Serializable] public sealed class DeviceStatus
    {
        public string schema_version="appearance-device-status-v1", study_session_id, participant_id, phase, condition;
        public string session_id, task_id, decision, message, build_sha256, command_id, command_error, capability_profile;
        public bool initialized, busy, validating, finished, awaiting_block, study_complete, faulted, command_accepted, can_edit, can_finish;
        public int trial, block, within_block;
        public AppearanceState observed;
        public Question question;
        public string query;
        public string[] captures;
        public float realtime;
    }

    // Researcher metadata stays in local storage. The panel never renders this object.
    public sealed class AppearanceDeviceBridge : MonoBehaviour
    {
        public AppearanceExperimentClient client;
        string root, lastId="", commandError="";
        bool accepted;
        bool journalReady=true;
        readonly HashSet<string> processed=new HashSet<string>();
        float nextPoll;

        void Awake()
        {
            root=Application.persistentDataPath;Directory.CreateDirectory(root);
            string receipt=Path.Combine(root,"appearance-command-result.json");
            try {if(File.Exists(receipt))lastId=JsonUtility.FromJson<DeviceStatus>(File.ReadAllText(receipt)).command_id??"";}
            catch(Exception){lastId="";}
            try
            {
                string journal=Path.Combine(root,"appearance-command-ids.log");
                if(File.Exists(journal))foreach(string id in File.ReadAllLines(journal))
                {
                    if(!Guid.TryParseExact(id,"N",out _))throw new IOException("Incomplete command journal.");
                    processed.Add(id);
                }
            }
            catch(Exception){journalReady=false;commandError="Command journal is unreadable; no commands will run.";}
        }
        void Update()
        {
            if(Time.unscaledTime<nextPoll||!client)return;
            nextPoll=Time.unscaledTime+.25f;
            try
            {
                if(client.Initialized&&journalReady)ReadCommand();
                AtomicWrite("appearance-status.json",JsonUtility.ToJson(Snapshot(),true));
            }
            catch(IOException){Debug.LogWarning("APPEARANCE_BRIDGE storage unavailable.");}
            catch(UnauthorizedAccessException){Debug.LogWarning("APPEARANCE_BRIDGE storage permission denied.");}
        }

        void ReadCommand()
        {
            string path=Path.Combine(root,"appearance-command.json");
            if(!File.Exists(path))return;
            DeviceCommand c;
            try{c=JsonUtility.FromJson<DeviceCommand>(File.ReadAllText(path));}
            catch(ArgumentException){return;}
            if(c==null||!Guid.TryParseExact(c.id,"N",out _)||c.id==lastId)return;
            if(processed.Contains(c.id))
            {
                lastId=c.id;accepted=false;commandError="Command ID was already processed; replay rejected.";
                AtomicWrite("appearance-command-result.json",JsonUtility.ToJson(Snapshot(),true));return;
            }
            // Record before dispatch. A crash can leave an unknown outcome, never a repeated mutation.
            using(var stream=new FileStream(Path.Combine(root,"appearance-command-ids.log"),FileMode.Append,FileAccess.Write,FileShare.Read))
            {
                byte[] line=Encoding.UTF8.GetBytes(c.id+"\n");stream.Write(line,0,line.Length);stream.Flush(true);
            }
            processed.Add(c.id);
            lastId=c.id;accepted=false;commandError="";
            if(c.study_session_id!=client.StudySessionId)commandError="Session mismatch; stale command rejected.";
            else if(c.action=="next")accepted=client.RequestNext();
            else if(c.action=="resume")accepted=client.RequestResume();
            else if(client.phase!="debug")commandError="Scripted participant actions are available only in debug.";
            else
            {
                switch(c.action)
                {
                    case "submit":accepted=client.RequestSubmit(string.IsNullOrEmpty(c.text)?null:c.text);break;
                    case "answer":accepted=client.RequestAnswer(c.value,c.text??"");break;
                    case "undo":accepted=client.RequestUndo(c.value);break;
                    case "finish":accepted=client.RequestFinish();break;
                    case "sit":var seat=FindObjectOfType<ConversationSeat>();accepted=seat&&seat.TrySit();break;
                    default:commandError="Unknown command.";break;
                }
            }
            if(!accepted&&string.IsNullOrEmpty(commandError))commandError="Action unavailable in the current interaction state.";
            // Persist the ID before the next poll; replaying a delivered command never repeats it.
            AtomicWrite("appearance-command-result.json",JsonUtility.ToJson(Snapshot(),true));
            Debug.Log("APPEARANCE_COMMAND action="+c.action+" accepted="+accepted);
        }

        DeviceStatus Snapshot()
        {
            var row=client.CurrentTrial;
            var avatar=client.avatar;
            return new DeviceStatus
            {
                study_session_id=client.StudySessionId,participant_id=client.participant,phase=client.phase,condition=client.condition,
                session_id=client.view.session_id,task_id=client.CurrentTask,decision=client.view.decision,message=client.Status,
                capability_profile=client.capabilityProfile,
                build_sha256=client.ObservedBuild,command_id=lastId,command_error=commandError,command_accepted=accepted,
                initialized=client.Initialized,busy=client.Busy,validating=client.Validating,finished=client.IsFinished,
                awaiting_block=client.WaitingForBlock,study_complete=client.StudyComplete,faulted=client.Faulted,
                can_edit=client.CanEditQuery,can_finish=client.CanFinish,trial=client.TrialNumber,block=row?.block??0,within_block=row?.withinBlock??0,
                observed=client.Initialized&&avatar?client.Observed():null,
                question=client.IsQuestion?client.view.question:null,query=client.query,captures=client.EvidencePaths,realtime=Time.realtimeSinceStartup
            };
        }
        void AtomicWrite(string name,string json)
        {
            string path=Path.Combine(root,name),temp=path+".tmp";
            File.WriteAllText(temp,json);
            if(File.Exists(path))File.Delete(path);
            File.Move(temp,path);
        }
    }
}
