"""data.py — API routes for price and macro data."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.data.storage import get_price_data, refresh_all_data, get_active_symbols
from app.data.market_data import fetch_ohlcv
from app.config import settings

router = APIRouter()


@router.get("/price/{symbol}")
def get_price(
    symbol: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    interval: str = Query("1d"),
    db: Session = Depends(get_db),
):
    """Get stored OHLCV price data for a symbol."""
    df = get_price_data(db, symbol.upper(), start_date, end_date, interval)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "rows": len(df),
        "data": df.to_dict(orient="records"),
    }


@router.post("/refresh")
def refresh_data(
    symbols: Optional[list[str]] = None,
    db: Session = Depends(get_db),
):
    """Trigger a manual data refresh for specified symbols (or all watchlist)."""
    target = [s.upper() for s in symbols] if symbols else get_active_symbols(db)
    if not target:
        target = settings.symbols_list[:10]   # Safety limit

    result = refresh_all_data(db, target)
    return {"status": "success", "result": result}


@router.get("/refresh/status")
def refresh_status(db: Session = Depends(get_db)):
    """Get data freshness status for all symbols."""
    from app.database.models import PriceData, Symbol
    from sqlalchemy import func

    symbols = db.query(Symbol).filter(Symbol.is_active == True).all()
    status = []

    for sym in symbols:
        latest = (
            db.query(func.max(PriceData.date))
            .filter(PriceData.symbol == sym.symbol)
            .scalar()
        )
        count = (
            db.query(func.count(PriceData.id))
            .filter(PriceData.symbol == sym.symbol)
            .scalar()
        )
        status.append({
            "symbol": sym.symbol,
            "name": sym.name,
            "asset_type": sym.asset_type,
            "latest_date": str(latest.date()) if latest else None,
            "total_rows": count,
        })

    return {"symbols": status}


@router.get("/macro")
def get_macro_data(db: Session = Depends(get_db)):
    """Get stored macro data series."""
    from app.database.models import MacroData
    from sqlalchemy import func

    series = (
        db.query(MacroData.series_id, MacroData.series_name, func.max(MacroData.date).label("latest"))
        .group_by(MacroData.series_id, MacroData.series_name)
        .all()
    )
    return {"series": [{"id": r.series_id, "name": r.series_name, "latest": str(r.latest)} for r in series]}


@router.get("/macro/{series_id}")
def get_macro_series(
    series_id: str,
    limit: int = Query(252, le=1000),
    db: Session = Depends(get_db),
):
    """Get historical values for a specific FRED macro series."""
    from app.database.models import MacroData

    rows = (
        db.query(MacroData)
        .filter(MacroData.series_id == series_id)
        .order_by(MacroData.date.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for series {series_id}")

    return {
        "series_id": series_id,
        "series_name": rows[0].series_name,
        "data": [{"date": str(r.date), "value": r.value} for r in reversed(rows)],
    }
