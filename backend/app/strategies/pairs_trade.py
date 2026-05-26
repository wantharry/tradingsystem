"""
pairs_trade.py — Price Z-Score Mean Reversion (Pairs-Style)

STRATEGY FAMILY: Hedge Equity

PLAIN ENGLISH EXPLANATION:
  Classic pairs trading means: buy stock A and short stock B when their
  price relationship (spread) stretches too far from its historical norm,
  then profit when the spread snaps back.

  This single-ticker implementation uses the same core math but applies
  it to a stock vs its own 63-day (3-month) mean price — effectively
  treating the rolling mean as the "pair". The z-score tells you how
  many standard deviations the price is from its recent mean:

    z = (current price - 63-day mean) / 63-day std dev

  When z < -2: the stock is SIGNIFICANTLY cheaper than its 3-month average
    → buy and wait for reversion to the mean.
  When z > +2: the stock is SIGNIFICANTLY more expensive than its average
    → sell and wait for reversion downward.

WHY THIS WORKS:
  Most large-cap stocks revert to their mean in range-bound regimes.
  Institutional price targets create "gravitational pull" — when a stock
  strays far from analyst consensus (proxied by the rolling mean), buy/sell
  programs kick in and pull it back. The z-score approach is market-regime
  agnostic (uses raw price deviation, not RSI or momentum).

  Key difference from Bollinger Band strategies:
    - Bollinger uses 20-day lookback → shorter memory, faster signals
    - Z-score uses 63-day lookback → catches bigger structural dislocations
    - Z-score exit is at z=0 (full reversion), not at a fixed price target

BEST MARKETS:
  - Highly liquid large-caps and mega-cap ETFs
  - ADX < 25 (confirmed range-bound — trends destroy mean reversion P&L)
  - Most effective in Q1/Q2 when mean reversion is strongest historically
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class PairsTradeStrategy(BaseStrategy):

    name = "Price Z-Score Reversion"
    family = "mean_reversion"
    asset_class = "equity"
    strategy_type = "hedge_equity"
    description = (
        "Computes a 63-day z-score of closing prices and enters when price is "
        ">2σ from its mean — betting on reversion. Exit target is the rolling mean "
        "(z=0). Filter: ADX < 25 to confirm non-trending environment."
    )

    def default_parameters(self) -> dict:
        return {
            "zscore_lookback": 63,     # 3-month rolling window for mean/std
            "entry_zscore": 2.0,       # Enter when |z| exceeds this
            "exit_zscore": 0.3,        # Target z-score at mean reversion (close to 0)
            "adx_max": 25,             # Don't trade in trending markets
            "rsi_neutral_min": 35,     # Avoid deeply oversold (may be trending down)
            "rsi_neutral_max": 65,     # Avoid deeply overbought (may be trending up)
            "atr_stop_mult": 1.5,      # Stop = entry ± (ATR × multiplier)
            "rr_target": 2.0,          # Min reward:risk ratio required
            "min_std_pct": 0.5,        # Min std dev (% of price) — skip ultra-low-vol
            "vol_confirm": True,       # Require above-average volume on entry bar
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        p = self.parameters
        lb = p["zscore_lookback"]
        if len(df) < lb + 30:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        # Compute rolling z-score
        df["roll_mean"] = df["close"].rolling(lb).mean()
        df["roll_std"] = df["close"].rolling(lb).std()
        df["zscore"] = (df["close"] - df["roll_mean"]) / df["roll_std"]

        signals = []
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        for i in range(lb + 15, len(df)):
            row = df.iloc[i]
            if pd.isna(row.get("zscore")) or pd.isna(row.get("adx")) or pd.isna(row.get("atr")):
                continue

            close = row["close"]
            atr = row["atr"]
            z = row["zscore"]
            roll_mean = row["roll_mean"]
            roll_std = row["roll_std"]
            adx = row["adx"]
            rsi = row["rsi"]
            vol_avg = row["vol_avg"]
            volume = row["volume"]

            # Trend filter: skip strong trends
            if adx > p["adx_max"]:
                continue

            # Std dev filter: skip if too low (compressed, not a range)
            if (roll_std / close) < p["min_std_pct"] / 100:
                continue

            # Volume confirmation
            vol_ok = (volume >= vol_avg) if p["vol_confirm"] else True

            # ── LONG: price far below 3-month mean ──
            if (
                z < -p["entry_zscore"]
                and rsi > p["rsi_neutral_min"]  # Not in freefall
                and vol_ok
            ):
                # Target: price reverts to rolling mean
                target = roll_mean
                stop = close - p["atr_stop_mult"] * atr
                risk = close - stop
                reward = target - close
                if risk <= 0 or reward / risk < p["rr_target"]:
                    continue

                signals.append(Signal(
                    symbol=symbol,
                    date=row["date"],
                    action="BUY",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=1.0,
                    confidence=min(0.85, 0.5 + abs(z) * 0.1),
                    risk_reward_ratio=reward / risk,
                    strategy_name=self.name,
                    reasoning=(
                        f"Z-score reversion LONG: z={z:.2f} (< -{p['entry_zscore']}), "
                        f"price={close:.2f} is {abs(z):.1f}σ below 63-day mean={roll_mean:.2f}. "
                        f"ADX={adx:.1f} (non-trending). Target = reversion to mean."
                    ),
                    indicators={
                        "zscore": round(z, 2),
                        "roll_mean_63d": round(roll_mean, 2),
                        "roll_std_63d": round(roll_std, 2),
                        "adx": round(adx, 1),
                        "rsi": round(rsi, 1),
                        "vol_vs_avg": round(volume / vol_avg, 2) if vol_avg else None,
                    },
                ))

            # ── SELL: price far above 3-month mean ──
            elif (
                z > p["entry_zscore"]
                and rsi < p["rsi_neutral_max"]  # Not in parabolic blow-off
                and vol_ok
            ):
                target = roll_mean
                stop = close + p["atr_stop_mult"] * atr
                risk = stop - close
                reward = close - target
                if risk <= 0 or reward / risk < p["rr_target"]:
                    continue

                signals.append(Signal(
                    symbol=symbol,
                    date=row["date"],
                    action="SELL",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=1.0,
                    confidence=min(0.85, 0.5 + abs(z) * 0.1),
                    risk_reward_ratio=reward / risk,
                    strategy_name=self.name,
                    reasoning=(
                        f"Z-score reversion SELL: z={z:.2f} (> +{p['entry_zscore']}), "
                        f"price={close:.2f} is {z:.1f}σ above 63-day mean={roll_mean:.2f}. "
                        f"ADX={adx:.1f} (non-trending). Target = reversion to mean."
                    ),
                    indicators={
                        "zscore": round(z, 2),
                        "roll_mean_63d": round(roll_mean, 2),
                        "roll_std_63d": round(roll_std, 2),
                        "adx": round(adx, 1),
                        "rsi": round(rsi, 1),
                        "vol_vs_avg": round(volume / vol_avg, 2) if vol_avg else None,
                    },
                ))

        return signals

    def get_documentation(self) -> dict:
        return {
            "overview": (
                "Computes a 63-day rolling z-score of closing prices. Enters long when "
                "price drops 2+ standard deviations below its 3-month mean, short when "
                "2+ std devs above. Exit target is full reversion to the mean (z = 0). "
                "Only trades when ADX < 25 confirms a non-trending environment."
            ),
            "when_to_use": [
                "Range-bound, sideways markets (ADX < 25)",
                "Large-cap liquid stocks with institutional price targets providing 'gravity'",
                "After a sharp earnings overreaction where fundamentals haven't changed",
                "When VIX is moderate (15-25) — too low means no movement, too high means trending",
            ],
            "when_to_avoid": [
                "Strong trending markets (ADX > 25) — mean reversion is a losing bet in trends",
                "Stocks with fundamental catalysts that justify the price move",
                "Small caps or low-float stocks — institutional gravity doesn't apply",
                "In the first 30 minutes / last 30 minutes of trading (price extremes are noise)",
            ],
            "entry_rules": [
                "1. Compute 63-day rolling mean and std deviation of close",
                "2. Z-score = (close - mean) / std — must be < -2.0 for long, > +2.0 for short",
                "3. ADX must be < 25 (confirmed range-bound)",
                "4. RSI must be 35–65 (avoid using in panics or euphoria extremes)",
                "5. Volume on entry bar must be ≥ 20-day average volume",
                "6. Confirm reward-to-risk ≥ 2.0 before entering",
            ],
            "exit_rules": [
                "Primary target: rolling 63-day mean (price reverts to z=0)",
                "If price returns to the mean within 10 days, consider exiting regardless of target",
                "Stop hit → exit with pre-defined loss, don't average down",
                "If ADX crosses above 25 while in trade, exit — trend is starting",
            ],
            "risk_rules": [
                "Risk max 1% of portfolio per trade",
                "Never average down on a z-score trade — widening spread = the thesis is wrong",
                "Max hold time: 20 trading days (mean reversion half-life for most large caps)",
                "If z-score reaches ±3.0 in your direction, consider reducing size (outlier event)",
            ],
            "examples": [
                "AAPL after a 10% sell-off in a neutral market: z-score = -2.3, ADX = 19, RSI = 42. Rolling mean = $175. Entry at $162, target $175, stop $157. Trade: +$13 in 12 days.",
                "SPY after a Fed-driven gap up: z-score = +2.1, ADX = 22, RSI = 63. Rolling mean = $450. Short at $468, target $450, stop $475. Trade: -$18 in 8 days (quick reversion).",
            ],
            "common_mistakes": [
                "Treating this as a trend strategy and entering in the direction of the z-score (you fade, not follow)",
                "Not checking ADX — applying mean reversion in a strong trend is the fastest way to lose",
                "Setting the target too far past the mean (mean reversion stops AT the mean, not through it)",
                "Averaging down when z-score widens further — this violates risk rules and can lead to large losses",
            ],
        }
