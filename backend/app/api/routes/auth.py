"""Authentication routes: /api/v1/auth/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import (
    Principal,
    get_auth_service,
    get_client_ip,
    get_current_principal,
    get_settings,
    require_role,
)
from app.api.schemas.auth import (
    AuthMeResponse,
    CapabilitiesOut,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserSummaryOut,
)
from app.core.config import Settings
from app.domain.entities.user import Role
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """Authenticate user with username and password, sets session cookie."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user, raw_token = auth_service.login(
        username=body.username,
        password=body.password,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    # Set-Cookie
    max_age_seconds = settings.session_ttl_minutes * 60
    response.set_cookie(
        key="netsentry_session",
        value=raw_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )

    return LoginResponse(
        user=UserSummaryOut(
            id=user.id,
            username=user.username,
            role=user.role.value,
            must_change_password=user.must_change_password,
        )
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Log out current user and revoke session token."""
    raw_token = principal.raw_token
    client_ip = get_client_ip(request)

    if raw_token:
        auth_service.logout(
            raw_token=raw_token,
            actor_username=principal.username,
            client_ip=client_ip,
        )

    # Clear cookie
    response.delete_cookie(
        key="netsentry_session",
        path="/",
        httponly=True,
        samesite="strict",
    )
    return Response(status_code=204)


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    principal: Principal = Depends(get_current_principal),
    settings: Settings = Depends(get_settings),
) -> AuthMeResponse:
    """Get current user summary and capabilities."""
    user = principal.user
    if user:
        user_out = UserSummaryOut(
            id=user.id,
            username=user.username,
            role=user.role.value,
            must_change_password=user.must_change_password,
        )
    else:
        user_out = UserSummaryOut(
            id=0,
            username=principal.username,
            role=principal.role.value,
            must_change_password=False,
        )

    return AuthMeResponse(
        user=user_out,
        capabilities=CapabilitiesOut(
            body_credentials=settings.allow_body_credentials,
        ),
    )


@router.post("/change-password", status_code=204)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    principal: Principal = Depends(require_role(Role.ADMIN, Role.OPERATOR, Role.VIEWER)),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Change password for current user."""
    if not principal.user:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_OPERATION", "message": "API key users cannot change password"}},
        )

    client_ip = get_client_ip(request)
    auth_service.change_password(
        user_id=principal.user.id,
        current_password=body.current_password,
        new_password=body.new_password,
        current_raw_token=principal.raw_token,
        client_ip=client_ip,
    )
    return Response(status_code=204)
