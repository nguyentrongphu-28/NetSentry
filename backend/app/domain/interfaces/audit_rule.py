from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.finding import Finding, Severity
from app.domain.entities.parsed_config import ParsedConfig


class AuditRule(ABC):
    rule_id: str
    title: str
    severity: Severity
    platforms: tuple[str, ...]

    @abstractmethod
    def check(self, config: ParsedConfig) -> list[Finding]:
        raise NotImplementedError

    def applies_to(self, platform: str) -> bool:
        return platform in self.platforms
