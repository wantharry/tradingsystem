"""
main.py — FastAPI Application Entry Point

This file wires together all modules:
  - Database initialization on startup
  - All API routes
  - Background scheduler for automated daily data refresh
  - CORS for frontend communication
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database.database import init_db, SessionLocal
from app.api.router import api_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  BACKGROUND SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler()


def run_hourly_refresh():
    """
    Hourly job: fetch latest prices for all symbols in DB, then rescan.
    Also exposed to the /screener/refresh endpoint for manual triggers.
    Skips if outside market hours (9 AM – 5 PM ET, Mon–Fri).
    """
    import pytz
    from datetime import datetime as _dt
    et = pytz.timezone("America/New_York")
    now_et = _dt.now(et)
    if now_et.weekday() >= 5:                    # Saturday / Sunday
        logger.info("Hourly refresh skipped — weekend")
        return
    if not (9 <= now_et.hour < 17):              # Outside 9 AM – 5 PM ET
        logger.info(f"Hourly refresh skipped — outside market hours ({now_et.hour}:00 ET)")
        return

    logger.info("Hourly refresh: starting …")
    db = SessionLocal()
    try:
        from app.data.storage import refresh_all_data
        from app.database.models import PriceData
        from sqlalchemy import func as sqlfunc

        # Update every symbol already in the DB
        rows = (
            db.query(PriceData.symbol)
            .filter(PriceData.interval == "1d")
            .distinct().all()
        )
        symbols = [r.symbol for r in rows]
        if not symbols:
            symbols = settings.symbols_list

        refresh_all_data(db, symbols)
        logger.info(f"Hourly refresh: updated {len(symbols)} symbols")

        # Rescan screener
        from app.screener.screener import run_screener, invalidate_cache
        invalidate_cache()
        result = run_screener(db, limit=200, force=True)
        logger.info(f"Hourly screener: {result.get('total_results', 0)} signals from {result.get('total_screened', 0)} symbols")

        # Also regenerate daily actions
        from app.daily.action_generator import generate_daily_actions
        actions = generate_daily_actions(db)
        logger.info(f"Daily actions regenerated: {len(actions.get('top_actions', []))} signals")
    except Exception as e:
        logger.error(f"Hourly refresh failed: {e}", exc_info=True)
    finally:
        db.close()


# Keep old name as alias so any existing references don't break
scheduled_data_refresh = run_hourly_refresh


# ─────────────────────────────────────────────────────────────────────────────
#  APP LIFECYCLE
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # 1. Initialize database tables
    init_db()

    # 2. Seed default symbols on first run
    _seed_default_symbols()

    # 3. Start background scheduler
    scheduler.add_job(
        run_hourly_refresh,
        "interval",
        hours=1,
        id="hourly_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — hourly refresh enabled")

    yield   # App is running

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def _seed_default_symbols():
    """Add default symbols to the watchlist on first startup."""
    db = SessionLocal()
    try:
        from app.database.models import Symbol
        existing_count = db.query(Symbol).count()
        if existing_count == 0:
            from app.data.storage import upsert_symbol
            for sym in settings.symbols_list[:5]:  # Only first 5 on startup to be fast
                upsert_symbol(db, sym)
            logger.info("Seeded default symbols")
    except Exception as e:
        logger.warning(f"Could not seed symbols: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
#  CREATE APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Automated trading analysis system with regime detection, backtesting, and daily action sheets.",
    lifespan=lifespan,
)

# CORS — allow the React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api": "/api/v1",
    }
