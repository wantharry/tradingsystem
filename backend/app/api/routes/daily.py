"""daily.py — API routes for daily action sheets and logs."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.daily.action_generator import generate_daily_actions, _build_trade_blueprint
from app.daily.outcome_tracker import compute_outcomes, get_last_trading_day, get_performance_summary
from app.database.models import DailyAction, DailyLog
from app.strategies.registry import STRATEGY_CLASS_MAP

router = APIRouter()


@router.get("/last-trading-day")
def last_trading_day(db: Session = Depends(get_db)):
    """
    Return the last date for which we have price data in the database.
    Used by the frontend to handle weekends / market holidays: the UI
    can show 'Analysis for next session (Mon May 27) based on Fri May 23 data'.
    """
    last = get_last_trading_day(db)
    today = date.today()
    return {
        "last_trading_day": str(last) if last else None,
        "today": str(today),
        "data_is_current": last is not None and last >= today,
        "market_closed": last is None or last < today,
    }


@router.get("/verify/{action_date}")
def verify_outcomes(
    action_date: date,
    forward_days: int = Query(15, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """
    Compute actual outcomes for all DailyActions on a past date.

    For each BUY/SELL action, looks at the following N trading days
    to determine if the predicted move happened:
      WIN            → target hit before stop
      LOSS           → stop hit before target
      EXPIRED_PROFIT → time limit reached, position profitable
      EXPIRED_LOSS   → time limit reached, position at a loss

    Updates the outcome and actual_pnl_pct fields in the database.
    """
    if action_date > date.today():
        raise HTTPException(status_code=400, detail="Cannot verify future dates — no outcome data yet.")

    results = compute_outcomes(db, action_date, forward_days=forward_days)
    if not results:
        raise HTTPException(status_code=404, detail=f"No actions found for {action_date}.")

    wins = sum(1 for r in results if r["outcome"] in ("WIN", "EXPIRED_PROFIT"))
    losses = sum(1 for r in results if r["outcome"] in ("LOSS", "EXPIRED_LOSS"))
    pnls = [r["actual_pnl_pct"] for r in results if r.get("actual_pnl_pct") is not None]

    return {
        "date": str(action_date),
        "forward_days": forward_days,
        "outcomes": results,
        "summary": {
            "total": len(results),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / len(results) * 100, 1) if results else None,
            "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else None,
        },
    }


@router.get("/performance")
def performance_summary(
    days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """
    Aggregate win/loss performance across verified actions over the past N days.
    Includes learning insights: which regimes work best, avg PnL, etc.
    """
    return get_performance_summary(db, limit_days=days)


@router.get("/actions")
def get_daily_actions(
    target_date: Optional[date] = Query(None),
    regenerate: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Get the daily action sheet.
    If regenerate=True or no cached actions exist, regenerates them fresh.
    """
    d = target_date or date.today()

    if not regenerate:
        # Check if we already have actions for today
        existing = db.query(DailyAction).filter(DailyAction.date == d).all()
        if existing:
            actions_out = []
            for a in sorted(existing, key=lambda x: x.confidence or 0, reverse=True):
                cls_info = STRATEGY_CLASS_MAP.get(a.strategy_key or "", {})
                rec = {
                    "symbol": a.symbol,
                    "action": a.action,
                    "regime": a.regime,
                    "entry_price": a.entry_price,
                    "stop_price": a.stop_price,
                    "target_price": a.target_price,
                    "risk_reward_ratio": a.risk_reward_ratio,
                    "confidence": a.confidence,
                    "reasoning": a.reasoning,
                    "position_size_pct": a.position_size_pct,
                    "outcome": a.outcome,
                    "actual_pnl_pct": a.actual_pnl_pct,
                    "strategy_key": a.strategy_key,
                    "asset_class": cls_info.get("asset_class", "equity"),
                    "asset_class_label": cls_info.get("asset_class_label", "Equity"),
                    "strategy_type": cls_info.get("strategy_type", ""),
                    "strategy_type_label": cls_info.get("strategy_type_label", ""),
                }
                rec["trade_blueprint"] = _build_trade_blueprint(rec, a.regime or "uptrend")
                actions_out.append(rec)
            return {
                "date": str(d),
                "source": "cached",
                "top_actions": actions_out,
            }

    # Generate fresh
    result = generate_daily_actions(db, d)
    result["source"] = "fresh"
    return result


@router.get("/logs")
def get_daily_logs(
    limit: int = Query(30, le=365),
    db: Session = Depends(get_db),
):
    """Get the daily market journal — all reasoning logged over time."""
    logs = (
        db.query(DailyLog)
        .order_by(DailyLog.date.desc())
        .limit(limit)
        .all()
    )
    return {
        "logs": [
            {
                "date": str(log.date),
                "regime_summary": log.market_regime_summary,
                "strategy_notes": log.strategy_notes,
                "top_opportunities": log.top_opportunities,
                "risk_alerts": log.risk_alerts,
                "no_trade_reasons": log.no_trade_reasons,
            }
            for log in logs
        ]
    }


@router.get("/logs/{log_date}")
def get_daily_log(log_date: date, db: Session = Depends(get_db)):
    """Get the daily log for a specific date."""
    log = db.query(DailyLog).filter(DailyLog.date == log_date).first()
    if not log:
        raise HTTPException(status_code=404, detail=f"No log found for {log_date}")
    return {
        "date": str(log.date),
        "regime_summary": log.market_regime_summary,
        "top_opportunities": log.top_opportunities,
        "macro_context": log.macro_context,
        "risk_alerts": log.risk_alerts,
        "strategy_notes": log.strategy_notes,
        "no_trade_reasons": log.no_trade_reasons,
        "portfolio_exposure": log.portfolio_exposure,
    }


@router.get("/history")
def get_action_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    """Get historical daily actions, optionally filtered by symbol."""
    query = db.query(DailyAction).order_by(DailyAction.date.desc())
    if symbol:
        query = query.filter(DailyAction.symbol == symbol.upper())
    actions = query.limit(limit).all()

    return {
        "actions": [
            {
                "date": str(a.date),
                "symbol": a.symbol,
                "action": a.action,
                "regime": a.regime,
                "entry_price": a.entry_price,
                "stop_price": a.stop_price,
                "target_price": a.target_price,
                "confidence": a.confidence,
                "risk_reward_ratio": a.risk_reward_ratio,
                "reasoning": a.reasoning,
                "outcome": a.outcome,
                "actual_pnl_pct": a.actual_pnl_pct,
            }
            for a in actions
        ]
    }
