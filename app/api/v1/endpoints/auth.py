"""
Authentication endpoints — register and login.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenOut
from app.services.user_service import UserService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    summary="Register a new user",
    responses={
        201: {"description": "User created successfully"},
        409: {"description": "Email already registered"},
        422: {"description": "Validation error (weak password, invalid email, etc.)"},
    },
)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """
    Create a new user account.

    - **full_name**: 2–100 characters
    - **email**: must be a valid, unique email address
    - **password**: min 8 chars, must include at least one letter and one digit
    - **role**: `viewer` (default), `analyst`, or `admin`
    """
    return UserService(db).create(data)


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Login and receive JWT token",
    responses={
        200: {"description": "Login successful, token returned"},
        401: {"description": "Incorrect email or password"},
        403: {"description": "Account is deactivated"},
    },
)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate and receive a Bearer token.

    Use the returned `access_token` in the `Authorization: Bearer <token>`
    header on all protected routes.
    """
    service = UserService(db)
    user = service.authenticate(data.email, data.password)
    token = service.build_token(user)
    return TokenOut(access_token=token, user=user)
