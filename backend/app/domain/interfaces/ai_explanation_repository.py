from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.ai_explanation import AiExplanation


class AiExplanationRepository(ABC):
    """Abstract repository for persisting validated AI explanations."""

    @abstractmethod
    def save(self, explanation: AiExplanation) -> None:
        """Save or update an AI explanation for an audit run."""
        ...

    @abstractmethod
    def get(self, run_id: int) -> AiExplanation | None:
        """Retrieve the cached AI explanation for an audit run if available."""
        ...

    @abstractmethod
    def delete(self, run_id: int) -> bool:
        """Delete an AI explanation for an audit run."""
        ...
