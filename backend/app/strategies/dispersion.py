"""
dispersion.py — Implied Correlation Dispersion Strategy

STRATEGY FAMILY: Options (Dispersion)

PLAIN ENGLISH EXPLANATION:
  Dispersion trading exploits a persistent anomaly in options markets:
  implied correlation (what the options market PREDICTS correlation
  between stocks will be) tends to trade ABOVE realized correlation
  (what correlation actually ends up being).

  The trade:
    - SELL index volatility (e.g., sell SPX straddle / SPY straddle)
    - BUY individual stock volatility (buy straddles on SPX members)

  You profit when stocks "disperse" — when individual stocks move in
  OPPOSITE DIRECTIONS, reducing the correlation between them. This
  makes the index option lose value (stocks cancel each other) while
  your single-stock options gain.

  THIS STRATEGY SIGNALS when the CONDITIONS for a dispersion trade
  are optimal — specifically when realized correlation is HIGH (stocks
  are too synchronized) and individual stock realized vol is compressed
  relative to the index. This sets up the mean reversion:
  high correlation → future dispersion → profitable long single-stock vol.

  PROXY APPROACH (single-ticker context):
    Since we're analyzing one stock, we use two signals:
    1. Short-term realized vol (20d) has compressed vs medium-term (60d)
       → the stock vol is artificially low relative to baseline
    2. RSI is near 50 and ADX is moderate → the stock is "indexing"
       (moving with the herd), not on its own fundamental story
    When BOTH compress, implied correlation is likely elevated → time to buy
    single-stock vol by entering straddle or strangle on this name.

WHY THIS WORKS:
  Index option buyers (risk managers, portfolio hedgers) consistently
  over-pay for index correlation protection. Hedge funds systematically
  extract this risk premium by going long single-stock vol and short
  index vol. The correlation risk premium averages 3–5 vega points
  of overpayment per month, making this one of the most consistent
  edge trades in professional options desks.

BEST MARKETS:
  - Large S&P 500 components with active single-stock options
  - High VIX environments (25+) where index IV is most inflated
  - Post-earnings for most components (removes binary event risk)
  - Early in the month (max time value for premium selling)
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class DispersionStrategy(BaseStrategy):

    name = "Implied Correlation Dispersion"
    family = "volatility"
    asset_class = "options"
    strategy_type = "dispersion"
    description = (
        "Detects high-correlation regimes (stocks moving in lockstep with the index) "
        "by measuring realized vol compression (20d vol << 60d vol) alongside neutral "
        "RSI. Signals the optimal time to enter a long single-stock vol / short index "
        "vol dispersion trade."
    )

    def default_parameters(self) -> dict:
        return {
            "short_vol_window": 20,      # Short-term realized vol window (days)
            "long_vol_window": 60,       # Medium-term realized vol window (days)
            "vol_compression_ratio": 0.75,  # Signal if short_vol / long_vol < this
            "rsi_neutral_band": 15,      # RSI within 50 ± this = stock is "indexing"
            "adx_correlation_range": (15, 35),  # ADX sweet spot: not flat, not trending
            "min_long_vol_pct": 1.0,    # Skip if stock has no vol at all (boring name)
            "atr_stop_mult": 2.0,       # Stop for the equity leg
            "rr_target": 2.0,           # Min reward:risk
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        p = self.parameters
        short_w = p["short_vol_window"]
        long_w = p["long_vol_window"]
        if len(df) < long_w + 30:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        # Compute realized volatility (annualized) for both windows
        returns = df["close"].pct_change()
        df["rvol_short"] = returns.rolling(short_w).std() * np.sqrt(252) * 100
        df["rvol_long"] = returns.rolling(long_w).std() * np.sqrt(252) * 100
        df["vol_ratio"] = df["rvol_short"] / df["rvol_long"]

        signals = []
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"
        adx_low, adx_high = p["adx_correlation_range"]

        for i in range(long_w + 15, len(df)):
            row = df.iloc[i]
            if pd.isna(row.get("vol_ratio")) or pd.isna(row.get("adx")) or pd.isna(row.get("rsi")):
                continue

            close = row["close"]
            atr = row["atr"]
            vol_ratio = row["vol_ratio"]
            rvol_short = row["rvol_short"]
            rvol_long = row["rvol_long"]
            rsi = row["rsi"]
            adx = row["adx"]

            # Long vol baseline check: stock must have meaningful historical vol
            if rvol_long < p["min_long_vol_pct"]:
                continue

            # ── DISPERSION SIGNAL CONDITIONS ──
            # 1. Vol is compressed: short-term vol << medium-term vol (artificial calm)
            vol_compressed = vol_ratio < p["vol_compression_ratio"]

            # 2. Stock is "indexing" — RSI near neutral (50), not its own story
            rsi_neutral = abs(rsi - 50) <= p["rsi_neutral_band"]

            # 3. ADX in moderate range — stock is correlated with index flow
            adx_correlated = adx_low <= adx <= adx_high

            if not (vol_compressed and rsi_neutral and adx_correlated):
                continue

            # Signal: long the single-stock straddle (ATM straddle entry proxy)
            # In practice: buy ATM call + ATM put on this stock, sell SPX straddle
            # Here we flag the equity-equivalent signal for the stock leg
            stop = close - p["atr_stop_mult"] * atr
            target = close + p["rr_target"] * p["atr_stop_mult"] * atr
            risk = close - stop
            reward = target - close

            if risk <= 0:
                continue

            # Confidence scales with how compressed vol is
            compression_degree = 1 - vol_ratio  # Higher = more compressed
            confidence = min(0.80, 0.45 + compression_degree * 0.6)

            signals.append(Signal(
                symbol=symbol,
                date=row["date"],
                action="BUY",
                entry_price=close,
                stop_price=stop,
                target_price=target,
                position_size_pct=0.5,     # Half size — this pairs with index short vol
                confidence=confidence,
                risk_reward_ratio=round(reward / risk, 2),
                strategy_name=self.name,
                reasoning=(
                    f"Dispersion signal: 20d realized vol ({rvol_short:.1f}%) is compressed to "
                    f"{vol_ratio:.0%} of 60d vol ({rvol_long:.1f}%) — implied correlation likely elevated. "
                    f"RSI={rsi:.0f} (neutral=indexing), ADX={adx:.1f} (correlated flow). "
                    f"Action: buy {symbol} single-stock straddle; pair with short SPX vol."
                ),
                indicators={
                    "rvol_20d_pct": round(rvol_short, 1),
                    "rvol_60d_pct": round(rvol_long, 1),
                    "vol_compression_ratio": round(vol_ratio, 2),
                    "rsi": round(rsi, 1),
                    "adx": round(adx, 1),
                    "compression_degree_pct": round(compression_degree * 100, 1),
                },
            ))

        return signals

    def get_documentation(self) -> dict:
        return {
            "overview": (
                "Detects when implied correlation is likely elevated by measuring realized "
                "volatility compression (20d vol < 75% of 60d vol) alongside RSI neutrality "
                "and moderate ADX — signs the stock is moving in lockstep with the index. "
                "Signals the entry for a long single-stock vol / short index vol dispersion trade."
            ),
            "when_to_use": [
                "When VIX is elevated (25+) — index IV is most inflated relative to realized",
                "After a prolonged low-vol period (vol compression signals the setup)",
                "Large S&P 500 components with liquid options (AAPL, MSFT, NVDA, JPM)",
                "Post-earnings season when most stocks have cleared binary events",
            ],
            "when_to_avoid": [
                "Individual stock with pending earnings or FDA/merger events — binary risk distorts vol",
                "Very low VIX environments (< 15) — index premium is too thin for dispersion edge",
                "Stocks with very low liquidity in options (wide bid-ask erodes the edge)",
                "When realized correlation is already low — the trade needs correlation to FALL further",
            ],
            "entry_rules": [
                "1. 20-day realized vol must be < 75% of 60-day realized vol (compression confirmed)",
                "2. RSI must be within 50 ± 15 (stock is neutral/indexing, not in its own move)",
                "3. ADX must be 15–35 (moderate correlation to index flow)",
                "4. Enter the single-stock straddle: buy ATM call + buy ATM put (same expiry)",
                "5. Pair with short position: sell SPX/SPY straddle or buy inverse VIX exposure",
                "6. Optimal expiry: 30–45 DTE on the single-stock options",
            ],
            "exit_rules": [
                "Close single-stock straddle when realized vol re-expands (20d vol > 80% of 60d)",
                "Target 30–50% profit on total P&L (vol trades don't need to run to expiry)",
                "Stop: exit if single-stock straddle loses 50% of premium (delta/vega move against you)",
                "At expiry: roll to next month if conditions still hold, otherwise close",
            ],
            "risk_rules": [
                "Position size: risk only 0.5% of portfolio per dispersion pair",
                "Total position including index short leg should be vega-neutral at entry",
                "Max 3 open dispersion pairs at once — correlation between legs reduces diversification",
                "Greeks to monitor: vega exposure on both legs must be approximately balanced",
            ],
            "examples": [
                "AAPL in Oct 2023: 20d rvol=14%, 60d rvol=22% (ratio=0.64). RSI=51, ADX=22. Implied corr elevated. Buy AAPL ATM straddle for $4.50, sell SPY straddle for $6.20. 3 weeks later AAPL gaps +7% on earnings while SPY barely moves → straddle worth $8.40, net profit +$4.20.",
                "SPY vs NVDA Oct 2024: Market in high-correlation mode (all stocks tracking Fed). NVDA 20d rvol=28% vs 60d=45% (compressed). Enter dispersion: long NVDA straddle, short SPX straddle. NVDA disperses +15% on AI catalyst while SPX flat → dispersion trade nets +2.3 vega per contract.",
            ],
            "common_mistakes": [
                "Going long dispersion when realized correlation is already low — you need correlation to FALL, so you enter when it's HIGH",
                "Ignoring the index short leg — buying single-stock vol alone is just long volatility, not dispersion",
                "Entering too large: dispersion has moderate Sharpe but high variance — keep size small",
                "Not being vega-neutral between legs — if you're net long vega, you're just a vol buyer, not a dispersion trader",
            ],
        }
