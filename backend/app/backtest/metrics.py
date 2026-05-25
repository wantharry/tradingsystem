"""
metrics.py — Backtest performance metrics calculations.

All metrics are calculated from a list of trade records.
Each trade record is a dict with: entry_date, exit_date, entry_price,
exit_price, direction ('long'/'short'), symbol, strategy.

WHY THESE METRICS:
  Win rate alone is misleading — a 90% win rate with 1:10 R:R loses money.
  We compute a comprehensive set of metrics to understand edge quality:

  1. Sharpe Ratio:   Risk-adjusted return. Above 1.0 is good. Above 2.0 is excellent.
  2. Sortino Ratio:  Like Sharpe but only penalizes downside volatility. More fair.
  3. Max Drawdown:   The worst peak-to-trough loss. Critical for position sizing.
  4. Profit Factor:  Gross profit / Gross loss. Above 1.5 is solid.
  5. Expectancy:     Average profit per trade. Must be positive.
  6. Win Rate:       % of trades that are profitable.
  7. Avg Hold Days:  How long trades are held on average.
"""

import numpy as np
import pandas as pd
from typing import Optional


def calculate_metrics(trades: list[dict], initial_capital: float = 100000) -> dict:
    """
    Calculate comprehensive performance metrics from a list of trades.

    Each trade dict must have:
      pnl_pct: profit/loss as a percentage (e.g. 2.5 for 2.5%)
      entry_date: date of entry
      exit_date: date of exit (optional for hold time calculation)
    """
    if not trades:
        return _empty_metrics()

    pnls = [t.get("pnl_pct", 0) for t in trades]
    pnls_arr = np.array(pnls)

    total_trades = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)  # In %

    # Equity curve
    equity = [initial_capital]
    for pnl in pnls:
        equity.append(equity[-1] * (1 + pnl / 100))

    equity_arr = np.array(equity)
    total_return_pct = (equity_arr[-1] / equity_arr[0] - 1) * 100

    # Annualized return (estimate using number of trades as proxy for time)
    # If we have dates, use actual time span
    days_span = _calc_days_span(trades)
    if days_span > 0:
        years = days_span / 365.0
        ann_return = (((equity_arr[-1] / equity_arr[0]) ** (1 / years)) - 1) * 100
    else:
        ann_return = total_return_pct

    # Drawdown
    max_drawdown = _calc_max_drawdown(equity_arr)

    # Sharpe and Sortino (using trade PnL as daily return proxy)
    if len(pnls_arr) > 1:
        pnl_std = np.std(pnls_arr)
        sharpe = (np.mean(pnls_arr) / pnl_std * np.sqrt(252)) if pnl_std > 0 else 0

        downside = pnls_arr[pnls_arr < 0]
        downside_std = np.std(downside) if len(downside) > 1 else 0
        sortino = (np.mean(pnls_arr) / downside_std * np.sqrt(252)) if downside_std > 0 else 0
    else:
        sharpe = 0
        sortino = 0

    # Average hold time
    avg_hold_days = _calc_avg_hold_days(trades)

    # Per-year breakdown
    yearly = _calc_yearly_breakdown(trades)

    # Consecutive wins/losses
    max_consec_wins, max_consec_losses = _calc_consecutive(pnls)

    return {
        "total_trades": total_trades,
        "win_rate_pct": round(win_rate * 100, 1),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 3),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "gross_profit_pct": round(gross_profit, 2),
        "gross_loss_pct": round(gross_loss, 2),
        "avg_hold_days": round(avg_hold_days, 1),
        "max_consec_wins": max_consec_wins,
        "max_consec_losses": max_consec_losses,
        "yearly_breakdown": yearly,
        "equity_curve": [round(v, 2) for v in equity_arr.tolist()],
        "is_valid": total_trades >= 30 and profit_factor > 0,   # Minimum for statistical reliability
    }


def _calc_max_drawdown(equity: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a percentage."""
    peak = equity[0]
    max_dd = 0.0
    for val in equity:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _calc_days_span(trades: list[dict]) -> int:
    """Calculate total calendar days covered by the trade history."""
    try:
        dates = [pd.to_datetime(t["entry_date"]) for t in trades if "entry_date" in t]
        if len(dates) < 2:
            return 0
        return (max(dates) - min(dates)).days
    except Exception:
        return 0


def _calc_avg_hold_days(trades: list[dict]) -> float:
    """Average number of days trades were held."""
    hold_days = []
    for t in trades:
        try:
            entry = pd.to_datetime(t.get("entry_date"))
            exit_ = pd.to_datetime(t.get("exit_date"))
            if entry and exit_:
                hold_days.append((exit_ - entry).days)
        except Exception:
            pass
    return np.mean(hold_days) if hold_days else 0


def _calc_yearly_breakdown(trades: list[dict]) -> dict:
    """Return a dict of {year: metrics} for per-year analysis."""
    yearly = {}
    for t in trades:
        try:
            year = str(pd.to_datetime(t.get("entry_date")).year)
        except Exception:
            continue
        if year not in yearly:
            yearly[year] = {"trades": 0, "total_pnl_pct": 0.0, "wins": 0}
        yearly[year]["trades"] += 1
        yearly[year]["total_pnl_pct"] += t.get("pnl_pct", 0)
        if t.get("pnl_pct", 0) > 0:
            yearly[year]["wins"] += 1

    # Add win rate per year
    for year in yearly:
        d = yearly[year]
        d["win_rate_pct"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] > 0 else 0
        d["total_pnl_pct"] = round(d["total_pnl_pct"], 2)

    return yearly


def _calc_consecutive(pnls: list) -> tuple[int, int]:
    """Return (max consecutive wins, max consecutive losses)."""
    max_wins = max_losses = curr_wins = curr_losses = 0
    for p in pnls:
        if p > 0:
            curr_wins += 1
            curr_losses = 0
        elif p < 0:
            curr_losses += 1
            curr_wins = 0
        max_wins = max(max_wins, curr_wins)
        max_losses = max(max_losses, curr_losses)
    return max_wins, max_losses


def _empty_metrics() -> dict:
    return {
        "total_trades": 0, "win_rate_pct": 0, "total_return_pct": 0,
        "annualized_return_pct": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
        "max_drawdown_pct": 0, "profit_factor": 0, "expectancy": 0,
        "avg_win_pct": 0, "avg_loss_pct": 0, "gross_profit_pct": 0,
        "gross_loss_pct": 0, "avg_hold_days": 0, "max_consec_wins": 0,
        "max_consec_losses": 0, "yearly_breakdown": {}, "equity_curve": [],
        "is_valid": False,
    }
