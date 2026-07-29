"""FastAPI dependencies: current user from the Bearer token."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.config import settings
from app.database import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise cred_exc
    user = db.get(User, user_id)
    if user is None:
        raise cred_exc
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended")
    # Guarantee the primary admin is always admin; never auto-demote others
    # (other admins are managed explicitly in the admin panel).
    if user.email.lower() == settings.admin_email.lower() and user.role != "admin":
        user.role = "admin"
        db.commit()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# HTTP 402 = "Payment Required": the SPA uses this exact status to show the
# subscribe page instead of a generic error.
PAYWALL = 402


def require_market_access(user: User, market: str | None) -> None:
    """Guard market data behind the subscription. Admin/staff always pass."""
    from app.plans import allowed_markets, can_access  # local: avoids an import cycle

    if can_access(user, market):
        return
    allowed = allowed_markets(user)
    detail = (
        f"Your plan doesn't include {market}." if (market and allowed)
        else "A subscription is required to view market data."
    )
    raise HTTPException(status_code=PAYWALL, detail=detail)
