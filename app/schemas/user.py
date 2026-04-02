"""
User schemas — Pydantic models for request validation and response serialization.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
import re

from app.models.user import UserRole


# ── Request Schemas ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Schema for new user registration."""
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.VIEWER

    @field_validator("full_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty.")
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(v) > 100:
            raise ValueError("Full name cannot exceed 100 characters.")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "full_name": "Alice Johnson",
                "email": "alice@example.com",
                "password": "SecurePass1",
                "role": "viewer",
            }
        }
    }


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "alice@example.com",
                "password": "SecurePass1",
            }
        }
    }


class UserUpdate(BaseModel):
    """Schema for updating an existing user (admin only)."""
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v or len(v) < 2:
                raise ValueError("Full name must be at least 2 characters.")
        return v


class ChangePassword(BaseModel):
    """Schema for a user changing their own password."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v


# ── Response Schemas ─────────────────────────────────────────────────────────

class UserOut(BaseModel):
    """Public user representation returned in API responses."""
    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    """Response schema after a successful login."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut
