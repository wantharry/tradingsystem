"""strategies.py — API routes for strategy management and signal generation."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.strategies.registry import (
    get_all_strategy_metadata, get_strategy, STRATEGY_FAMILIES,
    STRATEGY_TAXONOMY, REGIME_TO_STRATEGIES
)
from app.data.storage import get_price_data
from app.utils import sanitize_for_json

router = APIRouter()


@router.get("/")
def list_strategies():
    """List all registered strategies with metadata and 3-level taxonomy."""
    return {
        "strategies": get_all_strategy_metadata(),
        "taxonomy": STRATEGY_TAXONOMY,
        "families": STRATEGY_FAMILIES,
        "regime_mapping": REGIME_TO_STRATEGIES,
    }


@router.get("/{strategy_key}/documentation")
def get_strategy_docs(strategy_key: str):
    """Get full plain-English documentation for a strategy."""
    strategy = get_strategy(strategy_key)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_key}' not found")
    return strategy.get_documentation()


@router.get("/{strategy_key}/signals/{symbol}")
def get_signals(
    strategy_key: str,
    symbol: str,
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """
    Generate signals for a symbol using a specific strategy.
    Returns the most recent 'limit' signals.
    """
    strategy = get_strategy(strategy_key)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_key}' not found")

    df = get_price_data(db, symbol.upper())
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    df = df.copy()
    df["symbol"] = symbol.upper()

    signals = strategy.generate_signals(df)
    recent = signals[-limit:] if len(signals) > limit else signals

    return sanitize_for_json({
        "symbol": symbol.upper(),
        "strategy": strategy.name,
        "family": strategy.family,
        "total_signals": len(signals),
        "signals": [s.to_dict() for s in reversed(recent)],
    })


@router.post("/{strategy_key}/signals/batch")
def get_batch_signals(
    strategy_key: str,
    symbols: list[str],
    db: Session = Depends(get_db),
):
    """Generate the latest signal for multiple symbols using one strategy."""
    strategy = get_strategy(strategy_key)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_key}' not found")

    results = []
    for symbol in symbols[:20]:   # Limit for performance
        df = get_price_data(db, symbol.upper())
        if df.empty:
            continue
        df = df.copy()
        df["symbol"] = symbol.upper()
        signals = strategy.generate_signals(df)
        if signals:
            results.append(signals[-1].to_dict())

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return sanitize_for_json({"strategy": strategy.name, "signals": results})
