"""Service coordinating AI explanations for audit runs with caching, concurrency, and rate-limiting (Spec 8.8)."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Callable

from app.domain.entities.ai_explanation import AiExplanation
from app.domain.entities.audit_result import AuditStatus
from app.domain.errors import (
    AiBusyError,
    AiDisabledError,
    ExplanationNotFoundError,
    NetSentryError,
)
from app.domain.interfaces.ai_explanation_repository import AiExplanationRepository
from app.domain.interfaces.llm_client import LLMClient
from app.security.rate_limiter import InMemorySlidingWindowLimiter
from app.services.ai_explanation_validator import ExplanationValidator
from app.services.ai_prompt_builder import (
    EXPLANATION_JSON_SCHEMA,
    PROMPT_VERSION,
    PromptBuilder,
)
from app.services.audit_run_service import AuditRunService

logger = logging.getLogger(__name__)


class AiExplainService:
    """Manages generation, caching, and retrieval of security audit explanations."""

    def __init__(
        self,
        explanation_repository: AiExplanationRepository,
        audit_run_service: AuditRunService,
        llm_client: LLMClient,
        *,
        enabled: bool = False,
        timeout_seconds: int = 120,
        max_concurrency: int = 1,
        rate_limit: str = "5/3600",
    ) -> None:
        self.explanation_repository = explanation_repository
        self.audit_run_service = audit_run_service
        self.llm_client = llm_client
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

        # Semaphore for max concurrency
        self._semaphore = threading.Semaphore(max_concurrency)

        # Rate limiter per user (e.g. "5/3600")
        parts = rate_limit.split("/")
        max_req = int(parts[0]) if len(parts) >= 1 else 5
        window_sec = int(parts[1]) if len(parts) >= 2 else 3600
        self._limiter = InMemorySlidingWindowLimiter(max_requests=max_req, window_seconds=window_sec)

    def is_available(self) -> dict[str, object]:
        """Check status of AI explanation service."""
        if not self.enabled:
            return {"enabled": False, "reachable": False, "model": self.llm_client.model}
        reachable = self.llm_client.is_reachable()
        return {"enabled": True, "reachable": reachable, "model": self.llm_client.model}

    def get_explanation(self, run_id: int) -> AiExplanation:
        """Retrieve stored explanation for an audit run."""
        exp = self.explanation_repository.get(run_id)
        if exp is None:
            raise ExplanationNotFoundError(f"No AI explanation found for audit run {run_id}")
        return exp

    def explain(
        self,
        run_id: int,
        *,
        username: str,
        force: bool = False,
    ) -> AiExplanation:
        """Generate or retrieve cached AI explanation for an audit run."""
        if not self.enabled:
            raise AiDisabledError("AI explanation service is disabled by server configuration")

        # 1. Fetch audit run and verify it is COMPLETED
        audit_run = self.audit_run_service.get_run(run_id)
        if audit_run.summary.status != AuditStatus.COMPLETED:
            from app.domain.errors import DiffInputError
            raise DiffInputError(f"Audit run {run_id} is not in COMPLETED state (status: {audit_run.summary.status.value})")

        # 2. Compute input_sha256 from user prompt
        user_prompt = PromptBuilder.build_user_prompt(audit_run.findings)
        input_sha256 = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()
        model_name = self.llm_client.model

        # 3. Check cache
        if not force:
            cached = self.explanation_repository.get(run_id)
            if (
                cached is not None
                and cached.input_sha256 == input_sha256
                and cached.model == model_name
                and cached.prompt_version == PROMPT_VERSION
            ):
                return cached

        # 4. Check user rate limit
        now = time.time()
        allowed, retry_after = self._limiter.is_allowed(f"ai:{username}", now=now)
        if not allowed:
            raise AiBusyError(
                f"Rate limit exceeded for user '{username}'. Try again later.",
                retry_after=retry_after or 60,
            )

        # 5. Acquire semaphore (concurrency limit)
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            raise AiBusyError("AI service is currently busy processing another request. Please try again.")

        try:
            # 6. Call LLM
            system_prompt = PromptBuilder.build_system_prompt()
            raw_output = self.llm_client.generate_json(
                system=system_prompt,
                user=user_prompt,
                schema=EXPLANATION_JSON_SCHEMA,
                timeout_seconds=self.timeout_seconds,
            )

            # 7. Validate and sanitize
            explanation = ExplanationValidator.validate(
                raw_output,
                audit_run.findings,
                run_id=run_id,
                model=model_name,
                prompt_version=PROMPT_VERSION,
                input_sha256=input_sha256,
            )

            # 8. Save to repository
            self.explanation_repository.save(explanation)
            return explanation
        finally:
            self._semaphore.release()
