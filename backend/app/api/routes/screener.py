"""
routes/screener.py — Screener API endpoints.

GET  /screener/results            — Cached screener results (runs scan if stale)
POST /screener/refresh            — Force immediate data refresh + rescan
GET  /screener/universe/status    — Universe coverage stats
POST /screener/universe/download  — Bulk-download price data for full universe
"""

import logging
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.screener.screener import run_screener, get_cached_results, invalidate_cache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/results")
def get_results(
    limit: int = Query(50, ge=1, le=200),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Return screener results (cached if fresh, otherwise run a new scan)."""
    return run_screener(db, limit=limit, force=force)


@router.post("/refresh")
def refresh_screener(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger an immediate data refresh + screener rescan.
    Runs in the background; poll /screener/results to see the updated data.
    """
    invalidate_cache()
    background_tasks.add_task(_refresh_task)
    return {
        "status": "started",
        "message": "Refresh started. Check /screener/results in ~30 seconds.",
    }


@router.get("/universe/status")
def universe_status(db: Session = Depends(get_db)):
    """Show how many symbols are ready to screen."""
    from app.data.universe import get_universe_stats
    from app.database.models import PriceData
    from sqlalchemy import func

    stats = get_universe_stats()
    rows = (
        db.query(PriceData.symbol, func.count(PriceData.id).label("cnt"))
        .filter(PriceData.interval == "1d")
        .group_by(PriceData.symbol)
        .all()
    )
    ready = sum(1 for r in rows if r.cnt >= 50)
    insufficient = sum(1 for r in rows if r.cnt < 50)

    return {
        "universe": stats,
        "symbols_ready_to_screen": ready,
        "symbols_with_insufficient_data": insufficient,
        "total_symbols_in_db": len(rows),
    }


@router.post("/universe/download")
def download_universe(background_tasks: BackgroundTasks):
    """
    Kick off a bulk download of price data for the full universe.
    Runs in the background (may take several minutes for ~500 symbols).
    """
    background_tasks.add_task(_bulk_download_task)
    return {
        "status": "started",
        "message": "Bulk download started. Check /screener/universe/status for progress.",
    }


# ─── Background tasks ─────────────────────────────────────────────────────────

def _refresh_task():
    """Fetch latest prices for all DB symbols then rescan."""
    from app.database.database import SessionLocal
    from app.data.storage import refresh_all_data
    from app.database.models import PriceData
    from sqlalchemy import func

    db = SessionLocal()
    try:
        rows = (
            db.query(PriceData.symbol)
            .filter(PriceData.interval == "1d")
            .distinct()
            .all()
        )
        symbols = [r.symbol for r in rows]
        logger.info(f"Refresh task: updating {len(symbols)} symbols …")
        if symbols:
            refresh_all_data(db, symbols)

        # Now rescan
        run_screener(db, limit=200, force=True)
        logger.info("Refresh task complete")
    except Exception as e:
        logger.error(f"Refresh task failed: {e}")
    finally:
        db.close()


def _bulk_download_task():
    """Download historical data for every symbol in the universe."""
    from app.database.database import SessionLocal
    from app.data.universe import get_universe
    from app.data.storage import refresh_all_data

    db = SessionLocal()
    try:
        universe = get_universe(force_refresh=True)
        logger.info(f"Bulk download: {len(universe)} symbols")
        batch_size = 50
        for i in range(0, len(universe), batch_size):
            batch = universe[i: i + batch_size]
            try:
                refresh_all_data(db, batch)
                logger.info(f"  Batch {i // batch_size + 1} done ({batch[0]} … {batch[-1]})")
            except Exception as e:
                logger.error(f"  Batch {i // batch_size + 1} failed: {e}")
        logger.info("Bulk download complete")
    except Exception as e:
        logger.error(f"Bulk download task failed: {e}")
    finally:
        db.close()
