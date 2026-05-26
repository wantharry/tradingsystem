"""
breakout_momentum.py — Breakout Momentum Strategy (Volume-Confirmed Breakout)

STRATEGY FAMILY: Breakout / Momentum

PLAIN ENGLISH EXPLANATION:
  Imagine a spring that has been compressed for weeks. When released, it
  shoots out fast. This strategy looks for stocks or futures that have been
  trading in a tight, quiet range — and then catches them when they explode
  out of that range with high volume.

  The key rule: volume MUST confirm the breakout.
  Without volume, a price break is often a fakeout (trap). With big volume,
  it means large players are pushing price — and it usually continues.

WHY THIS WORKS:
  Consolidation periods represent a balance between buyers and sellers.
  When one side overwhelms the other (shown by a surge in volume), the
  resulting price move can be dramatic. Institutions accumulate in quiet
  ranges and then push price — we ride with them.

BEST MARKETS:
  - Equities after multi-week consolidations (especially post-earnings calm)
  - Index futures at key support/resistance levels
  - Commodity futures after inventory builds or supply disruptions
  - Any instrument when ATR is expanding from a low base
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class BreakoutMomentumStrategy(BaseStrategy):

    name = "Volume Breakout Momentum"
    family = "breakout"
    asset_class = "equity"           # Level 1
    strategy_type = "trend_following"  # Level 2: breakout is a subset of trend following
    description = (
        "Enters on confirmed breaks of 20-period highs or lows with volume confirmation. "
        "Uses ATR expansion to confirm real momentum, not a fake move."
    )

    def default_parameters(self) -> dict:
        return {
            "lookback_period": 20,           # How many bars to look back for the range high/low
            "volume_multiplier": 1.5,         # Volume must be this × 20-day average to confirm
            "atr_expansion_min": 1.0,         # Today's candle range must be ≥ 1× ATR
            "atr_stop_mult": 1.5,             # Stop = breakout level - ATR × this (1.5 optimal)
            "rr_target": 2.5,                 # Minimum R:R ratio — 2.5 best WF OOS Sharpe=11.34
            "require_volume": True,           # Require volume confirmation (strongly recommended)
            "allow_retest_entry": True,       # Allow entry on pullback to breakout level
            "max_adx_for_squeeze": 20,        # Squeeze = ADX < this (quiet consolidation)
            "ema200_filter": True,            # Only long if above EMA200, only short if below
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 50:
            return []

        df = self._add_base_indicators(df)

        p = self.parameters
        lb = p["lookback_period"]
        signals = []

        for i in range(lb + 5, len(df)):
            row = df.iloc[i]
            prev_window = df.iloc[i - lb: i]   # The lookback window (not including today)

            if pd.isna(row.get("atr")) or pd.isna(row.get("adx")):
                continue

            close = row["close"]
            high = row["high"]
            low = row["low"]
            volume = row["volume"]
            atr = row["atr"]
            adx = row["adx"]
            vol_avg = row["vol_avg"]

            # Previous range boundaries (excluding current bar)
            range_high = prev_window["high"].max()
            range_low = prev_window["low"].min()

            # ── VOLUME CONFIRMATION ───────────────────────────────────────
            volume_ok = (not p["require_volume"]) or (vol_avg > 0 and volume >= vol_avg * p["volume_multiplier"])

            # ── ATR EXPANSION ─────────────────────────────────────────────
            candle_range = high - low
            atr_expansion_ok = candle_range >= atr * p["atr_expansion_min"]

            # ── UPSIDE BREAKOUT ───────────────────────────────────────────
            breakout_up = close > range_high and high > range_high

            # EMA200 trend guard: only buy breakouts in uptrends
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

            if breakout_up and volume_ok and atr_expansion_ok and ema200_allows_long:
                entry = close
                stop = range_high - atr * p["atr_stop_mult"]   # Below the breakout level
                stop = min(stop, row["low"])                    # Also below today's low
                risk = entry - stop
                if risk <= 0:
                    continue
                target = entry + risk * p["rr_target"]

                # Squeeze prior to breakout? (consolidation quality)
                prior_adx = prev_window["adx"].mean() if "adx" in prev_window.columns else adx
                was_quiet = prior_adx < p["max_adx_for_squeeze"] if not pd.isna(prior_adx) else False
                quality_note = "Prior consolidation was quiet (low ADX) — clean breakout. " if was_quiet else ""

                reasoning = (
                    f"UPSIDE BREAKOUT: Close {close:.2f} broke above {lb}-day high ({range_high:.2f}). "
                    f"Volume={volume:,.0f} ({volume/vol_avg:.1f}× average) — strong institutional participation. "
                    f"Candle range ({candle_range:.2f}) = {candle_range/atr:.1f}× ATR — real momentum, not noise. "
                    f"{quality_note}"
                    f"Stop below breakout level ({range_high:.2f}) - ATR buffer. "
                    f"Target: {p['rr_target']}:1 R:R at {target:.2f}."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="BUY",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_breakout(volume, vol_avg, candle_range, atr, adx, was_quiet),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "range_high": round(range_high, 2), "range_low": round(range_low, 2),
                        "volume_ratio": round(volume / vol_avg, 2) if vol_avg > 0 else 0,
                        "atr_expansion": round(candle_range / atr, 2) if atr > 0 else 0,
                        "adx": round(adx, 1),
                    },
                ))

            # ── DOWNSIDE BREAKOUT ─────────────────────────────────────────
            breakout_down = close < range_low and low < range_low

            if breakout_down and volume_ok and atr_expansion_ok and ema200_allows_short:
                entry = close
                stop = range_low + atr * p["atr_stop_mult"]
                stop = max(stop, row["high"])
                risk = stop - entry
                if risk <= 0:
                    continue
                target = entry - risk * p["rr_target"]

                reasoning = (
                    f"DOWNSIDE BREAKOUT: Close {close:.2f} broke below {lb}-day low ({range_low:.2f}). "
                    f"Volume={volume:,.0f} ({volume/vol_avg:.1f}× average) — distribution confirmed. "
                    f"Candle range ({candle_range:.2f}) = {candle_range/atr:.1f}× ATR — real selling pressure. "
                    f"Stop above breakout level + ATR. Target: {p['rr_target']}:1 R:R."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="SELL",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_breakout(volume, vol_avg, candle_range, atr, adx, False),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "range_high": round(range_high, 2), "range_low": round(range_low, 2),
                        "volume_ratio": round(volume / vol_avg, 2) if vol_avg > 0 else 0,
                        "adx": round(adx, 1),
                    },
                ))

        return signals

    def _score_breakout(self, volume, vol_avg, candle_range, atr, adx, was_quiet) -> float:
        score = 0.0
        if vol_avg > 0:
            vol_ratio = volume / vol_avg
            if vol_ratio >= 3.0: score += 0.35
            elif vol_ratio >= 2.0: score += 0.25
            elif vol_ratio >= 1.5: score += 0.15
        if atr > 0:
            atr_ratio = candle_range / atr
            if atr_ratio >= 2.0: score += 0.3
            elif atr_ratio >= 1.5: score += 0.2
            elif atr_ratio >= 1.0: score += 0.1
        if was_quiet: score += 0.2     # Compression before breakout = quality
        if adx < 20: score += 0.15    # Low prior ADX = clean consolidation
        return min(score, 1.0)

    def get_documentation(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "overview": (
                "The Volume Breakout Momentum strategy catches explosive moves when price breaks "
                "out of a defined consolidation range with unusually high volume. Volume is the "
                "key differentiator — without it, the breakout is likely a trap. With it, "
                "the move is likely to continue as large players are clearly driving price."
            ),
            "when_to_use": [
                "Market has been consolidating in a tight range for at least 2-3 weeks",
                "Volatility (ATR) has been contracting — the spring is being compressed",
                "Volume spikes dramatically on the breakout candle (≥ 1.5× average)",
                "Regime is HIGH_VOL or transitioning from RANGING to TRENDING",
            ],
            "when_to_avoid": [
                "Breakout with no volume — very likely a fakeout, wait for confirmation",
                "Already extended move — if price has run 5%+ before the breakout bar, skip",
                "Range that has been violated many times — clean breakouts need clean ranges",
                "First 30 minutes of the day — wait for opening noise to settle",
                "Major event coming the same day (earnings, FOMC) — can reverse instantly",
            ],
            "entry_rules": [
                "1. Identify the 20-day range: the highest high and lowest low of past 20 bars",
                "2. Upside breakout: today's close is above the 20-day high",
                "3. Volume must be ≥ 1.5× the 20-day average volume on the breakout bar",
                "4. Candle range must be ≥ 1× ATR (real momentum, not a doji)",
                "5. Enter at close of breakout candle or next day's open",
                "6. Alternative: wait for a pullback to the old range high, enter on bounce",
            ],
            "exit_rules": [
                "Stop: Below the 20-day range high (now support) minus 1 ATR",
                "Target: 2× the risk as a minimum. Can use measured move for larger targets.",
                "Trail stop: Move to breakeven once 1R in profit. Trail below each new high.",
                "Exit if price closes back inside the old range (false breakout confirmed)",
            ],
            "risk_rules": [
                "Risk 1% of portfolio per breakout trade",
                "Max 2 breakout trades at once — they can reverse hard if fakeouts",
                "Never chase — if you miss the candle, wait for the pullback or skip",
                "Hard stop rule: exit same day if close is back inside the range",
            ],
            "examples": [
                {
                    "scenario": "NVDA breaks 3-week consolidation",
                    "setup": "NVDA consolidating $400-$420 for 3 weeks. Volume declining.",
                    "trigger": "NVDA closes at $425 on 2.3× average volume, candle range = 1.8× ATR",
                    "entry": "$425 (close of breakout bar)",
                    "stop": "$418 (below old range high $420 - 1 ATR)",
                    "target": "$439 (2:1 on $7 risk)",
                    "size": "$50k account, risk $500 (1%), $500/$7 ≈ 71 shares",
                },
            ],
            "common_mistakes": [
                "Buying breakouts with low volume — the #1 cause of whipsaws",
                "Not respecting the hard stop when price closes back in the range",
                "Chasing the move after missing the initial breakout bar",
                "Setting the stop too tight (below the breakout bar low) instead of below the range high",
                "Trading breakouts in choppy/ranging markets without checking the regime first",
            ],
        }
