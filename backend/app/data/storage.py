"""
storage.py — Append-only storage layer for all market and macro data.

DESIGN PRINCIPLES:
  1. Append-only: we never delete or overwrite historical records.
  2. Idempotent: running a fetch twice produces the same database state.
  3. Traceable: every record has a source and created_at timestamp.
  4. Fast reads: indexes on (symbol, date) for quick strategy queries.
"""

import logging
from datetime import date, datetime
from typing import Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database.models import PriceData, MacroData, Symbol, RegimeHistory
from app.data.market_data import fetch_ohlcv, fetch_symbol_info, fetch_all_fred_series

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  SYMBOL MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def upsert_symbol(db: Session, symbol: str) -> Symbol:
    """Add a symbol to the watchlist if it doesn't exist. Update metadata if it does."""
    existing = db.query(Symbol).filter(Symbol.symbol == symbol).first()
    info = fetch_symbol_info(symbol)

    if existing:
        existing.name = info.get("name", existing.name)
        existing.sector = info.get("sector", existing.sector)
        existing.exchange = info.get("exchange", existing.exchange)
        existing.asset_type = info.get("asset_type", existing.asset_type)
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing

    new_symbol = Symbol(
        symbol=symbol,
        name=info.get("name", symbol),
        sector=info.get("sector", "Unknown"),
        exchange=info.get("exchange", "Unknown"),
        asset_type=info.get("asset_type", "equity"),
        is_active=True,
    )
    db.add(new_symbol)
    db.commit()
    db.refresh(new_symbol)
    logger.info(f"Added symbol: {symbol} ({info.get('name', '')})")
    return new_symbol


def get_active_symbols(db: Session) -> list[str]:
    """Return list of all active symbol tickers."""
    return [row.symbol for row in db.query(Symbol.symbol).filter(Symbol.is_active == True).all()]


# ─────────────────────────────────────────────────────────────────────────────
#  PRICE DATA STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def store_price_data(db: Session, df: pd.DataFrame) -> int:
    """
    Store OHLCV data. Skips rows that already exist (idempotent).
    Returns the number of new rows inserted.
    """
    if df.empty:
        return 0

    # Get existing dates for this symbol+interval to avoid duplicates
    symbol = df["symbol"].iloc[0]
    interval = df.get("interval", pd.Series(["1d"])).iloc[0]
    existing_dates = set(
        row.date for row in
        db.query(PriceData.date).filter(
            PriceData.symbol == symbol,
            PriceData.interval == interval,
        ).all()
    )

    new_rows = []
    for _, row in df.iterrows():
        row_date = pd.to_datetime(row["date"]).to_pydatetime()
        if row_date not in existing_dates:
            new_rows.append(PriceData(
                symbol=row["symbol"],
                date=row_date,
                interval=interval,
                open=float(row.get("open", 0) or 0),
                high=float(row.get("high", 0) or 0),
                low=float(row.get("low", 0) or 0),
                close=float(row.get("close", 0) or 0),
                volume=float(row.get("volume", 0) or 0),
                adj_close=float(row.get("adj_close", row.get("close", 0)) or 0),
                source=row.get("source", "yfinance"),
            ))

    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()
        logger.info(f"Stored {len(new_rows)} new rows for {symbol}")

    return len(new_rows)


def get_price_data(
    db: Session,
    symbol: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Load price data from the database for a symbol.
    Falls back to fetching from yfinance if no data is stored.
    """
    query = db.query(PriceData).filter(
        PriceData.symbol == symbol,
        PriceData.interval == interval,
    )

    if start_date:
        query = query.filter(PriceData.date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(PriceData.date <= datetime.combine(end_date, datetime.max.time()))

    rows = query.order_by(PriceData.date.asc()).all()

    if not rows:
        # No stored data — fetch and store it now
        logger.info(f"No stored data for {symbol}, fetching from yfinance...")
        df = fetch_ohlcv(symbol, period="3y", interval=interval)
        if not df.empty:
            store_price_data(db, df)
        return df

    return pd.DataFrame([{
        "date": r.date,
        "open": r.open,
        "high": r.high,
        "low": r.low,
        "close": r.close,
        "volume": r.volume,
        "adj_close": r.adj_close,
    } for r in rows])


# ─────────────────────────────────────────────────────────────────────────────
#  MACRO DATA STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def store_macro_data(db: Session, df: pd.DataFrame) -> int:
    """Store FRED macro data. Idempotent — skips existing records."""
    if df.empty:
        return 0

    series_id = df["series_id"].iloc[0]
    existing_dates = set(
        row.date for row in
        db.query(MacroData.date).filter(MacroData.series_id == series_id).all()
    )

    new_rows = []
    for _, row in df.iterrows():
        row_date = row["date"] if isinstance(row["date"], date) else pd.to_datetime(row["date"]).date()
        if row_date not in existing_dates:
            new_rows.append(MacroData(
                series_id=series_id,
                series_name=row.get("series_name", series_id),
                date=row_date,
                value=float(row["value"]),
                source=row.get("source", "fred"),
            ))

    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()
        logger.info(f"Stored {len(new_rows)} new macro rows for {series_id}")

    return len(new_rows)


def refresh_all_data(db: Session, symbols: list[str]) -> dict:
    """
    Master refresh function — run at end of each trading day.
    Fetches latest data for all symbols and macro series.
    """
    results = {"symbols_updated": 0, "rows_added": 0, "macro_updated": 0}

    # Ensure all symbols exist in the DB
    for symbol in symbols:
        upsert_symbol(db, symbol)

    # Fetch and store latest OHLCV data
    for symbol in symbols:
        df = fetch_ohlcv(symbol, period="3y")
        if not df.empty:
            added = store_price_data(db, df)
            results["rows_added"] += added
            results["symbols_updated"] += 1

    # Fetch and store FRED macro data
    fred_data = fetch_all_fred_series()
    for series_id, df in fred_data.items():
        added = store_macro_data(db, df)
        results["macro_updated"] += added

    return results
