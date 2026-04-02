"""
User Service — all business logic for user management.
Keeps the route handlers thin and focused.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.schemas.user import UserRegister, UserUpdate, ChangePassword
from app.core.security import hash_password, verify_password, create_access_token


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found.",
            )
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email.lower()).first()

    def get_all(self) -> List[User]:
        return self.db.query(User).order_by(User.created_at.desc()).all()

    def create(self, data: UserRegister) -> User:
        """Register a new user. Raises 409 if email already exists."""
        if self.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        user = User(
            full_name=data.full_name.strip(),
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            role=data.role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User:
        """Verify credentials. Raises 401/403 on failure."""
        user = self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated.",
            )
        return user

    def build_token(self, user: User) -> str:
        return create_access_token(data={"sub": str(user.id)})

    def update(self, user_id: int, data: UserUpdate) -> User:
        """Update a user's profile fields (admin action)."""
        user = self.get_by_id(user_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, data: ChangePassword) -> User:
        """Allow a user to change their own password after verifying the current one."""
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )
        if data.current_password == data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must differ from the current password.",
            )
        user.hashed_password = hash_password(data.new_password)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: int, requesting_user: User) -> None:
        """Delete a user. Admins cannot delete themselves."""
        if user_id == requesting_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account.",
            )
        user = self.get_by_id(user_id)
        self.db.delete(user)
        self.db.commit()
