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
from app.models import Asset, DailyBar, Recommendation, SubscriptionEvent, User
from app import plans
from app.schemas import (
    AdminStats, AdminUserOut, CreateUserRequest, GrantSubscriptionRequest,
    UpdateUserRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _is_the_admin(email: str) -> bool:
    return email.lower() == settings.admin_email.lower()


def _to_out(u: User) -> AdminUserOut:
    return AdminUserOut(
        id=u.id, email=u.email, role=u.role, is_active=u.is_active,
        is_primary=_is_the_admin(u.email),
        created_at=u.created_at, last_login_at=u.last_login_at,
        plan=u.plan, plan_until=u.plan_until, plan_source=u.plan_source,
        subscription_active=plans.subscription_active(u),
        markets=plans.allowed_markets(u),
    )


@router.post("/users/{user_id}/subscription", response_model=AdminUserOut)
def set_subscription(
    user_id: int,
    req: GrantSubscriptionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Grant, extend or revoke a plan by hand — comps, refunds, friends, testing.

    `plan=None` revokes. Otherwise pass either `until` (exact expiry) or `days`
    (extends from the later of now / current expiry, so nobody loses paid time).
    """
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")

    if req.plan is None:
        u.plan, u.plan_until, u.plan_source = None, None, None
        action = "revoke"
    else:
        plan = req.plan.strip().lower()
        if plan not in plans.PLANS:
            raise HTTPException(status_code=400,
                                detail=f"Unknown plan — use one of: {', '.join(plans.PLANS)}")
        if req.until is not None:
            until = req.until
        else:
            days = req.days if (req.days and req.days > 0) else 30
            base = plans._aware(u.plan_until)
            now = dt.datetime.now(dt.timezone.utc)
            until = (base if base and base > now else now) + dt.timedelta(days=days)
        u.plan, u.plan_until, u.plan_source = plan, until, "manual"
        action = "grant"

    db.add(SubscriptionEvent(
        user_id=u.id, action=action, plan=u.plan, source="manual",
        reference=admin.email, until=u.plan_until,
        note=(req.note or "")[:255] or None,
    ))
    db.commit()
    db.refresh(u)
    return _to_out(u)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = db.execute(select(User).order_by(User.created_at)).scalars().all()
    return [_to_out(u) for u in users]


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
    return _to_out(user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, req: UpdateUserRequest, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    is_self = user.id == admin.id
    is_primary = _is_the_admin(user.email)

    if req.role is not None:
        # staff = full market access without paying, but no admin panel.
        if req.role not in ("admin", "staff", "member"):
            raise HTTPException(status_code=400, detail="Role must be admin, staff or member")
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
    return _to_out(user)


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


@router.get("/payments")
def payments(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Revenue + subscription activity.

    Two different numbers, deliberately labelled apart:
      * `collected` — money we have a RECORD of (event amounts). Authoritative-ish,
        but only counts events we captured, so treat the provider dashboard as truth.
      * `mrr_estimate` — active plans priced at their monthly rate. An estimate:
        annual subscribers really pay 1/12 of their annual price per month, which is
        why it's called an estimate and not revenue.
    """
    now = dt.datetime.now(dt.timezone.utc)
    users = db.execute(select(User)).scalars().all()

    # Count anyone with a live PAID plan, including admins/staff — they may well have
    # bought one (the first real purchase here was an admin's, and skipping roles made
    # the page read "0 active subscribers" next to a $10 payment).
    active, by_plan, expiring = [], {}, []
    for u in users:
        if u.plan_source == "manual":
            continue          # comped by an admin: real access, but not revenue
        if plans.subscription_active(u):
            active.append(u)
            by_plan[u.plan] = by_plan.get(u.plan, 0) + 1
            until = plans._aware(u.plan_until)
            if until and (until - now).days <= 7:
                expiring.append({
                    "email": u.email, "plan": u.plan,
                    "plan_until": u.plan_until,
                    "days_left": max(0, (until - now).days),
                    "source": u.plan_source,
                })

    # Period per user, from their latest paid event — lets MRR treat annual properly.
    latest_period: dict[int, str] = {}
    for ev in db.execute(
        select(SubscriptionEvent)
        .where(SubscriptionEvent.action.in_(("activate", "renew")))
        .order_by(SubscriptionEvent.created_at)
    ).scalars().all():
        if ev.period:
            latest_period[ev.user_id] = ev.period

    mrr = 0.0
    for u in active:
        period = latest_period.get(u.id, "monthly")
        if period == "annual":
            annual = plans.price_of(u.plan or "", "annual") or 0.0
            mrr += annual / 12.0
        else:
            mrr += plans.price_of(u.plan or "", "monthly") or 0.0

    events = db.execute(
        select(SubscriptionEvent).order_by(SubscriptionEvent.created_at.desc()).limit(100)
    ).scalars().all()
    emails = {u.id: u.email for u in users}
    collected = sum((e.amount or 0.0) for e in events if e.action in ("activate", "renew"))
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    collected_month = sum(
        (e.amount or 0.0) for e in events
        if e.action in ("activate", "renew")
        and plans._aware(e.created_at) and plans._aware(e.created_at) >= month_start
    )

    return {
        "currency": "USD",
        "provider": settings.billing_provider,
        "active_subscribers": len(active),
        "comped": sum(1 for u in users if u.plan_source == "manual"
                      and plans.subscription_active(u)),
        "by_plan": by_plan,
        "mrr_estimate": round(mrr, 2),
        "collected": round(collected, 2),
        "collected_this_month": round(collected_month, 2),
        "paying_users": len(active),
        "free_role_users": sum(1 for u in users if u.role in plans.FREE_ROLES),
        "unpaid_users": sum(
            1 for u in users
            if u.role not in plans.FREE_ROLES and not plans.subscription_active(u)
        ),
        "expiring_soon": sorted(expiring, key=lambda x: x["days_left"]),
        "events": [
            {
                "created_at": e.created_at, "email": emails.get(e.user_id, "?"),
                "action": e.action, "plan": e.plan, "period": e.period,
                "amount": e.amount, "source": e.source, "reference": e.reference,
                "until": e.until, "note": e.note,
            }
            for e in events
        ],
    }
