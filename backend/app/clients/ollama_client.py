"""Ollama client using standard library urllib with loopback and safety enforcement (Spec 8.5)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.domain.errors import AiOutputInvalidError, AiUnavailableError
from app.domain.interfaces.llm_client import LLMClient

logger = logging.getLogger(__name__)

_MAX_RESPONSE_BYTES = 256 * 1024  # 256 KB


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not follow redirects
        return None


class OllamaClient(LLMClient):
    """Local Ollama client communicating via HTTP POST /api/chat with JSON schema formatting."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model_name: str = "qwen2.5:7b-instruct",
        *,
        allow_remote: bool = False,
    ) -> None:
        self._raw_base_url = base_url.rstrip("/")
        self._model = model_name
        self._allow_remote = allow_remote

        parsed = urllib.parse.urlparse(self._raw_base_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: '{parsed.scheme}'. Only http and https are allowed.")

        host = (parsed.hostname or "").lower()
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        if not is_loopback and not self._allow_remote:
            raise ValueError(
                f"Ollama host '{host}' is not a loopback address. Set allow_remote=True if intentional."
            )

        self._base_url = self._raw_base_url
        self._opener = urllib.request.build_opener(_NoRedirectHandler)

    @property
    def model(self) -> str:
        return self._model

    def is_reachable(self) -> bool:
        """Check reachability by calling GET /api/tags."""
        url = f"{self._base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")
        try:
            with self._opener.open(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, object],
        timeout_seconds: int = 120,
    ) -> dict[str, object]:
        """Request structured JSON completion from Ollama chat API."""
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.2},
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with self._opener.open(req, timeout=timeout_seconds) as resp:
                resp_bytes = resp.read(_MAX_RESPONSE_BYTES + 1)
                if len(resp_bytes) > _MAX_RESPONSE_BYTES:
                    raise AiOutputInvalidError("AI response exceeded maximum allowed size (256 KB)")
        except AiOutputInvalidError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Ollama connection failed: %s", type(exc).__name__)
            raise AiUnavailableError("AI service is currently unavailable or unreachable") from None
        except Exception as exc:
            logger.warning("Unexpected error communicating with Ollama: %s", type(exc).__name__)
            raise AiUnavailableError("AI service encountered an unexpected error") from None

        try:
            resp_json = json.loads(resp_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AiOutputInvalidError("Failed to decode JSON response from AI service")

        message = resp_json.get("message", {})
        content_str = message.get("content", "")
        if not content_str:
            raise AiOutputInvalidError("Empty content received from AI service")

        try:
            data = json.loads(content_str)
            if not isinstance(data, dict):
                raise AiOutputInvalidError("Structured output is not a JSON object")
            return data
        except json.JSONDecodeError:
            raise AiOutputInvalidError("Failed to parse structured output inside AI response message")
