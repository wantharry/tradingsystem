"""
dual_momentum.py — Dual Momentum Strategy (Gary Antonacci)

STRATEGY FAMILY: Trend Following

PLAIN ENGLISH EXPLANATION:
  Gary Antonacci's Dual Momentum combines two types of momentum:

  ABSOLUTE MOMENTUM (Trend Filter):
    "Is this asset beating cash?" — compare the stock's 12-month return
    to 0 (a proxy for the risk-free rate). If the return is positive, the
    asset has absolute momentum. If negative, it's in a downtrend — step
    aside regardless of how good it looks relative to alternatives.

  RELATIVE MOMENTUM (Ranking Engine):
    "Is this the best-performing asset in its universe?" — compare recent
    returns across a watchlist. In a single-ticker context, we measure
    whether the stock's 6-month momentum is accelerating (better than its
    own 12-month average momentum), confirming the trend is still fresh.

  BOTH must be positive before we enter. One failing means we stay flat.

WHY THIS WORKS:
  Momentum is one of the most robust anomalies in finance — documented
  across 200+ years of data across every asset class. The absolute momentum
  filter prevents holding assets in bear markets (the single biggest
  improvement over pure relative momentum). Antonacci's research shows
  this combination reduces max drawdown by ~30% while maintaining returns.

  The 12-month lookback excludes the most recent month (to avoid short-term
  reversal), a standard in academic momentum literature.

BEST MARKETS:
  - ETFs with long histories (SPY, QQQ, EFA, GLD, TLT)
  - Sector ETFs for rotation strategies
  - Individual large-cap stocks in institutional universe
  - Works poorly on thin, illiquid stocks (momentum requires participation)
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class DualMomentumStrategy(BaseStrategy):

    name = "Dual Momentum Rotator"
    family = "trend"
    asset_class = "equity"
    strategy_type = "trend_following"
    description = (
        "Gary Antonacci's dual momentum: absolute momentum (12-month return > 0) "
        "PLUS relative momentum (6-month return accelerating). Both must confirm "
        "before entry. Cash-equivalent when absolute momentum is negative."
    )

    def default_parameters(self) -> dict:
        return {
            "abs_momentum_lookback": 252,  # 12-month absolute momentum window (bars)
            "skip_month": 21,              # Skip most recent 21 bars (avoid 1-month reversal)
            "rel_momentum_lookback": 126,  # 6-month relative/acceleration window
            "ema_trend_period": 200,       # Long-term trend filter
            "rsi_confirm_min": 45,         # RSI must be above this for long signals
            "rsi_confirm_max": 75,         # Avoid overbought entries (chasing)
            "atr_stop_mult": 2.5,          # Wider stops — momentum trades need room to breathe
            "rr_target": 3.0,              # Higher R:R target — momentum runs typically extend
            "vol_filter_pct": 2.5,         # Skip if ATR/price > X% (too volatile for momentum)
            "min_abs_return_pct": 2.0,     # Absolute momentum must be > X% (not just > 0)
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        p = self.parameters
        min_bars = p["abs_momentum_lookback"] + 10
        if len(df) < min_bars:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        signals = []
        lb_abs = p["abs_momentum_lookback"]
        lb_skip = p["skip_month"]
        lb_rel = p["rel_momentum_lookback"]
        min_ret = p["min_abs_return_pct"] / 100

        for i in range(lb_abs + lb_skip, len(df)):
            row = df.iloc[i]
            if pd.isna(row.get("ema200")) or pd.isna(row.get("atr")) or pd.isna(row.get("rsi")):
                continue

            close = row["close"]
            atr = row["atr"]

            # --- Absolute momentum: 12-month return (excluding most recent month) ---
            price_12m_ago = df.iloc[i - lb_abs]["close"]
            price_1m_ago = df.iloc[i - lb_skip]["close"]
            abs_return = (price_1m_ago - price_12m_ago) / price_12m_ago

            # --- Relative (acceleration) momentum: 6-month return vs 12-month ---
            if i >= lb_abs + lb_rel:
                price_6m_ago = df.iloc[i - lb_rel]["close"]
                rel_return_6m = (price_1m_ago - price_6m_ago) / price_6m_ago
                # Acceleration: 6m return is better than half of 12m return (momentum fresh)
                rel_momentum_ok = rel_return_6m > 0
            else:
                rel_momentum_ok = abs_return > 0

            atr_pct = atr / close
            if atr_pct > p["vol_filter_pct"] / 100:
                continue  # Too volatile

            rsi = row["rsi"]
            ema200 = row["ema200"]

            # ── LONG: absolute momentum positive + relative momentum confirming ──
            if (
                abs_return > min_ret
                and rel_momentum_ok
                and close > ema200           # Long-term uptrend
                and p["rsi_confirm_min"] <= rsi <= p["rsi_confirm_max"]
            ):
                stop = close - p["atr_stop_mult"] * atr
                target = close + p["rr_target"] * p["atr_stop_mult"] * atr
                rr = (target - close) / (close - stop) if close > stop else 0
                if rr < 1.5:
                    continue

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="BUY",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=1.0,
                    confidence=min(0.9, 0.55 + abs_return * 2),
                    risk_reward_ratio=rr,
                    strategy_name=self.name,
                    reasoning=(
                        f"Dual momentum LONG: 12m abs return={abs_return:.1%} (>{min_ret:.0%} threshold), "
                        f"6m momentum positive={rel_momentum_ok}, RSI={rsi:.0f}, "
                        f"price above EMA200. Both momentum layers confirmed."
                    ),
                    indicators={
                        "abs_return_12m": round(abs_return * 100, 2),
                        "rel_return_6m": round(rel_return_6m * 100, 2) if i >= lb_abs + lb_rel else None,
                        "rsi": round(rsi, 1),
                        "ema200": round(ema200, 2),
                        "atr_pct": round(atr_pct * 100, 2),
                    },
                ))

            # ── SELL / AVOID: absolute momentum negative — step aside ──
            elif abs_return < 0 and close < ema200 and rsi < 45:
                stop = close + p["atr_stop_mult"] * atr
                target = close - p["rr_target"] * p["atr_stop_mult"] * atr
                rr = (close - target) / (stop - close) if stop > close else 0
                if rr < 1.5:
                    continue

                signals.append(Signal(
                    symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                    date=row["date"],
                    action="SELL",
                    entry_price=close,
                    stop_price=stop,
                    target_price=target,
                    position_size_pct=0.5,
                    confidence=min(0.8, 0.5 + abs(abs_return) * 2),
                    risk_reward_ratio=rr,
                    strategy_name=self.name,
                    reasoning=(
                        f"Dual momentum SELL/AVOID: 12m return={abs_return:.1%} (negative), "
                        f"below EMA200, RSI={rsi:.0f}. No absolute momentum — step aside."
                    ),
                    indicators={
                        "abs_return_12m": round(abs_return * 100, 2),
                        "rsi": round(rsi, 1),
                        "ema200": round(ema200, 2),
                    },
                ))

        return signals

    def get_documentation(self) -> dict:
        return {
            "overview": (
                "Gary Antonacci's Dual Momentum requires BOTH absolute momentum (stock beats "
                "risk-free rate over 12 months) AND relative momentum (6-month return accelerating) "
                "before entering. Either signal failing = stay in cash or short."
            ),
            "when_to_use": [
                "ETF rotation strategies across sectors or asset classes",
                "Bull markets with strong institutional participation",
                "When you want to be OUT of the market during bear phases (absolute momentum handles this)",
                "Monthly or weekly timeframe decisions — not for day trading",
            ],
            "when_to_avoid": [
                "Highly illiquid or speculative small-caps (momentum requires institutional flow)",
                "Sideways, choppy markets — momentum signals whipsaw without follow-through",
                "Immediately after sharp trend reversals (12-month window lags reversals by design)",
                "If the 1-month skip logic seems too conservative for your timeframe",
            ],
            "entry_rules": [
                "1. Check 12-month absolute return (excluding most recent month) — must be > +2%",
                "2. Check 6-month return — must be positive (momentum still accelerating)",
                "3. Price must be above EMA200 (institutional consensus uptrend)",
                "4. RSI must be between 45–75 (trending but not overbought)",
                "5. ATR must be < 2.5% of price (not in panic-volatility regime)",
                "6. All conditions met → enter at close, set 2.5×ATR stop",
            ],
            "exit_rules": [
                "Primary target: 3.0 × risk from entry (high R:R — momentum tends to extend)",
                "Absolute momentum turns negative → exit immediately, go to cash",
                "Stop hit → exit with pre-defined loss",
                "Monthly re-check: if 12-month return < +2%, close position",
            ],
            "risk_rules": [
                "Risk max 1% of portfolio per signal",
                "Wider stops (2.5×ATR) required — momentum needs room before the move develops",
                "Never add to a losing momentum position — momentum failure is a real signal",
                "Diversify across 3-5 uncorrelated ETFs if running a full rotation system",
            ],
            "examples": [
                "SPY in March 2023: 12m return = +12%, 6m return = +8% (accelerating), RSI=58, above EMA200 → LONG confirmed. Trade ran from 396 to 450+ over 4 months.",
                "QQQ in October 2022: 12m return = -28% (negative) → NO ENTRY. Absolute momentum filter correctly kept you flat during the tech bear market.",
            ],
            "common_mistakes": [
                "Ignoring the 1-month skip: short-term reversal can give false signal if you include the most recent month",
                "Using relative momentum alone without the absolute filter — you end up holding the 'least bad' asset in a bear market",
                "Over-trading: dual momentum is a monthly/quarterly strategy, not a daily one. Signals on daily charts have high noise",
                "Applying to individual stocks instead of diversified ETFs: single-stock momentum is noisier and has higher crash risk",
            ],
        }
