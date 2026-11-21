from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Protocol for communicating with local LLM engine (e.g. Ollama)."""

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        """Request structured JSON completion from model."""
        ...

    def is_reachable(self) -> bool:
        """Check if LLM server is up and responsive."""
        ...

    @property
    def model(self) -> str:
        """Configured model name."""
        ...
