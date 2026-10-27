from typing import Generator, Optional
from fastapi import Cookie, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.revoked_token import RevokedToken
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)


def get_db() -> Generator:
    """Dependency that yields a database session and ensures closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def extract_token_from_header_or_cookie(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> Optional[str]:
    """Extracts JWT token from Authorization header or cookie."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    if access_token:
        return access_token
    return None


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(extract_token_from_header_or_cookie),
) -> User:
    """Validates JWT, verifies token is not revoked, and returns current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # Check if token or JTI is blacklisted / revoked
    jti = payload.get("jti")
    if jti:
        is_revoked = db.query(RevokedToken).filter(
            (RevokedToken.token == token) | (RevokedToken.jti == jti)
        ).first()
    else:
        is_revoked = db.query(RevokedToken).filter(RevokedToken.token == token).first()

    if is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if subject is None:
        raise credentials_exception

    # Subject can be user ID or email
    user = None
    if subject.isdigit():
        user = db.query(User).filter(User.id == int(subject)).first()
    if not user:
        user = db.query(User).filter(User.email == subject).first()
    if not user:
        user = db.query(User).filter(User.username == subject).first()

    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensures authenticated user is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def get_optional_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(extract_token_from_header_or_cookie),
) -> Optional[User]:
    """Returns current user if token provided and not revoked, otherwise None without failing."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None

    # Check blacklist
    jti = payload.get("jti")
    if jti:
        is_revoked = db.query(RevokedToken).filter(
            (RevokedToken.token == token) | (RevokedToken.jti == jti)
        ).first()
    else:
        is_revoked = db.query(RevokedToken).filter(RevokedToken.token == token).first()
    if is_revoked:
        return None

    subject = payload.get("sub")
    if subject.isdigit():
        user = db.query(User).filter(User.id == int(subject)).first()
        if user:
            return user
    return db.query(User).filter(
        (User.email == subject) | (User.username == subject)
    ).first()
