"""
market_data.py — Unified data fetcher for all market data sources.

FREE DATA SOURCES:
  1. yfinance   — Yahoo Finance. No API key. OHLCV for stocks, ETFs, futures.
  2. FRED       — Federal Reserve. Free key. Macro: VIX, rates, CPI, GDP.
  3. Alpha Vantage — Free key (25 req/day). Supplemental + earnings dates.

DESIGN:
  All fetchers return a pandas DataFrame with a consistent column schema:
    date, open, high, low, close, volume, adj_close, source

  The storage layer handles deduplication and append-only writes.
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional
import pandas as pd
import yfinance as yf

from app.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  YAHOO FINANCE FETCHER (primary, no key required)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ohlcv(
    symbol: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "3y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch OHLCV price data from Yahoo Finance.

    Args:
        symbol:     Ticker symbol (e.g. 'AAPL', 'ES=F', 'SPY')
        start_date: Start date. If None, uses 'period' instead.
        end_date:   End date. Defaults to today.
        period:     Used when start_date is None. e.g. '1y', '3y', '5y'
        interval:   Data frequency. '1d' (daily), '1h' (hourly), '15m'

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, adj_close, source
    """
    try:
        ticker = yf.Ticker(symbol)

        if start_date:
            df = ticker.history(
                start=str(start_date),
                end=str(end_date or date.today()),
                interval=interval,
                auto_adjust=True,
            )
        else:
            df = ticker.history(period=period, interval=interval, auto_adjust=True)

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()

        df = df.reset_index()

        # Normalize column names
        col_map = {
            "Date": "date", "Datetime": "date",
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        }
        df = df.rename(columns=col_map)
        df["adj_close"] = df["close"]   # yfinance auto-adjusts by default
        df["source"] = "yfinance"
        df["symbol"] = symbol
        df["interval"] = interval

        # Ensure datetime format
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        # Keep only needed columns
        keep = ["symbol", "date", "interval", "open", "high", "low", "close", "volume", "adj_close", "source"]
        df = df[[c for c in keep if c in df.columns]]

        logger.info(f"Fetched {len(df)} rows for {symbol} ({interval})")
        return df

    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()


def fetch_symbol_info(symbol: str) -> dict:
    """Fetch metadata for a symbol (name, sector, exchange, asset type)."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName", symbol),
            "sector": info.get("sector", "Unknown"),
            "exchange": info.get("exchange", "Unknown"),
            "asset_type": _classify_asset_type(symbol, info),
        }
    except Exception as e:
        logger.warning(f"Could not fetch info for {symbol}: {e}")
        return {"symbol": symbol, "name": symbol, "sector": "Unknown", "exchange": "Unknown", "asset_type": "equity"}


def fetch_options_chain(symbol: str) -> dict:
    """
    Fetch options chain for a symbol.
    Returns implied volatility data used for volatility regime detection.
    """
    try:
        ticker = yf.Ticker(symbol)
        exp_dates = ticker.options
        if not exp_dates:
            return {}

        # Use the nearest expiry for IV snapshot
        nearest = exp_dates[0]
        chain = ticker.option_chain(nearest)
        calls = chain.calls
        puts = chain.puts

        # Average implied volatility across ATM strikes
        atm_price = ticker.history(period="1d")["Close"].iloc[-1]
        atm_calls = calls[(calls["strike"] - atm_price).abs() < atm_price * 0.05]
        atm_iv = atm_calls["impliedVolatility"].mean() if not atm_calls.empty else None

        return {
            "symbol": symbol,
            "expiry": nearest,
            "atm_iv": atm_iv,
            "iv_source": "yfinance",
        }
    except Exception as e:
        logger.warning(f"Could not fetch options for {symbol}: {e}")
        return {}


def fetch_multiple_symbols(symbols: list, period: str = "3y") -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple symbols. Returns a dict of {symbol: DataFrame}."""
    results = {}
    for symbol in symbols:
        df = fetch_ohlcv(symbol, period=period)
        if not df.empty:
            results[symbol] = df
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  FRED FETCHER (macro data, free API key)
# ─────────────────────────────────────────────────────────────────────────────

# Key macro series we track and why
FRED_SERIES = {
    "VIXCLS":   "VIX Volatility Index — fear gauge, tells us if market is stressed",
    "DFF":      "Fed Funds Rate — monetary policy regime driver",
    "T10Y2Y":   "10Y-2Y Yield Curve — negative = recession risk",
    "CPIAUCSL": "CPI Inflation — macro trend driver",
    "UMCSENT":  "Consumer Sentiment — economic cycle indicator",
    "DCOILWTICO": "WTI Crude Oil Price — commodity/inflation pressure",
}


def fetch_fred_series(series_id: str, start_date: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch a macro data series from FRED.
    Requires FRED_API_KEY in .env. Returns empty DataFrame if key is missing.
    """
    if not settings.FRED_API_KEY:
        logger.info("FRED_API_KEY not set — skipping macro data fetch")
        return pd.DataFrame()

    try:
        from fredapi import Fred
        fred = Fred(api_key=settings.FRED_API_KEY)

        start = start_date or "2010-01-01"
        data = fred.get_series(series_id, observation_start=start)

        df = data.reset_index()
        df.columns = ["date", "value"]
        df["series_id"] = series_id
        df["series_name"] = FRED_SERIES.get(series_id, series_id)
        df["source"] = "fred"
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.dropna(subset=["value"])

        logger.info(f"Fetched {len(df)} FRED observations for {series_id}")
        return df

    except Exception as e:
        logger.error(f"FRED fetch error for {series_id}: {e}")
        return pd.DataFrame()


def fetch_all_fred_series() -> dict[str, pd.DataFrame]:
    """Fetch all tracked macro series from FRED."""
    results = {}
    for series_id in FRED_SERIES:
        df = fetch_fred_series(series_id)
        if not df.empty:
            results[series_id] = df
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _classify_asset_type(symbol: str, info: dict) -> str:
    """Guess asset type from symbol and metadata."""
    if symbol.endswith("=F"):
        return "future"
    q_type = info.get("quoteType", "").lower()
    if q_type == "etf":
        return "etf"
    if q_type == "future":
        return "future"
    if q_type == "index":
        return "index"
    return "equity"
