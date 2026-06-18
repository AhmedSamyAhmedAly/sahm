"""Auth routes: invite-gated registration, login, current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_token, hash_password, verify_password
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

    # First registered user becomes admin.
    is_first = (db.execute(select(func.count(User.id))).scalar() or 0) == 0
    user = User(email=email, hashed_password=hash_password(req.password),
                role="admin" if is_first else "member")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    email = req.email.lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role)


@router.get("/me", response_model=TokenResponse)
def me(user: User = Depends(get_current_user)):
    # Re-issue a fresh token alongside identity (handy for the SPA).
    token = create_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, email=user.email, role=user.role)
