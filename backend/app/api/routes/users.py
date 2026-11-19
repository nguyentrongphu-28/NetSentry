"""Administrative user management routes: /api/v1/users/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import (
    Principal,
    get_client_ip,
    get_user_service,
    require_role,
)
from app.api.schemas.users import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserOut,
)
from app.domain.entities.user import Role
from app.domain.errors import UserNotFoundError
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    principal: Principal = Depends(require_role(Role.ADMIN)),
    user_service: UserService = Depends(get_user_service),
) -> list[UserOut]:
    """List all users (Admin only)."""
    users = user_service.list_users()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            role=u.role.value,
            is_active=u.is_active,
            must_change_password=u.must_change_password,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    request: Request,
    body: CreateUserRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
    user_service: UserService = Depends(get_user_service),
) -> UserOut:
    """Create new user (Admin only)."""
    client_ip = get_client_ip(request)
    role_enum = Role(body.role)
    user = user_service.create_user(
        username=body.username,
        password=body.password,
        role=role_enum,
        actor_username=principal.username,
        client_ip=client_ip,
    )
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role.value,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    request: Request,
    body: UpdateUserRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
    user_service: UserService = Depends(get_user_service),
) -> UserOut:
    """Update user role or active status (Admin only)."""
    client_ip = get_client_ip(request)
    role_enum = Role(body.role) if body.role else None

    updated = user_service.update_role_active(
        user_id=user_id,
        role=role_enum,
        is_active=body.is_active,
        actor_username=principal.username,
        client_ip=client_ip,
    )
    return UserOut(
        id=updated.id,
        username=updated.username,
        role=updated.role.value,
        is_active=updated.is_active,
        must_change_password=updated.must_change_password,
        created_at=updated.created_at,
        last_login_at=updated.last_login_at,
    )


@router.post("/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: int,
    request: Request,
    body: ResetPasswordRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
    user_service: UserService = Depends(get_user_service),
) -> Response:
    """Reset user password (Admin only)."""
    client_ip = get_client_ip(request)
    user_service.reset_password(
        user_id=user_id,
        new_password=body.new_password,
        actor_username=principal.username,
        client_ip=client_ip,
    )
    return Response(status_code=204)
