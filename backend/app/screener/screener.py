"""
screener.py — Core Stock Screener

Runs all regime-appropriate strategies across every symbol that has
sufficient price data in the database.  Returns a ranked list of
actionable signals for user selection.

Results are kept in an in-process cache so the API can respond
instantly; the hourly scheduler and the manual Refresh button both
invalidate the cache and trigger a fresh scan.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.data.storage import get_price_data
from app.database.models import PriceData
from app.regime.detector import detect_market_regime, detect_regime
from app.strategies.registry import (
    get_strategy,
    get_strategies_for_regime,
    STRATEGY_CLASS_MAP,
)

logger = logging.getLogger(__name__)

# ─── In-memory results cache ──────────────────────────────────────────────────
_cache: dict = {
    "results": None,
    "last_run": None,
    "is_running": False,
}

CACHE_TTL_MINUTES = 55  # treat results as stale just before the next hourly tick


def get_cached_results() -> dict:
    return _cache


def is_cache_fresh() -> bool:
    if _cache["results"] is None or _cache["last_run"] is None:
        return False
    return datetime.now() - _cache["last_run"] < timedelta(minutes=CACHE_TTL_MINUTES)


def run_screener(db: Session, limit: int = 50, force: bool = False) -> dict:
    """
    Run (or return cached) screener results.

    Args:
        db:    SQLAlchemy session.
        limit: Max number of signals to return.
        force: If True, bypass the cache and re-scan.
    """
    global _cache

    if not force and is_cache_fresh():
        logger.info("Screener: returning cached results")
        results = dict(_cache["results"])
        results["results"] = results["results"][:limit]
        return results

    if _cache["is_running"]:
        # Another thread is already scanning – return stale data while we wait
        stale = _cache["results"]
        if stale:
            out = dict(stale)
            out["status"] = "scanning"
            out["results"] = out["results"][:limit]
            return out
        return {"status": "scanning", "results": [], "last_updated": None}

    _cache["is_running"] = True
    try:
        result = _do_scan(db, limit=200)  # always scan full set; trim on return
        _cache["results"] = result
        _cache["last_run"] = datetime.now()
        out = dict(result)
        out["results"] = out["results"][:limit]
        return out
    finally:
        _cache["is_running"] = False


def invalidate_cache():
    """Force next call to run_screener() to do a fresh scan."""
    _cache["last_run"] = None


# ─── Internal scan ────────────────────────────────────────────────────────────

def _do_scan(db: Session, limit: int = 200) -> dict:
    logger.info("Screener: starting full scan …")
    start = datetime.now()

    # Symbols with at least 50 daily bars in the DB
    from sqlalchemy import func
    rows = (
        db.query(PriceData.symbol, func.count(PriceData.id).label("cnt"))
        .filter(PriceData.interval == "1d")
        .group_by(PriceData.symbol)
        .having(func.count(PriceData.id) >= 50)
        .all()
    )
    available = [r.symbol for r in rows]
    logger.info(f"Screener: {len(available)} symbols with ≥50 bars")

    if not available:
        return {
            "status": "no_data",
            "message": (
                "No symbols have sufficient price data. "
                "Click 'Download Universe Data' to fetch it."
            ),
            "results": [],
            "total_screened": 0,
            "total_signals": 0,
            "regime": "unknown",
            "last_updated": datetime.now().isoformat(),
        }

    # Detect regime from liquid anchor ETFs (or first few available)
    regime_anchors = [s for s in ("SPY", "QQQ", "IWM") if s in available] or available[:3]
    market_regime = detect_market_regime(db, regime_anchors)
    regime = market_regime["regime"]
    strategies = get_strategies_for_regime(regime)
    logger.info(f"Screener regime: {regime} → strategies: {strategies}")

    data_end = date.today() - timedelta(days=1)
    all_signals = []
    screened = 0

    for symbol in available:
        try:
            df = get_price_data(db, symbol, end_date=data_end)
            if df.empty or len(df) < 50:
                continue
            df = df.copy()
            df["symbol"] = symbol
            screened += 1
            sym_regime = detect_regime(df, symbol)

            for strat_key in strategies:
                strategy = get_strategy(strat_key)
                if not strategy:
                    continue
                try:
                    signals = strategy.generate_signals(df)
                    if signals:
                        all_signals.append({
                            "signal": signals[-1],
                            "symbol": symbol,
                            "strategy_key": strat_key,
                            "symbol_regime": sym_regime["regime"],
                        })
                except Exception as e:
                    logger.debug(f"Signal error {symbol}/{strat_key}: {e}")
        except Exception as e:
            logger.debug(f"Screener symbol error {symbol}: {e}")

    # Score & rank
    scored = []
    for item in all_signals:
        sig = item["signal"]
        if not sig.is_actionable():
            continue
        score = sig.confidence * 0.5 + min(sig.risk_reward_ratio / 10, 0.3)
        cls_info = STRATEGY_CLASS_MAP.get(item["strategy_key"], {})
        scored.append({
            "rank": 0,
            "symbol": sig.symbol,
            "action": sig.action,
            "strategy": sig.strategy_name,
            "strategy_key": item["strategy_key"],
            "asset_class": cls_info.get("asset_class", "equity"),
            "asset_class_label": cls_info.get("asset_class_label", "Equity"),
            "strategy_type": cls_info.get("strategy_type", ""),
            "strategy_type_label": cls_info.get("strategy_type_label", ""),
            "entry_price": sig.entry_price,
            "stop_price": sig.stop_price,
            "target_price": sig.target_price,
            "risk_reward_ratio": sig.risk_reward_ratio,
            "confidence": sig.confidence,
            "composite_score": round(score, 3),
            "reasoning": sig.reasoning,
            "regime": item["symbol_regime"],
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, s in enumerate(scored):
        s["rank"] = i + 1

    elapsed = round((datetime.now() - start).total_seconds(), 1)
    logger.info(
        f"Screener done: {screened} screened, {len(scored)} signals, {elapsed}s"
    )

    return {
        "status": "ok",
        "results": scored[:limit],
        "total_results": len(scored),
        "total_screened": screened,
        "total_universe": len(available),
        "regime": regime,
        "regime_details": market_regime,
        "strategies_used": strategies,
        "elapsed_seconds": elapsed,
        "last_updated": datetime.now().isoformat(),
    }
