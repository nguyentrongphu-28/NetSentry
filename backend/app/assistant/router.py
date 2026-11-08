from fastapi import APIRouter

from .providers import ProviderError, provider_from_env
from .schemas import ExplainRequest, ExplainResponse
from .service import explain

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/explain", response_model=ExplainResponse)
def explain_finding(req: ExplainRequest) -> ExplainResponse:
    # NOTE (B): add auth/RBAC dependency here (role >= viewer) and write an audit_log entry.
    try:
        provider = provider_from_env()
    except ProviderError as e:
        return ExplainResponse(provider="none", explanation=None, rejected_reason=f"Assistant not configured: {e}")
    return explain(req, provider)
