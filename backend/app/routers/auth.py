"""Auth routes: invite-gated registration, login, current user."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, hash_password, role_for_email, verify_password
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.invite_code != settings.invite_code:
        raise HTTPException(status_code=403, detail="Invalid invite code")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    email = req.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Role is pinned by email — only the configured admin email is ever admin.
    user = User(email=email, hashed_password=hash_password(req.password),
                role=role_for_email(email), is_active=True, last_login_at=_utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role, budget=user.budget)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    email = req.email.lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended — contact the admin")

    # The primary admin is always admin; other users keep their stored role.
    if user.email.lower() == settings.admin_email.lower():
        user.role = "admin"
    user.last_login_at = _utcnow()
    db.commit()
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role, budget=user.budget)


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)):
    # Re-issue a fresh token alongside identity (handy for the SPA).
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role, budget=user.budget)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)
