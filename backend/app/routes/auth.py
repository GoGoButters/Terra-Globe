"""Authentication routes: register, login, refresh, logout, Google OAuth."""

from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse, RefreshRequest,
)
from app.services.auth_service import (
    authenticate_user, create_access_token, create_refresh_token,
    get_password_hash, get_or_create_oauth_user, store_refresh_token,
    revoke_refresh_token, validate_refresh_token, get_current_user,
)

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user with email/password."""
    # Check if email or username already exists
    existing = await db.execute(
        select(User).where(
            (User.email == req.email) | (User.username == req.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        )

    user = User(
        email=req.email,
        username=req.username,
        hashed_password=get_password_hash(req.password),
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    await store_refresh_token(user.id, refresh, db)

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email/password."""
    user = await authenticate_user(req.email, req.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    await store_refresh_token(user.id, refresh, db)

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using a valid refresh token."""
    user = await validate_refresh_token(req.refresh_token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Revoke old refresh token
    await revoke_refresh_token(req.refresh_token, db)

    # Issue new tokens
    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    await store_refresh_token(user.id, refresh, db)

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout")
async def logout(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Revoke a refresh token (logout)."""
    revoked = await revoke_refresh_token(req.refresh_token, db)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token not found or already revoked",
        )
    return {"message": "Logged out successfully"}


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth2 flow."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth is not configured",
        )

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(code: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth2 callback."""
    import httpx

    # Exchange authorization code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
        token_data = token_resp.json()

        if "error" in token_data:
            raise HTTPException(
                status_code=400,
                detail=f"Google OAuth error: {token_data.get('error_description', token_data['error'])}",
            )

        id_token_str = token_data.get("id_token")
        if not id_token_str:
            raise HTTPException(status_code=400, detail="No ID token from Google")

        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.google_client_id,
        )

    # Extract user info
    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    username = idinfo.get("email", "").split("@")[0]
    full_name = idinfo.get("name", "")
    avatar_url = idinfo.get("picture", "")

    # Get or create user
    user = await get_or_create_oauth_user(
        provider="google",
        oauth_id=google_id,
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        db=db,
    )

    # Generate tokens
    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    await store_refresh_token(user.id, refresh, db)

    # Redirect to frontend with tokens
    redirect_url = (
        f"{settings.frontend_url}/auth/callback"
        f"?access_token={access}"
        f"&refresh_token={refresh}"
    )
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
    )
