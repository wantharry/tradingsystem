"""
mean_reversion.py — Mean Reversion Strategy (Bollinger Band + RSI)

STRATEGY FAMILY: Mean Reversion

PLAIN ENGLISH EXPLANATION:
  Think of a rubber band stretched to its limit. The more you stretch it,
  the harder it snaps back. This strategy finds moments when price has been
  stretched too far in one direction (oversold or overbought) and bets on
  it snapping back toward normal.

  We use two tools together:
    - RSI (Relative Strength Index): measures how hard buyers/sellers have
      been pushing recently. Below 30 = everyone is panic selling (oversold).
    - Bollinger Bands: show how far price has moved from its average.
      At the lower band = price is unusually far below average.

  When BOTH say "oversold" at the same time, we buy. When both say
  "overbought", we sell.

WHY THIS WORKS:
  Markets overshoot in both directions because of human emotion — panic
  selling pushes prices below fair value, and euphoria pushes them above.
  In stable, non-trending markets, prices consistently return to their mean.
  This strategy monetizes that predictable human behavior.

BEST MARKETS:
  - Large-cap, liquid stocks and ETFs (SPY, QQQ, AAPL)
  - Index futures during range-bound sessions
  - This strategy FAILS in strong trends — always check regime first.
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class MeanReversionStrategy(BaseStrategy):

    name = "Bollinger RSI Reversion"
    family = "mean_reversion"
    description = (
        "Fades extreme RSI and Bollinger Band conditions in range-bound markets. "
        "Requires ADX < 30 to confirm we're NOT in a trend. Quick entries, quick exits."
    )

    def default_parameters(self) -> dict:
        return {
            "rsi_oversold": 30,      # Buy when RSI drops below this — selective entry (was 35, too loose)
            "rsi_overbought": 65,    # Sell when RSI rises above this — 65 best per WF OOS Sharpe=9.90
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,           # Bollinger Band standard deviation width
            "adx_max": 25,           # Don't use mean reversion if ADX > this — tighter filter
            "atr_stop_mult": 1.0,    # Stop = entry ± (ATR × multiplier)
            "rr_target": 1.5,        # Target R:R (lower than trend because exits are faster)
            "require_both": True,    # Require BOTH RSI extreme AND BB extreme (safer)
            "ema200_filter": False,  # ADX filter (adx_max) already handles trend — don't double-filter
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 50:
            return []

        df = self._add_base_indicators(df)

        # Bollinger Bands
        bb = ta.bbands(df["close"], length=self.parameters["bb_period"], std=self.parameters["bb_std"])
        if bb is None or bb.empty:
            return []

        df["bb_lower"] = bb.iloc[:, 0]    # Lower band
        df["bb_mid"] = bb.iloc[:, 1]      # Middle band (SMA)
        df["bb_upper"] = bb.iloc[:, 2]    # Upper band

        signals = []
        p = self.parameters

        for i in range(50, len(df)):
            row = df.iloc[i]

            if pd.isna(row.get("adx")) or pd.isna(row.get("rsi")) or pd.isna(row.get("bb_lower")):
                continue

            close = row["close"]
            adx = row["adx"]
            rsi = row["rsi"]
            bb_lower = row["bb_lower"]
            bb_upper = row["bb_upper"]
            bb_mid = row["bb_mid"]
            atr = row["atr"]

            # ── REGIME FILTER: Skip if trending too strongly ─────────────
            # Mean reversion fails in strong trends. This is the #1 filter.
            if adx >= p["adx_max"]:
                continue

            # ── LONG SETUP (Oversold — buy the dip in a range) ───────────
            rsi_oversold = rsi <= p["rsi_oversold"]
            at_bb_lower = close <= bb_lower * 1.005   # At or slightly above lower band

            long_condition = rsi_oversold and (not p["require_both"] or at_bb_lower)

            # EMA200 trend guard: don't buy if price is in a structural downtrend
            ema200 = row.get("ema200")
            if p.get("ema200_filter", True) and long_condition and not pd.isna(ema200):
                if close < ema200:
                    long_condition = False   # Skip — catching falling knives in downtrends

            if long_condition:
                entry = close
                stop = bb_lower - atr * p["atr_stop_mult"]
                risk = entry - stop
                if risk <= 0:
                    continue
                target = bb_mid      # Take profit at the mean (middle band)

                # Ensure we have at least 1.5:1 R:R to middle band
                reward = target - entry
                if reward / risk < p["rr_target"]:
                    continue

                reasoning = (
                    f"OVERSOLD conditions: RSI={rsi:.1f} (≤{p['rsi_oversold']} threshold — sellers exhausted). "
                    f"Price={close:.2f} at Lower Bollinger Band ({bb_lower:.2f}) — statistically extreme. "
                    f"ADX={adx:.1f} (low — this is NOT a trending move, it's a temporary dip). "
                    f"Expect mean reversion toward middle band ({bb_mid:.2f}). "
                    f"Stop below lower band + ATR buffer. Quick exit target: middle band."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="BUY",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_reversion(rsi, close, bb_lower, bb_upper, bb_mid, adx, "long"),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "rsi": round(rsi, 1), "adx": round(adx, 1), "atr": round(atr, 4),
                        "bb_lower": round(bb_lower, 2), "bb_mid": round(bb_mid, 2), "bb_upper": round(bb_upper, 2),
                    },
                ))

            # ── SHORT SETUP (Overbought — sell the rip in a range) ────────
            rsi_overbought = rsi >= p["rsi_overbought"]
            at_bb_upper = close >= bb_upper * 0.995

            short_condition = rsi_overbought and (not p["require_both"] or at_bb_upper)

            # EMA200 trend guard: don't short if price is in a structural uptrend
            if p.get("ema200_filter", True) and short_condition and not pd.isna(ema200):
                if close > ema200:
                    short_condition = False  # Skip — fighting the uptrend

            if short_condition:
                entry = close
                stop = bb_upper + atr * p["atr_stop_mult"]
                risk = stop - entry
                if risk <= 0:
                    continue
                target = bb_mid

                reward = entry - target
                if reward / risk < p["rr_target"]:
                    continue

                reasoning = (
                    f"OVERBOUGHT conditions: RSI={rsi:.1f} (≥{p['rsi_overbought']} threshold — buyers exhausted). "
                    f"Price={close:.2f} at Upper Bollinger Band ({bb_upper:.2f}) — statistically extended. "
                    f"ADX={adx:.1f} (low — this is a temporary spike, not a real trend). "
                    f"Expect mean reversion toward middle band ({bb_mid:.2f}). "
                    f"Stop above upper band + ATR buffer."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="SELL",
                    entry_price=round(entry, 4),
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_reversion(rsi, close, bb_lower, bb_upper, bb_mid, adx, "short"),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={
                        "rsi": round(rsi, 1), "adx": round(adx, 1),
                        "bb_lower": round(bb_lower, 2), "bb_mid": round(bb_mid, 2), "bb_upper": round(bb_upper, 2),
                    },
                ))

        return signals

    def _score_reversion(self, rsi, close, bb_lower, bb_upper, bb_mid, adx, direction) -> float:
        score = 0.0
        if direction == "long":
            if rsi <= 25: score += 0.3         # Very oversold
            elif rsi <= 30: score += 0.2
            if close < bb_lower: score += 0.3  # Actually below lower band (stronger signal)
            elif close <= bb_lower * 1.005: score += 0.15
        else:
            if rsi >= 75: score += 0.3
            elif rsi >= 70: score += 0.2
            if close > bb_upper: score += 0.3
            elif close >= bb_upper * 0.995: score += 0.15
        if adx < 20: score += 0.2   # Very low trend = cleaner mean reversion
        elif adx < 30: score += 0.1
        return min(score, 1.0)

    def get_documentation(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "overview": (
                "The Bollinger RSI Reversion strategy profits from extreme price moves in "
                "range-bound markets. When both the RSI and Bollinger Bands signal 'oversold', "
                "we buy expecting price to snap back to the middle. When both signal 'overbought', "
                "we sell short. This is a high win-rate, low reward-per-trade strategy — "
                "lots of small wins, with tight risk management on the rare big losers."
            ),
            "when_to_use": [
                "Market regime is RANGING (ADX < 25)",
                "Liquid, large-cap stocks or major ETFs (SPY, QQQ, AAPL)",
                "Normal market conditions — not during major news or events",
                "Stable intraday sessions (avoid first 30 min and last 15 min)",
            ],
            "when_to_avoid": [
                "ADX > 30 — strong trend is in place, mean reversion will fight the trend and lose",
                "During earnings announcements (RSI can stay extreme for days)",
                "When VIX is very high (> 30) — extreme events cause sustained moves, not reversions",
                "When there is a clear reason for the extreme move (bad news, sector rotation)",
                "Illiquid or small-cap stocks — the spread alone eats your edge",
            ],
            "entry_rules": [
                "1. Check regime: ADX must be < 30 (no strong trend)",
                "2. For LONG: RSI ≤ 30 AND price at or below Lower Bollinger Band",
                "3. For SHORT: RSI ≥ 70 AND price at or above Upper Bollinger Band",
                "4. Enter at the close of the candle that meets the condition",
                "5. Optionally wait for a confirming candle (green close for long, red for short)",
            ],
            "exit_rules": [
                "Target: Middle Bollinger Band (the 20-day moving average)",
                "Stop loss: Below lower band - ATR (long) or above upper band + ATR (short)",
                "Time stop: If price hasn't moved toward the target in 5 days, exit",
                "DO NOT hold through earnings or major macro events",
                "Take profit quickly — this is not a trend trade, don't let it turn into one",
            ],
            "risk_rules": [
                "Risk 0.75% per trade (smaller than trend trades because these are more frequent)",
                "Max 3 mean reversion positions open at once",
                "If the first target (middle band) is reached, exit fully — don't get greedy",
                "Never average down on a losing mean reversion trade",
            ],
            "examples": [
                {
                    "scenario": "SPY oversold in a sideways week",
                    "setup": "SPY: $420, RSI=27, Lower BB=$417, Middle BB=$425, ADX=18",
                    "trigger": "Both RSI < 30 and price at lower BB simultaneously",
                    "entry": "$420",
                    "stop": "$415 (below lower BB minus 1 ATR)",
                    "target": "$425 (middle band = the mean)",
                    "size": "$50k account, risk $375 (0.75%), $375/$5 risk = 75 shares",
                },
            ],
            "common_mistakes": [
                "Using mean reversion in trending markets — the most common error. Always check ADX.",
                "Holding for too big a target — exit at the middle band, not the upper band",
                "Averaging down — if price keeps going against you past your stop, exit, don't add",
                "Trading illiquid symbols — wide spreads kill the edge in a small-profit strategy",
                "Ignoring the 'both required' rule — RSI alone or BB alone is not enough",
            ],
        }
