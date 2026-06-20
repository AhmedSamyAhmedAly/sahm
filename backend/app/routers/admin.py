"""Admin-only user management + platform stats. Guarded by require_admin.

Role is pinned to settings.admin_email — this router never grants admin to anyone
else, and the admin cannot lock themselves out (no self delete/suspend/demote).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password, role_for_email
from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import Asset, DailyBar, Recommendation, User, WatchlistItem
from app.schemas import AdminStats, AdminUserOut, CreateUserRequest, UpdateUserRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _is_the_admin(email: str) -> bool:
    return email.lower() == settings.admin_email.lower()


def _to_out(u: User, watch_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=u.id, email=u.email, role=u.role, is_active=u.is_active,
        is_primary=_is_the_admin(u.email),
        created_at=u.created_at, last_login_at=u.last_login_at,
        watchlist_count=watch_count,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    counts = dict(
        db.execute(
            select(WatchlistItem.user_id, func.count(WatchlistItem.id))
            .group_by(WatchlistItem.user_id)
        ).all()
    )
    users = db.execute(select(User).order_by(User.created_at)).scalars().all()
    return [_to_out(u, counts.get(u.id, 0)) for u in users]


@router.post("/users", response_model=AdminUserOut)
def create_user(req: CreateUserRequest, db: Session = Depends(get_db),
                _: User = Depends(require_admin)):
    email = req.email.lower()
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    # Role is pinned by email — ignore any attempt to create another admin.
    user = User(email=email, hashed_password=hash_password(req.password),
                role=role_for_email(email), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_out(user, 0)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, req: UpdateUserRequest, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    is_self = user.id == admin.id
    is_primary = _is_the_admin(user.email)

    if req.role is not None:
        if req.role not in ("admin", "member"):
            raise HTTPException(status_code=400, detail="Role must be admin or member")
        if req.role != "admin" and is_primary:
            raise HTTPException(status_code=400, detail="Cannot demote the primary admin")
        if req.role != "admin" and is_self:
            raise HTTPException(status_code=400, detail="Cannot demote yourself")
        user.role = req.role

    if req.is_active is not None:
        if not req.is_active and (is_self or is_primary):
            raise HTTPException(status_code=400, detail="Cannot suspend this account")
        user.is_active = req.is_active

    if req.password is not None:
        if len(req.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        user.hashed_password = hash_password(req.password)

    db.commit()
    db.refresh(user)
    count = db.execute(
        select(func.count(WatchlistItem.id)).where(WatchlistItem.user_id == user.id)
    ).scalar() or 0
    return _to_out(user, count)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id or _is_the_admin(user.email):
        raise HTTPException(status_code=400, detail="Cannot delete the admin account")
    db.delete(user)
    db.commit()
    return {"deleted": user_id}


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    week_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    total = db.execute(select(func.count(User.id))).scalar() or 0
    active = db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ).scalar() or 0
    admins = db.execute(
        select(func.count(User.id)).where(User.role == "admin")
    ).scalar() or 0
    logins_7d = db.execute(
        select(func.count(User.id)).where(User.last_login_at >= week_ago)
    ).scalar() or 0
    recs = db.execute(select(func.count(Recommendation.id))).scalar() or 0
    last_scan = db.execute(select(func.max(Recommendation.date))).scalar()
    universe = db.execute(
        select(func.count(Asset.id)).where(Asset.is_listed.is_(True))
    ).scalar() or 0
    active_assets = db.execute(
        select(func.count(Asset.id)).where(Asset.is_active.is_(True))
    ).scalar() or 0
    return AdminStats(
        total_users=total, active_users=active, admins=admins,
        logins_last_7d=logins_7d, recommendations=recs, last_scan_date=last_scan,
        universe_size=universe, active_assets=active_assets,
    )
