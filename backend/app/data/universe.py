"""
universe.py — Stock universe management.

Provides the full set of symbols the screener checks.
Order of preference:
  1. Local cache file (if < 7 days old)
  2. Wikipedia S&P 500 + Nasdaq 100 (with timeout)
  3. CORE_UNIVERSE hardcoded fallback (~150 liquid stocks)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "universe_cache.json"
_CACHE_TTL_DAYS = 7

# Hardcoded high-liquidity universe (~150 stocks + ETFs + futures)
CORE_UNIVERSE = [
    # Mega-cap technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD", "INTC", "QCOM",
    "AVGO", "TXN", "AMAT", "LRCX", "MU", "ORCL", "CRM", "ADBE", "NOW", "INTU",
    "PANW", "FTNT", "SNOW", "PLTR", "CDNS", "KEYS", "MRVL", "ON", "NXPI", "ADI",
    # Financials
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP",
    "C", "USB", "PNC", "COF", "SPGI", "MCO", "CME", "ICE", "SCHW", "TFC",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "BMY", "PFE", "AMGN",
    "GILD", "ISRG", "SYK", "BSX", "MDT", "VRTX", "REGN", "BIIB", "ZTS", "CI",
    "ELV", "HUM", "CVS", "IQV", "IDXX",
    # Consumer Discretionary
    "HD", "MCD", "NKE", "LOW", "SBUX", "TGT", "TJX", "BKNG", "MAR", "HLT",
    "ABNB", "NFLX", "DIS", "CMCSA", "GM", "F",
    # Consumer Staples
    "WMT", "PG", "KO", "PEP", "COST", "PM", "MO", "CL", "GIS",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "VLO", "PSX", "OXY", "HAL", "BKR",
    # Industrials
    "GE", "CAT", "HON", "UNP", "RTX", "DE", "BA", "UPS", "FDX", "LMT",
    "NOC", "GD", "ITW", "ETN", "EMR", "PH", "CSX", "NSC", "CARR", "OTIS",
    "ROK", "AME", "VRT", "PWR", "GWW", "FAST", "HUBB",
    # Materials
    "LIN", "APD", "ECL", "SHW", "FCX", "NEM", "PPG", "ALB",
    # Utilities
    "NEE", "DUK", "SO", "AEP", "EXC", "XEL", "PCG",
    # REITs
    "AMT", "PLD", "EQIX", "CCI", "PSA", "SBAC", "WELL", "O",
    # Telecom
    "T", "VZ", "TMUS",
    # Broad ETFs
    "SPY", "QQQ", "IWM", "VTI", "GLD", "TLT", "AGG", "SLV", "USO", "IAU",
    # Sector ETFs
    "XLF", "XLE", "XLV", "XLK", "XLI", "XLP", "XLU", "XLY", "XLRE", "XLB", "GDX",
    # Futures
    "ES=F", "NQ=F", "CL=F", "GC=F", "SI=F",
]


def _load_cached_universe() -> Optional[list]:
    try:
        if not _CACHE_FILE.exists():
            return None
        data = json.loads(_CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at > timedelta(days=_CACHE_TTL_DAYS):
            return None
        return data["symbols"]
    except Exception:
        return None


def _save_universe_cache(symbols: list):
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({
            "cached_at": datetime.now().isoformat(),
            "symbols": symbols,
            "count": len(symbols),
        }, indent=2))
    except Exception as e:
        logger.warning(f"Could not save universe cache: {e}")


def _fetch_sp500_wikipedia() -> list:
    import pandas as pd
    tables = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        attrs={"id": "constituents"},
        timeout=15,
    )
    symbols = tables[0]["Symbol"].tolist()
    return [str(s).replace(".", "-") for s in symbols]


def _fetch_ndx100_wikipedia() -> list:
    import pandas as pd
    tables = pd.read_html(
        "https://en.wikipedia.org/wiki/Nasdaq-100",
        timeout=15,
    )
    for table in tables:
        for col in ("Ticker", "Symbol"):
            if col in table.columns:
                return [str(s) for s in table[col].tolist()]
    return []


def get_universe(force_refresh: bool = False) -> list:
    """
    Return the full screener universe.
    Uses cache first, then Wikipedia, then CORE_UNIVERSE fallback.
    """
    if not force_refresh:
        cached = _load_cached_universe()
        if cached:
            logger.info(f"Loaded universe from cache: {len(cached)} symbols")
            return cached

    symbols = set(CORE_UNIVERSE)

    try:
        sp500 = _fetch_sp500_wikipedia()
        symbols.update(sp500)
        logger.info(f"Added {len(sp500)} S&P 500 symbols from Wikipedia")
    except Exception as e:
        logger.warning(f"Wikipedia S&P 500 fetch failed: {e}")

    try:
        ndx = _fetch_ndx100_wikipedia()
        symbols.update(ndx)
        logger.info(f"Added {len(ndx)} Nasdaq 100 symbols from Wikipedia")
    except Exception as e:
        logger.warning(f"Wikipedia Nasdaq 100 fetch failed: {e}")

    # Remove empty/invalid tickers
    valid = [
        s for s in symbols
        if s and 1 <= len(s) <= 8
        and s.replace("-", "").replace("=", "").replace(".", "").isalnum()
    ]

    # Sort: stocks first (alphabetical), then ETFs/futures
    futures = sorted([s for s in valid if "=" in s])
    etfs_long = sorted([s for s in valid if "=" not in s and len(s) > 4])
    stocks = sorted([s for s in valid if "=" not in s and len(s) <= 4])
    result = stocks + etfs_long + futures

    _save_universe_cache(result)
    logger.info(f"Universe ready: {len(result)} symbols")
    return result


def get_universe_stats() -> dict:
    cached = _load_cached_universe()
    if not cached:
        return {
            "symbols": len(CORE_UNIVERSE),
            "source": "fallback",
            "cached_at": None,
        }
    try:
        data = json.loads(_CACHE_FILE.read_text())
        return {
            "symbols": len(cached),
            "source": "cache",
            "cached_at": data.get("cached_at"),
        }
    except Exception:
        return {"symbols": len(cached), "source": "cache", "cached_at": None}
