"""Study identity validation shared by the importer and researcher launcher."""
import re

PHASE_PATTERNS = {
    'debug': re.compile(r'^(DEBUG|ENGINEERING)[A-Z0-9_-]{0,36}$'),
    'pilot': re.compile(r'^PILOT0[12]$'),
    'formal': re.compile(r'^(P00[1-9]|P01[0-9]|P020)$'),
}
SESSION_RE = re.compile(r'^[A-Za-z0-9_-]{3,80}$')


def validate_identity(participant_id, phase, session_id):
    pattern = PHASE_PATTERNS.get(phase) if isinstance(phase, str) else None
    if not isinstance(participant_id, str) or not pattern or not pattern.fullmatch(participant_id):
        raise ValueError('Participant ID and debug/pilot/formal phase disagree.')
    if not isinstance(session_id, str) or not SESSION_RE.fullmatch(session_id):
        raise ValueError('Invalid study session ID.')


def validate_config(data):
    if not isinstance(data, dict) or data.get('schema_version') != 'appearance-session-v1':
        raise ValueError('Expected a session configuration, not questionnaire answers.')
    validate_identity(data.get('participant_id'), data.get('phase'), data.get('study_session_id'))
    return {key: data[key] for key in ('participant_id', 'phase', 'study_session_id')}
