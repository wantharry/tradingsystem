"""
detector.py — Market Regime Detection Engine

WHY REGIME DETECTION MATTERS:
  The single most important thing in trading is knowing WHAT kind of market
  you're in. The same strategy that makes money in a trending market LOSES
  money in a choppy, sideways market. Regime detection is the filter that
  routes you to the right strategy family.

REGIMES:
  uptrend   → Price is trending up, ADX strong, use trend-following long
  downtrend → Price is trending down, ADX strong, use trend-following short
  ranging   → Low ADX, price oscillating, use mean reversion
  high_vol  → ATR percentile high, use breakout or long-vol
  risk_off  → Market-wide stress (VIX spike, broad decline), reduce all exposure
  event     → Major scheduled catalyst within 2 days

HOW WE DETECT EACH REGIME:
  1. ADX tells us if a trend exists (directional movement strength)
  2. EMA alignment tells us trend direction (up or down)
  3. ATR percentile tells us if volatility is elevated
  4. Price structure (higher highs/lows) confirms trend quality
  5. Breadth (% of watchlist symbols trending) gives market-wide context
"""

import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd
import pandas_ta as ta
from sqlalchemy.orm import Session

from app.database.models import RegimeHistory
from app.data.storage import get_price_data
from app.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLE SYMBOL REGIME DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_regime(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    as_of_date: Optional[date] = None,
) -> dict:
    """
    Detect the current market regime for a single symbol.

    Returns a dict:
      regime:          The classified regime name
      confidence:      0-1 score (how clearly defined the regime is)
      adx:             Trend strength
      atr_percentile:  Where current ATR sits in 1-year range (0-100)
      rsi:             Current RSI value
      above_200ema:    Is price above the long-term trend?
      notes:           Human-readable explanation
    """
    if df.empty or len(df) < 30:
        return _unknown_regime(symbol)

    df = df.copy().sort_values("date").reset_index(drop=True)

    # If as_of_date is specified, only use data up to that date
    if as_of_date:
        df = df[df["date"] <= pd.Timestamp(as_of_date)]

    if len(df) < 30:
        return _unknown_regime(symbol)

    # ── Calculate indicators ──────────────────────────────────────────
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)
    df["rsi"] = ta.rsi(df["close"], length=14)
    atr_series = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr"] = atr_series

    adx_data = ta.adx(df["high"], df["low"], df["close"], length=14)
    if adx_data is not None and not adx_data.empty:
        df["adx"] = adx_data.iloc[:, 0]
    else:
        df["adx"] = None

    # ATR percentile: where is today's ATR relative to the past year?
    lb = min(252, len(df) - 1)
    df["atr_pct_rank"] = df["atr"].rolling(lb).apply(
        lambda x: float((x[-1] > x[:-1]).mean()) * 100 if len(x) > 1 else 50.0,
        raw=True,
    )

    # Use the latest row
    latest = df.iloc[-1]
    close = latest["close"]
    adx = latest.get("adx") or 0
    rsi = latest.get("rsi") or 50
    atr = latest.get("atr") or 0
    atr_pct_rank = latest.get("atr_pct_rank") or 50
    ema20 = latest.get("ema20") or close
    ema50 = latest.get("ema50") or close
    ema200 = latest.get("ema200") or close

    # ── Regime classification logic ──────────────────────────────────
    adx_val = float(adx) if not pd.isna(adx) else 0
    rsi_val = float(rsi) if not pd.isna(rsi) else 50
    atr_rank_val = float(atr_pct_rank) if not pd.isna(atr_pct_rank) else 50
    ema50_val = float(ema50) if not pd.isna(ema50) else close
    ema200_val = float(ema200) if not pd.isna(ema200) else close

    above_200ema = close > ema200_val
    above_50ema = close > ema50_val
    emas_aligned_up = ema50_val > ema200_val and close > ema50_val
    emas_aligned_down = ema50_val < ema200_val and close < ema50_val

    # Higher highs / higher lows check (last 5 bars)
    recent = df.tail(10)
    hh_hl = (recent["high"].is_monotonic_increasing and
              recent["low"].iloc[-1] > recent["low"].iloc[0]) if len(recent) > 5 else False
    ll_lh = (recent["low"].is_monotonic_decreasing and
              recent["high"].iloc[-1] < recent["high"].iloc[0]) if len(recent) > 5 else False

    # Very high vol = potential risk-off
    extreme_vol = atr_rank_val >= 90

    # ── Decision tree ────────────────────────────────────────────────
    regime = "ranging"     # Default
    confidence = 0.5
    notes_parts = []

    if extreme_vol and not emas_aligned_up:
        # Extreme volatility + not in uptrend = risk-off or crash
        regime = "risk_off"
        confidence = 0.7 + (atr_rank_val - 90) / 100
        notes_parts = [
            f"RISK-OFF: ATR rank={atr_rank_val:.0f}th percentile (extremely elevated vol).",
            "Reduce all exposure. Only defined-risk positions.",
        ]

    elif adx_val >= settings.ADX_TREND_THRESHOLD and emas_aligned_up:
        regime = "uptrend"
        confidence = min(0.5 + (adx_val - 25) / 50 + (0.2 if hh_hl else 0), 1.0)
        notes_parts = [
            f"UPTREND: ADX={adx_val:.1f} (strong directional move). EMAs aligned bullish.",
            f"RSI={rsi_val:.1f}. Use trend-following long strategies.",
            "EMA pullback entries recommended." if not hh_hl else "Higher highs/lows confirmed — strong structure.",
        ]

    elif adx_val >= settings.ADX_TREND_THRESHOLD and emas_aligned_down:
        regime = "downtrend"
        confidence = min(0.5 + (adx_val - 25) / 50 + (0.2 if ll_lh else 0), 1.0)
        notes_parts = [
            f"DOWNTREND: ADX={adx_val:.1f}. EMAs aligned bearish.",
            "Use trend-following short strategies or reduce longs.",
        ]

    elif atr_rank_val >= 70:
        regime = "high_vol"
        confidence = min(0.4 + (atr_rank_val - 70) / 60, 1.0)
        notes_parts = [
            f"HIGH VOL: ATR rank={atr_rank_val:.0f}th percentile. Elevated uncertainty.",
            "Use breakout or volatility strategies. Reduce position size.",
        ]

    else:
        regime = "ranging"
        confidence = min(0.4 + (30 - adx_val) / 60 if adx_val < 30 else 0.4, 1.0)
        notes_parts = [
            f"RANGING: ADX={adx_val:.1f} (weak directional movement). Market oscillating.",
            "Use mean reversion strategies. Avoid trend-following.",
        ]

    return {
        "symbol": symbol,
        "regime": regime,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "adx": round(adx_val, 1),
        "atr": round(float(atr) if not pd.isna(atr) else 0, 4),
        "atr_percentile": round(atr_rank_val, 1),
        "rsi": round(rsi_val, 1),
        "above_200ema": bool(above_200ema),
        "ema20": round(float(ema20) if not pd.isna(ema20) else close, 2),
        "ema50": round(float(ema50_val), 2),
        "ema200": round(float(ema200_val), 2),
        "notes": " ".join(notes_parts),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  MARKET-WIDE REGIME (uses SPY + breadth)
# ─────────────────────────────────────────────────────────────────────────────

def detect_market_regime(
    db: Session,
    symbols: list[str],
    end_date: Optional[date] = None,
) -> dict:
    """
    Detect the overall market regime using the watchlist symbols.

    Returns a summary including:
      - SPY/index regime as the primary signal
      - Breadth: % of symbols in uptrend (market participation)
      - Dominant regime across all symbols

    end_date: if provided, only use price data up to this date (for historical analysis).
    """
    # Start with SPY or ES=F as the market benchmark
    benchmark = "SPY"
    if benchmark not in symbols:
        benchmark = symbols[0] if symbols else "SPY"

    bench_df = get_price_data(db, benchmark, end_date=end_date)
    market_regime = detect_regime(bench_df, benchmark)

    # Check breadth across all symbols
    uptrend_count = 0
    total_checked = 0
    symbol_regimes = {}

    for sym in symbols[:20]:   # Limit to first 20 for speed
        df = get_price_data(db, sym, end_date=end_date)
        if not df.empty:
            reg = detect_regime(df, sym)
            symbol_regimes[sym] = reg
            total_checked += 1
            if reg["regime"] in ("uptrend",):
                uptrend_count += 1

    breadth_pct = (uptrend_count / total_checked * 100) if total_checked > 0 else 50

    # Breadth modifies the market regime
    if breadth_pct < 30 and market_regime["regime"] not in ("risk_off",):
        # Less than 30% of stocks are trending up — deteriorating breadth
        market_regime["breadth_warning"] = True
        market_regime["notes"] += f" ⚠ BREADTH WARNING: Only {breadth_pct:.0f}% of symbols in uptrend."

    market_regime["breadth_pct"] = round(breadth_pct, 1)
    market_regime["symbols_checked"] = total_checked
    market_regime["symbol_regimes"] = symbol_regimes

    return market_regime


def save_regime(db: Session, regime_data: dict, as_of: date) -> None:
    """Store a detected regime in the database for historical tracking."""
    from datetime import datetime

    existing = (
        db.query(RegimeHistory)
        .filter(RegimeHistory.symbol == regime_data["symbol"], RegimeHistory.date == as_of)
        .first()
    )

    if existing:
        existing.regime = regime_data["regime"]
        existing.adx = regime_data.get("adx")
        existing.atr_pct = regime_data.get("atr")
        existing.atr_percentile = regime_data.get("atr_percentile")
        existing.rsi = regime_data.get("rsi")
        existing.above_200ema = regime_data.get("above_200ema")
        existing.regime_score = regime_data.get("confidence")
        existing.notes = regime_data.get("notes", "")
    else:
        db.add(RegimeHistory(
            symbol=regime_data["symbol"],
            date=as_of,
            regime=regime_data["regime"],
            adx=regime_data.get("adx"),
            atr_pct=regime_data.get("atr"),
            atr_percentile=regime_data.get("atr_percentile"),
            rsi=regime_data.get("rsi"),
            above_200ema=regime_data.get("above_200ema"),
            regime_score=regime_data.get("confidence"),
            notes=regime_data.get("notes", ""),
        ))

    db.commit()


def _unknown_regime(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "regime": "unknown",
        "confidence": 0.0,
        "adx": 0, "atr": 0, "atr_percentile": 50,
        "rsi": 50, "above_200ema": False,
        "notes": "Insufficient data to determine regime.",
    }
