# Qwen Token Plan access check — 2026-11-10

Interactive credential validation only. No Unity or running backend integration changed.

Credential stored in repository-root `.env.qwen-token-plan`, mode 0600, ignored by Git, outside Assets. No key or key fingerprint is recorded here. Key appeared in chat; rotate before continued use.

| Endpoint region | Requested model | HTTP | Provider result |
|---|---|---|---|
| Singapore | qwen-audio-3.1-tts-flash | 401 | InvalidApiKey |
| Singapore | qwen3-asr-flash | 401 | InvalidApiKey |
| Beijing | qwen-audio-3.1-tts-flash | 404 | InvalidParameter: Model not exist. |
| Beijing | qwen3-asr-flash | 404 | InvalidParameter: Model not exist. |

Four HTTP requests reached the provider, with no successful generation or recognition and no usage field returned. This does not independently verify billing. Earlier sandbox DNS failures did not reach the provider.

TTS input: “Hello.”, voice longanhuan_v3.1. ASR input: generated one-second silent WAV, solely for access validation, not recognition quality. Local macOS speech synthesis was unavailable. No participant audio was used.

Beijing is saved as the candidate Token Plan endpoint because it returned a model-level error; this is not proof of successful account authentication or model usability. Both requested models remain unavailable through the tested endpoint/key combination. Do not infer global model nonexistence from this result.

Evidence: StudyData/validation/qwen-token-plan-20261110.json and qwen-token-plan-beijing-20261110.json (redacted, local only).

Official Token Plan examples list qwen-audio-3.0-asr-flash and qwen-audio-3.0-tts-plus. Neither alternative was called and project model choices were not silently changed.

Sources:
- https://help.aliyun.com/zh/model-studio/token-plan-integration-overview
- https://help.aliyun.com/zh/model-studio/token-plan-speech-recognition
- https://help.aliyun.com/zh/model-studio/token-plan-speech-synthesis
- https://www.alibabacloud.com/help/en/model-studio/more-tools

Next: use a standard Model Studio workspace API key for the VR custom backend; match its region and model availability, then validate actual English speech recognition and synthesis. Token Plan capability testing is distinct from permitted custom-backend deployment.

## Follow-up: supported 3.0 models — successful

User identified qwen-audio-3.0-asr-flash and qwen-audio-3.0-tts-plus. Both are listed in official Token Plan speech integration documentation.

- Beijing TTS: HTTP 200; voice longanhuan_v3.6; rate 1.0; synthesized “Please speak a little more slowly.” Returned an audio URL. Usage: 34 characters (7 input tokens, 34 output tokens, 41 total tokens as reported).
- Beijing ASR: HTTP 200; transcribed the TTS audio URL as “Please speak a little more slowly.” Usage: 3 seconds.
- Two calls, no retries. No participant audio, no key in evidence.
- Evidence: StudyData/validation/qwen-token-plan-3.0-20261110.json.

This confirms the saved credential works at the Beijing Token Plan endpoint for these two models. Earlier failures were for different models/region, not proof of an invalid key. Isolated local Token Plan configuration now selects the verified 3.0 models. DeepSeek and Unity runtime remain unchanged. Speech rate extremes, three English voices, tone differentiation and headset playback are not yet validated. Token Plan custom-backend usage restrictions remain a separate issue from technical access.
