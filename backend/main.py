import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api import (
    assets,
    dashboard,
    deposits,
    import_export,
    jobs as jobs_api,
    orders,
    portfolio,
    prices,
    stats,
    strategies,
    tags,
)
from backend.api.dependencies import _binance, _price_service
from backend.config import (
    BG_JOBS_ENABLED,
    DAILY_SNAPSHOT_HOUR_UTC,
    FUNDING_SYNC_HOURS,
    PRICE_CACHE_REFRESH_SECONDS,
)
from backend.db.database import SessionLocal, init_db
from backend.jobs.benchmark_sync import run_benchmark_sync_job
from backend.jobs.equity_snapshot import run_equity_snapshot_job
from backend.jobs.funding_rate import run_funding_sync_job
from backend.jobs.price_cache import run_price_cache_job
from backend.util.logging import setup_logging


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic now. Fresh installs run:
    #   alembic upgrade head
    # (dev.sh handles this on first boot). DO NOT call init_db() here —
    # SQLAlchemy's create_all() races with Alembic and silently creates
    # tables that should have come in via a migration.
    scheduler = None
    if BG_JOBS_ENABLED:
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            run_price_cache_job,
            IntervalTrigger(seconds=PRICE_CACHE_REFRESH_SECONDS),
            args=[_price_service],
            id="price_cache",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_equity_snapshot_job,
            CronTrigger(hour=DAILY_SNAPSHOT_HOUR_UTC, minute=0),
            args=[_price_service],
            id="equity_snapshot",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_funding_sync_job,
            IntervalTrigger(hours=FUNDING_SYNC_HOURS),
            args=[_binance],
            id="funding_sync",
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            run_benchmark_sync_job,
            CronTrigger(hour=DAILY_SNAPSHOT_HOUR_UTC, minute=5),  # 5 min after snapshot
            args=[_price_service],
            id="benchmark_sync",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Background scheduler started — 3 jobs registered")
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="CryptoJournal", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(orders.router)
app.include_router(deposits.router)
app.include_router(dashboard.router)
app.include_router(stats.router)
app.include_router(jobs_api.router)
app.include_router(import_export.router)
app.include_router(assets.router)
app.include_router(strategies.router)
app.include_router(tags.router)
app.include_router(prices.router)


@app.get("/api/health")
def health() -> dict:
    """Liveness probe — cheap, always-on. Use /api/health/deep for readiness."""
    return {"status": "ok"}


@app.get("/api/health/deep")
async def health_deep() -> dict:
    """Verifies every subsystem the app depends on. Returns 200 even when
    degraded — the caller inspects each check's status."""
    checks: dict = {}
    overall_ok = True

    # 1. Database connectivity
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = {"status": "ok"}
        finally:
            db.close()
    except Exception as exc:
        checks["database"] = {"status": "error", "detail": str(exc)}
        overall_ok = False

    # 2. Price service (can we reach the primary exchange?)
    try:
        price = await _price_service.get_price("BTC", "USDT")
        checks["price_service"] = {"status": "ok", "btc_usdt": str(price)}
    except Exception as exc:
        checks["price_service"] = {"status": "degraded", "detail": str(exc)}
        # Don't fail overall — price service has its own fallback chain

    # 3. Background scheduler
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        checks["scheduler"] = {"status": "disabled" if not BG_JOBS_ENABLED else "error"}
        if BG_JOBS_ENABLED:
            overall_ok = False
    else:
        if scheduler.running:
            jobs = [
                {"id": j.id, "next_run": str(j.next_run_time)}
                for j in scheduler.get_jobs()
            ]
            checks["scheduler"] = {"status": "ok", "jobs": jobs}
        else:
            checks["scheduler"] = {"status": "error", "detail": "scheduler not running"}
            overall_ok = False

    return {"status": "ok" if overall_ok else "degraded", "checks": checks}
