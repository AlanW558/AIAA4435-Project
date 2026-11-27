using System;

namespace IAI.Tutor
{
    // The panel only consumes the presentation projection, never private branches.
    public interface ITutorPanelClient
    {
        TutorView View { get; }
        bool Busy { get; }
        bool Connected { get; }
        bool UnknownOutcome { get; }
        bool HasQuestion { get; }
        bool HasQueuedAnswer { get; }
        bool CanEdit { get; }
        bool CanSubmit { get; }
        bool CanUndo { get; }
        bool CanRetry { get; }
        string Error { get; }
        string Activity { get; }
        event Action Changed;
        void Connect();
        void RefreshState();
        void Retry();
        void SubmitUserUtterance(string transcript);
        void SubmitClarification(string transcript);
        void ChooseOption(string id);
        void SetReplyLength(int index);
        void SetSpeechRate(float value);
        void SetTone(int index);
        void SetVoice(int index);
        void SetDialogueSettings(TutorDialoguePatch patch);
        bool CanUndoSetting(string field);
        void UndoSetting(string field);
        void UndoReplyLength();
    }
}
