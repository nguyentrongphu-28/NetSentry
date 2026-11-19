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
    AuditAlreadyRunningError,
    AuditNotFoundError,
    BodyCredentialsDisabledError,
    CredentialsRequiredError,
    DeviceNotFoundError,
    DuplicateDeviceError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidDeviceError,
    LastAdminError,
    NetSentryError,
    NotAuthenticatedError,
    OriginNotAllowedError,
    PasswordChangeRequiredError,
    RateLimitedError,
    UserExistsError,
    UserNotFoundError,
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
