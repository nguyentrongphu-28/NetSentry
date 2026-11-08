import json

from app.assistant.providers import LLMProvider, ProviderError
from app.assistant.schemas import ExplainRequest, FindingInput


class Scripted(LLMProvider):
    """Returns a fixed raw string and records the prompt it was given."""
    name = "scripted"

    def __init__(self, raw: str | None = None, exc: Exception | None = None):
        self.raw, self.exc, self.last_user, self.calls = raw, exc, "", 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        self.last_user = user
        if self.exc:
            raise self.exc
        return self.raw or ""


def good(**over) -> dict:
    d = {"summary": "Telnet is allowed.", "why_it_matters": "Clear text credentials.",
         "evidence_refs": [" transport input telnet ssh"], "suggested_action": None,
         "suggested_params": {}, "confidence": "medium", "caveats": ["Not verified."]}
    d.update(over)
    return d


def req(evidence=None, question=None, **kw) -> ExplainRequest:
    ev = [" transport input telnet ssh"] if evidence is None else evidence
    return ExplainRequest(finding=FindingInput(rule_id="NS-001", title="Telnet enabled", severity="high",
                          evidence=ev, rationale="r", remediation="m", **kw), question=question)


__all__ = ["Scripted", "good", "req", "json", "ProviderError"]
