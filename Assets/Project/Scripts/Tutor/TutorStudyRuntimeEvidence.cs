using System;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IAI.Tutor
{
    /// <summary>Submitted runtime text survives a lost connection/headset restart.</summary>
    public static class TutorStudyRuntimeEvidence
    {
        public static string Save(TutorStudyJournal journal,string runId,string route,string json)
        {
            if(journal==null || json==null)return null;
            var body=JObject.Parse(json);string id=body.Value<string>("request_id");
            if(string.IsNullOrEmpty(id))throw new InvalidOperationException("Managed runtime operations require an ID.");
            string[] parts=route.Trim('/').Split('/');
            string operation=parts.Length==6?parts[5]+":"+parts[4]:parts[3];
            var packet=new JObject{["study_run_id"]=runId,["runtime_id"]=parts[2],["operation"]=operation,["body"]=body};
            string scope="runtime:"+parts[2]+":"+id;
            var old=journal.RestoreLocal(scope);string value=packet.ToString(Formatting.None);
            if(old!=null && old!=value)throw new InvalidOperationException("Saved runtime request conflicts.");
            if(old==null)journal.SaveLocal(scope,value);
            return scope;
        }
        public static void Acknowledge(TutorStudyJournal journal,string scope,string response)
        {
            if(journal!=null && scope!=null)journal.SaveLocal("runtime-ack:"+scope.Substring(8),response);
        }
    }
}
