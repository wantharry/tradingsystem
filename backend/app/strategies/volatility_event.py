"""
volatility_event.py — Volatility Squeeze Breakout Strategy

STRATEGY FAMILY: Volatility / Momentum

PLAIN ENGLISH EXPLANATION:
  Think of a coiled spring. Markets go through quiet periods where
  price range contracts and volatility shrinks — a "squeeze." When
  the spring finally releases, the resulting move is often explosive
  and directional.

  This strategy has two phases:

  PHASE 1 — IDENTIFY THE SQUEEZE:
    Volatility (ATR) falls into the bottom 25% of its 100-day range
    for at least 5 consecutive bars. Like a volcano building pressure.

  PHASE 2 — TRADE THE BREAKOUT:
    When ATR starts expanding AND price breaks out of its recent
    20-bar high or low with volume confirmation, we enter in the
    direction of the breakout. We ride the release of compressed energy.

WHY THIS WORKS:
  Consolidation = temporary balance between buyers and sellers. When
  the balance breaks — confirmed by expanding volatility and volume —
  the resulting move tends to continue as late participants chase.
  The squeeze filter reduces false breakouts by requiring genuine
  prior compression, not just a random range break.

BEST MARKETS:
  - Any liquid equity or ETF
  - Stocks before and after earnings (natural compression cycles)
  - Index ETFs (SPY, QQQ) around key macro events
"""

import pandas as pd
import numpy as np
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class VolatilityEventStrategy(BaseStrategy):

    name = "Volatility Squeeze Breakout"
    family = "volatility"
    description = (
        "Identifies volatility squeezes (ATR contracting to historical lows) then trades "
        "the directional breakout when the squeeze releases with volume confirmation. "
        "Requires genuine prior compression — not a random range break."
    )

    def default_parameters(self) -> dict:
        return {
            "atr_lookback": 50,            # Bars to compute ATR percentile range (responsive)
            "squeeze_percentile": 35,       # ATR must be in bottom X% to be in squeeze
            "min_squeeze_bars": 3,          # Minimum consecutive squeeze bars before entry
            "breakout_lookback": 20,        # Bars to define the range high/low
            "atr_stop_mult": 1.5,          # Stop = entry ± ATR × this (stock-price based)
            "rr_target": 2.5,              # Target reward-to-risk ratio
            "volume_confirm": True,         # Require volume expansion on breakout bar
            "volume_mult": 1.1,            # Volume must be ≥ this × 20-day average
            "atr_expand_pct": 5,           # ATR must grow by X% from prior bar (expanding)
            "range_tolerance_pct": 0.3,    # Allow entry if within X% of range boundary
            "ema200_filter": True,          # Only long if above EMA200, only short if below
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """
        Two-phase detection:
          Phase 1 — Squeeze: ATR falls into the bottom squeeze_percentile% of its
                    atr_lookback-day range for min_squeeze_bars consecutive bars.
          Phase 2 — Breakout: ATR is expanding AND price breaks out of its
                    breakout_lookback-day high (long) or low (short), with volume.

        The squeeze (Phase 1) must have existed in the PRIOR bar — we enter on the
        breakout bar itself (direction confirmed). The squeeze ensures there was
        genuine compression before the move, filtering random breakouts.

        All prices are stock-price-relative for compatibility with the equity engine.
        """
        lb = self.parameters["atr_lookback"]
        min_len = lb + self.parameters["min_squeeze_bars"] + self.parameters["breakout_lookback"] + 5
        if len(df) < min_len:
            return []

        df = self._add_base_indicators(df)
        p = self.parameters

        # Compute ATR percentile rank over rolling atr_lookback window
        df["atr_pct_rank"] = df["atr"].rolling(lb).apply(
            lambda x: (x[-1] > x[:-1]).mean() * 100, raw=True
        )

        # Mark each bar as "in squeeze" (1) or not (0)
        df["in_squeeze"] = (df["atr_pct_rank"] <= p["squeeze_percentile"]).astype(int)

        # Consecutive squeeze streak ending at each row
        streak = []
        count = 0
        for val in df["in_squeeze"]:
            count = (count + 1) if val else 0
            streak.append(count)
        df["squeeze_streak"] = streak

        signals = []
        bl = p["breakout_lookback"]
        tol = p["range_tolerance_pct"] / 100   # e.g. 0.003 for 0.3%

        for i in range(lb + bl + 5, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(row.get("atr_pct_rank")) or pd.isna(row.get("atr")):
                continue

            close = row["close"]
            atr = row["atr"]
            volume = row["volume"]
            vol_avg = row.get("vol_avg", 0)

            # ── PHASE 1: Was there a squeeze in the prior bars? ───────────
            prior_streak = df["squeeze_streak"].iloc[i - 1]
            had_squeeze = prior_streak >= p["min_squeeze_bars"]
            if not had_squeeze:
                continue

            # ── PHASE 2: ATR expanding (squeeze releasing) ────────────────
            atr_prev = prev["atr"]
            if pd.isna(atr_prev) or atr_prev <= 0:
                continue
            atr_expanding = atr > atr_prev * (1 + p["atr_expand_pct"] / 100)
            if not atr_expanding:
                continue

            # ── VOLUME CONFIRMATION ───────────────────────────────────────
            volume_ok = (
                not p["volume_confirm"]
                or (vol_avg > 0 and volume >= vol_avg * p["volume_mult"])
            )
            if not volume_ok:
                continue

            # ── PRICE BREAKOUT: tolerance allows entry near the boundary ──
            price_window = df.iloc[i - bl: i]
            range_high = price_window["high"].max()
            range_low = price_window["low"].min()

            squeeze_bars_count = int(prior_streak)
            vol_ratio = volume / vol_avg if vol_avg > 0 else 1.0

            # EMA200 trend guard
            ema200 = row.get("ema200")
            ema200_allows_long = (
                not p.get("ema200_filter", True)
                or pd.isna(ema200)
                or close > ema200
            )
            ema200_allows_short = (
                not p.get("ema200_filter", True)
                or pd.isna(ema200)
                or close < ema200
            )

            # Upside breakout: close at or above range_high (within tolerance)
            breaking_up = close >= range_high * (1 - tol) and ema200_allows_long

            # Downside breakout: close at or below range_low (within tolerance)
            breaking_down = close <= range_low * (1 + tol) and ema200_allows_short

            # ── LONG BREAKOUT ─────────────────────────────────────────────
            if breaking_up:
                entry = close
                stop = entry - atr * p["atr_stop_mult"]
                stop = max(stop, range_low - atr * 0.5)   # Not below recent low
                stop = min(stop, entry - atr * 0.5)        # At least half ATR away
                risk = entry - stop
                if risk <= 0:
                    continue
                target = entry + risk * p["rr_target"]

                reasoning = (
                    f"VOLATILITY SQUEEZE BREAKOUT (LONG): ATR rank was in bottom "
                    f"{p['squeeze_percentile']}% for {squeeze_bars_count} bars — "
                    f"market was building compressed energy. "
                    f"ATR now expanding {((atr/atr_prev - 1)*100):.1f}% "
                    f"({atr_prev:.3f} → {atr:.3f}), price reached {bl}-bar high "
                    f"({range_high:.2f}). "
                    f"Volume {vol_ratio:.1f}× average — confirms participation. "
                    f"Stop at {stop:.2f} (ATR × {p['atr_stop_mult']}). "
                    f"Target {p['rr_target']}:1 R:R at {target:.2f}."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="BUY",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_squeeze_breakout(
                        squeeze_bars_count, p["min_squeeze_bars"], atr, atr_prev, vol_ratio
                    ),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "squeeze_bars": squeeze_bars_count,
                        "atr_rank_now": round(float(row["atr_pct_rank"]), 1),
                        "atr_expansion_pct": round((atr / atr_prev - 1) * 100, 1),
                        "range_high": round(range_high, 2),
                        "range_low": round(range_low, 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "atr": round(atr, 4),
                        "trade_type": "Squeeze Breakout Long",
                    },
                ))

            # ── SHORT BREAKOUT ────────────────────────────────────────────
            elif breaking_down:
                entry = close
                stop = entry + atr * p["atr_stop_mult"]
                stop = min(stop, range_high + atr * 0.5)
                stop = max(stop, entry + atr * 0.5)
                risk = stop - entry
                if risk <= 0:
                    continue
                target = entry - risk * p["rr_target"]

                reasoning = (
                    f"VOLATILITY SQUEEZE BREAKOUT (SHORT): ATR rank was in bottom "
                    f"{p['squeeze_percentile']}% for {squeeze_bars_count} bars — "
                    f"market was compressing. "
                    f"ATR now expanding {((atr/atr_prev - 1)*100):.1f}% "
                    f"({atr_prev:.3f} → {atr:.3f}), price broke below {bl}-bar low "
                    f"({range_low:.2f}). "
                    f"Volume {vol_ratio:.1f}× average — distribution confirmed. "
                    f"Stop at {stop:.2f}. Target {p['rr_target']}:1 R:R at {target:.2f}."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="SELL",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_squeeze_breakout(
                        squeeze_bars_count, p["min_squeeze_bars"], atr, atr_prev, vol_ratio
                    ),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "squeeze_bars": squeeze_bars_count,
                        "atr_rank_now": round(float(row["atr_pct_rank"]), 1),
                        "atr_expansion_pct": round((atr / atr_prev - 1) * 100, 1),
                        "range_high": round(range_high, 2),
                        "range_low": round(range_low, 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "atr": round(atr, 4),
                        "trade_type": "Squeeze Breakout Short",
                    },
                ))

        return signals

    def _score_squeeze_breakout(
        self, squeeze_bars: int, min_bars: int, atr: float, atr_prev: float, vol_ratio: float
    ) -> float:
        score = 0.0
        # Longer squeeze = more compressed energy = stronger signal
        extra = squeeze_bars - min_bars
        if extra >= 15: score += 0.35
        elif extra >= 8: score += 0.25
        elif extra >= 3: score += 0.15
        # ATR expansion magnitude
        if atr_prev > 0:
            expand = atr / atr_prev
            if expand >= 1.5: score += 0.35
            elif expand >= 1.25: score += 0.25
            elif expand >= 1.10: score += 0.15
        # Volume confirmation
        if vol_ratio >= 3.0: score += 0.30
        elif vol_ratio >= 2.0: score += 0.20
        elif vol_ratio >= 1.3: score += 0.10
        return min(score, 1.0)

    def get_documentation(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "overview": (
                "The Volatility Squeeze Breakout strategy identifies periods of abnormally "
                "low volatility (ATR in the bottom 25% of its 100-day range for 5+ consecutive "
                "bars), then trades the explosive breakout when volatility re-expands and price "
                "breaks out of its recent range. Volume must confirm the move."
            ),
            "when_to_use": [
                "ATR has been compressing for at least 5 consecutive bars (long squeeze = better)",
                "ATR suddenly starts expanding from the squeeze (momentum returning)",
                "Price breaks above 20-day high (long) or below 20-day low (short)",
                "Volume is 1.3× or more the 20-day average on the breakout bar",
            ],
            "when_to_avoid": [
                "No prior compression — a random breakout without squeeze has lower probability",
                "Volume is below average — no institutional confirmation",
                "Major counter-trend: don't short in a strong uptrend (check EMA 200)",
                "After earnings gaps — the gap itself is the event, squeeze breakout needs time",
            ],
            "entry_rules": [
                "Confirm squeeze: ATR rank ≤ 25th percentile for 5+ bars",
                "Breakout bar: ATR expands ≥ 10% from prior bar AND exits the squeeze zone",
                "Long: close > 20-day high. Short: close < 20-day low.",
                "Volume ≥ 1.3× 20-day average on the breakout bar.",
            ],
            "exit_rules": [
                "Target: 2.5× risk (R:R = 2.5:1)",
                "Stop: 1.5× ATR below entry (long) or above entry (short)",
                "Time stop: exit after 20 bars if neither stop nor target hit",
                "If ATR immediately collapses back into squeeze without follow-through, exit early",
            ],
            "risk_rules": [
                "Risk 1% of portfolio per trade",
                "Max 2 squeeze breakout positions at once (correlated moves)",
                "Reduce size during high-VIX regimes (squeeze breaks are more reliable in low-VIX)",
            ],
        }
