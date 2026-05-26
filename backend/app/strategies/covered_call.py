"""
covered_call.py — Covered Call Writer Strategy

STRATEGY FAMILY: Options Income (Covered Calls)

PLAIN ENGLISH EXPLANATION:
  A covered call means you own 100 shares of a stock and sell someone
  else the RIGHT (but not obligation) to buy those shares from you at
  a fixed price (the strike) before a set date (expiration).

  You get PAID a premium upfront for selling that right. If the stock
  stays below your strike price, the option expires worthless and you
  keep ALL the premium — free income on your existing position.
  If the stock surges past your strike, you sell your shares at the
  strike price (you still profit, just capped).

  THE OPTIMAL SETUP (Delta ~0.20–0.30, 30–45 DTE):
    - Sell the call with a strike roughly 5–8% above current price
    - At expiration 30–45 days later, if price < strike → full premium kept
    - If price > strike → stock gets called away at a profit + premium

  THIS STRATEGY SIGNALS:
    When conditions are ideal for writing a new covered call position:
    stock is in a mild uptrend, not overbought, implied volatility (proxied
    by ATR/price ratio) is elevated enough to make premium worth collecting.

WHY THIS WORKS:
  Options sellers have a structural edge: time decay (theta) works FOR you
  every day you hold the short call. 70–80% of options expire worthless
  historically. By selling premium when IV is elevated and collecting
  theta decay, covered call writers earn consistent income regardless of
  whether the stock makes a big move.

  The covered call caps upside but dramatically smooths portfolio returns
  — the CBOE BuyWrite Index (systematic covered calls on SPX) has matched
  buy-and-hold returns with 30% less volatility over 30+ years.

BEST MARKETS:
  - Stable, slowly rising large-cap stocks (AAPL, MSFT, JPM)
  - Sector ETFs (XLK, XLF, XLV) — diversified, liquid options chains
  - Ranging to mildly bullish regimes — not strong uptrends (you'd be capped)
  - When IV rank is elevated (ATR > 1.5% of price) — more premium to collect
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class CoveredCallStrategy(BaseStrategy):

    name = "Monthly Covered Call Writer"
    family = "options"
    asset_class = "options"
    strategy_type = "covered_calls"
    description = (
        "Identifies ideal conditions to write covered calls: stock above EMA50 "
        "(mild uptrend), RSI 40–65 (not overbought), and elevated IV proxy (ATR > 1.5% "
        "of price). Signals the entry to buy 100 shares and sell the 30-delta OTM call."
    )

    def default_parameters(self) -> dict:
        return {
            "atr_iv_min_pct": 1.5,      # ATR/price minimum (IV proxy) — need enough premium
            "atr_iv_max_pct": 4.0,      # ATR/price maximum — too volatile = unsafe to write
            "rsi_min": 40,              # Stock must not be oversold (calls have no value)
            "rsi_max": 65,              # Stock must not be overbought (don't cap near blow-off)
            "call_otm_pct": 5.0,        # Strike = close × (1 + this/100) — 5% OTM
            "ema_trend_period": 50,     # Stock must be above this EMA (mild uptrend required)
            "ema_long_period": 200,     # Don't write calls in a bear market (below 200 EMA)
            "adx_max": 30,              # Avoid strong trends — covered calls underperform in rallies
            "premium_est_pct": 1.2,     # Estimated premium as % of underlying (conservative)
            "stop_pct": 5.0,            # Stop the equity position at X% below entry
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        p = self.parameters
        if len(df) < 210:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        signals = []
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        for i in range(205, len(df)):
            row = df.iloc[i]
            if pd.isna(row.get("ema200")) or pd.isna(row.get("atr")) or pd.isna(row.get("rsi")):
                continue

            close = row["close"]
            atr = row["atr"]
            rsi = row["rsi"]
            ema50 = row["ema50"]
            ema200 = row["ema200"]
            adx = row["adx"]

            # IV proxy: ATR as percentage of price
            atr_pct = atr / close * 100

            # ── CONDITIONS: ideal covered call setup ──
            iv_in_range = p["atr_iv_min_pct"] <= atr_pct <= p["atr_iv_max_pct"]
            rsi_in_range = p["rsi_min"] <= rsi <= p["rsi_max"]
            mild_uptrend = close > ema50           # Above 50 EMA (mild bullish bias)
            not_bear_mkt = close > ema200          # Above 200 EMA (not in bear market)
            not_too_trendy = adx <= p["adx_max"]  # Avoid strong trending moves

            if not (iv_in_range and rsi_in_range and mild_uptrend and not_bear_mkt and not_too_trendy):
                continue

            # ── SIGNAL: write the covered call ──
            # "Entry" = buy 100 shares at close (the covered leg)
            # "Target" = call strike price (where we'd be happy to sell shares)
            strike = round(close * (1 + p["call_otm_pct"] / 100), 2)
            stop = round(close * (1 - p["stop_pct"] / 100), 2)
            estimated_premium = close * p["premium_est_pct"] / 100

            # Effective yield: premium / equity at risk
            net_target = strike + estimated_premium
            risk = close - stop
            reward = net_target - close

            if risk <= 0 or reward / risk < 1.0:
                continue

            signals.append(Signal(
                symbol=symbol,
                date=row["date"],
                action="BUY",     # Buy 100 shares (covered leg) + sell 30-delta call
                entry_price=close,
                stop_price=stop,
                target_price=strike,
                position_size_pct=1.0,
                confidence=min(0.80, 0.55 + (rsi - 40) / 100 + (atr_pct - 1.5) / 20),
                risk_reward_ratio=round(reward / risk, 2),
                strategy_name=self.name,
                reasoning=(
                    f"Covered call setup: buy 100 shares at {close:.2f}, sell ~{strike:.2f} "
                    f"call (5% OTM, ~30 delta, 30–45 DTE). "
                    f"IV proxy (ATR%)={atr_pct:.1f}% (in sweet spot {p['atr_iv_min_pct']}–{p['atr_iv_max_pct']}%), "
                    f"RSI={rsi:.0f}, above EMA50={ema50:.2f} + EMA200={ema200:.2f}. "
                    f"Est. monthly premium ~${estimated_premium:.2f}/share ({p['premium_est_pct']}%)."
                ),
                indicators={
                    "call_strike": strike,
                    "estimated_premium_per_share": round(estimated_premium, 2),
                    "atr_pct": round(atr_pct, 2),
                    "rsi": round(rsi, 1),
                    "adx": round(adx, 1),
                    "ema50": round(ema50, 2),
                    "ema200": round(ema200, 2),
                    "call_otm_pct": p["call_otm_pct"],
                },
            ))

        return signals

    def get_documentation(self) -> dict:
        return {
            "overview": (
                "Identifies ideal conditions to write covered calls: stock in mild uptrend "
                "(above EMA50 and EMA200), not overbought (RSI 40–65), and with elevated IV "
                "proxy (ATR > 1.5% of price). When all conditions align, buy 100 shares and "
                "sell the ~30-delta call 30–45 days to expiration."
            ),
            "when_to_use": [
                "Ranging to mildly bullish markets (ADX < 30, mild uptrend confirmed)",
                "When IV rank is elevated (30%+) — selling elevated IV is the edge",
                "Large-cap stocks you are comfortable owning if the stock gets called away",
                "Monthly income generation during flat or slow-grind-up regimes",
            ],
            "when_to_avoid": [
                "Strong bull markets with ADX > 30 — you'll be capped on the big winners",
                "Bear markets (below EMA200) — buying shares to cover a call is dangerous",
                "Earnings-imminent stocks — IV crush after earnings can distort the trade",
                "Low-IV environments (ATR < 1.5%) — premium is too thin to be worth it",
            ],
            "entry_rules": [
                "1. Stock must be above both EMA50 and EMA200",
                "2. RSI must be 40–65 (mild strength but not overbought)",
                "3. ATR/price must be 1.5–4.0% (enough IV for meaningful premium)",
                "4. ADX must be ≤ 30 (not in a strong trend that will run past your strike)",
                "5. Buy 100 shares at market close",
                "6. Immediately sell the call: strike = close × 1.05 (5% OTM), expiry 30–45 DTE",
            ],
            "exit_rules": [
                "Expiration: if stock < strike, call expires worthless — keep full premium, repeat next month",
                "Stock called away: if stock > strike at expiry, sell shares at strike + keep premium",
                "Early buy-back: if call loses 50% of its value before expiry, buy it back and keep the gain",
                "Stop on equity: if stock drops > 5% from entry, exit the entire position (shares + call)",
                "Roll: if stock approaches strike mid-cycle, roll call up and out 30 days for net credit",
            ],
            "risk_rules": [
                "Max 5% of portfolio in a single covered call position (100 shares is a large notional)",
                "Only write calls on stocks you want to OWN — the covered leg is real equity risk",
                "Never write naked calls (uncovered) — this strategy requires the shares as collateral",
                "Avoid writing calls on stocks with pending binary events (earnings, FDA, mergers)",
            ],
            "examples": [
                "AAPL at $175: RSI=55, ATR=2.8% (elevated), above EMA50=$168. Sell the $184 call (5% OTM) for $2.10 premium → 1.2% monthly yield. If AAPL < $184 at expiry: keep $210 per 100 shares. If called away: sell at $184 + keep $210 premium = net $186.10 vs $175 cost.",
                "SPY at $450: ADX=18 (ranging), ATR=1.9%, RSI=52. Sell the $472 call (~5% OTM) for $4.50 → 1.0% monthly. Classic BuyWrite index strategy — the CBOE BXM index has done this systematically for 30+ years.",
            ],
            "common_mistakes": [
                "Writing calls too close to the money (< 2% OTM) — you cap upside too aggressively and the stock gets called away on normal moves",
                "Writing calls on weak, downtrending stocks — the premium doesn't compensate for the equity loss",
                "Not rolling the call when the stock approaches the strike — letting the assignment happen accidentally instead of managing it",
                "Writing calls into earnings — IV crush removes your edge, and a gap move can blow through your strike or crash your shares",
            ],
        }
