"""Approved voice identities and speech rendering settings; no credentials."""
PROFILE_VERSION = "speech-selected-v2"
DEFAULT_VOICE = "voice_d"
VOICE_IDS = ('voice_a', 'voice_b', 'voice_c', 'voice_d', 'voice_e')
VOICE_PROVIDERS = {'voice_a': 'longanlingxin', 'voice_b': 'longanhuan_v3.6', 'voice_c': 'qwen-audio-3.0-tts-plus-loongolivialin', 'voice_d': 'qwen-audio-3.0-tts-plus-loongadriangao', 'voice_e': 'qwen-audio-3.0-tts-plus-loongjameszhao'}
SAMPLE_TEXT = "Let's explore this idea together, one step at a time."
TONE_INSTRUCTIONS = {'professional': 'Speak in English with a professional, composed and matter-of-fact delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.', 'friendly': 'Speak in English with a warm, approachable and conversational delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.', 'encouraging': 'Speak in English with a supportive, reassuring and gently motivating delivery. Keep the selected speaker identity and requested speaking rate. Read only the supplied text without additions or sound effects.'}
FIXED_PARAMETERS = {'format': 'wav', 'sample_rate': 24000, 'volume': 50, 'pitch': 1.0, 'seed': 4435, 'language_hints': ['en']}
