using System;
using System.Text.RegularExpressions;

namespace IAI.Appearance
{
    // Researcher-only configuration. Never included in the model's public context.
    [Serializable]
    public sealed class AppearanceSessionConfig
    {
        public string schema_version, participant_id, phase, study_session_id;
        public string condition, task_id, backend_url, expected_build_sha256;
        public string capability_profile;
        public bool assigned;

        public void Validate()
        {
            if (schema_version != "appearance-session-v1") throw new ArgumentException("Invalid configuration schema.");
            if (!string.IsNullOrEmpty(capability_profile) && capability_profile != "study-v1" && capability_profile != "avatar-demo-v1")
                throw new ArgumentException("Unknown capability profile.");
            if (capability_profile == "avatar-demo-v1" && (phase != "debug" || assigned || !string.IsNullOrEmpty(task_id)))
                throw new ArgumentException("Avatar demo requires an unassigned debug session without a study task.");
            string pattern = phase == "debug" ? @"\A(DEBUG|ENGINEERING)[A-Z0-9_-]{0,36}\z" :
                phase == "pilot" ? @"\APILOT0[12]\z" : phase == "formal" ? @"\A(P00[1-9]|P01[0-9]|P020)\z" : null;
            if (pattern == null || !Regex.IsMatch(participant_id ?? "", pattern) ||
                !Regex.IsMatch(study_session_id ?? "", @"\A[A-Za-z0-9_-]{3,80}\z"))
                throw new ArgumentException("Participant, phase and study session do not agree.");
            if (phase == "formal")
            {
                if (!assigned || !string.IsNullOrEmpty(condition) || !string.IsNullOrEmpty(task_id))
                    throw new ArgumentException("Formal tasks and conditions must come exclusively from the frozen schedule.");
            }
            else if (assigned || (!string.IsNullOrEmpty(condition) && Array.IndexOf(new[]{"E","A","N","S"}, condition) < 0))
                throw new ArgumentException("Invalid practice/debug condition.");
            if (!string.IsNullOrEmpty(expected_build_sha256) && !Regex.IsMatch(expected_build_sha256, @"\A[a-f0-9]{64}\z"))
                throw new ArgumentException("Invalid build fingerprint.");
            if (!string.IsNullOrEmpty(backend_url) && (!Uri.TryCreate(backend_url, UriKind.Absolute, out var uri) ||
                (uri.Scheme != "http" && uri.Scheme != "https") || !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment)))
                throw new ArgumentException("Invalid backend URL.");
        }
    }
}
