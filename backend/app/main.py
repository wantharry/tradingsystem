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


def scheduled_data_refresh():
    """Runs after market close to fetch latest data and generate tomorrow's actions."""
    logger.info("Scheduled: Starting end-of-day data refresh...")
    db = SessionLocal()
    try:
        from app.data.storage import refresh_all_data
        from app.daily.action_generator import generate_daily_actions

        symbols = settings.symbols_list
        results = refresh_all_data(db, symbols)
        logger.info(f"Data refresh complete: {results}")

        actions = generate_daily_actions(db)
        logger.info(f"Daily actions generated: {len(actions.get('top_actions', []))} signals")
    except Exception as e:
        logger.error(f"Scheduled refresh failed: {e}")
    finally:
        db.close()


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
        scheduled_data_refresh,
        "cron",
        hour=settings.DATA_REFRESH_HOUR,
        minute=0,
        id="daily_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — daily refresh at {settings.DATA_REFRESH_HOUR}:00")

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
