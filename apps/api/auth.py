"""Authentication and authorization — Argon2 password hashing + JWT + RBAC."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.database import get_db
from packages.domain.entities.models import User
from packages.domain.enums.common import UserRole

ph = PasswordHasher()
security = HTTPBearer()
settings = get_settings()


# ── Password hashing ────────────────────────────────────────

def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# ── JWT tokens ──────────────────────────────────────────────

def create_access_token(
    user_id: uuid.UUID,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── Dependencies ────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from JWT."""
    payload = decode_token(credentials.credentials)
    user_id = uuid.UUID(payload["sub"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


class RequireRole:
    """RBAC dependency — restrict access to specific roles."""

    def __init__(self, *allowed_roles: UserRole):
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {current_user.role.value} not authorized. Required: {[r.value for r in self.allowed_roles]}",
            )
        return current_user


# Convenience role checkers
require_admin = RequireRole(UserRole.ADMIN)
require_analyst = RequireRole(UserRole.ADMIN, UserRole.ANALYST)
require_viewer = RequireRole(UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER)
