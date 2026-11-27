using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using IAI.Tutor;

public static class TutorStudyFlowSetup
{
    [MenuItem("AIAA4435/Tutor/Study/Enable New Study Flow")]
    public static void Enable()
    {
        if(EditorApplication.isPlayingOrWillChangePlaymode)throw new InvalidOperationException("Stop Play mode before changing study scenes.");
        foreach(string path in new[]{TutorComparisonSetup.DesktopScene,TutorComparisonSetup.VRScene})
        {
            var scene=EditorSceneManager.OpenScene(path);
            var panel=UnityEngine.Object.FindObjectOfType<TutorPanel>();
            if(!panel || !panel.comparison)throw new InvalidOperationException("Comparison panel missing.");
            panel.durableStudy=true;panel.comparison.connectOnStart=false;
            EditorSceneManager.MarkSceneDirty(scene);EditorSceneManager.SaveScene(scene);
        }
        Debug.Log("STUDY_FLOW_SCENES_ENABLED");
    }
    public static void RunChecks()
    {
        SessionState.SetBool("IAI_STUDY_FLOW_CHECK",true);
        EditorSceneManager.OpenScene(TutorComparisonSetup.DesktopScene);
        // Headless checks have no emulated input devices. The simulator creates its
        // UI during Start, so disable its source too instead of only existing UI.
        foreach(var behaviour in UnityEngine.Object.FindObjectsOfType<MonoBehaviour>(true))
            if(behaviour.GetType().Name=="XRDeviceSimulatorUI" || behaviour.GetType().Name=="XRDeviceSimulator")behaviour.gameObject.SetActive(false);
        EditorApplication.isPlaying=true;
    }
    // Explicit fixture entry points only. Scene changes are not saved.
    public static void RunControlsChecks(){RunInteractionChecks("controls");}
    public static void RunAudioChecks(){RunInteractionChecks("audio");}
    static void RunInteractionChecks(string kind)
    {
        SessionState.SetString("IAI_INTERACTION_CHECK",kind);
        SessionState.SetFloat("IAI_INTERACTION_CHECK_START",(float)EditorApplication.timeSinceStartup);
        EditorSceneManager.OpenScene(TutorComparisonSetup.FreeDesktopScene);
        var panel=UnityEngine.Object.FindObjectOfType<TutorPanel>();panel.seat=null;
        foreach(var behaviour in UnityEngine.Object.FindObjectsOfType<MonoBehaviour>(true))
            if(behaviour.GetType().Name=="XRDeviceSimulatorUI" || behaviour.GetType().Name=="XRDeviceSimulator")behaviour.gameObject.SetActive(false);
        EditorApplication.isPlaying=true;
    }
    [InitializeOnLoadMethod]
    static void Install(){EditorApplication.update-=Tick;EditorApplication.update+=Tick;}
    static void Tick()
    {
        string interaction=SessionState.GetString("IAI_INTERACTION_CHECK","");
        if(interaction.Length>0)
        {
            if(!EditorApplication.isPlaying || EditorApplication.isCompiling)return;
            var interactionPanel=UnityEngine.Object.FindObjectOfType<TutorPanel>();if(!interactionPanel || !interactionPanel.comparison)return;
            var target=interactionPanel.comparison.gameObject;
            string result;
            if(interaction=="controls")
            {
                var check=target.GetComponent<TutorControlsChecks>();
                if(!check){target.AddComponent<TutorControlsChecks>();return;}
                result=check.Result;
            }
            else
            {
                var check=target.GetComponent<TutorAudioChecks>();
                if(!check){target.AddComponent<TutorAudioChecks>();return;}
                result=check.Result;
            }
            if(result=="Running" && EditorApplication.timeSinceStartup-SessionState.GetFloat("IAI_INTERACTION_CHECK_START",0)<180)return;
            bool passed=result.StartsWith("PASS:");SessionState.EraseString("IAI_INTERACTION_CHECK");
            string folder=System.Environment.GetEnvironmentVariable("IAI_STUDY_CHECK_OUT");
            File.WriteAllText(Path.Combine(folder,"unity-"+interaction+".json"),new Newtonsoft.Json.Linq.JObject{["passed"]=passed,["result"]=result,["provider_calls"]=0,["microphone_used"]=false,["headset_tested"]=false}.ToString());
            EditorApplication.Exit(passed?0:1);return;
        }
        if(!SessionState.GetBool("IAI_STUDY_FLOW_CHECK",false)||!EditorApplication.isPlaying||EditorApplication.isCompiling)return;
        var panel=UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if(!panel||!panel.StudyFlow)return;
        SessionState.SetBool("IAI_STUDY_FLOW_CHECK",false);
        if(!string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("IAI_STUDY_RECOVERY_PHASE")))panel.gameObject.AddComponent<TutorStudyRecoveryChecks>();
        else panel.gameObject.AddComponent<TutorStudyFlowChecks>();
    }
}
