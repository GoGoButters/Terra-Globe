"""Authentication service: JWT, password hashing, OAuth."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, Settings
from app.db.session import get_db
from app.models import User, RefreshToken

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def hash_token(token: str) -> str:
    """Hash a refresh token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> Optional[User]:
    """Authenticate user by email and password."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_or_create_oauth_user(
    provider: str, oauth_id: str, email: str, username: str,
    full_name: str = "", avatar_url: str = "", db: AsyncSession = None,
) -> User:
    """Get existing OAuth user or create a new one."""
    result = await db.execute(
        select(User).where(
            User.oauth_provider == provider,
            User.oauth_id == oauth_id,
        )
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    # Ensure username is unique
    base_username = username
    counter = 1
    while True:
        check = await db.execute(
            select(User).where(User.username == base_username)
        )
        if not check.scalar_one_or_none():
            break
        base_username = f"{username}{counter}"
        counter += 1

    user = User(
        email=email,
        username=base_username,
        oauth_provider=provider,
        oauth_id=oauth_id,
        full_name=full_name,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    return user


async def store_refresh_token(user_id: str, token: str, db: AsyncSession) -> None:
    """Store a hashed refresh token in the database."""
    rt = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(rt)


async def revoke_refresh_token(token: str, db: AsyncSession) -> bool:
    """Revoke a refresh token. Returns True if found and revoked."""
    token_hash = hash_token(token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt and not rt.revoked:
        rt.revoked = True
        return True
    return False


async def validate_refresh_token(token: str, db: AsyncSession) -> Optional[User]:
    """Validate a refresh token and return the associated user."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None

        # Check if token is in DB and not revoked
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(token),
                RefreshToken.revoked == False,
            )
        )
        rt = result.scalar_one_or_none()
        if not rt:
            return None

        # Check expiry
        if rt.expires_at < datetime.now(timezone.utc):
            return None

        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and validate JWT, return current user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=[ALGORITHM]
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optional auth dependency: returns user if token is valid, None otherwise."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
