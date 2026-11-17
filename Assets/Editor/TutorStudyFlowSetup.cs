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
        foreach(var behaviour in UnityEngine.Object.FindObjectsOfType<MonoBehaviour>())
            if(behaviour.GetType().Name=="XRDeviceSimulatorUI")behaviour.gameObject.SetActive(false);
        EditorApplication.isPlaying=true;
    }
    [InitializeOnLoadMethod]
    static void Install(){EditorApplication.update-=Tick;EditorApplication.update+=Tick;}
    static void Tick()
    {
        if(!SessionState.GetBool("IAI_STUDY_FLOW_CHECK",false)||!EditorApplication.isPlaying||EditorApplication.isCompiling)return;
        var panel=UnityEngine.Object.FindObjectOfType<TutorPanel>();
        if(!panel||!panel.StudyFlow)return;
        SessionState.SetBool("IAI_STUDY_FLOW_CHECK",false);
        if(!string.IsNullOrEmpty(System.Environment.GetEnvironmentVariable("IAI_STUDY_RECOVERY_PHASE")))panel.gameObject.AddComponent<TutorStudyRecoveryChecks>();
        else panel.gameObject.AddComponent<TutorStudyFlowChecks>();
    }
}
