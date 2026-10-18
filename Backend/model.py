"""OpenAI-compatible DeepSeek adapter. No credentials are logged or sent to Unity."""
from __future__ import annotations
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

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

CAPABILITIES = {"jacket_color":["blue","orange","green","gray","red","purple"],"accessory":["none","hat","glasses"],"scale":{"min":0.85,"max":1.15,"step":0.05}}

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
        for attempt in range(1, self.max_attempts + 1):
            begin = time.monotonic()
            record = {"role":role,"attempt":attempt,"requested_model":self.model,"request_sha256":sha(payload),"system_prompt_sha256":hashlib.sha256(system.encode()).hexdigest(),"temperature":0.2,"thinking":{"type":"disabled"},"max_tokens":1200,"started_unix":time.time(),"started_monotonic_ms":begin*1000}
            retryable = True
            try:
                req = urllib.request.Request(self.base_url + "/chat/completions", data=encoded, headers={"Authorization":"Bearer " + self.key,"Content-Type":"application/json"})
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
        return self._call("proposer", PROPOSER_PROMPT, context)

    def decide(self, context: dict) -> tuple[dict, list[dict]]:
        return self._call("native_gate", NATIVE_PROMPT, context)

class MockModel:
    """Explicit development fixture; never represented as DeepSeek output or participant data."""
    mode, model = "mock", "deterministic-development-fixture"
    def propose(self, context: dict) -> tuple[dict, list[dict]]:
        query, state = context["query"].lower(), context["state"]
        patches, refs, overrides = [], [], []
        explicit = any(word in query for word in ("这次", "this time", "虽然", "although"))
        colors = {"blue":"蓝","orange":"橙","green":"绿","gray":"灰","red":"红","purple":"紫"}
        patch = {}
        for name, chinese in colors.items():
            if name in query or chinese in query:
                patch["jacket_color"] = name
        if any(x in query for x in ("去掉", "摘掉", "remove", "无配饰", "no accessory")):
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
