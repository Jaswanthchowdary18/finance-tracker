"""
User management endpoints.

Route order is important:
  GET /me         — must come before GET /{user_id}
  PATCH /me/password — dedicated password-change endpoint
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate, ChangePassword
from app.services.user_service import UserService
from app.utils.dependencies import get_current_user, require_admin

router = APIRouter()


# ── Current-user routes (no admin required) ───────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get your own profile",
)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    return current_user


@router.patch(
    "/me/password",
    response_model=UserOut,
    summary="Change your own password",
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "New password is the same as the current one"},
        401: {"description": "Current password is incorrect"},
    },
)
def change_my_password(
    data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change the authenticated user's password.

    - Requires the correct **current password**
    - New password must meet the same strength requirements as registration
    - New password must differ from the current one
    """
    return UserService(db).change_password(current_user, data)


# ── Admin-only routes ─────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[UserOut],
    summary="List all users (admin)",
    responses={
        200: {"description": "List of all registered users"},
        403: {"description": "Admin role required"},
    },
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Retrieve all registered users, ordered by registration date.

    **Requires**: Admin role.
    """
    return UserService(db).get_all()


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get a user by ID (admin)",
    responses={
        200: {"description": "User found"},
        403: {"description": "Admin role required"},
        404: {"description": "User not found"},
    },
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Retrieve a specific user by their ID.

    **Requires**: Admin role.
    """
    return UserService(db).get_by_id(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Update a user (admin)",
    responses={
        200: {"description": "User updated"},
        403: {"description": "Admin role required"},
        404: {"description": "User not found"},
    },
)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Update a user's name, role, or active status.

    **Requires**: Admin role.
    """
    return UserService(db).update(user_id, data)


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Delete a user (admin)",
    responses={
        204: {"description": "User deleted"},
        400: {"description": "Cannot delete your own account"},
        403: {"description": "Admin role required"},
        404: {"description": "User not found"},
    },
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Permanently delete a user and all their transactions (cascade).

    **Requires**: Admin role. Admins cannot delete themselves.
    """
    UserService(db).delete(user_id, current_user)
