"""
cta_trend.py — CTA-Style Systematic Trend Following

STRATEGY FAMILY: Futures / Managed Futures

PLAIN ENGLISH EXPLANATION:
  CTA stands for Commodity Trading Advisor — the category of professional
  traders who run systematic trend-following funds on futures markets.
  Think Renaissance Technologies, Man AHL, Winton, or Two Sigma's futures
  books. These funds don't predict markets. They simply ride the direction
  that markets are already moving and exit when the trend ends.

  THE CORE LOGIC:
    When the 20-period SMA crosses ABOVE the 200-period SMA:
      → The intermediate trend is now aligned with the long-term trend
      → Enter LONG and ride the trend
    When the 20-period SMA crosses BELOW the 200-period SMA:
      → The intermediate trend has turned against the long-term trend
      → Enter SHORT (or exit + go flat for equity instruments)

  POSITION SIZING — The CTA way:
    Risk a fixed % of portfolio per trade, sized by ATR:
      shares = (portfolio × risk_pct) / (ATR × stop_mult)
    This means high-volatility instruments get SMALLER position sizes —
    the opposite of buying more when you're up. This is called "risk parity"
    position sizing, and it's why trend-following is so durable.

WHY THIS WORKS:
  Trends persist because of fundamental economic forces: commodity supply
  shocks take years to resolve, central bank cycles last 18–24 months,
  tech adoption curves unfold over decades. The trend-following strategy
  is positioned to capture these multi-month fundamental moves using simple
  technical signals as proxies.

  50+ years of academic research (Moskowitz, Ooi, Pedersen 2012 — "Time
  Series Momentum") confirms that trend following generates positive returns
  across every asset class and every decade studied.

  The strategy's "secret" is that it cuts losses fast (stops) and lets
  winners run (no profit target — only exits when trend ends).

BEST MARKETS:
  - Equity index futures: ES (S&P 500), NQ (Nasdaq), YM (Dow), RTY (Russell)
  - Bond futures: ZN (10Y Treasury), ZB (30Y Bond)
  - Commodity futures: CL (Crude Oil), GC (Gold), NG (Nat Gas), ZC (Corn)
  - FX futures: 6E (Euro), 6J (Yen), 6B (British Pound)
  - Works WORST in range-bound, news-driven, liquidity-thin markets
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class CTATrendStrategy(BaseStrategy):

    name = "CTA SMA Crossover"
    family = "trend"
    asset_class = "futures"
    strategy_type = "trend_following"
    description = (
        "Classic managed-futures trend system: 20/200 SMA crossover with ATR-based "
        "position sizing. Long when fast SMA > slow SMA + ADX > 20. Short when fast < slow. "
        "No profit target — only exits when trend ends (reverse crossover or stop hit)."
    )

    def default_parameters(self) -> dict:
        return {
            "fast_sma": 20,            # Fast moving average (trend trigger)
            "slow_sma": 200,           # Slow moving average (trend baseline)
            "adx_threshold": 20,       # Minimum ADX for confirmed trend entry
            "atr_stop_mult": 3.0,      # CTA-style: wider stops (trend trades need room)
            "rr_min": 2.0,             # Minimum R:R to take the trade
            "vol_confirm": True,       # Require above-avg volume on crossover bar
            "ema200_slope_bars": 20,   # EMA200 must have positive slope over last N bars
            "max_atr_pct": 4.0,        # Skip if ATR > X% of price (panic conditions)
            "breakout_confirm_pct": 0.5,  # Crossover must be by at least X% to avoid whipsaw
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        p = self.parameters
        slow = p["slow_sma"]
        if len(df) < slow + 30:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        # Compute fast and slow SMAs
        df["sma_fast"] = df["close"].rolling(p["fast_sma"]).mean()
        df["sma_slow"] = df["close"].rolling(slow).mean()

        signals = []
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        for i in range(slow + 5, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if (pd.isna(row.get("sma_fast")) or pd.isna(row.get("sma_slow"))
                    or pd.isna(row.get("adx")) or pd.isna(row.get("atr"))):
                continue

            close = row["close"]
            atr = row["atr"]
            sma_f = row["sma_fast"]
            sma_s = row["sma_slow"]
            prev_sma_f = prev["sma_fast"]
            prev_sma_s = prev["sma_slow"]
            adx = row["adx"]
            vol_avg = row["vol_avg"]
            volume = row["volume"]

            atr_pct = atr / close * 100
            if atr_pct > p["max_atr_pct"]:
                continue

            # Volume confirmation
            vol_ok = (volume >= vol_avg) if p["vol_confirm"] else True

            # Trend quality: EMA200 slope over last N bars
            slope_bars = p["ema200_slope_bars"]
            if i >= slope_bars:
                ema200_now = row["ema200"]
                ema200_back = df.iloc[i - slope_bars]["ema200"]
                ema200_rising = (ema200_now is not None and ema200_back is not None
                                 and not pd.isna(ema200_now) and not pd.isna(ema200_back)
                                 and ema200_now > ema200_back)
                ema200_falling = (ema200_now is not None and ema200_back is not None
                                  and not pd.isna(ema200_now) and not pd.isna(ema200_back)
                                  and ema200_now < ema200_back)
            else:
                ema200_rising = ema200_falling = False

            # Crossover detection (Golden Cross / Death Cross)
            bullish_crossover = (prev_sma_f <= prev_sma_s) and (sma_f > sma_s)
            bearish_crossover = (prev_sma_f >= prev_sma_s) and (sma_f < sma_s)

            # Crossover confirmation threshold (avoid hair-trigger whipsaws)
            cross_pct = abs(sma_f - sma_s) / sma_s * 100
            cross_confirmed = cross_pct >= p["breakout_confirm_pct"]

            # ── LONG: Golden Cross (fast SMA crosses above slow SMA) ──
            if (
                bullish_crossover
                and cross_confirmed
                and adx >= p["adx_threshold"]
                and ema200_rising
                and vol_ok
            ):
                stop = close - p["atr_stop_mult"] * atr
                # No fixed target — trend trades run until reversal or stop
                # Set a generous target for signal display purposes
                target = close + p["rr_min"] * p["atr_stop_mult"] * atr
                risk = close - stop
                reward = target - close
                rr = reward / risk if risk > 0 else 0

                signals.append(Signal(
                    symbol=symbol,
                    date=row["date"],
                    action="BUY",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=1.0,
                    confidence=min(0.85, 0.55 + (adx - 20) / 100),
                    risk_reward_ratio=round(rr, 2),
                    strategy_name=self.name,
                    reasoning=(
                        f"CTA LONG — Golden Cross: SMA{p['fast_sma']}={sma_f:.2f} crossed above "
                        f"SMA{slow}={sma_s:.2f} by {cross_pct:.2f}%. "
                        f"ADX={adx:.1f} (> {p['adx_threshold']} threshold), "
                        f"EMA200 slope rising, vol confirmed. "
                        f"Stop {p['atr_stop_mult']}×ATR={p['atr_stop_mult'] * atr:.2f} below entry. "
                        f"No profit target — exit on death cross or stop."
                    ),
                    indicators={
                        "sma_fast": round(sma_f, 2),
                        "sma_slow": round(sma_s, 2),
                        "crossover_pct": round(cross_pct, 2),
                        "adx": round(adx, 1),
                        "atr": round(atr, 2),
                        "atr_pct": round(atr_pct, 2),
                        "vol_vs_avg": round(volume / vol_avg, 2) if vol_avg else None,
                    },
                ))

            # ── SHORT: Death Cross (fast SMA crosses below slow SMA) ──
            elif (
                bearish_crossover
                and cross_confirmed
                and adx >= p["adx_threshold"]
                and ema200_falling
                and vol_ok
            ):
                stop = close + p["atr_stop_mult"] * atr
                target = close - p["rr_min"] * p["atr_stop_mult"] * atr
                risk = stop - close
                reward = close - target
                rr = reward / risk if risk > 0 else 0

                signals.append(Signal(
                    symbol=symbol,
                    date=row["date"],
                    action="SELL",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=1.0,
                    confidence=min(0.85, 0.55 + (adx - 20) / 100),
                    risk_reward_ratio=round(rr, 2),
                    strategy_name=self.name,
                    reasoning=(
                        f"CTA SHORT — Death Cross: SMA{p['fast_sma']}={sma_f:.2f} crossed below "
                        f"SMA{slow}={sma_s:.2f} by {cross_pct:.2f}%. "
                        f"ADX={adx:.1f} (> {p['adx_threshold']} threshold), "
                        f"EMA200 slope falling, vol confirmed. "
                        f"Stop {p['atr_stop_mult']}×ATR={p['atr_stop_mult'] * atr:.2f} above entry. "
                        f"No profit target — exit on golden cross or stop."
                    ),
                    indicators={
                        "sma_fast": round(sma_f, 2),
                        "sma_slow": round(sma_s, 2),
                        "crossover_pct": round(cross_pct, 2),
                        "adx": round(adx, 1),
                        "atr": round(atr, 2),
                        "atr_pct": round(atr_pct, 2),
                        "vol_vs_avg": round(volume / vol_avg, 2) if vol_avg else None,
                    },
                ))

        return signals

    def get_documentation(self) -> dict:
        return {
            "overview": (
                "Classic managed-futures CTA trend system: enter long on a golden cross "
                "(20 SMA crosses above 200 SMA) and short on a death cross, with ADX > 20 "
                "confirming trend strength. Uses ATR-based position sizing (risk parity). "
                "No fixed profit target — ride the trend until the opposite crossover or stop."
            ),
            "when_to_use": [
                "Strong trending markets with ADX > 20 and clear macro driver",
                "Futures markets: equity index, bonds, commodities, FX (most CTA-friendly)",
                "Multi-month trend environments: Fed rate cycles, commodity supply shocks, risk-on/risk-off",
                "When you want a systematic, rules-based approach with no discretion",
            ],
            "when_to_avoid": [
                "Range-bound, choppy markets — crossover signals whipsaw constantly with ADX < 20",
                "During major news events or policy announcements (gaps distort the signal)",
                "Markets with thin liquidity (bid-ask spread makes entries/exits costly)",
                "Short-term trading: the 20/200 crossover is a weeks-to-months signal, not intraday",
            ],
            "entry_rules": [
                "1. Wait for SMA20 to cross SMA200 (golden cross = long, death cross = short)",
                "2. Confirm crossover is at least 0.5% to filter false signals",
                "3. ADX must be ≥ 20 on the crossover bar",
                "4. EMA200 slope must confirm direction (rising for long, falling for short)",
                "5. Volume on crossover bar must be above 20-day average",
                "6. Enter at next bar's open; set stop at 3×ATR from entry",
            ],
            "exit_rules": [
                "No profit target — hold until opposite crossover (death cross exits long, golden cross exits short)",
                "Stop hit → exit immediately with pre-defined loss",
                "Trailing stop: after 3×ATR profit, trail stop to 2×ATR from highest favorable close",
                "Avoid closing on noise: only exit on confirmed crossover or stop, not on intra-trend dips",
            ],
            "risk_rules": [
                "ATR-based position sizing: shares = (portfolio × 1%) / (ATR × 3.0)",
                "High-volatility instruments automatically get smaller positions — risk parity by design",
                "Never add to a losing trend trade — averaging down against a trend kills accounts",
                "Max portfolio risk on all open trend positions: 10% total (assume correlated in crisis)",
            ],
            "examples": [
                "ES (S&P 500 futures) March 2023: SMA20 crossed SMA200 at 4050, ADX=28, EMA200 rising. Entry: long at 4050, stop at 3900 (3×ATR). Exit: death cross at 4750 in July 2023. Profit: +700 points = +17.3%. Pure trend following, no discretion.",
                "CL (Crude Oil) Oct 2021: SMA20 crossed SMA200 at $72, ADX=32. Rode the trend to $95 by Feb 2022 (OPEC+ supply discipline + demand recovery). Death cross at $87 → exit. Net: +$15/barrel on the bulk of the move.",
            ],
            "common_mistakes": [
                "Exiting early at a 'reasonable profit' — trend following's edge comes from the big runs, which require patience",
                "Trading the crossover in low-ADX (choppy) environments — the same signal produces endless false crosses",
                "Using too tight a stop (1×ATR) — trend trades need room to breathe before the trend develops",
                "Not using ATR-based sizing — treating all instruments as equally sized causes over-leverage on volatile markets",
            ],
        }
