"""LLM providers. Default is an offline mock so the project runs with no key and no cost.

Free options via OpenAICompatibleProvider (all expose an OpenAI-style /chat/completions):
  - Google Gemini : base_url=https://generativelanguage.googleapis.com/v1beta/openai  (free tier, key from AI Studio)
  - Groq          : base_url=https://api.groq.com/openai/v1                          (free tier)
  - OpenRouter    : base_url=https://openrouter.ai/api/v1  (models ending in ':free')
  - Ollama (local): base_url=http://127.0.0.1:11434/v1     (fully free, offline, no key)
Free-tier limits and model names change; check each provider's current docs.
"""
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


class ProviderError(Exception):
    pass


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...


# Canned knowledge keyed by rule_id used by the mock (mirrors docs/rules in sample data).
_MOCK_KB = {
    "NS-001": ("Telnet is permitted on the VTY lines.", "Telnet sends credentials in clear text, so anyone able to observe the management path could capture them.", None),
    "NS-002": ("SSH version 2 is not explicitly enforced.", "Older SSH protocol versions have known weaknesses; enforcing v2 removes that option.", None),
    "NS-003": ("A default SNMP community string is configured.", "Default community names are widely known; if SNMP is reachable, device data could be read.", None),
    "NS-004": ("No login banner is configured.", "A banner supports legal notice policy; it is not a technical vulnerability.", None),
    "NS-005": ("An unused access port is administratively enabled.", "Unused enabled ports can allow unauthorized device attachment, depending on your baseline.", "configure_access_port"),
}


class MockProvider(LLMProvider):
    name = "mock"

    def complete(self, system: str, user: str) -> str:
        rule_id = user.split("Finding:", 1)[1].split("|", 1)[0].strip() if "Finding:" in user else ""
        summary, why, _ = _MOCK_KB.get(rule_id, ("This finding matches an audit rule.", "See the rule rationale and evidence.", None))
        evidence_block = user.split("<untrusted_data>", 1)[1].split("</untrusted_data>", 1)[0].strip() if "<untrusted_data>" in user else ""
        refs = [l for l in evidence_block.splitlines() if l.strip() and not l.startswith("[line removed") and not l.startswith("(no evidence")]
        has_ev = bool(refs)
        return json.dumps({
            "summary": summary, "why_it_matters": why, "evidence_refs": refs[:5],
            "suggested_action": None, "suggested_params": {},
            "confidence": "medium" if has_ev else "low",
            "caveats": ["Configuration finding only; actual exposure was not verified.", "Compare with your baseline before changing the device."]
                       + ([] if has_ev else ["No usable evidence was provided."]),
        })


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 30):
        self.base_url, self.api_key, self.model, self.timeout = base_url.rstrip("/"), api_key, model, timeout
        self.name = f"openai_compat:{model}"

    def complete(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": self.model, "temperature": 0, "max_tokens": 700,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 (URL from trusted env config)
                data = json.load(r)
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as e:
            raise ProviderError(f"LLM request failed: {type(e).__name__}") from e


def provider_from_env() -> LLMProvider:
    kind = os.getenv("ASSISTANT_PROVIDER", "mock").lower()
    if kind == "mock":
        return MockProvider()
    if kind == "openai_compat":
        base = os.getenv("ASSISTANT_BASE_URL")
        model = os.getenv("ASSISTANT_MODEL")
        if not base or not model:
            raise ProviderError("ASSISTANT_BASE_URL and ASSISTANT_MODEL are required")
        return OpenAICompatibleProvider(base, os.getenv("ASSISTANT_API_KEY", "none"), model)
    raise ProviderError(f"Unknown ASSISTANT_PROVIDER '{kind}'")
