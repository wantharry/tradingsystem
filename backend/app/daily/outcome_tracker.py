"""
outcome_tracker.py — Verify past predictions against actual price movements.

HOW VERIFICATION WORKS:
  For every DailyAction on a past date, we look at the N trading days AFTER
  that date and check whether the predicted move actually happened:

  BUY prediction:
    - WIN  → price reached target_price before touching stop_price
    - LOSS → price touched stop_price before reaching target_price
    - EXPIRED_PROFIT → held for max days, ended above entry (profitable but target not hit)
    - EXPIRED_LOSS   → held for max days, ended below entry

  SELL_SHORT prediction:
    - Inverted logic: target is below entry, stop is above entry

WHY THIS MATTERS:
  This creates a feedback loop. Over time you can see:
  - Which strategies have real predictive power
  - Which regimes produce the best signals
  - What confidence thresholds actually mean (does 80% conf → 80% win rate?)
  - Mistakes to learn from: specific patterns that looked good but failed
"""

import logging
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.models import DailyAction, PriceData

logger = logging.getLogger(__name__)

# How many trading days forward to check before marking as EXPIRED
DEFAULT_FORWARD_DAYS = 15


def get_last_trading_day(db: Session) -> Optional[date]:
    """Return the most recent date for which we have ANY price data."""
    result = db.query(func.max(PriceData.date)).scalar()
    return result.date() if result else None


def compute_outcomes(
    db: Session,
    action_date: date,
    forward_days: int = DEFAULT_FORWARD_DAYS,
) -> list[dict]:
    """
    For all DailyActions on action_date, compute actual outcomes using
    subsequent price data and update the DB records.

    Returns a list of outcome dicts (one per action).
    """
    actions = db.query(DailyAction).filter(DailyAction.date == action_date).all()

    if not actions:
        return []

    results = []

    for action in actions:
        # Non-directional actions can't be verified by price movement
        if action.action not in ("BUY", "SELL_SHORT", "SELL"):
            if action.outcome != "SKIPPED":
                action.outcome = "SKIPPED"
            results.append({
                "id": action.id,
                "symbol": action.symbol,
                "action": action.action,
                "date": str(action_date),
                "outcome": "SKIPPED",
                "actual_pnl_pct": None,
                "note": "Non-directional action — cannot verify by price.",
            })
            continue

        # Pull price data AFTER action_date (the days following the signal)
        from datetime import datetime
        start_dt = datetime.combine(action_date + timedelta(days=1), datetime.min.time())
        rows = (
            db.query(PriceData)
            .filter(
                PriceData.symbol == action.symbol,
                PriceData.interval == "1d",
                PriceData.date >= start_dt,
            )
            .order_by(PriceData.date.asc())
            .limit(forward_days)
            .all()
        )

        if not rows:
            results.append({
                "id": action.id,
                "symbol": action.symbol,
                "action": action.action,
                "date": str(action_date),
                "outcome": "NO_DATA",
                "actual_pnl_pct": None,
                "note": f"No price data found after {action_date} for {action.symbol}.",
                "entry_price": action.entry_price,
                "target_price": action.target_price,
                "stop_price": action.stop_price,
            })
            continue

        entry = action.entry_price or 0
        target = action.target_price
        stop = action.stop_price
        is_long = action.action == "BUY"

        outcome = "OPEN"
        actual_pnl_pct = None
        hit_day = None
        days_checked = len(rows)

        for i, row in enumerate(rows):
            high = row.high or 0
            low = row.low or 0

            if is_long:
                # Check target hit (high touched target)
                if target and high >= target and entry > 0:
                    outcome = "WIN"
                    actual_pnl_pct = round((target - entry) / entry * 100, 2)
                    hit_day = i + 1
                    break
                # Check stop hit (low touched stop)
                if stop and low <= stop and entry > 0:
                    outcome = "LOSS"
                    actual_pnl_pct = round((stop - entry) / entry * 100, 2)
                    hit_day = i + 1
                    break
            else:
                # Short: target is below entry, stop is above entry
                if target and low <= target and entry > 0:
                    outcome = "WIN"
                    actual_pnl_pct = round((entry - target) / entry * 100, 2)
                    hit_day = i + 1
                    break
                if stop and high >= stop and entry > 0:
                    outcome = "LOSS"
                    actual_pnl_pct = round((entry - stop) / entry * 100, 2)
                    hit_day = i + 1
                    break

        # If we never hit target or stop, evaluate the final close vs entry
        if outcome == "OPEN" and rows:
            last_close = rows[-1].close or entry
            if entry > 0:
                if is_long:
                    actual_pnl_pct = round((last_close - entry) / entry * 100, 2)
                else:
                    actual_pnl_pct = round((entry - last_close) / entry * 100, 2)
            outcome = "EXPIRED_PROFIT" if (actual_pnl_pct or 0) > 0 else "EXPIRED_LOSS"

        # Persist to DB
        action.outcome = outcome
        action.actual_pnl_pct = actual_pnl_pct

        results.append({
            "id": action.id,
            "symbol": action.symbol,
            "action": action.action,
            "date": str(action_date),
            "entry_price": entry,
            "target_price": target,
            "stop_price": stop,
            "confidence": action.confidence,
            "outcome": outcome,
            "actual_pnl_pct": actual_pnl_pct,
            "hit_day": hit_day,
            "days_checked": days_checked,
            "reasoning": action.reasoning,
            "regime": action.regime,
        })

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save outcomes for {action_date}: {e}")
        db.rollback()

    return results


def get_performance_summary(db: Session, limit_days: int = 90) -> dict:
    """
    Aggregate win/loss stats across all verified actions over the past N days.
    Used for the 'learning' / feedback panel.
    """
    from datetime import datetime
    cutoff = date.today() - timedelta(days=limit_days)

    actions = (
        db.query(DailyAction)
        .filter(
            DailyAction.date >= cutoff,
            DailyAction.outcome.isnot(None),
            DailyAction.outcome.notin_(["SKIPPED", "NO_DATA"]),
        )
        .all()
    )

    total = len(actions)
    if total == 0:
        return {"total_verified": 0, "win_rate": None, "avg_pnl_pct": None}

    wins = sum(1 for a in actions if a.outcome in ("WIN", "EXPIRED_PROFIT"))
    losses = sum(1 for a in actions if a.outcome in ("LOSS", "EXPIRED_LOSS"))
    pnls = [a.actual_pnl_pct for a in actions if a.actual_pnl_pct is not None]

    # Group by strategy/regime for learning insights
    regime_stats = {}
    for a in actions:
        r = a.regime or "unknown"
        if r not in regime_stats:
            regime_stats[r] = {"wins": 0, "losses": 0, "total": 0}
        regime_stats[r]["total"] += 1
        if a.outcome in ("WIN", "EXPIRED_PROFIT"):
            regime_stats[r]["wins"] += 1
        else:
            regime_stats[r]["losses"] += 1

    return {
        "total_verified": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total > 0 else None,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "best_trade": max(pnls) if pnls else None,
        "worst_trade": min(pnls) if pnls else None,
        "regime_stats": regime_stats,
        "period_days": limit_days,
        "insights": _generate_insights(actions, regime_stats),
    }


def _generate_insights(actions: list, regime_stats: dict) -> list[str]:
    """Generate human-readable learning insights from outcome data."""
    insights = []

    if not actions:
        return insights

    pnls = [a.actual_pnl_pct for a in actions if a.actual_pnl_pct is not None]
    wins = [a for a in actions if a.outcome in ("WIN", "EXPIRED_PROFIT")]
    losses = [a for a in actions if a.outcome in ("LOSS", "EXPIRED_LOSS")]

    win_rate = len(wins) / len(actions) * 100 if actions else 0

    if win_rate >= 60:
        insights.append(f"✓ Strong signal quality: {win_rate:.0f}% win rate across {len(actions)} trades.")
    elif win_rate < 40:
        insights.append(f"⚠ Low win rate ({win_rate:.0f}%). Review entry criteria and position sizing rules.")

    # Which regime performs best?
    best_regime = max(regime_stats.items(), key=lambda x: x[1]["wins"] / max(x[1]["total"], 1), default=None)
    if best_regime and best_regime[1]["total"] >= 3:
        r_wr = best_regime[1]["wins"] / best_regime[1]["total"] * 100
        insights.append(f"Best regime: '{best_regime[0]}' ({r_wr:.0f}% win rate, {best_regime[1]['total']} trades).")

    worst_regime = min(regime_stats.items(), key=lambda x: x[1]["wins"] / max(x[1]["total"], 1), default=None)
    if worst_regime and worst_regime[1]["total"] >= 3 and worst_regime != best_regime:
        r_wr = worst_regime[1]["wins"] / worst_regime[1]["total"] * 100
        insights.append(f"Worst regime: '{worst_regime[0]}' ({r_wr:.0f}% win rate). Consider reducing size here.")

    if pnls:
        avg = sum(pnls) / len(pnls)
        if avg > 0:
            insights.append(f"Avg trade result: +{avg:.1f}%. System has positive expectancy.")
        else:
            insights.append(f"Avg trade result: {avg:.1f}%. Negative expectancy — review stop placement.")

    return insights
