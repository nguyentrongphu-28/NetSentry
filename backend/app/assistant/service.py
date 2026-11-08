"""Explain-a-finding pipeline. Never raises to the caller: failures become rejected_reason."""
import json
import re

from pydantic import ValidationError

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .providers import LLMProvider, ProviderError
from .sanitizer import clean_text, contains_cli, looks_like_injection, sanitize_evidence
from .schemas import ALLOWED_ACTIONS, AssistantExplanation, ExplainRequest, ExplainResponse

_IFACE = re.compile(r"^(Gi|Fa)\d+/\d+$")
_VLAN_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _vlan_ok(v: str) -> bool:
    return v.isdigit() and 2 <= int(v) <= 4094 and not (1002 <= int(v) <= 1005)


def validate_proposal(action: str | None, params: dict[str, str]) -> bool:
    """Shape check only. B's remediation module re-validates authoritatively."""
    if action is None:
        return not params
    if action not in ALLOWED_ACTIONS:
        return False
    if action == "create_vlan":
        return set(params) == {"vlan_id", "vlan_name"} and _vlan_ok(params["vlan_id"]) and bool(_VLAN_NAME.match(params["vlan_name"]))
    if action == "configure_access_port":
        return set(params) == {"interface", "vlan_id"} and bool(_IFACE.match(params["interface"])) and _vlan_ok(params["vlan_id"])
    return False


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    obj = json.loads(raw[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


def explain(req: ExplainRequest, provider: LLMProvider) -> ExplainResponse:
    def reject(reason: str) -> ExplainResponse:
        return ExplainResponse(provider=provider.name, explanation=None, rejected_reason=reason)

    question = clean_text(req.question, 500) if req.question else None
    if question and looks_like_injection(question):
        return reject("Question looks like an attempt to override assistant rules or request device actions; it was not sent to the model.")

    evidence, removed = sanitize_evidence(req.finding.evidence)
    f = req.finding.model_dump()
    f["rationale"] = clean_text(f["rationale"], 2000)
    prompt = build_user_prompt(f, evidence, question, removed)

    try:
        raw = provider.complete(SYSTEM_PROMPT, prompt)
    except ProviderError as e:
        return reject(f"Assistant unavailable: {e}")
    except Exception:  # provider bugs must not leak stack traces to clients
        return reject("Assistant unavailable: unexpected provider error")

    try:
        exp = AssistantExplanation.model_validate(_extract_json(raw))
    except (ValueError, ValidationError):
        return reject("Model response did not match the required schema.")

    text_fields = [exp.summary, exp.why_it_matters, *exp.caveats]
    if any(contains_cli(t) for t in text_fields):
        return reject("Model response contained CLI commands, which the assistant may not output.")
    if any(looks_like_injection(t) for t in text_fields):
        return reject("Model response contained instruction-like content and was discarded.")

    caveats = list(exp.caveats)
    # Evidence references must be real (no hallucinated evidence).
    real = set(evidence)
    kept = [r for r in exp.evidence_refs if r in real]
    if len(kept) != len(exp.evidence_refs):
        caveats.append("Some evidence references from the model did not match the real evidence and were removed.")
    confidence = exp.confidence
    if not req.finding.evidence and confidence != "low":
        confidence = "low"
        caveats.append("No evidence was supplied, so confidence was lowered.")

    action, params = exp.suggested_action, exp.suggested_params
    if not validate_proposal(action, params):
        action, params = None, {}
        caveats.append("The model's suggested action was discarded because it failed validation.")

    final = exp.model_copy(update={"evidence_refs": kept, "caveats": caveats[:10], "confidence": confidence,
                                   "suggested_action": action, "suggested_params": params})
    return ExplainResponse(provider=provider.name, explanation=final, rejected_reason=None)
