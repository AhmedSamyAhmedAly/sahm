"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import Asset, DailyBar, PipelineRun, Recommendation, User
from app.routers import auth, picks, stocks, track_record


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sahm — EGX Signals API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Auth is via Bearer token in the Authorization header (no cookies), so we
    # don't need credentialed CORS — this lets "*" be used safely if desired.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sahm"}


@app.get("/api/status")
def status(db: Session = Depends(get_db)):
    """Public status: data freshness + whether a token is configured. No secrets."""
    data_date = db.execute(select(func.max(DailyBar.date))).scalar()
    last_scan = db.execute(select(func.max(Recommendation.date))).scalar()
    users = db.execute(select(func.count(User.id))).scalar() or 0
    active = db.execute(
        select(func.count(Asset.id)).where(Asset.is_active.is_(True))
    ).scalar() or 0
    last_run = db.execute(
        select(PipelineRun).order_by(PipelineRun.id.desc()).limit(1)
    ).scalar_one_or_none()
    return {
        "data_date": str(data_date) if data_date else None,
        "last_scan_date": str(last_scan) if last_scan else None,
        "active_assets": active,
        "users": users,
        "eodhd_token_configured": bool(settings.eodhd_api_token),
        "universe_size": (last_run.universe_size if last_run else None),
    }


app.include_router(auth.router)
app.include_router(picks.router)
app.include_router(stocks.router)
app.include_router(track_record.router)
