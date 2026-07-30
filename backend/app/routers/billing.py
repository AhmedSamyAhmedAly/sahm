"""Billing: plan catalogue, activation after PayPal checkout, and the webhook."""
from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import lemonsqueezy as lemon
from app import paypal, plans
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import SubscriptionEvent, User
from app.schemas import (
    ActivateSubscriptionRequest, CheckoutRequest, SubscriptionOut,
)

log = logging.getLogger("saeed.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])


def _record(db: Session, user: User, action: str, *, plan=None, period=None,
            amount=None, source=None, reference=None, note=None) -> None:
    db.add(SubscriptionEvent(
        user_id=user.id, action=action, plan=plan, period=period, amount=amount,
        currency="USD" if amount else None, source=source, reference=reference,
        until=user.plan_until, note=note,
    ))


def subscription_out(user: User) -> SubscriptionOut:
    return SubscriptionOut(
        plan=user.plan,
        plan_until=user.plan_until,
        plan_source=user.plan_source,
        active=plans.subscription_active(user),
        markets=plans.allowed_markets(user),
        role=user.role,
        needs_payment=(user.role not in plans.FREE_ROLES and not plans.subscription_active(user)),
    )


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """Public pricing + the PayPal plan ids the checkout button needs."""
    return {
        "plans": plans.public_plans(),
        "paypal_client_id": settings.paypal_client_id,   # public by design
        "provider": settings.billing_provider,
        "paypal_configured": settings.paypal_configured,
        "lemon_configured": settings.lemon_configured,
        # True when the active provider can actually take money right now.
        "payments_ready": (
            settings.lemon_configured if settings.billing_provider == "lemonsqueezy"
            else settings.paypal_configured
        ),
        "currency": "USD",
        # Lets the register form drop the invite field when signup is public.
        "open_registration": settings.open_registration,
        # Live proof of what each plan actually gets you today.
        "market_stats": _market_stats(db),
    }


def _market_stats(db: Session) -> dict:
    """Today's signal counts per market — so the pricing page shows what a plan
    actually delivers instead of a vague promise."""
    from app.models import Asset, Recommendation
    out: dict = {}
    for code in ("EGX", "US"):
        ex_tickers = select(Asset.ticker).where(Asset.exchange == code)
        latest = db.execute(
            select(func.max(Recommendation.date))
            .where(Recommendation.ticker.in_(ex_tickers))
        ).scalar()
        buys = 0
        if latest:
            buys = db.execute(
                select(func.count(Recommendation.id)).where(
                    Recommendation.ticker.in_(ex_tickers),
                    Recommendation.date == latest,
                    Recommendation.signal.in_(
                        ("buy", "strong_buy", "super_strong_buy")),
                )
            ).scalar() or 0
        out[code] = {
            "scan_date": str(latest) if latest else None,
            "buy_signals": buys,
            "tracked": db.execute(
                select(func.count(Asset.id))
                .where(Asset.exchange == code, Asset.is_active.is_(True))
            ).scalar() or 0,
        }
    return out


@router.get("/ads")
def ads_config():
    """Ad-network wiring, served at runtime so switching networks is a config
    change (Railway variable) rather than a redeploy."""
    return {
        "enabled": settings.ads_enabled and bool(settings.ads_slot_html),
        "head_snippet": settings.ads_head_snippet,
        "slot_html": settings.ads_slot_html,
        # Paying subscribers shouldn't see ads — they already paid.
        "hide_for_subscribers": True,
    }


@router.get("/me", response_model=SubscriptionOut)
def my_subscription(user: User = Depends(get_current_user)):
    return subscription_out(user)


@router.post("/activate", response_model=SubscriptionOut)
def activate(req: ActivateSubscriptionRequest,
             db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    """Called by the SPA after PayPal approval.

    The subscription id is VERIFIED against PayPal — we never trust the plan or
    price the browser claims. The plan is derived from PayPal's own plan id.
    """
    try:
        sub = paypal.get_subscription(req.subscription_id.strip())
    except paypal.PayPalError as e:
        log.warning("paypal lookup failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not verify the subscription with PayPal")

    status = (sub.get("status") or "").upper()
    if status not in ("ACTIVE", "APPROVED"):
        raise HTTPException(status_code=400, detail=f"Subscription is {status.title() or 'not active'}")

    mapped = paypal.plan_period_for(sub.get("plan_id", ""))
    if not mapped:
        raise HTTPException(status_code=400, detail="Unknown PayPal plan — contact support")
    plan, period = mapped

    # Guard against one PayPal subscription being claimed by two accounts.
    taken = db.execute(
        select(User).where(User.paypal_subscription_id == sub.get("id"), User.id != user.id)
    ).scalar_one_or_none()
    if taken:
        raise HTTPException(status_code=409, detail="That subscription is already linked to another account")

    user.plan = plan
    user.plan_until = plans.extend(user.plan_until, period)
    user.plan_source = "paypal"
    user.paypal_subscription_id = sub.get("id")
    _record(db, user, "activate", plan=plan, period=period,
            amount=plans.price_of(plan, period), source="paypal", reference=sub.get("id"))
    db.commit()
    db.refresh(user)
    return subscription_out(user)


@router.post("/checkout")
def checkout(req: CheckoutRequest, user: User = Depends(get_current_user)):
    """Hand back a Lemon Squeezy hosted-checkout URL for the chosen plan.

    The user id is embedded as custom data so the webhook can tie the payment to
    this account even if they pay with a different email address.
    """
    if settings.billing_provider != "lemonsqueezy":
        raise HTTPException(status_code=400, detail="Lemon Squeezy is not the active provider")
    plan = (req.plan or "").strip().lower()
    period = (req.period or "monthly").strip().lower()
    if plan not in plans.PLANS or period not in plans.PERIODS:
        raise HTTPException(status_code=400, detail="Unknown plan or period")
    variant = plans.lemon_variant_id(plan, period)
    if not variant:
        raise HTTPException(status_code=503,
                            detail="That plan isn't purchasable yet — contact the admin")
    try:
        url = lemon.checkout_url(variant, email=user.email, user_id=user.id,
                                 redirect_to=req.redirect_to or None)
    except lemon.LemonError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"url": url, "plan": plan, "period": period}


@router.post("/webhook/lemonsqueezy")
async def lemon_webhook(request: Request, db: Session = Depends(get_db)):
    """Lemon Squeezy subscription events.

    Every event is HMAC-verified against the signing secret; unverified requests are
    rejected outright, because this endpoint is public and grants paid access.
    """
    body = await request.body()
    if not lemon.verify_webhook(request.headers.get("x-signature"), body):
        log.warning("rejected unverified Lemon Squeezy webhook")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = await request.json()
    meta = event.get("meta") or {}
    etype = (meta.get("event_name") or "").lower()
    data = (event.get("data") or {})
    attrs = data.get("attributes") or {}
    sub_id = str(data.get("id") or "")

    # Prefer the id we planted at checkout; fall back to matching the email.
    custom = (meta.get("custom_data") or {})
    user = None
    if custom.get("user_id"):
        try:
            user = db.get(User, int(custom["user_id"]))
        except (TypeError, ValueError):
            user = None
    if user is None and attrs.get("user_email"):
        user = db.execute(
            select(User).where(User.email == str(attrs["user_email"]).lower())
        ).scalar_one_or_none()
    if user is None:
        log.warning("lemon webhook %s: no matching user", etype)
        return {"ok": True, "ignored": "unknown user"}

    mapped = lemon.plan_period_for(attrs.get("variant_id") or "")
    plan, period = mapped if mapped else (user.plan, "monthly")

    if etype in ("subscription_created", "subscription_resumed", "subscription_unpaused",
                 "subscription_payment_success", "subscription_updated"):
        status = (attrs.get("status") or "").lower()
        if status in ("cancelled", "expired", "unpaid"):
            user.plan_source = "cancelled"
            _record(db, user, "cancel", plan=user.plan, source="lemonsqueezy",
                    reference=sub_id, note=f"{etype}/{status}")
        else:
            # Trust Lemon Squeezy's own renewal date when it gives one.
            renews = attrs.get("renews_at")
            until = _parse_dt(renews) if renews else None
            user.plan = plan or user.plan
            user.plan_until = until or plans.extend(user.plan_until, period)
            user.plan_source = "lemonsqueezy"
            user.paypal_subscription_id = sub_id   # provider-agnostic subscription ref
            _record(db, user, "renew" if etype == "subscription_payment_success" else "activate",
                    plan=user.plan, period=period, amount=plans.price_of(user.plan or "", period),
                    source="lemonsqueezy", reference=sub_id, note=etype)
    elif etype in ("subscription_cancelled", "subscription_expired", "subscription_paused"):
        # Keep access to the end of the paid term; just stop renewing.
        user.plan_source = "cancelled"
        if etype == "subscription_expired":
            user.plan_until = _utcnow()
        _record(db, user, "cancel", plan=user.plan, source="lemonsqueezy",
                reference=sub_id, note=etype)
    elif etype == "subscription_payment_failed":
        _record(db, user, "payment_failed", plan=user.plan, source="lemonsqueezy",
                reference=sub_id, note=etype)
    else:
        return {"ok": True, "ignored": etype}

    db.commit()
    return {"ok": True, "handled": etype}


def _parse_dt(value: str):
    """Lemon Squeezy sends ISO-8601 UTC (often with a trailing Z)."""
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Stop future billing. Access remains until the paid term ends."""
    if settings.billing_provider == "lemonsqueezy":
        if user.paypal_subscription_id:
            try:
                lemon.cancel_subscription(user.paypal_subscription_id)
            except lemon.LemonError as e:
                log.warning("lemon cancel failed: %s", e)
                raise HTTPException(status_code=502, detail="Could not cancel — try again")
        user.plan_source = "cancelled"
        _record(db, user, "cancel", plan=user.plan, source="lemonsqueezy",
                reference=user.paypal_subscription_id, note="access retained until plan_until")
        db.commit()
        db.refresh(user)
        return subscription_out(user)

    if user.paypal_subscription_id:
        try:
            paypal.cancel_subscription(user.paypal_subscription_id)
        except paypal.PayPalError as e:
            log.warning("paypal cancel failed: %s", e)
            raise HTTPException(status_code=502, detail="Could not cancel with PayPal — try again")
    user.plan_source = "cancelled"
    _record(db, user, "cancel", plan=user.plan, source="paypal",
            reference=user.paypal_subscription_id,
            note="access retained until plan_until")
    db.commit()
    db.refresh(user)
    return subscription_out(user)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """PayPal renewals / cancellations / failures.

    Unverified events are ignored — anyone can POST here, so the signature check is
    the only thing standing between a stranger and a free subscription.
    """
    body = await request.body()
    if not paypal.verify_webhook(request.headers, body):
        log.warning("rejected unverified PayPal webhook")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = await request.json()
    etype = (event.get("event_type") or "").upper()
    res = event.get("resource") or {}
    sub_id = res.get("id") or (res.get("billing_agreement_id") if "billing_agreement_id" in res else None)
    if not sub_id:
        return {"ok": True, "ignored": "no subscription id"}

    user = db.execute(
        select(User).where(User.paypal_subscription_id == sub_id)
    ).scalar_one_or_none()
    if not user:
        return {"ok": True, "ignored": "unknown subscription"}

    if etype in ("PAYMENT.SALE.COMPLETED", "BILLING.SUBSCRIPTION.ACTIVATED",
                 "BILLING.SUBSCRIPTION.RE-ACTIVATED"):
        mapped = paypal.plan_period_for(res.get("plan_id", "")) or (user.plan, "monthly")
        plan, period = mapped
        user.plan = plan or user.plan
        user.plan_until = plans.extend(user.plan_until, period)
        user.plan_source = "paypal"
        _record(db, user, "renew", plan=user.plan, period=period, source="paypal",
                reference=sub_id, note=etype)
    elif etype in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED",
                   "BILLING.SUBSCRIPTION.SUSPENDED"):
        # Keep access until the paid term ends; just stop auto-renewal.
        user.plan_source = "cancelled"
        _record(db, user, "cancel", plan=user.plan, source="paypal",
                reference=sub_id, note=etype)
    elif etype == "PAYMENT.SALE.DENIED":
        _record(db, user, "payment_failed", plan=user.plan, source="paypal",
                reference=sub_id, note=etype)
    else:
        return {"ok": True, "ignored": etype}

    db.commit()
    return {"ok": True, "handled": etype}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)
