"""
engine.py — Backtesting Engine with Walk-Forward Testing

WHAT IS BACKTESTING:
  Backtesting applies a strategy's rules to historical data to see how
  it would have performed. This helps validate that a strategy has edge
  before risking real money.

WHAT IS WALK-FORWARD TESTING:
  Standard backtesting has a problem: you can keep tweaking parameters
  until the backtest looks great — but that's just fitting to past data,
  not real edge. Walk-forward testing solves this:

    Step 1: Use 70% of data as "training" (optimize parameters)
    Step 2: Test on the remaining 30% WITHOUT changing parameters
    Step 3: The out-of-sample (30%) result is the honest measure of edge

  If a strategy works well in-sample but fails out-of-sample, it's
  overfitted — a red flag. We want strategies where in-sample and
  out-of-sample results are both positive and close to each other.

TRANSACTION COSTS:
  All backtest trades include a 0.1% round-trip cost (covers spread + commission).
  Without this, results look unrealistically good.
"""

import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd

from app.strategies.base import BaseStrategy
from app.backtest.metrics import calculate_metrics
from app.config import settings

logger = logging.getLogger(__name__)


def run_backtest(
    strategy: BaseStrategy,
    df: pd.DataFrame,
    symbol: str,
    transaction_cost_pct: float = None,
) -> dict:
    """
    Run a standard full-history backtest on a strategy.

    Returns a metrics dict with full trade log.
    """
    tc = transaction_cost_pct if transaction_cost_pct is not None else settings.TRANSACTION_COST_PCT

    if df.empty:
        return {"error": "No price data", "symbol": symbol}

    df = df.copy()
    if "symbol" not in df.columns:
        df["symbol"] = symbol

    # Generate all signals
    signals = strategy.generate_signals(df)
    if not signals:
        return {
            "symbol": symbol,
            "strategy": strategy.name,
            "total_trades": 0,
            "error": "No signals generated",
        }

    # Simulate trades
    trades = _simulate_trades(signals, df, tc)

    metrics = calculate_metrics(trades)
    metrics["symbol"] = symbol
    metrics["strategy"] = strategy.name
    metrics["family"] = strategy.family
    metrics["start_date"] = str(df["date"].min().date() if hasattr(df["date"].min(), "date") else df["date"].min())
    metrics["end_date"] = str(df["date"].max().date() if hasattr(df["date"].max(), "date") else df["date"].max())
    metrics["trades_log"] = trades   # Full trade log for detailed analysis

    return metrics


def run_walk_forward(
    strategy: BaseStrategy,
    df: pd.DataFrame,
    symbol: str,
    train_ratio: float = None,
    transaction_cost_pct: float = None,
) -> dict:
    """
    Run walk-forward backtest: train on first 70%, test on last 30%.

    Returns:
      in_sample_metrics:   Training period results
      out_sample_metrics:  Test period results (the honest number)
      combined_metrics:    Full period results
      is_robust:           True if both periods are profitable
    """
    tr = train_ratio or settings.WALK_FORWARD_TRAIN_RATIO
    tc = transaction_cost_pct or settings.TRANSACTION_COST_PCT

    df = df.copy().sort_values("date").reset_index(drop=True)
    split_idx = int(len(df) * tr)

    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    if len(train_df) < 100 or len(test_df) < 30:
        return {"error": "Insufficient data for walk-forward split"}

    train_df["symbol"] = symbol
    test_df["symbol"] = symbol

    # Run on both halves
    train_signals = strategy.generate_signals(train_df)
    test_signals = strategy.generate_signals(test_df)

    train_trades = _simulate_trades(train_signals, train_df, tc)
    test_trades = _simulate_trades(test_signals, test_df, tc)

    in_sample = calculate_metrics(train_trades)
    out_sample = calculate_metrics(test_trades)

    # Walk-forward efficiency ratio: out_sample / in_sample sharpe
    in_sharpe = in_sample.get("sharpe_ratio", 0)
    out_sharpe = out_sample.get("sharpe_ratio", 0)
    wf_efficiency = (out_sharpe / in_sharpe) if in_sharpe != 0 else 0

    # A strategy is "robust" if:
    # 1. Both periods are profitable (positive total return)
    # 2. Out-of-sample Sharpe is at least 50% of in-sample
    is_robust = (
        in_sample.get("total_return_pct", 0) > 0
        and out_sample.get("total_return_pct", 0) > 0
        and wf_efficiency >= 0.5
    )

    full_trades = train_trades + test_trades
    combined = calculate_metrics(full_trades)

    return {
        "symbol": symbol,
        "strategy": strategy.name,
        "family": strategy.family,
        "train_period": f"{train_df['date'].iloc[0].date()} → {train_df['date'].iloc[-1].date()}",
        "test_period": f"{test_df['date'].iloc[0].date()} → {test_df['date'].iloc[-1].date()}",
        "in_sample": in_sample,
        "out_sample": out_sample,
        "combined": combined,
        "walk_forward_efficiency": round(wf_efficiency, 2),
        "is_robust": is_robust,
        "robustness_notes": _robustness_notes(in_sample, out_sample, wf_efficiency),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  TRADE SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

def _simulate_trades(signals, df: pd.DataFrame, tc: float) -> list[dict]:
    """
    Convert signals to trades with PnL.

    Simple simulation rules:
    - Enter at next day's open (realistic — we see the signal at close)
    - Exit when stop or target is hit, using daily high/low
    - Apply transaction cost on entry and exit
    """
    trades = []
    df_by_date = {row["date"]: row for _, row in df.iterrows()}
    dates = sorted(df_by_date.keys())

    for sig in signals:
        sig_date = pd.Timestamp(sig.date)
        sig_date_idx = None

        for idx, d in enumerate(dates):
            if pd.Timestamp(d) >= sig_date:
                sig_date_idx = idx
                break

        if sig_date_idx is None or sig_date_idx + 1 >= len(dates):
            continue

        # Enter next day's open
        entry_date = dates[sig_date_idx + 1]
        entry_row = df_by_date[entry_date]
        entry_price = entry_row["open"] * (1 + tc / 2)  # Adjust for spread

        stop = sig.stop_price
        target = sig.target_price
        direction = 1 if sig.action == "BUY" else -1

        # Check each subsequent day for stop/target hit
        exit_price = None
        exit_date = None
        exit_reason = "timeout"

        max_hold = 30   # Max hold in trading days before time-exit

        for i in range(sig_date_idx + 1, min(sig_date_idx + 1 + max_hold, len(dates))):
            day = dates[i]
            row = df_by_date[day]

            if direction == 1:   # Long
                if row["low"] <= stop:
                    exit_price = stop * (1 - tc / 2)
                    exit_reason = "stop"
                elif row["high"] >= target:
                    exit_price = target * (1 - tc / 2)
                    exit_reason = "target"
            else:                # Short
                if row["high"] >= stop:
                    exit_price = stop * (1 + tc / 2)
                    exit_reason = "stop"
                elif row["low"] <= target:
                    exit_price = target * (1 + tc / 2)
                    exit_reason = "target"

            if exit_price is not None:
                exit_date = day
                break

        # Time-exit at close of last day
        if exit_price is None:
            last_idx = min(sig_date_idx + max_hold, len(dates) - 1)
            exit_date = dates[last_idx]
            exit_price = df_by_date[exit_date]["close"] * (1 - tc / 2 * direction)
            exit_reason = "time"

        pnl_pct = direction * ((exit_price - entry_price) / entry_price) * 100

        trades.append({
            "symbol": sig.symbol,
            "strategy": sig.strategy_name,
            "direction": "long" if direction == 1 else "short",
            "entry_date": str(entry_date.date() if hasattr(entry_date, "date") else entry_date),
            "exit_date": str(exit_date.date() if hasattr(exit_date, "date") else exit_date),
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "stop_price": round(stop, 4),
            "target_price": round(target, 4),
            "pnl_pct": round(pnl_pct, 3),
            "exit_reason": exit_reason,
            "signal_confidence": sig.confidence,
        })

    return trades


def _robustness_notes(in_s: dict, out_s: dict, wf_eff: float) -> str:
    notes = []
    if in_s.get("total_return_pct", 0) > 0 and out_s.get("total_return_pct", 0) > 0:
        notes.append("✓ Profitable in both in-sample and out-of-sample periods.")
    elif out_s.get("total_return_pct", 0) <= 0:
        notes.append("✗ Out-of-sample is not profitable — strategy may be overfitted to historical data.")

    if wf_eff >= 0.8:
        notes.append("✓ Walk-forward efficiency is high — strategy generalizes well.")
    elif wf_eff >= 0.5:
        notes.append("~ Walk-forward efficiency is moderate — acceptable but watch live results.")
    else:
        notes.append("✗ Walk-forward efficiency is low — in-sample and out-of-sample differ significantly.")

    if in_s.get("max_drawdown_pct", 100) > 25:
        notes.append("⚠ High drawdown in training period — reduce position size.")

    if in_s.get("total_trades", 0) < 30:
        notes.append("⚠ Low trade count — results may not be statistically reliable.")

    return " ".join(notes)
