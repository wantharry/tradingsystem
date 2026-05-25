"""backtest.py — API routes for backtesting."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.backtest.engine import run_backtest, run_walk_forward
from app.strategies.registry import get_strategy, get_all_strategy_metadata
from app.data.storage import get_price_data
from app.database.models import BacktestResult
from app.utils import sanitize_for_json

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy_key: str
    symbol: str
    walk_forward: bool = True
    parameters: Optional[dict] = None


@router.post("/run")
def run_backtest_endpoint(request: BacktestRequest, db: Session = Depends(get_db)):
    """Run a backtest for a strategy + symbol combination."""
    strategy = get_strategy(request.strategy_key, request.parameters)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{request.strategy_key}' not found")

    df = get_price_data(db, request.symbol.upper())
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {request.symbol}")

    df = df.copy()
    df["symbol"] = request.symbol.upper()

    if request.walk_forward:
        result = run_walk_forward(strategy, df, request.symbol.upper())
    else:
        result = run_backtest(strategy, df, request.symbol.upper())

    # Store result in DB
    _save_backtest_result(db, result, request.strategy_key, request.walk_forward)

    return sanitize_for_json(result)


@router.post("/run/batch")
def run_batch_backtest(
    strategy_key: str,
    symbols: list[str],
    walk_forward: bool = True,
    db: Session = Depends(get_db),
):
    """Run a backtest for one strategy across multiple symbols."""
    strategy = get_strategy(strategy_key)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_key}' not found")

    results = []
    for symbol in symbols[:15]:   # Limit for performance
        df = get_price_data(db, symbol.upper())
        if df.empty:
            continue
        df = df.copy()
        df["symbol"] = symbol.upper()
        try:
            if walk_forward:
                r = run_walk_forward(strategy, df, symbol.upper())
            else:
                r = run_backtest(strategy, df, symbol.upper())
            results.append(r)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    # Sort by out-of-sample Sharpe (or total return for non-WF)
    results.sort(
        key=lambda x: (x.get("out_sample", {}) or {}).get("sharpe_ratio", 0),
        reverse=True,
    )
    return sanitize_for_json({"strategy": strategy.name, "results": results})


@router.get("/history/{symbol}")
def get_backtest_history(
    symbol: str,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Get stored backtest results for a symbol."""
    rows = (
        db.query(BacktestResult)
        .filter(BacktestResult.symbol == symbol.upper())
        .order_by(BacktestResult.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "symbol": symbol.upper(),
        "results": [
            {
                "id": r.id,
                "strategy_id": r.strategy_id,
                "total_return_pct": r.total_return_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "win_rate_pct": r.win_rate_pct,
                "profit_factor": r.profit_factor,
                "total_trades": r.total_trades,
                "is_walk_forward": r.is_walk_forward,
                "test_sharpe": r.test_sharpe,
                "created_at": str(r.created_at),
            }
            for r in rows
        ],
    }


def _save_backtest_result(db: Session, result: dict, strategy_key: str, is_wf: bool):
    """Persist a backtest result to the database."""
    from app.database.models import Strategy
    try:
        strat_db = db.query(Strategy).filter(Strategy.name == strategy_key).first()
        metrics = result.get("combined", result) if is_wf else result
        db.add(BacktestResult(
            strategy_id=strat_db.id if strat_db else None,
            symbol=result.get("symbol", "UNKNOWN"),
            start_date=None,
            end_date=None,
            total_return_pct=metrics.get("total_return_pct"),
            annualized_return_pct=metrics.get("annualized_return_pct"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            sortino_ratio=metrics.get("sortino_ratio"),
            max_drawdown_pct=metrics.get("max_drawdown_pct"),
            win_rate_pct=metrics.get("win_rate_pct"),
            profit_factor=metrics.get("profit_factor"),
            expectancy=metrics.get("expectancy"),
            total_trades=metrics.get("total_trades"),
            avg_hold_days=metrics.get("avg_hold_days"),
            is_walk_forward=is_wf,
            train_sharpe=result.get("in_sample", {}).get("sharpe_ratio") if is_wf else None,
            test_sharpe=result.get("out_sample", {}).get("sharpe_ratio") if is_wf else None,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
