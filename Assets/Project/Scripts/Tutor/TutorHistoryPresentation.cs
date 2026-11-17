using System;
using System.Globalization;
using System.Linq;
using System.Text;

namespace IAI.Tutor
{
    // Render the projected history only; hidden branch records never enter here.
    public static class TutorHistoryPresentation
    {
        public static readonly string[] Fields = { "speech_rate", "reply_length", "tone", "voice", "avatar_id", "outfit", "jacket_color", "accessory", "scale" };
        public static string Label(string field)
        {
            switch (field)
            {
                case "speech_rate": return "Speech rate";
                case "reply_length": return "Reply length";
                case "avatar_id": return "Avatar";
                case "jacket_color": return "Colour";
                default: return Capital(field);
            }
        }
        static string Capital(string value) => string.IsNullOrEmpty(value) ? "—" : char.ToUpperInvariant(value[0]) + value.Substring(1);
        public static string Value(TutorSettings s, string field)
        {
            if (s == null) return "—";
            switch (field)
            {
                case "speech_rate": return s.speech_rate.ToString("0.00", CultureInfo.InvariantCulture) + "×";
                case "reply_length": return Capital(s.reply_length);
                case "tone": return Capital(s.tone);
                case "voice": return string.IsNullOrEmpty(s.voice) ? "—" : "Voice " + s.voice.Substring(s.voice.Length - 1).ToUpperInvariant();
                case "avatar_id": return Capital(s.avatar_id);
                case "outfit": return s.outfit == "sport" ? "Sportswear" : Capital(s.outfit);
                case "jacket_color": return Capital(s.jacket_color);
                case "accessory": return Capital(s.accessory);
                case "scale": return s.scale.ToString("0.00", CultureInfo.InvariantCulture) + "×";
                default: return "—";
            }
        }
        public static bool CanUndo(TutorView view, string field) => view != null && (field == "all" || Fields.Contains(field))
            && (view.changes ?? Array.Empty<TutorChange>()).Any(c => c.kind == "commit"
                && (c.remaining_fields ?? Array.Empty<string>()).Any(f => field == "all" || f == field));
        public static string Format(TutorChange change)
        {
            var fields = Fields.Where(f => Value(change.before, f) != Value(change.after, f)).ToArray();
            var title = change.kind == "undo" ? "UNDO" : string.Join(" + ", fields.Select(Label)).ToUpperInvariant();
            var text = new StringBuilder(title).Append(" · ").Append(Capital(change.source?.Replace('_', ' '))).Append('\n');
            foreach (var field in fields)
                text.Append(Label(field)).Append(": ").Append(Value(change.before, field)).Append(" → ").Append(Value(change.after, field)).Append('\n');
            if (!string.IsNullOrEmpty(change.query)) text.Append(change.query).Append('\n');
            int remaining = (change.remaining_fields ?? Array.Empty<string>()).Length;
            text.Append(change.kind == "undo" ? "Restored" : remaining == 0 ? "Undone" : remaining < fields.Length ? "Partly undone" : "Applied");
            return text.Append("\n\n").ToString();
        }
    }
}
