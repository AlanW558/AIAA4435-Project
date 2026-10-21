"""OpenAI-compatible DeepSeek adapter. No credentials are logged or sent to Unity."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
import threading
import urllib.error
import urllib.request
from typing import Any

from capabilities import AVATAR_DEFAULTS, DEMO_PROFILE, STUDY_PROFILE, WHOLE_REPLACEMENT_PHRASES

PROPOSER_PROMPT = '''You are the shared appearance interpretation module in an experiment.
Interpret only the user's public request and public context. Do not decide whether to ask a question.
Supported appearance fields: jacket_color in blue/orange/green/gray/red/purple;
accessory in none/hat/glasses; scale in 0.85..1.15 on a 0.05 grid.
Return JSON with exactly this structure:
{"supported":true,"reason":"brief factual explanation","candidates":[{"id":"c1","patch":{"jacket_color":"blue"},"evidence":"short quote or contextual evidence"}],"default_id":"c1","unresolved_references":[],"possible_soft_preference_overrides":[],"explicit_override":false}
Provide 1 to 3 plausible distinct patches; one for a clear request, never invent ambiguity.
Only include changed/requested fields; never adjust unrelated properties. An intentional no-change patch may be {}.
Choose the most plausible default, without knowledge of the experiment condition.
Use unresolved_references only for an execution-relevant reference with multiple possible referents.
Use possible_soft_preference_overrides only for a current persistent preference that may be overridden without explicit authorization. Explicit requests such as 'although usually X, this time Y' authorize overriding soft preferences. Soft preferences are not hard locks.
For subjective appearance words, describe plausible concrete alternatives without claiming that any color or accessory inherently implies a personality.
Use history only as public context. If there is no supported, grounded interpretation, return supported:false, candidates:[], default_id:"", with a brief reason. Unsupported requests must not silently map to unrelated appearance edits.
Output JSON only. Do not return executable code, confidence scores, strategy recommendations, or private goals.'''

NATIVE_PROMPT = '''You control a customizable embodied character. Given the same public user request, state, public history, soft preferences, supported capabilities and a proposal, choose whether to ACT on the default candidate, ASK the available shared question, or leave it UNRESOLVED. Decide using your own judgment about serving the user. An ASK costs an interruption but may resolve uncertainty. ACT is followed by visible feedback and undo. You cannot change the candidates, question or patch here. Return JSON only: {"decision":"ACT|ASK|UNRESOLVED","reason":"brief explanation"}.'''

CAPABILITIES = STUDY_PROFILE.capabilities

DEMO_PROPOSER_PROMPT = PROPOSER_PROMPT.replace(
    "Supported appearance fields: jacket_color in blue/orange/green/gray/red/purple;\n"
    "accessory in none/hat/glasses; scale in 0.85..1.15 on a 0.05 grid.",
    "Supported appearance fields for avatar-demo-v1: jacket_color in blue/orange/green/gray/red/purple/yellow;\n"
    "accessory in none/hat/glasses; scale in 0.85..1.15 on a 0.05 grid;\n"
    "avatar_id in liang/nailong; outfit in suit/sport/none.",
) + '''
Demo semantics:
- liang is the user's Liang Wenfeng (梁文锋/梁文峰) character: muscular human, short black hair and glasses, initially blue suit.
- nailong is the yellow cartoon dinosaur 奶龙; 奶蛙 and 奶娃 are user aliases for that same character.
- jacket_color means clothing color on liang (shorts when outfit=none), and body color on nailong.
- liang supports suit (西装), sport (运动装), and none (bare muscular torso with training shorts).
  nailong supports only outfit=none. Both avatars support the listed accessories and scales.
- An explicit avatar replacement is atomic. Include all five target state fields, including avatar_id.
  Default liang replacement: avatar_id=liang, outfit=suit, jacket_color=blue, accessory=glasses, scale=1.0.
  Default nailong replacement: avatar_id=nailong, outfit=none, jacket_color=yellow, accessory=none, scale=1.0.
  A clear request "全部替换", "整体替换", "全部换掉", "整个换掉", "全都换掉", "replace everything" without another target means the nailong replacement.
  A clear "换成奶龙/奶蛙/奶娃" likewise uses the nailong defaults; do not invent alternatives or ask for confirmation.
  Explicit requested overrides or instructions to keep a field take precedence over these defaults:
  include the current value for every explicitly preserved field even if unchanged.
  A clear whole-avatar replacement explicitly authorizes these default changes to old appearance fields;
  set explicit_override=true for that replacement, while still honoring explicitly preserved fields.
  If preservation or a request requires an unsupported combination (e.g. nailong wearing suit), return supported:false.
- A color, accessory, outfit, or scale request without an avatar replacement must keep avatar_id unchanged.
  Never infer a character switch from a color, personality, outfit, or size word alone.
- Distinct character or clothing alternatives count as real ambiguity. A clear named choice has one candidate.
- Keep all unsupported edits unresolved; never silently reduce a full character or clothing request to an old color-only edit.
'''

def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()

class ModelError(Exception):
    def __init__(self, message: str, records: list[dict] | None = None):
        super().__init__(message)
        self.records = records or []

class DeepSeekModel:
    mode = "live"
    def __init__(self, model: str, timeout: float = 20, max_attempts: int = 2):
        self.model = model
        self.key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.fallback_key = os.environ.get("DEEPSEEK_FALLBACK_API_KEY", "").strip()
        self._using_fallback = False
        self._credential_lock = threading.Lock()
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        if not self.key:
            raise ValueError("Live mode requires DEEPSEEK_API_KEY in the server environment; mock fallback is disabled.")
        if not self.model:
            raise ValueError("Live mode requires DEEPSEEK_MODEL (or --model) to be explicitly configured.")
        if not self.base_url.startswith("https://"):
            raise ValueError("DEEPSEEK_BASE_URL must use HTTPS to protect the API credential.")
        self.timeout, self.max_attempts = timeout, max_attempts

    def _call(self, role: str, system: str, context: dict) -> tuple[dict, list[dict]]:
        payload = {"model":self.model,"messages":[{"role":"system","content":system},{"role":"user","content":stable_json(context)}],"response_format":{"type":"json_object"},"thinking":{"type":"disabled"},"temperature":0.2,"max_tokens":1200,"stream":False}
        encoded = stable_json(payload).encode()
        records = []
        attempt, attempt_limit = 0, self.max_attempts
        while attempt < attempt_limit:
            attempt += 1
            begin = time.monotonic()
            record = {"role":role,"attempt":attempt,"requested_model":self.model,"request_sha256":sha(payload),"system_prompt_sha256":hashlib.sha256(system.encode()).hexdigest(),"temperature":0.2,"thinking":{"type":"disabled"},"max_tokens":1200,"started_unix":time.time(),"started_monotonic_ms":begin*1000}
            with self._credential_lock:
                key, using_fallback = self.key, self._using_fallback
            record["credential_slot"] = "fallback" if using_fallback else "primary"
            retryable = True
            try:
                req = urllib.request.Request(self.base_url + "/chat/completions", data=encoded, headers={"Authorization":"Bearer " + key,"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("oversized_response")
                result = json.loads(raw)
                record["response_model"] = result.get("model")
                record["usage"] = result.get("usage", {})
                record["response_id"] = result.get("id")
                choice = result["choices"][0]
                record["finish_reason"] = choice.get("finish_reason")
                if choice.get("finish_reason") == "length":
                    raise ValueError("truncated_response")
                content = choice["message"]["content"]
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError("expected_json_object")
                record.update(status="ok", duration_seconds=time.monotonic()-begin, response_sha256=sha(value))
                records.append(record)
                return value, records
            except urllib.error.HTTPError as exc:
                record.update(status="error", error="provider_http_error", http_status=exc.code)
                retryable = exc.code in (408,429,500,502,503,504)
                # DeepSeek documents HTTP 402 as insufficient balance. Other failures
                # must never silently spend the user's fallback account.
                if exc.code == 402 and not using_fallback and self.fallback_key and self.fallback_key != key:
                    with self._credential_lock:
                        self.key, self._using_fallback = self.fallback_key, True
                    record["credential_fallback_reason"] = "insufficient_balance"
                    retryable = True
                    attempt_limit += 1  # a rejected billing call does not consume the backup attempt
            except (urllib.error.URLError, TimeoutError, OSError):
                record.update(status="error", error="provider_connection_error")
            except (ValueError, KeyError, TypeError, IndexError):
                record.update(status="error", error="invalid_provider_json")
            record["duration_seconds"] = time.monotonic()-begin
            records.append(record)
            if not retryable:
                break
        raise ModelError("DeepSeek request failed; no appearance edit was applied. Check server configuration or retry with a new request ID.", records)

    def propose(self, context: dict) -> tuple[dict, list[dict]]:
        prompt=DEMO_PROPOSER_PROMPT if context.get("capability_profile") == DEMO_PROFILE.name else PROPOSER_PROMPT
        return self._call("proposer", prompt, context)

    def decide(self, context: dict) -> tuple[dict, list[dict]]:
        return self._call("native_gate", NATIVE_PROMPT, context)

class MockModel:
    """Explicit development fixture; never represented as DeepSeek output or participant data."""
    mode, model = "mock", "deterministic-development-fixture"
    def propose(self, context: dict) -> tuple[dict, list[dict]]:
        query, state = context["query"].lower(), context["state"]
        demo=context.get("capability_profile") == DEMO_PROFILE.name
        patches, refs, overrides = [], [], []
        explicit = any(word in query for word in ("这次", "this time", "虽然", "although"))
        colors = {"blue":"蓝","orange":"橙","green":"绿","gray":"灰","red":"红","purple":"紫"}
        if demo: colors["yellow"]="黄"
        patch = {}
        if demo:
            targets={name:max((query.rfind(word) for word in words),default=-1) for name,words in {
                "liang":("梁文锋","梁文峰","liang"),
                "nailong":("奶龙","奶蛙","奶娃","nailong"),
            }.items()}
            target=max(targets,key=targets.get)
            if targets[target]>=0:
                patch=dict(AVATAR_DEFAULTS[target])
                explicit=True
            elif any(word in query for word in WHOLE_REPLACEMENT_PHRASES):
                patch=dict(AVATAR_DEFAULTS["nailong"])
                explicit=True
        for name, chinese in colors.items():
            if name in query or chinese in query:
                patch["jacket_color"] = name
        remove_accessory=any(x in query for x in ("去掉", "摘掉", "remove", "无配饰", "no accessory"))
        if demo:
            remove_accessory=remove_accessory and any(x in query for x in ("配饰","帽","眼镜","accessory","hat","glasses"))
            if any(x in query for x in ("西装","suit")): patch["outfit"]="suit"
            if any(x in query for x in ("运动装","运动服","sport")): patch["outfit"]="sport"
            if any(x in query for x in ("不穿衣服","脱掉外衣","脱掉外套","默认外形","no outfit")): patch["outfit"]="none"
        if remove_accessory:
            patch["accessory"] = "none"
        elif "眼镜" in query or "glasses" in query:
            patch["accessory"] = "glasses"
        elif "帽" in query or "hat" in query:
            patch["accessory"] = "hat"
        if any(x in query for x in ("稍微大", "大一点", "slightly bigger")):
            patch["scale"] = round(min(1.15, state["scale"]+.05),2)
        if any(x in query for x in ("稍微小", "小一点", "slightly smaller")):
            patch["scale"] = round(max(.85, state["scale"]-.05),2)
        match = re.search(r"(?:scale|比例)\s*[:=为到]?\s*(0\.\d+|1(?:\.\d+)?)", query)
        if match:
            patch["scale"] = float(match.group(1))
        if demo:
            aliases={"jacket_color":("颜色","color"),"accessory":("配饰","帽","眼镜","accessory","hat","glasses"),
                     "scale":("大小","比例","size","scale"),"outfit":("衣服","服装","西装","运动装","outfit","clothes")}
            for clause in re.split(r"[，,。.;；\n]",query):
                if any(word in clause for word in ("保留","保持","不变","keep","unchanged","preserve")):
                    for name,words in aliases.items():
                        if any(word in clause for word in words):
                            patch[name]=state[name]
        if patch:
            patches = [patch]
        elif any(x in query for x in ("之前", "上次", "previous")):
            values = []
            for item in context.get("history", []):
                old = item.get("state", item.get("after", {}))
                if old.get("jacket_color") and old["jacket_color"] not in values:
                    values.append(old["jacket_color"])
            patches = [{"jacket_color": value} for value in values[-3:]]
            if len(patches)>1:
                refs = ["‘之前’可能指不同的公开历史颜色"]
        elif any(x in query for x in ("风格", "正式", "style", "formal", "醒目")):
            patches = [{"jacket_color":"orange"}, {"accessory":"hat"}]
        elif demo and any(x in query for x in ("换个形象","换个角色","different avatar","different character")):
            patches=[dict(AVATAR_DEFAULTS["liang"]),dict(AVATAR_DEFAULTS["nailong"])]
        if demo and any({**state,**p}["avatar_id"]=="nailong" and {**state,**p}["outfit"]!="none" for p in patches):
            patches=[]
        if not explicit:
            for pref in context.get("soft_preferences", []):
                if "field" in pref and any(pref["field"] in p and p[pref["field"]] != pref["value"] for p in patches):
                    overrides.append("请求可能覆盖已表达的软偏好")
        candidates = [{"id":f"c{i+1}","patch":p,"evidence":"mock fixture: "+context["query"][:160]} for i,p in enumerate(patches)]
        result = {"supported":bool(candidates),"reason":"Explicit mock fixture; not a measured LLM result.","candidates":candidates,"default_id":candidates[0]["id"] if candidates else "","unresolved_references":refs,"possible_soft_preference_overrides":overrides,"explicit_override":explicit}
        return result, [{"role":"proposer","status":"mock","duration_seconds":0,"requested_model":self.model}]

    def decide(self, context: dict) -> tuple[dict, list[dict]]:
        decision = "ASK" if len(context["proposal"]["candidates"])>1 else "ACT"
        return {"decision":decision,"reason":"Mock native fixture; not a real LLM decision."}, [{"role":"native_gate","status":"mock","duration_seconds":0,"requested_model":self.model}]
