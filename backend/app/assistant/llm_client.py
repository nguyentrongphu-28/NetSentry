"""Giao diện LLM tối giản: complete(system, user) -> str.

MockLLM dùng cho test (không cần mạng/API key). OpenAIClient / GeminiClient gọi REST bằng urllib.
LƯU Ý: hai client thật CHƯA được kiểm tra với API thật trong môi trường dựng module này (không có mạng/key).
Tên model KHÔNG hard-code (dễ lỗi thời): đặt biến môi trường NETSENTRY_AI_MODEL.
"""
import json
import os
import urllib.error
import urllib.request

from app.core.env import load_env


class LLMClient:
    def complete(self, system: str, user: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class MockLLM(LLMClient):
    """Trả lần lượt các phản hồi đã định sẵn (str | Exception | callable(system,user)->str)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, user):
        self.calls.append({"system": system, "user": user})
        if not self.responses:
            raise RuntimeError("MockLLM: hết phản hồi định sẵn")
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r(system, user) if callable(r) else r


def _post_json(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:      # noqa: S310 (URL cố định, https)
        return json.loads(resp.read().decode("utf-8"))


class OpenAIClient(LLMClient):
    def __init__(self, api_key, model, timeout=30, base_url="https://api.openai.com/v1"):
        self.api_key, self.model, self.timeout, self.base_url = api_key, model, timeout, base_url

    def complete(self, system, user):
        data = _post_json(f"{self.base_url}/chat/completions",
                          {"Authorization": f"Bearer {self.api_key}"},
                          {"model": self.model, "temperature": 0,
                           "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                          self.timeout)
        return data["choices"][0]["message"]["content"]


class GeminiClient(LLMClient):
    def __init__(self, api_key, model, timeout=30):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete(self, system, user):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        data = _post_json(url, {"x-goog-api-key": self.api_key},
                          {"systemInstruction": {"parts": [{"text": system}]},
                           "contents": [{"role": "user", "parts": [{"text": user}]}],
                           "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                          self.timeout)
        return data["candidates"][0]["content"]["parts"][0]["text"]


def make_client_from_env():
    """NETSENTRY_AI_PROVIDER=openai|gemini, NETSENTRY_AI_MODEL=<tên model>, OPENAI_API_KEY / GEMINI_API_KEY.
    Tự nạp .env ở thư mục gốc repo (biến môi trường thật được ưu tiên). Thiếu cấu hình => RuntimeError rõ ràng."""
    load_env()
    provider = os.environ.get("NETSENTRY_AI_PROVIDER", "").lower()
    model = os.environ.get("NETSENTRY_AI_MODEL", "")
    if not model:
        raise RuntimeError("Thiếu NETSENTRY_AI_MODEL")
    try:
        timeout = int(os.environ.get("NETSENTRY_AI_TIMEOUT", "30"))
    except ValueError:
        raise RuntimeError("NETSENTRY_AI_TIMEOUT phải là số nguyên (giây)") from None
    key_var = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
    if key_var is None:
        raise RuntimeError("NETSENTRY_AI_PROVIDER phải là 'openai' hoặc 'gemini'")
    key = os.environ.get(key_var, "")
    if not key:
        raise RuntimeError(f"Thiếu {key_var}")
    return OpenAIClient(key, model, timeout) if provider == "openai" else GeminiClient(key, model, timeout)
