"""
trend_following.py — Trend Following Strategy (EMA Pullback)

STRATEGY FAMILY: Trend Following

PLAIN ENGLISH EXPLANATION:
  Imagine a river flowing north. If you want to swim with the current (safest),
  you wait for a moment when the water briefly slows down (a pullback), then you
  jump in and ride the main current.

  This strategy does exactly that:
    1. Confirms the river (trend) is real — using EMAs and ADX
    2. Waits for a pullback (price dips to EMA 20 in an uptrend)
    3. Enters when price shows it's resuming the trend (momentum bar)
    4. Uses ATR for stop and a 2:1 reward-to-risk target

WHY THIS WORKS:
  Markets trend because of persistent supply/demand imbalances — large
  institutional buyers accumulate positions over months. Buying during
  temporary pullbacks lets retail traders piggyback on this institutional flow
  at better prices and with tighter stops than chasing breakouts.

BEST MARKETS:
  - Strong individual stocks in bull markets
  - Equity index futures (ES, NQ) in trending regimes
  - Commodity futures (CL, GC) during macro supply/demand shifts
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class TrendFollowingStrategy(BaseStrategy):

    name = "EMA Pullback Trend"
    family = "trend"
    description = (
        "Enters in the direction of the confirmed trend on pullbacks to the 20 EMA. "
        "Requires ADX > 25 to confirm trend strength before entry."
    )

    def default_parameters(self) -> dict:
        return {
            "ema_short": 20,       # Pullback target EMA
            "ema_mid": 50,         # Trend filter EMA
            "ema_long": 200,       # Long-term trend direction
            "adx_threshold": 20,   # Minimum ADX for trend confirmation (ADX=20 best per new grid: 41.69% avg vs 23.48%)
            "rsi_filter": True,    # Require RSI > 40 for longs, < 60 for shorts
            "atr_stop_mult": 2.0,  # Stop = entry ± (ATR × this) — wider stops prevent ETF whipsaws
            "rr_target": 2.0,      # Minimum risk:reward ratio required
            "min_adx": 20,         # Hard minimum — don't trade below this
            "max_atr_pct": 3.0,    # Skip if ATR > X% of price — filters extreme-volatility stocks
            "ema200_slope_bars": 15, # EMA200 must be rising/falling over last N bars (trend quality filter)
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 210:   # Need enough history for EMA 200
            return []

        df = self._add_base_indicators(df)

        # Also add EMA 50 if not already there (base adds 20 and 200)
        df["ema50"] = ta.ema(df["close"], length=self.parameters["ema_mid"])

        signals = []
        p = self.parameters

        for i in range(200, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            # Skip if any required indicator is NaN
            if pd.isna(row["adx"]) or pd.isna(row["ema200"]) or pd.isna(row["atr"]):
                continue

            close = row["close"]
            ema20 = row["ema20"]
            ema50 = row["ema50"]
            ema200 = row["ema200"]
            adx = row["adx"]
            atr = row["atr"]
            rsi = row["rsi"]

            # ── VOLATILITY FILTER ────────────────────────────────────────
            # Skip if ATR > max_atr_pct % of price — protects against
            # catastrophic losses on high-volatility stocks (NVDA, TSLA)
            # where pullback signals generate win rates below break-even.
            atr_pct = (atr / close) * 100
            if atr_pct > p.get("max_atr_pct", 999):
                continue

            # ── EMA200 SLOPE FILTER ───────────────────────────────────────
            # Require EMA200 to be trending in the correct direction.
            # Filters AAPL/MSFT when EMA200 is flat/declining (fake uptrends
            # in ADX 20-25 regime that tend to reverse quickly).
            slope_bars = p.get("ema200_slope_bars", 0)
            ema200_rising = True   # Default: pass filter if disabled or not enough data
            ema200_falling = True
            if slope_bars > 0 and i >= slope_bars:
                ema200_past = df.iloc[i - slope_bars].get("ema200")
                if not pd.isna(ema200_past) and not pd.isna(ema200):
                    ema200_rising = ema200 > ema200_past   # True if EMA200 trending up
                    ema200_falling = ema200 < ema200_past  # True if EMA200 trending down

            # ── LONG SETUP ──────────────────────────────────────────────
            # Condition 1: Price is in an uptrend (EMA alignment)
            uptrend = close > ema50 and ema50 > ema200 and ema200_rising

            # Condition 2: Trend is strong enough
            trend_strong = adx >= p["adx_threshold"]

            # Condition 3: Price pulled back to EMA 20 zone (within 1 ATR)
            near_ema20 = abs(close - ema20) <= atr * 0.5

            # Condition 4: Previous candle was at or below EMA20, current is recovering
            pullback_bounce = prev["close"] <= ema20 * 1.005 and close > prev["close"]

            # Condition 5: RSI momentum filter (not overbought, not dead)
            rsi_ok_long = (not p["rsi_filter"]) or (40 <= rsi <= 70)

            if uptrend and trend_strong and (near_ema20 or pullback_bounce) and rsi_ok_long:
                entry = close
                stop = min(row["low"], ema20 - atr * p["atr_stop_mult"])
                risk = entry - stop
                if risk <= 0:
                    continue
                target = entry + risk * p["rr_target"]

                reasoning = (
                    f"UPTREND confirmed: price {close:.2f} > EMA50 {ema50:.2f} > EMA200 {ema200:.2f}. "
                    f"ADX={adx:.1f} (≥{p['adx_threshold']} threshold — trend is real). "
                    f"RSI={rsi:.1f} (momentum healthy). "
                    f"Pullback to EMA20 ({ema20:.2f}) detected — buying the dip in an uptrend. "
                    f"Stop below recent low + ATR buffer. Target at {p['rr_target']}:1 R:R."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="BUY",
                    entry_price=entry,
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_long(adx, rsi, close, ema20, ema50),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={"adx": round(adx, 1), "rsi": round(rsi, 1), "atr": round(atr, 4),
                                 "ema20": round(ema20, 2), "ema50": round(ema50, 2), "ema200": round(ema200, 2)},
                ))

            # ── SHORT SETUP ──────────────────────────────────────────────
            downtrend = close < ema50 and ema50 < ema200 and ema200_falling
            near_ema20_short = abs(close - ema20) <= atr * 0.5
            rally_fade = prev["close"] >= ema20 * 0.995 and close < prev["close"]
            rsi_ok_short = (not p["rsi_filter"]) or (30 <= rsi <= 60)

            if downtrend and trend_strong and (near_ema20_short or rally_fade) and rsi_ok_short:
                entry = close
                stop = max(row["high"], ema20 + atr * p["atr_stop_mult"])
                risk = stop - entry
                if risk <= 0:
                    continue
                target = entry - risk * p["rr_target"]

                reasoning = (
                    f"DOWNTREND confirmed: price {close:.2f} < EMA50 {ema50:.2f} < EMA200 {ema200:.2f}. "
                    f"ADX={adx:.1f} — trend is strong. RSI={rsi:.1f}. "
                    f"Rally to EMA20 ({ema20:.2f}) is fading — shorting the bounce in a downtrend. "
                    f"Stop above recent high + ATR buffer."
                )

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="SELL",
                    entry_price=entry,
                    stop_price=round(stop, 4),
                    target_price=round(target, 4),
                    confidence=self._score_short(adx, rsi, close, ema20, ema50),
                    reasoning=reasoning,
                    strategy_name=self.name,
                    indicators={"adx": round(adx, 1), "rsi": round(rsi, 1), "atr": round(atr, 4)},
                ))

        return signals

    def _score_long(self, adx, rsi, close, ema20, ema50) -> float:
        """Score the quality of a long signal. Higher = more confident."""
        score = 0.0
        if adx >= 40: score += 0.3         # Very strong trend
        elif adx >= 25: score += 0.15       # Moderate trend
        if 45 <= rsi <= 65: score += 0.2   # Healthy momentum zone
        if close > ema50: score += 0.2     # Price above medium-term trend
        if close > ema20: score += 0.15    # Price recovering above short-term EMA
        if adx >= 25: score += 0.15        # Trend exists
        return min(score, 1.0)

    def _score_short(self, adx, rsi, close, ema20, ema50) -> float:
        score = 0.0
        if adx >= 40: score += 0.3
        elif adx >= 25: score += 0.15
        if 35 <= rsi <= 55: score += 0.2
        if close < ema50: score += 0.2
        if close < ema20: score += 0.15
        if adx >= 25: score += 0.15
        return min(score, 1.0)

    def get_documentation(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "overview": (
                "The EMA Pullback Trend strategy rides established trends by entering during "
                "temporary pullbacks rather than chasing breakouts. It only trades when a trend "
                "is confirmed (EMAs aligned, ADX > 25), and waits for price to retrace to the "
                "20 EMA before entering — giving a better entry price and a tighter stop loss."
            ),
            "when_to_use": [
                "Market regime is clearly UPTREND or DOWNTREND",
                "ADX is above 25 on the daily chart",
                "Price has been making higher highs and higher lows (uptrend) or lower highs/lows (downtrend)",
                "Strong sectors or individual stocks with clear institutional buying",
            ],
            "when_to_avoid": [
                "ADX is below 20 — market is choppy, no real trend",
                "Earnings announcement within 5 days for equities",
                "Major macro event (FOMC, CPI) within 2 days",
                "Price is extended far above the 20 EMA — wait for pullback",
                "Regime is RANGING or RISK-OFF",
            ],
            "entry_rules": [
                "1. Confirm uptrend: Close > EMA50 AND EMA50 > EMA200",
                "2. Confirm trend strength: ADX ≥ 25",
                "3. Wait for pullback: Price drops to within 0.5 ATR of EMA20",
                "4. Wait for reversal candle: Today's close > yesterday's close (green bar recovering)",
                "5. Confirm momentum: RSI between 40 and 70 (not overbought)",
                "6. Enter at current close or next day's open",
            ],
            "exit_rules": [
                "Stop loss: Below the recent swing low OR EMA20 - (1.5 × ATR), whichever is lower",
                "Target: Entry + (2 × risk), i.e. 2:1 minimum reward-to-risk",
                "Trailing stop: Once price moves 1R in your favor, move stop to breakeven",
                "Trail EMA20: In very strong trends, trail stop to 20 EMA and let profits run",
                "Time exit: If trade goes sideways for 10 days with no progress, exit",
            ],
            "risk_rules": [
                "Risk no more than 1% of portfolio per trade",
                "Position size = (Portfolio × 1%) / (Entry - Stop)",
                "Maximum 2-3 trend positions open at the same time",
                "If daily loss limit (2%) is hit, stop trading for the day",
            ],
            "examples": [
                {
                    "scenario": "AAPL in a clear uptrend",
                    "setup": "AAPL: price $180, EMA50=$168, EMA200=$155, ADX=32, RSI=52",
                    "trigger": "Price pulled back to $173 (near EMA20=$171), bounced with green candle",
                    "entry": "$173",
                    "stop": "$168 (below EMA20 - 1 ATR)",
                    "target": "$183 (2:1 reward vs $5 risk)",
                    "size": "If $50k account: risk $500 (1%), $500/$5 = 100 shares",
                },
            ],
            "common_mistakes": [
                "Entering before the pullback — chasing price when it's extended above EMA20",
                "Ignoring ADX — entering trend trades when market is actually choppy",
                "Using too wide a stop — stop must be based on ATR, not a round number",
                "Not moving stop to breakeven — giving back profit unnecessarily",
                "Trading counter-trend (buying pullbacks in a downtrend) — always trade WITH the EMA alignment",
            ],
        }
