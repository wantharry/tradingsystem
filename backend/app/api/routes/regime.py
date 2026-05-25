"""regime.py — API routes for market regime detection."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.regime.detector import detect_regime, detect_market_regime
from app.data.storage import get_price_data, get_active_symbols
from app.database.models import RegimeHistory

router = APIRouter()


@router.get("/market")
def get_market_regime(db: Session = Depends(get_db)):
    """Get the current overall market regime."""
    symbols = get_active_symbols(db)
    if not symbols:
        from app.config import settings
        symbols = settings.symbols_list
    return detect_market_regime(db, symbols)


@router.get("/symbol/{symbol}")
def get_symbol_regime(symbol: str, db: Session = Depends(get_db)):
    """Get the current regime for a specific symbol."""
    df = get_price_data(db, symbol.upper())
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    result = detect_regime(df, symbol.upper())
    return result


@router.get("/history/{symbol}")
def get_regime_history(
    symbol: str,
    limit: int = Query(90, le=500),
    db: Session = Depends(get_db),
):
    """Get historical regime classifications for a symbol."""
    rows = (
        db.query(RegimeHistory)
        .filter(RegimeHistory.symbol == symbol.upper())
        .order_by(RegimeHistory.date.desc())
        .limit(limit)
        .all()
    )
    return {
        "symbol": symbol.upper(),
        "history": [
            {
                "date": str(r.date),
                "regime": r.regime,
                "adx": r.adx,
                "atr_percentile": r.atr_percentile,
                "rsi": r.rsi,
                "notes": r.notes,
            }
            for r in reversed(rows)
        ],
    }


@router.get("/all")
def get_all_regimes(db: Session = Depends(get_db)):
    """Get current regime for all active watchlist symbols."""
    symbols = get_active_symbols(db)
    results = []
    for sym in symbols:
        df = get_price_data(db, sym)
        if not df.empty:
            r = detect_regime(df, sym)
            results.append(r)
    return {"regimes": results}
