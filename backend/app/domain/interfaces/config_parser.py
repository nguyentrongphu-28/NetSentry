from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.parsed_config import ParsedConfig


class ConfigParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParsedConfig:
        raise NotImplementedError
