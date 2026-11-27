using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEngine;

namespace IAI.Tutor
{
    [Serializable] public class TutorTaskCard
    {
        public string task_code, display_code, scenario, title, instructions, context_text, keep_unchanged, request_example;
        public TutorStudyMaterial[] materials;
        public string DisplayCode => string.IsNullOrEmpty(display_code) ? task_code : display_code;
        public string ParticipantInstructions => "Task goal\n" + instructions + "\n\nKeep unchanged\n" +
            (string.IsNullOrWhiteSpace(keep_unchanged) ? "All settings other than the requested change." : keep_unchanged) +
            "\n\nRequest example\n" + (string.IsNullOrWhiteSpace(request_example) ? "Use your own words to ask the tutor for the requested change." : request_example);
    }
    [Serializable] public class TutorStudyMaterial { public string label, text; public TutorSettings settings; }
    [Serializable] public class TutorTaskModule
    { public string direction, title; public TutorTaskCard[] tasks; }
    [Serializable] public class TutorTaskManifest
    {
        public string version, purpose, materials_version;
        [NonSerialized] public string catalog_sha256;
        public TutorTaskModule[] modules;
        public static TutorTaskManifest Parse(string json)
        {
            var value = JsonUtility.FromJson<TutorTaskManifest>(json);
            var directions = new[] { "speech_rate", "reply_length", "tone", "voice" };
            bool studyVersion = value != null && value.purpose == "study_preview" &&
                (value.version == "task-navigation-v2" && value.materials_version == "attribute-materials-v1" ||
                 value.version == "task-navigation-v3" && value.materials_version == "attribute-materials-v2" ||
                 value.version == "task-navigation-v4" && value.materials_version == "attribute-materials-v3");
            if (value == null || !(value.version == "task-navigation-v1" && value.purpose == "practice" || studyVersion) || value.modules == null || value.modules.Length == 0 || value.modules.Length > 4)
                throw new ArgumentException("Use a versioned practice task manifest.");
            var codes = new HashSet<string>(); var used = new HashSet<string>();
            foreach (var module in value.modules)
            {
                if (module == null || !directions.Contains(module.direction) || !used.Add(module.direction) || !Text(module.title, 80) || module.tasks == null || module.tasks.Length == 0 || module.tasks.Length > 32)
                    throw new ArgumentException("Each direction needs a unique module and task list.");
                foreach (var task in module.tasks)
                    if (task == null || task.task_code == null || !Regex.IsMatch(task.task_code, @"\A[A-Za-z0-9_-]{1,64}\z") || !codes.Add(task.task_code) ||
                        !new[] { "C1", "C2", "C3", "C4" }.Contains(task.scenario) || !Text(task.title, 100) || !Text(task.instructions, 1500))
                        throw new ArgumentException("Task codes must be unique; each task needs a title, scenario and instructions.");
                if (value.version == "task-navigation-v4")
                    foreach (var scenario in new[] { "C1", "C2", "C3", "C4" })
                    {
                        var pair = module.tasks.Where(t => t.scenario == scenario).ToArray();
                        for (int i = 0; i < pair.Length; i++)
                            if (!Text(pair[i].display_code, 64) || !pair[i].display_code.EndsWith("-" + (i + 1)) ||
                                !Text(pair[i].keep_unchanged, 1500) || !Text(pair[i].request_example, 1500))
                                throw new ArgumentException("Current task cards need consecutive display numbers and all three instruction sections.");
                    }
            }
            if (value.purpose == "study_preview")
            {
                if (value.modules.Length != 4 || value.modules.Any(m => m.tasks.Length != 8 || new[] { "C1", "C2", "C3", "C4" }.Any(c => m.tasks.Count(t => t.scenario == c) != 2)))
                    throw new ArgumentException("Study preview needs 32 tasks: two per scenario.");
                using (var sha = SHA256.Create()) value.catalog_sha256 = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(json))).Replace("-", "").ToLowerInvariant();
            }
            return value;
        }
        static bool Text(string value, int limit) => !string.IsNullOrWhiteSpace(value) && value.Length <= limit;
    }

    // Strict transport DTO: private participant instructions never enter requests.
    [Serializable] public class TutorTaskStart { public string task_code, domain, scenario; }

    [Serializable] public class TutorSequenceTask { public string task_code, scenario; }
    [Serializable] public class TutorSequenceModule { public string domain; public TutorSequenceTask[] tasks; }
    [Serializable] public class TutorSequencePlan
    { public string version = "attribute-sequence-v1", purpose = "practice"; public TutorSequenceModule[] modules; }

    [Serializable] public class TutorStudySequencePlan : TutorSequencePlan { public string materials_version, catalog_sha256; }

    public sealed class TutorTaskNavigation
    {
        readonly TutorComparisonClient client;
        readonly TutorTaskManifest manifest;
        int moduleIndex, taskIndex;
        string taskId = "", seriesId = "";
        bool moving, advanceIssued, details, acrossModule;
        public bool Active { get; private set; }
        public string Error { get; private set; } = "";
        public TutorTaskNavigation(TutorComparisonClient client, string json)
        {
            this.client = client;
            try { manifest = TutorTaskManifest.Parse(json); }
            catch (Exception) { Error = "Task instructions are unavailable. Please ask the researcher."; }
        }
        public bool StudyPreview => manifest?.purpose == "study_preview";
        public TutorTaskModule Module => manifest?.modules[moduleIndex];
        public TutorTaskCard Task => Module?.tasks[taskIndex];
        public bool HasNextInModule => manifest != null && taskIndex + 1 < Module.tasks.Length;
        public bool HasNextModule => manifest != null && moduleIndex + 1 < manifest.modules.Length;
        public bool AtPreferenceBoundary => Active && client.Connected && client.State.lifecycle == "submitted" && !HasNextInModule;
        public bool AwaitingPreference => AtPreferenceBoundary && !string.IsNullOrEmpty(client.State.sequence?.preference_scope);
        public bool ComparisonComplete => AtPreferenceBoundary && client.State.sequence?.comparison_complete == true;
        public bool CanContinueModule => AtPreferenceBoundary && HasNextModule && !moving && !client.Busy && !client.UnknownOutcome && client.State.sequence?.attribute_saved == true && !client.State.sequence.preference_paused && !client.State.sequence.preference_exited;
        public string NextModuleTitle => HasNextModule ? manifest.modules[moduleIndex + 1].title : "";
        int SequenceIndex => manifest.modules.Take(moduleIndex).Sum(m => m.tasks.Length) + taskIndex + 1;
        public bool ShowCard => Error.Length > 0 || !client.Connected || Active && (details || AtPreferenceBoundary);
        public bool CanBegin => manifest != null && Error.Length == 0 && !client.Busy && !client.UnknownOutcome &&
            (!client.Connected && !client.CanRetry || Active && details && client.Open && !client.Paused);
        public bool CanNext => Active && !ShowCard && !moving && !client.Busy && !client.UnknownOutcome && !client.Paused &&
            (client.State.can_submit || client.State.lifecycle == "submitted" && HasNextInModule);
        public string Progress => manifest == null ? "Task sequence unavailable" :
            $"{(StudyPreview ? "Study preview" : "Practice")} · {Module.title} · Task {taskIndex + 1}/{Module.tasks.Length}";
        public string Title => AtPreferenceBoundary ? "Task comparisons complete" : Task?.DisplayCode ?? "Task instructions";
        public string Instructions => Error.Length > 0 ? Error : AtPreferenceBoundary
            ? "Complete the strategy preference on this panel before continuing."
            : Task?.ParticipantInstructions ?? "";
        public string Guidance => Error.Length > 0 ? Error : !Active ? (StudyPreview ? "32-task study preview · Not participant collection." : "Practice sequence · Not formal study data.")
            : ComparisonComplete ? "Comparison feedback complete. The natural conversation module comes next."
            : AtPreferenceBoundary ? "Complete the preference feedback before continuing."
            : moving ? "Saving feedback and opening the next task..."
            : client.State?.lifecycle == "aborted" ? "Task ended without submission. Please ask the researcher."
            : client.State?.can_submit == true ? "Feedback is complete. You can continue."
            : client.State?.results_visible == true ? "Complete feedback for all four current results before continuing." : "";

        public static TutorTaskStart PublicTask(TutorTaskModule module, TutorTaskCard task) =>
            new TutorTaskStart { task_code = task.task_code, domain = module.direction, scenario = task.scenario };

        public void Begin()
        {
            if (!CanBegin) return;
            if (client.Connected) { details = false; return; }
            Active = true; details = false;
            client.ConnectTask(PublicTask(Module, Task), PublicSequence(manifest));
        }
        public static TutorSequencePlan PublicSequence(TutorTaskManifest value)
        {
            TutorSequencePlan plan = value.purpose == "study_preview" ? new TutorStudySequencePlan { version = "attribute-sequence-v2", purpose = "study_preview", materials_version = value.materials_version, catalog_sha256 = value.catalog_sha256 } : new TutorSequencePlan();
            plan.modules = value.modules.Select(m => new TutorSequenceModule { domain = m.direction, tasks = m.tasks.Select(t => new TutorSequenceTask { task_code = t.task_code, scenario = t.scenario }).ToArray() }).ToArray();
            return plan;
        }
        public void ContinueModule()
        {
            if (!CanContinueModule) return;
            moving = true; acrossModule = true; advanceIssued = false;
        }
        public void ShowDetails() { if (Active && client.Connected && !client.Paused) details = true; }
        public void Next()
        {
            if (!CanNext) return;
            moving = true;
            if (client.State.lifecycle != "submitted") client.SubmitTask();
        }
        public void Update()
        {
            if (!Active || !client.Connected || Error.Length > 0) return;
            var state = client.State;
            if (taskId.Length == 0)
            {
                if (!Matches(state, Task) || state.sequence_index != 1) { Mismatch(); return; }
                taskId = state.task_id; seriesId = state.series_id;
            }
            else if (state.task_id != taskId)
            {
                int nextModule = acrossModule ? moduleIndex + 1 : moduleIndex;
                int nextTask = acrossModule ? 0 : taskIndex + 1;
                if (!moving || (acrossModule ? !HasNextModule : !HasNextInModule) || state.previous_task_id != taskId || state.series_id != seriesId ||
                    state.sequence_index != SequenceIndex + 1 || !Matches(state, manifest.modules[nextModule], manifest.modules[nextModule].tasks[nextTask])) { Mismatch(); return; }
                moduleIndex = nextModule; taskIndex = nextTask; taskId = state.task_id; moving = advanceIssued = acrossModule = false; details = true;
            }
            else if (!Matches(state, Task) || state.series_id != seriesId) { Mismatch(); return; }
            if (!moving || client.Busy || client.UnknownOutcome || client.CanRetry) return;
            if (state.lifecycle == "submitted")
            {
                if (!HasNextInModule && !acrossModule) { moving = false; details = true; return; }
                if (!advanceIssued)
                {
                    advanceIssued = true;
                    var next = acrossModule ? manifest.modules[moduleIndex + 1] : Module;
                    client.AdvanceToTask(JsonUtility.ToJson(PublicTask(next, next.tasks[acrossModule ? 0 : taskIndex + 1])));
                }
                else { moving = advanceIssued = acrossModule = false; } // Known rejection; a new explicit Next can retry.
            }
            else if (state.lifecycle != "submitted") moving = advanceIssued = acrossModule = false;
        }
        bool Matches(ComparisonView state, TutorTaskCard task) => Matches(state, Module, task);
        bool Matches(ComparisonView state, TutorTaskModule module, TutorTaskCard task) => state.task_code == task.task_code && state.domain == module.direction && state.scenario == task.scenario;
        void Mismatch() { Error = "The task sequence could not be verified. Please ask the researcher."; moving = false; }
    }
}
