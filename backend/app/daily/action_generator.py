"""
action_generator.py — Daily Action Sheet Generator

THIS IS THE BRAIN OF THE SYSTEM.

Every morning, this module:
  1. Loads today's data for all watchlist symbols
  2. Detects the market regime
  3. Selects the appropriate strategy family
  4. Generates signals for each symbol
  5. Ranks them by confidence and risk-reward
  6. Writes the daily log explaining all reasoning
  7. Returns a structured action sheet for the UI

DAILY LOG FORMAT:
  We log not just WHAT the system suggests, but WHY.
  Even when no trade is suggested, we log the reasoning.
  This is how you learn and improve the system over time.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.database.models import DailyAction, DailyLog, Strategy
from app.data.storage import get_price_data, get_active_symbols
from app.regime.detector import detect_regime, detect_market_regime
from app.strategies.registry import (
    STRATEGY_REGISTRY, get_strategy, get_strategies_for_regime,
    STRATEGY_FAMILIES, REGIME_TO_STRATEGIES, STRATEGY_CLASS_MAP
)
from app.config import settings

logger = logging.getLogger(__name__)


def generate_daily_actions(db: Session, target_date: Optional[date] = None) -> dict:
    """
    Main function — generates the complete daily action sheet.

    Returns a dict with:
      date:             The date of the action sheet
      market_regime:    Overall market regime and details
      top_actions:      Top 5 ranked actionable setups
      all_actions:      All generated signals
      daily_log:        Narrative reasoning for the day
      risk_summary:     Portfolio risk and no-trade conditions
    """
    today = target_date or date.today()
    logger.info(f"Generating daily action sheet for {today}")

    # ── Data cutoff: use data UP TO but not including the analysis date ──
    # On morning of analysis_date, we only have data through the previous
    # trading day's close. This prevents look-ahead bias in historical analysis.
    data_end = today - timedelta(days=1)

    symbols = get_active_symbols(db)
    if not symbols:
        symbols = settings.symbols_list

    # ── Step 1: Market regime detection ──────────────────────────────
    market_regime = detect_market_regime(db, symbols, end_date=data_end)
    regime = market_regime["regime"]
    regime_confidence = market_regime["confidence"]

    # ── Step 2: Select strategy families for this regime ──────────────
    recommended_strategies = get_strategies_for_regime(regime)

    regime_note = _build_regime_explanation(regime, market_regime)

    # ── Step 3: Generate signals for each symbol ───────────────────────
    all_signals = []
    no_trade_reasons = []

    # Risk-off: no new positions
    if regime == "risk_off":
        no_trade_reasons.append(
            "RISK-OFF regime detected. No new positions recommended. "
            "Reduce existing exposure and move to cash/hedges."
        )
    elif not recommended_strategies:
        no_trade_reasons.append(
            f"No strategies mapped for current regime: {regime}. "
            "Staying flat until regime is clearer."
        )
    else:
        for symbol in symbols:
            df = get_price_data(db, symbol, end_date=data_end)
            if df.empty or len(df) < 50:
                continue

            # Add symbol column for strategy signal generation
            df = df.copy()
            df["symbol"] = symbol

            # Detect per-symbol regime
            sym_regime = detect_regime(df, symbol)

            # Run each recommended strategy
            for strat_key in recommended_strategies:
                strategy = get_strategy(strat_key)
                if not strategy:
                    continue

                try:
                    signals = strategy.generate_signals(df)
                    # Only use the most recent signal for each symbol+strategy
                    if signals:
                        latest_signal = signals[-1]   # Last signal = most recent
                        all_signals.append({
                            "signal": latest_signal,
                            "symbol": symbol,
                            "strategy_key": strat_key,
                            "symbol_regime": sym_regime["regime"],
                            "regime_match": sym_regime["regime"] in REGIME_TO_STRATEGIES.get(regime, []),
                        })
                except Exception as e:
                    logger.warning(f"Error generating signals for {symbol} / {strat_key}: {e}")

    # ── Step 4: Score and rank signals ───────────────────────────────
    scored = []
    for item in all_signals:
        sig = item["signal"]
        if not sig.is_actionable():
            continue

        # Composite score: confidence + R:R bonus + regime alignment bonus
        score = sig.confidence * 0.5
        score += min(sig.risk_reward_ratio / 10, 0.3)   # R:R contributes up to 0.3
        if item["regime_match"]:
            score += 0.2                                  # Bonus for regime alignment

        scored.append({**item, "composite_score": round(score, 3)})

    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # ── Diversity selection: guarantee best options + futures signal appear ──
    # If options or futures strategies generated signals, reserve 1 slot each
    # so the user always sees cross-asset-class recommendations.
    top_options = next(
        (s for s in scored if STRATEGY_CLASS_MAP.get(s["strategy_key"], {}).get("asset_class") == "options"), None
    )
    top_futures = next(
        (s for s in scored if STRATEGY_CLASS_MAP.get(s["strategy_key"], {}).get("asset_class") == "futures"), None
    )
    pinned = [s for s in [top_options, top_futures] if s is not None]
    pinned_ids = {id(s) for s in pinned}
    remaining = [s for s in scored if id(s) not in pinned_ids]
    top_actions = (pinned + remaining)[:20]
    top_actions.sort(key=lambda x: x["composite_score"], reverse=True)

    # ── Step 5: Build daily action records ────────────────────────────
    action_records = []
    for rank, item in enumerate(top_actions):
        sig = item["signal"]
        family = STRATEGY_REGISTRY.get(item["strategy_key"], type("", (), {"family": "unknown"}))().family
        cls_info = STRATEGY_CLASS_MAP.get(item["strategy_key"], {})
        rec = {
            "rank": rank + 1,
            "symbol": sig.symbol,
            "action": sig.action,
            "strategy": sig.strategy_name,
            "strategy_key": item["strategy_key"],
            "family": family,
            "asset_class": cls_info.get("asset_class", "equity"),
            "asset_class_label": cls_info.get("asset_class_label", "Equity"),
            "strategy_type": cls_info.get("strategy_type", ""),
            "strategy_type_label": cls_info.get("strategy_type_label", ""),
            "entry_price": sig.entry_price,
            "stop_price": sig.stop_price,
            "target_price": sig.target_price,
            "risk_reward_ratio": sig.risk_reward_ratio,
            "confidence": sig.confidence,
            "composite_score": item["composite_score"],
            "reasoning": sig.reasoning,
            "indicators": sig.indicators,
            "regime": item["symbol_regime"],
        }
        rec["trade_blueprint"] = _build_trade_blueprint(rec, regime)
        action_records.append(rec)

    # ── Step 6: Save to database ──────────────────────────────────────
    _save_daily_actions(db, action_records, today)

    # ── Step 7: Write daily log ────────────────────────────────────────
    log = _write_daily_log(
        db, today, regime, market_regime, action_records,
        regime_note, no_trade_reasons, recommended_strategies
    )

    # ── Return the full sheet ─────────────────────────────────────────
    return {
        "date": str(today),
        "market_regime": {
            **market_regime,
            "recommended_strategies": recommended_strategies,
            "family_descriptions": {
                k: STRATEGY_FAMILIES[k]["label"]
                for k in set(
                    STRATEGY_REGISTRY.get(s, type("", (), {"family": "unknown"}))().family
                    for s in recommended_strategies
                    if s in STRATEGY_REGISTRY
                )
                if k in STRATEGY_FAMILIES
            },
        },
        "top_actions": action_records,
        "total_signals_generated": len(all_signals),
        "actionable_signals": len(scored),
        "no_trade_reasons": no_trade_reasons,
        "regime_explanation": regime_note,
        "risk_rules": _get_daily_risk_rules(regime),
        "daily_log_id": log.id if log else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  DAILY LOG WRITING
# ─────────────────────────────────────────────────────────────────────────────

def _write_daily_log(
    db: Session,
    today: date,
    regime: str,
    market_regime: dict,
    actions: list,
    regime_note: str,
    no_trade_reasons: list,
    recommended_strategies: list,
) -> Optional[DailyLog]:
    """Write the daily narrative log to the database."""
    try:
        existing = db.query(DailyLog).filter(DailyLog.date == today).first()

        top_opps = [
            {"rank": a["rank"], "symbol": a["symbol"], "action": a["action"],
             "strategy": a["strategy"], "confidence": a["confidence"]}
            for a in actions[:3]
        ]

        strategy_notes = (
            f"Active strategy families today: {', '.join(recommended_strategies) or 'None'}. "
            f"Regime: {regime} (confidence: {market_regime['confidence']:.0%}). "
            f"{regime_note}"
        )

        if existing:
            existing.market_regime_summary = regime_note
            existing.top_opportunities = top_opps
            existing.strategy_notes = strategy_notes
            existing.no_trade_reasons = " ".join(no_trade_reasons) if no_trade_reasons else None
            db.commit()
            return existing

        log = DailyLog(
            date=today,
            market_regime_summary=regime_note,
            top_opportunities=top_opps,
            macro_context=f"Breadth: {market_regime.get('breadth_pct', 50):.0f}% of symbols in uptrend.",
            risk_alerts=[r for r in no_trade_reasons if r],
            strategy_notes=strategy_notes,
            no_trade_reasons=" ".join(no_trade_reasons) if no_trade_reasons else None,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    except Exception as e:
        logger.error(f"Failed to write daily log: {e}")
        return None


def _save_daily_actions(db: Session, actions: list, today: date):
    """Save daily action records to the database. Replaces all records for the date."""
    # Delete old records for this date so diverse multi-strategy results replace old ones
    db.query(DailyAction).filter(DailyAction.date == today).delete()
    for a in actions:
        db.add(DailyAction(
            date=today,
            symbol=a["symbol"],
            regime=a["regime"],
            action=a["action"],
            entry_price=a["entry_price"],
            stop_price=a["stop_price"],
            target_price=a["target_price"],
            position_size_pct=settings.DEFAULT_RISK_PER_TRADE_PCT,
            confidence=a["confidence"],
            risk_reward_ratio=a["risk_reward_ratio"],
            reasoning=a["reasoning"],
            strategy_key=a.get("strategy_key"),
        ))
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save daily actions: {e}")
        db.rollback()


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_regime_explanation(regime: str, market_data: dict) -> str:
    adx = market_data.get("adx", 0)
    atr_pct = market_data.get("atr_percentile", 50)
    breadth = market_data.get("breadth_pct", 50)
    rsi = market_data.get("rsi", 50)

    explanations = {
        "uptrend": (
            f"The market is in a confirmed UPTREND. "
            f"ADX={adx:.1f} (≥25 = trend is real). {breadth:.0f}% of symbols trending up. "
            f"Best strategies: ride the trend with pullback entries, "
            f"or buy confirmed breakouts. Avoid mean reversion — don't fight the trend."
        ),
        "downtrend": (
            f"The market is in a confirmed DOWNTREND. "
            f"ADX={adx:.1f}. Only {breadth:.0f}% of symbols trending up. "
            f"Best strategies: short rallies, or sit in cash. "
            f"Do not buy dips unless you have strong conviction and the sector is an outlier."
        ),
        "ranging": (
            f"The market is SIDEWAYS. ADX={adx:.1f} (below 25 = no real trend). "
            f"Price is oscillating without direction. "
            f"Best strategies: mean reversion (fade extremes). "
            f"Avoid trend-following — you'll get chopped up."
        ),
        "high_vol": (
            f"ELEVATED VOLATILITY regime. ATR is at the {atr_pct:.0f}th percentile. "
            f"Larger-than-normal price swings. "
            f"Best strategies: breakout (ride the expansion) or "
            f"buy cheap volatility options (if IV is low). Reduce position size by 50%."
        ),
        "risk_off": (
            f"RISK-OFF: Extreme volatility and broad market selling. "
            f"ATR at {atr_pct:.0f}th percentile. Only {breadth:.0f}% of symbols rising. "
            f"DO NOT open new directional positions. "
            f"If holding longs: tighten stops or reduce size. "
            f"Cash is a position. Wait for regime to stabilize."
        ),
        "event": (
            f"EVENT regime: Major catalyst expected. "
            f"Use only defined-risk setups. Consider long volatility (straddles) "
            f"if the expected move is underpriced. Avoid holding naked positions through events."
        ),
    }
    return explanations.get(regime, f"Market regime: {regime}.")


def _get_daily_risk_rules(regime: str) -> list[str]:
    base_rules = [
        f"Max risk per trade: {settings.DEFAULT_RISK_PER_TRADE_PCT}% of portfolio",
        f"Max daily loss: {settings.MAX_DAILY_LOSS_PCT}% — stop all trading if hit",
        f"Max concurrent positions: {settings.MAX_CONCURRENT_POSITIONS}",
    ]
    if regime == "risk_off":
        base_rules.insert(0, "🔴 RISK-OFF: No new positions. Reduce existing exposure.")
    elif regime == "high_vol":
        base_rules.insert(0, "⚠ HIGH VOL: Reduce position size by 50%. Widen stops.")
    elif regime == "event":
        base_rules.insert(0, "⚠ EVENT: Only defined-risk trades. Max 0.5% risk per position.")
    return base_rules


def _build_trade_blueprint(action: dict, regime: str) -> dict:
    """
    Build a complete step-by-step trade plan for a given signal.

    This answers the three questions every trader must know before entering:
      1. When to enter (and how — limit vs market, conditions)
      2. When to exit (take profit, stop loss, time-based)
      3. How much to buy (position sizing based on risk %)
    """
    entry = action["entry_price"] or 0.0
    stop  = action["stop_price"]  or 0.0
    target = action["target_price"] or 0.0
    act    = action["action"]          # BUY | SELL_SHORT | STRADDLE | CONDOR
    family = action.get("family", "trend")
    rr     = action.get("risk_reward_ratio", 0.0) or 0.0
    risk_per_share = abs(entry - stop)
    reward_per_share = abs(target - entry)

    # ── Trade style by strategy family ──────────────────────────────────────
    style_map = {
        "trend": (
            "Swing Trade",
            "5–15 trading days",
            "This is NOT day trading. You ride a confirmed multi-day trend. "
            "You enter during a brief pullback and hold until price hits the target or stop. "
            "Think of it like surfing — you wait for the right wave (pullback), then paddle in.",
        ),
        "mean_reversion": (
            "Swing Trade (Mean Reversion)",
            "2–7 trading days",
            "Price stretched too far from average. You bet on it snapping back. "
            "Short hold — exit quickly once price returns to the mean. "
            "Not trend-following — you are fading the extreme move.",
        ),
        "breakout": (
            "Momentum Trade",
            "3–10 trading days",
            "Price just broke through a key resistance level with volume. "
            "You enter on the breakout and trail stops as price expands. "
            "Works best when volume confirms the break — avoid false breakouts.",
        ),
        "volatility": (
            "Options Volatility Trade",
            "1–5 trading days",
            "This is an OPTIONS strategy (requires options approval with your broker). "
            "You are trading the size of the move, not the direction. "
            "Straddle = buy both a call and a put. You profit if price moves sharply in either direction.",
        ),
        "event": (
            "Event-Driven Trade",
            "1–3 trading days",
            "Short-duration trade around a specific catalyst (earnings, Fed meeting, product launch). "
            "Enter 1–2 days before the event. Exit the same day or next day after the event. "
            "Avoid holding through the event if IV is elevated (options get expensive).",
        ),
    }
    style_name, hold_days, style_desc = style_map.get(
        family, ("Swing Trade", "3–15 trading days", "Technical swing setup.")
    )

    # ── Entry instructions ───────────────────────────────────────────────────
    if act == "BUY":
        max_chase = entry * 1.005
        entry_instructions = [
            f"Place a LIMIT BUY order at ${entry:.2f} (never pay more than ${max_chase:.2f})",
            "Set the order before market open, or within the first 30 min of trading",
            "If price already gapped up more than 1% above entry — SKIP this trade today",
            "Confirm volume is above yesterday's average before entering",
            f"After your order fills: immediately set a stop-loss order at ${stop:.2f}",
        ]
    elif act == "SELL_SHORT":
        min_short = entry * 0.995
        entry_instructions = [
            f"Place a LIMIT SHORT SELL order at ${entry:.2f} (never accept less than ${min_short:.2f})",
            "Verify your broker allows short selling this symbol (check locate availability)",
            "If price already gapped down more than 1% — SKIP this trade today",
            f"After fill: immediately place a BUY TO COVER stop order at ${stop:.2f}",
            "Short selling has theoretically unlimited loss — respect the stop religiously",
        ]
    elif act in ("STRADDLE", "CONDOR"):
        entry_instructions = [
            "Requires OPTIONS TRADING approval with your broker (Level 2 minimum for straddle)",
            "Look up the at-the-money (ATM) call and put for the next expiration after the catalyst",
            "Enter 1–2 days before the expected event for best pricing",
            f"Your maximum risk = net debit paid (the combined premium of both options)",
            "Set a stop if the combined option value drops 50% from your entry cost",
        ]
    else:
        entry_instructions = [f"Enter at ${entry:.2f}"]

    # ── Exit plan ────────────────────────────────────────────────────────────
    if act == "BUY":
        exit_plan = {
            "take_profit": {
                "price": round(target, 2),
                "instruction": (
                    f"Sell ALL shares at ${target:.2f} (the target). "
                    "Or sell 50% at target and trail a stop on the rest to let winners run."
                ),
                "trailing_tip": (
                    f"To trail: once price is up 1 full ATR from entry, move your stop to breakeven (${entry:.2f}). "
                    "This locks in a no-loss trade while giving room to run further."
                ),
            },
            "stop_loss": {
                "price": round(stop, 2),
                "instruction": (
                    f"EXIT IMMEDIATELY if price closes below ${stop:.2f}. "
                    "This is not negotiable — it is your capital protection. "
                    "Do NOT 'wait and see' once the stop is hit."
                ),
                "setup_tip": "Enter this as a stop-limit or stop-market order right after your buy fills.",
            },
            "time_exit": {
                "days": hold_days,
                "instruction": (
                    f"If the stock hasn't hit the target or stop within {hold_days}: "
                    "EXIT at the close. A trade that goes sideways for too long is tying up capital "
                    "that could be used in better setups."
                ),
            },
        }
    elif act == "SELL_SHORT":
        exit_plan = {
            "take_profit": {
                "price": round(target, 2),
                "instruction": f"BUY TO COVER at ${target:.2f} to close the short and realize profit.",
                "trailing_tip": "If price drops sharply, trail your cover stop down to lock in gains.",
            },
            "stop_loss": {
                "price": round(stop, 2),
                "instruction": (
                    f"BUY TO COVER immediately if price rises above ${stop:.2f}. "
                    "Short losses accelerate as price rises — do not hold through a stop."
                ),
                "setup_tip": "Use a stop-market BUY order placed right after your short fill.",
            },
            "time_exit": {
                "days": hold_days,
                "instruction": f"Cover the short within {hold_days} if target not reached.",
            },
        }
    else:  # Options
        exit_plan = {
            "take_profit": {
                "price": round(target, 2),
                "instruction": "Sell the option(s) when the position value doubles (100% gain), or at target delta move.",
                "trailing_tip": "For event trades: sell within 1 day after the event, regardless of profit/loss.",
            },
            "stop_loss": {
                "price": round(stop, 2),
                "instruction": "Exit the options position if combined value drops 50% from entry cost.",
                "setup_tip": "Use a GTC limit order to close at the stop price.",
            },
            "time_exit": {
                "days": hold_days,
                "instruction": f"Close all options within {hold_days}. Time decay (theta) erodes value daily.",
            },
        }

    # ── Position sizing ──────────────────────────────────────────────────────
    risk_pct = settings.DEFAULT_RISK_PER_TRADE_PCT  # e.g. 1.0
    examples = []
    for acct in [5_000, 10_000, 25_000, 50_000, 100_000]:
        risk_dollars = acct * risk_pct / 100
        shares = int(risk_dollars / risk_per_share) if risk_per_share > 0.001 else 0
        position_value = round(shares * entry, 2)
        examples.append({
            "account": acct,
            "risk_dollars": round(risk_dollars, 2),
            "shares": max(0, shares),
            "position_value": position_value,
        })

    position_sizing = {
        "risk_pct": risk_pct,
        "risk_per_share": round(risk_per_share, 4),
        "reward_per_share": round(reward_per_share, 4),
        "formula": (
            f"Shares = (Account × {risk_pct}%) ÷ ${risk_per_share:.2f} per share risk"
        ),
        "explanation": (
            f"You risk exactly {risk_pct}% of your account per trade. "
            f"Each share risks ${risk_per_share:.2f} (entry minus stop). "
            f"This limits total loss to {risk_pct}% even if the stop is hit."
        ),
        "examples": examples,
    }

    # ── Pre-trade checklist ──────────────────────────────────────────────────
    checklist = [
        f"Market regime is {regime} — favorable for this strategy family ({family})",
        f"R:R = {rr:.1f}:1 — minimum 1.5:1 required {'(PASS)' if rr >= 1.5 else '(FAIL — skip trade)'}",
        "No earnings announcement within the hold period (check investor relations website)",
        "No major Fed announcement or CPI report on a hold day",
        f"Entry price is available: stock trading near ${entry:.2f} at time of order",
        "Total open positions will still be 5 or fewer after this trade",
        "Stop-loss order is placed IMMEDIATELY after the entry fill",
        "Trade is journaled: date, reason, entry, stop, target written down",
        f"Position size calculated using the formula above — NOT a round number guess",
    ]
    if act == "SELL_SHORT":
        checklist.insert(2, "Confirmed broker has shares available to borrow (short locate)")
    if family == "volatility":
        checklist.insert(2, "Options approval level confirmed with broker (Level 2+)")
        checklist.insert(3, "Implied Volatility (IV) checked — avoid buying options when IV is already very high")

    return {
        "trade_style": style_name,
        "hold_days": hold_days,
        "style_description": style_desc,
        "entry_instructions": entry_instructions,
        "exit_plan": exit_plan,
        "position_sizing": position_sizing,
        "checklist": checklist,
    }
