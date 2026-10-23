from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import extract_token_from_header_or_cookie, get_current_active_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Registers a new user account with validated email and unique username."""
    # Check email duplicate
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # Check username duplicate
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists."
        )

    user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Authenticates credentials and issues a signed JWT access token."""
    identifier = login_data.username_or_email.strip()
    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive."
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires
    )

    # Set secure HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(extract_token_from_header_or_cookie),
    current_user: User = Depends(get_current_active_user)
):
    """
    Logs out user:
    1. Requires and validates authentication token.
    2. Revokes the token and JTI, storing it on the blacklist table.
    3. Clears HTTP-only access cookie.
    4. Returns confirmation of session termination.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak tokena do unieważnienia",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    jti = payload.get("jti") if payload else None
    exp_timestamp = payload.get("exp") if payload else None
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else None

    # Idempotent write to blacklist
    existing = db.query(RevokedToken).filter(RevokedToken.token == token).first()
    if not existing:
        revoked = RevokedToken(
            token=token,
            jti=jti,
            expires_at=expires_at
        )
        db.add(revoked)
        db.commit()

    response.delete_cookie(key="access_token")
    return {
        "status": "success",
        "message": "Pomyślnie wylogowano. Token został unieważniony.",
        "revoked": True
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves current authenticated user's profile."""
    return current_user
