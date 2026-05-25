"""
event_driven.py — Event-Driven Strategy (Earnings, FOMC, CPI)

STRATEGY FAMILY: Event Driven

PLAIN ENGLISH EXPLANATION:
  Some price moves are predictable — not in direction, but in TIMING.
  Earnings reports, Federal Reserve meetings, and major economic data
  (CPI, jobs report) consistently cause sharp moves in prices.

  This strategy has two phases:
    BEFORE the event: Position based on momentum, trend, or options structure
    AFTER the event:  Trade the follow-through move (drift) once direction is clear

  The key rule: we NEVER hold a full position THROUGH the event itself.
  We either position before (with defined risk) or trade the aftermath.

WHY THIS WORKS:
  - Post-earnings drift is well-documented: stocks that gap up on earnings
    often continue higher for 5-20 days (and vice versa).
  - Markets consistently underreact to major surprises, giving time to trade.
  - The timing of events is known in advance, so risk is manageable.

IMPORTANT NOTE:
  This strategy without live earnings/event calendar data uses price-based
  proxies (gap detection, volume surge). For best results, connect an
  earnings calendar (e.g. Yahoo Finance earnings via yfinance).
"""

import pandas as pd
import pandas_ta as ta
from app.strategies.base import BaseStrategy, Signal
from app.config import settings


class EventDrivenStrategy(BaseStrategy):

    name = "Post-Event Momentum Drift"
    family = "event"
    description = (
        "Trades the post-earnings or post-catalyst drift. Detects gap-and-go setups "
        "where price gaps significantly on high volume and follows through in same direction."
    )

    def default_parameters(self) -> dict:
        return {
            "gap_threshold_pct": 3.0,         # Minimum gap % — 3% filters noise, improves quality
            "volume_spike_mult": 2.5,          # Volume must be this × average — stronger confirmation
            "hold_days_min": 3,                # Minimum expected drift days
            "hold_days_max": 15,               # Maximum hold before exiting
            "atr_stop_mult": 2.0,              # Stop = gap fill level × ATR buffer — more breathing room
            "rr_target": 2.0,                  # Minimum R:R for entry
            "allow_short_gaps": True,          # Also trade downside gaps
            "gap_fill_invalidation": True,     # Exit if gap is fully filled (bad sign)
        }

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 30:
            return []

        df = self._add_base_indicators(df)
        df = df.sort_values("date").reset_index(drop=True)

        signals = []
        p = self.parameters

        for i in range(20, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(row.get("atr")) or row.get("vol_avg", 0) == 0:
                continue

            close = row["close"]
            open_ = row["open"]
            prev_close = prev["close"]
            volume = row["volume"]
            vol_avg = row["vol_avg"]
            atr = row["atr"]

            # ── GAP DETECTION ────────────────────────────────────────────
            gap_pct = ((open_ - prev_close) / prev_close) * 100
            volume_spike = volume >= vol_avg * p["volume_spike_mult"]

            # ── UPSIDE GAP (bullish event — earnings beat, positive catalyst) ──
            if gap_pct >= p["gap_threshold_pct"] and volume_spike:
                # Entry: Close of event day (confirms the gap held)
                if close > open_ * 0.98:   # Closed near open (gap held, no fill)
                    entry = close
                    # Stop: Below the gap (if gap fills, event is being reversed — exit)
                    gap_level = prev_close + (open_ - prev_close) * 0.5   # Mid-gap
                    stop = max(prev_close + atr * 0.5, open_ - atr * p["atr_stop_mult"])
                    risk = entry - stop
                    if risk <= 0:
                        continue
                    target = entry + risk * p["rr_target"]

                    reasoning = (
                        f"BULLISH EVENT GAP: Price gapped up {gap_pct:.1f}% from {prev_close:.2f} to open {open_:.2f}. "
                        f"Volume={volume:,.0f} ({volume/vol_avg:.1f}× average) — large players drove the move. "
                        f"Gap HELD: Close ({close:.2f}) near open — buyers are supporting the level. "
                        f"POST-EVENT DRIFT: Markets tend to underreact to positive surprises. "
                        f"Stop below the gap zone. Exit if gap is filled (the event is being rejected)."
                    )

                    signals.append(Signal(
                        symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                        date=row["date"],
                        action="BUY",
                        entry_price=round(entry, 4),
                        stop_price=round(stop, 4),
                        target_price=round(target, 4),
                        confidence=self._score_gap(gap_pct, volume, vol_avg, "up"),
                        reasoning=reasoning,
                        strategy_name=self.name,
                        indicators={
                            "gap_pct": round(gap_pct, 2),
                            "volume_ratio": round(volume / vol_avg, 2),
                            "gap_open": round(open_, 2),
                            "prev_close": round(prev_close, 2),
                            "atr": round(atr, 4),
                            "event_type": "Gap Up (Likely Earnings Beat or Positive Catalyst)",
                        },
                    ))

            # ── DOWNSIDE GAP (bearish event — earnings miss, negative catalyst) ──
            if p["allow_short_gaps"] and gap_pct <= -p["gap_threshold_pct"] and volume_spike:
                if close < open_ * 1.02:   # Gap held (no recovery)
                    entry = close
                    stop = min(prev_close - atr * 0.5, open_ + atr * p["atr_stop_mult"])
                    risk = stop - entry
                    if risk <= 0:
                        continue
                    target = entry - risk * p["rr_target"]

                    reasoning = (
                        f"BEARISH EVENT GAP: Price gapped down {abs(gap_pct):.1f}% from {prev_close:.2f} to {open_:.2f}. "
                        f"Volume={volume:,.0f} ({volume/vol_avg:.1f}× average) — heavy selling pressure. "
                        f"Gap HELD: Close ({close:.2f}) near open — sellers dominating. "
                        f"POST-EVENT DRIFT: Negative surprises cause continued selling as more holders exit. "
                        f"Stop above the gap zone. Exit if gap fills (sellers failing)."
                    )

                    signals.append(Signal(
                        symbol=df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN",
                        date=row["date"],
                        action="SELL",
                        entry_price=round(entry, 4),
                        stop_price=round(stop, 4),
                        target_price=round(target, 4),
                        confidence=self._score_gap(abs(gap_pct), volume, vol_avg, "down"),
                        reasoning=reasoning,
                        strategy_name=self.name,
                        indicators={
                            "gap_pct": round(gap_pct, 2),
                            "volume_ratio": round(volume / vol_avg, 2),
                            "gap_open": round(open_, 2),
                            "prev_close": round(prev_close, 2),
                            "atr": round(atr, 4),
                            "event_type": "Gap Down (Likely Earnings Miss or Negative Catalyst)",
                        },
                    ))

        return signals

    def _score_gap(self, gap_pct, volume, vol_avg, direction) -> float:
        score = 0.0
        if gap_pct >= 8.0: score += 0.4
        elif gap_pct >= 5.0: score += 0.3
        elif gap_pct >= 3.0: score += 0.2
        elif gap_pct >= 2.0: score += 0.1
        if vol_avg > 0:
            vol_ratio = volume / vol_avg
            if vol_ratio >= 5.0: score += 0.4
            elif vol_ratio >= 3.0: score += 0.3
            elif vol_ratio >= 2.0: score += 0.2
        return min(score, 1.0)

    def get_documentation(self) -> dict:
        return {
            "name": self.name,
            "family": self.family,
            "overview": (
                "The Post-Event Momentum Drift strategy captures the multi-day follow-through "
                "that typically occurs after a major catalyst (earnings, FOMC reaction, economic "
                "data surprise). It enters AFTER the event gap, once the direction is confirmed, "
                "and holds for the expected drift period. Never holds through the event itself."
            ),
            "when_to_use": [
                "After an earnings surprise with a significant gap (≥ 2%) that HOLDS on event day",
                "After FOMC decision creates a sustained directional move",
                "After CPI or jobs data causes a large, sustained move in index futures",
                "Event day volume is 2× or more the average (confirms institutional activity)",
            ],
            "when_to_avoid": [
                "Trading INTO the event — binary risk is too high without directional edge",
                "Gap fades within the first hour — this is a failed event trade, move on",
                "Earnings of a very small-cap stock — gaps can reverse violently",
                "Multiple consecutive events in the same week — wait for calm",
                "When the broader market is in a RISK-OFF regime — even good earnings get sold",
            ],
            "entry_rules": [
                "1. Identify the gap: Open must be ≥ 2% above (long) or below (short) previous close",
                "2. Confirm volume: Event day volume must be ≥ 2× the 20-day average",
                "3. Confirm gap holds: End of event day close is near the open (gap did not fill)",
                "4. Enter at the CLOSE of the event day, or at next day's open",
                "5. Skip if the gap partially filled (>50%) by end of day — signal is weak",
            ],
            "exit_rules": [
                "Stop: Just below the gap open level (if gap fills, the event is being rejected)",
                "Target: 2× the risk as minimum. Many event trades continue for 5-15 days.",
                "Time stop: Exit within 10-15 trading days regardless — drift usually fades",
                "Exit immediately if the stock closes back in the pre-event range",
            ],
            "risk_rules": [
                "Risk 0.75% of portfolio per event trade",
                "Max 2 event positions at once — catalysts can reverse hard",
                "NEVER average down on a failed event trade",
                "Size down if the gap is very large (>10%) — these can be more volatile",
            ],
            "examples": [
                {
                    "scenario": "AAPL earnings beat with gap up",
                    "setup": "AAPL previous close $180. Earnings: beat by 15%. Gap up to $192 on open.",
                    "trigger": "AAPL closes at $190 (+5.5% on day) on 4× average volume. Gap holds.",
                    "entry": "$190 (close of earnings day)",
                    "stop": "$185 (below mid-gap level)",
                    "target": "$200 (2:1 on $5 risk)",
                    "hold": "Expected 5-10 days of drift higher as analysts upgrade",
                    "size": "$50k account, risk $375 (0.75%), $375/$5 = 75 shares",
                },
            ],
            "common_mistakes": [
                "Buying into earnings BEFORE the report — this is gambling, not trading",
                "Holding after the gap fills — a filled gap means the event is being rejected",
                "Not cutting positions that go sideways after an event (time decay on the thesis)",
                "Trading earnings gaps in bear markets — good earnings get sold in downtrends",
                "Using full position size on event trades — always reduce size for binary events",
            ],
        }
