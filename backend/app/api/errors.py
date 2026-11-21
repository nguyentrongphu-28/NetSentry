"""Exception handlers for FastAPI application."""

from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import UnauthorizedError
from app.domain.errors import (
    AccountLockedError,
    ActivePlanExistsError,
    AiBusyError,
    AiDisabledError,
    AiOutputInvalidError,
    AiUnavailableError,
    AuditAlreadyRunningError,
    AuditNotFoundError,
    BaselineDisabledError,
    BaselineFailuresNotConfirmedError,
    BaselineNotFoundError,
    BodyCredentialsDisabledError,
    ConfirmationMismatchError,
    ContentDisabledError,
    CredentialsRequiredError,
    DeviceBusyError,
    DeviceNotFoundError,
    DiffInputError,
    DuplicateDeviceError,
    ExecutionDisabledError,
    ExplanationNotFoundError,
    FindingNotFailingError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvalidDeviceError,
    InvalidTransitionError,
    LastAdminError,
    NetSentryError,
    NotAuthenticatedError,
    NotEligibleError,
    OriginNotAllowedError,
    PasswordChangeRequiredError,
    PlanExpiredError,
    PlanHashMismatchError,
    PlanNotFoundError,
    PlanStaleError,
    RateLimitedError,
    ReauthFailedError,
    RemediationDisabledError,
    SelfApprovalError,
    SnapshotInUseError,
    SnapshotNotFoundError,
    UserExistsError,
    UserNotFoundError,
    UserSessionRequiredError,
    WeakPasswordError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotAuthenticatedError)
    def not_authenticated_handler(request: Request, exc: NotAuthenticatedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(InvalidCredentialsError)
    def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(ForbiddenError)
    def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(PasswordChangeRequiredError)
    def password_change_required_handler(request: Request, exc: PasswordChangeRequiredError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(OriginNotAllowedError)
    def origin_not_allowed_handler(request: Request, exc: OriginNotAllowedError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AccountLockedError)
    def account_locked_handler(request: Request, exc: AccountLockedError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(RateLimitedError)
    def rate_limited_handler(request: Request, exc: RateLimitedError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(exc.retry_after)},
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(WeakPasswordError)
    def weak_password_handler(request: Request, exc: WeakPasswordError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(BodyCredentialsDisabledError)
    def body_credentials_disabled_handler(request: Request, exc: BodyCredentialsDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )
    @app.exception_handler(InvalidCurrentPasswordError)
    def invalid_current_password_handler(
        request: Request, exc: InvalidCurrentPasswordError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )
    @app.exception_handler(UserExistsError)
    def user_exists_handler(request: Request, exc: UserExistsError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(LastAdminError)
    def last_admin_handler(request: Request, exc: LastAdminError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(UserNotFoundError)
    def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )
    @app.exception_handler(UnauthorizedError)
    def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API key",
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: list[dict[str, str]] = []
        for err in exc.errors():
            # Filter out 'body' locator prefix
            loc_parts = [str(part) for part in err.get("loc", ()) if part != "body"]
            field_name = ".".join(loc_parts) if loc_parts else "body"
            details.append({
                "field": field_name,
                "message": err.get("msg", "Validation error"),
            })

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": details,
                }
            },
        )

    @app.exception_handler(DeviceNotFoundError)
    def device_not_found_handler(
        request: Request, exc: DeviceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AuditNotFoundError)
    def audit_not_found_handler(
        request: Request, exc: AuditNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(DuplicateDeviceError)
    def duplicate_device_handler(
        request: Request, exc: DuplicateDeviceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AuditAlreadyRunningError)
    def audit_already_running_handler(
        request: Request, exc: AuditAlreadyRunningError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(InvalidDeviceError)
    def invalid_device_handler(
        request: Request, exc: InvalidDeviceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(ContentDisabledError)
    def content_disabled_handler(request: Request, exc: ContentDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(SnapshotNotFoundError)
    def snapshot_not_found_handler(request: Request, exc: SnapshotNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(ExplanationNotFoundError)
    def explanation_not_found_handler(request: Request, exc: ExplanationNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(DiffInputError)
    def diff_input_handler(request: Request, exc: DiffInputError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AiBusyError)
    def ai_busy_handler(request: Request, exc: AiBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(getattr(exc, "retry_after", 30))},
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AiOutputInvalidError)
    def ai_output_invalid_handler(request: Request, exc: AiOutputInvalidError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AiDisabledError)
    def ai_disabled_handler(request: Request, exc: AiDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(AiUnavailableError)
    def ai_unavailable_handler(request: Request, exc: AiUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(BaselineNotFoundError)
    def baseline_not_found_handler(request: Request, exc: BaselineNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(BaselineFailuresNotConfirmedError)
    def baseline_failures_not_confirmed_handler(
        request: Request, exc: BaselineFailuresNotConfirmedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(SnapshotInUseError)
    def snapshot_in_use_handler(request: Request, exc: SnapshotInUseError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(BaselineDisabledError)
    def baseline_disabled_handler(request: Request, exc: BaselineDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(RemediationDisabledError)
    def remediation_disabled_handler(request: Request, exc: RemediationDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(NotEligibleError)
    def not_eligible_handler(request: Request, exc: NotEligibleError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(FindingNotFailingError)
    def finding_not_failing_handler(request: Request, exc: FindingNotFailingError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(ReauthFailedError)
    def reauth_failed_handler(request: Request, exc: ReauthFailedError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(ActivePlanExistsError)
    def active_plan_exists_handler(request: Request, exc: ActivePlanExistsError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(PlanStaleError)
    def plan_stale_handler(request: Request, exc: PlanStaleError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(PlanExpiredError)
    def plan_expired_handler(request: Request, exc: PlanExpiredError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(InvalidTransitionError)
    def invalid_transition_handler(request: Request, exc: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(PlanNotFoundError)
    def plan_not_found_handler(request: Request, exc: PlanNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(SelfApprovalError)
    def self_approval_handler(request: Request, exc: SelfApprovalError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(UserSessionRequiredError)
    def user_session_required_handler(request: Request, exc: UserSessionRequiredError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(ExecutionDisabledError)
    def execution_disabled_handler(request: Request, exc: ExecutionDisabledError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(DeviceBusyError)
    def device_busy_handler(request: Request, exc: DeviceBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(PlanHashMismatchError)
    def plan_hash_mismatch_handler(request: Request, exc: PlanHashMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.exception_handler(ConfirmationMismatchError)
    def confirmation_mismatch_handler(request: Request, exc: ConfirmationMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )


    @app.exception_handler(CredentialsRequiredError)
    def credentials_required_handler(
        request: Request, exc: CredentialsRequiredError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(NetSentryError)
    def generic_netsentry_error_handler(
        request: Request, exc: NetSentryError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        if exc.status_code == 401:
            code = "UNAUTHORIZED"
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                }
            },
        )

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error processing %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected internal error occurred",
                }
            },
        )
