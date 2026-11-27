"""Approved voice identities and speech rendering settings; no credentials."""
PROFILE_VERSION = "speech-selected-v2"
DEFAULT_VOICE = "voice_d"
VOICE_IDS = ('voice_a', 'voice_b', 'voice_c', 'voice_d', 'voice_e')
VOICE_PROVIDERS = {'voice_a': 'longanlingxin', 'voice_b': 'longanhuan_v3.6', 'voice_c': 'qwen-audio-3.0-tts-plus-loongolivialin', 'voice_d': 'qwen-audio-3.0-tts-plus-loongadriangao', 'voice_e': 'qwen-audio-3.0-tts-plus-loongjameszhao'}
# Provider catalog labels, not acoustic inference. Voice B verified 2026-11-27
# against the official Qwen-Audio-TTS voice list (exact longanhuan_v3.6 ID).
VOICE_LABELS = {'voice_a': 'Female voice 1', 'voice_b': 'Female voice 2', 'voice_c': 'Female voice 3', 'voice_d': 'Male voice 1', 'voice_e': 'Male voice 2'}
VOICE_DESCRIPTIONS = {
    'voice_a': {'catalog_gender': 'female', 'source': 'Official Plus voice list; recorded in STAGE_4_SPEECH_PROFILE.json'},
    'voice_b': {'catalog_gender': 'female', 'source': 'https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list (longanhuan_v3.6; checked 2026-11-27)'},
    'voice_c': {'catalog_gender': 'female', 'source': 'Official Plus catalog Sheet1 B578:H578'},
    'voice_d': {'catalog_gender': 'male', 'source': 'Official Plus catalog Sheet1 B582:H582'},
    'voice_e': {'catalog_gender': 'male', 'source': 'Official Plus catalog Sheet1 B583:H583'},
}
SAMPLE_TEXT = "Let's explore this idea together, one step at a time."
TONE_INSTRUCTIONS = {'professional': 'Speak in English with a professional, composed and matter-of-fact delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.', 'friendly': 'Speak in English with a warm, approachable and conversational delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.', 'encouraging': 'Speak in English with a supportive, reassuring and gently motivating delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.'}
FIXED_PARAMETERS = {'format': 'wav', 'sample_rate': 24000, 'volume': 50, 'pitch': 1.0, 'seed': 4435, 'language_hints': ['en']}
