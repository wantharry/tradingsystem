"""
models.py — All database table definitions.

DESIGN PRINCIPLE: Append-only data. We never overwrite historical records.
Every data point has a source and created_at timestamp for full auditability.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Date, Text, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database.database import Base


class Symbol(Base):
    """
    The watchlist — all symbols the system tracks.
    asset_type: 'equity', 'etf', 'future', 'index'
    """
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200))
    asset_type = Column(String(20), default="equity")   # equity, etf, future, index
    sector = Column(String(100))
    exchange = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    price_data = relationship("PriceData", back_populates="symbol_ref")
    regime_history = relationship("RegimeHistory", back_populates="symbol_ref")


class PriceData(Base):
    """
    OHLCV data for each symbol. Core dataset for all analysis.

    WHY WE STORE THIS:
      Rather than fetching data from Yahoo Finance every time we run a
      strategy or backtest, we store it locally. This makes backtests
      fast, reproducible, and immune to API outages.

    Data is split by interval: 'daily', '1h', '15m', etc.
    """
    __tablename__ = "price_data"
    __table_args__ = (
        UniqueConstraint("symbol", "date", "interval", name="uq_price_symbol_date_interval"),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey("symbols.symbol"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    interval = Column(String(10), default="1d")   # 1d, 1h, 15m
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adj_close = Column(Float)   # Adjusted for splits and dividends
    source = Column(String(50), default="yfinance")
    created_at = Column(DateTime, default=datetime.utcnow)

    symbol_ref = relationship("Symbol", back_populates="price_data")


class MacroData(Base):
    """
    Macroeconomic indicators from FRED.
    Examples: DFF (Fed Funds Rate), CPIAUCSL (CPI), VIXCLS (VIX), T10Y2Y (yield curve)

    WHY WE STORE THIS:
      Macro regime drives everything. A rising rate environment changes which
      sectors trend. High VIX changes strategy selection. These indicators
      are context for every daily decision.
    """
    __tablename__ = "macro_data"
    __table_args__ = (
        UniqueConstraint("series_id", "date", name="uq_macro_series_date"),
    )

    id = Column(Integer, primary_key=True)
    series_id = Column(String(50), nullable=False, index=True)   # e.g. 'VIXCLS'
    series_name = Column(String(200))
    date = Column(Date, nullable=False, index=True)
    value = Column(Float)
    source = Column(String(50), default="fred")
    created_at = Column(DateTime, default=datetime.utcnow)


class RegimeHistory(Base):
    """
    Daily market regime classification for each symbol.

    REGIME VALUES:
      - 'uptrend'     → Strong upward trend, use trend-following long strategies
      - 'downtrend'   → Strong downward trend, use trend-following short strategies
      - 'ranging'     → Sideways market, use mean reversion strategies
      - 'high_vol'    → Elevated volatility, use breakout or long-vol strategies
      - 'risk_off'    → Stress/panic, reduce all exposure
      - 'event'       → Major catalyst imminent (earnings, FOMC, CPI)

    WHY WE STORE REGIME HISTORY:
      Strategy performance attribution by regime. We can answer: "Does our
      trend strategy actually outperform during uptrend regimes?" This is the
      foundation of regime-aware position sizing and strategy rotation.
    """
    __tablename__ = "regime_history"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_regime_symbol_date"),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), ForeignKey("symbols.symbol"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    regime = Column(String(20), nullable=False)     # See docstring above
    adx = Column(Float)             # Trend strength indicator (>25 = trend present)
    atr_pct = Column(Float)         # ATR as % of price (measures volatility)
    atr_percentile = Column(Float)  # Where current ATR sits in 1-year distribution
    rsi = Column(Float)             # Momentum indicator
    above_200ema = Column(Boolean)  # Is price above long-term trend?
    regime_score = Column(Float)    # Composite score used to determine regime
    notes = Column(Text)            # Human-readable explanation
    created_at = Column(DateTime, default=datetime.utcnow)

    symbol_ref = relationship("Symbol", back_populates="regime_history")


class Strategy(Base):
    """
    Strategy configuration. Each row is one strategy with its parameters.
    Parameters are stored as JSON so they're flexible and user-editable.
    """
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    family = Column(String(50), nullable=False)   # trend, mean_reversion, breakout, volatility, event
    description = Column(Text)
    parameters = Column(JSON, default={})          # Strategy-specific config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    backtest_results = relationship("BacktestResult", back_populates="strategy")
    daily_actions = relationship("DailyAction", back_populates="strategy")


class BacktestResult(Base):
    """
    Stored results of a backtest run for a strategy + symbol combination.

    WHY WE STORE THESE:
      Backtesting is slow. We store results so the UI can instantly display
      historical performance without re-running the test each time.
      We also track WHEN the test was run so we know if results are stale.
    """
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    # Core performance metrics
    total_return_pct = Column(Float)
    annualized_return_pct = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown_pct = Column(Float)
    win_rate_pct = Column(Float)
    profit_factor = Column(Float)    # gross profit / gross loss (>1.5 is good)
    expectancy = Column(Float)       # average profit per trade in R multiples
    total_trades = Column(Integer)
    avg_hold_days = Column(Float)
    # Walk-forward specific
    is_walk_forward = Column(Boolean, default=False)
    train_sharpe = Column(Float)
    test_sharpe = Column(Float)     # Out-of-sample Sharpe — most important metric
    # Full trade log stored as JSON for detailed analysis
    trades_json = Column(JSON, default=[])
    regime_breakdown = Column(JSON, default={})   # Performance per regime
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy", back_populates="backtest_results")


class DailyAction(Base):
    """
    Generated trading action for a specific symbol on a specific day.

    WHY WE LOG EVERY ACTION:
      Even if you don't take a trade, we log what the system suggested.
      Over time this builds a record of signal quality, accuracy rate,
      and whether skipping signals was the right call.
    """
    __tablename__ = "daily_actions"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"))
    regime = Column(String(20))             # What regime was detected that day
    action = Column(String(10))             # BUY, SELL, HOLD, AVOID
    entry_price = Column(Float)
    stop_price = Column(Float)
    target_price = Column(Float)
    position_size_pct = Column(Float)       # % of portfolio
    confidence = Column(Float)              # 0-1 confidence score
    risk_reward_ratio = Column(Float)       # (target - entry) / (entry - stop)
    reasoning = Column(Text)               # Plain-English explanation of WHY
    strategy_key = Column(String(50))      # Registry key (e.g. "trend_following", "covered_call")
    outcome = Column(String(20))           # Filled in at end of day: WIN, LOSS, SKIPPED
    actual_pnl_pct = Column(Float)         # Actual PnL if trade was taken
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy", back_populates="daily_actions")


class DailyLog(Base):
    """
    Daily market journal — written automatically each day.
    Captures the narrative reasoning behind all decisions.

    WHY WE WRITE THIS:
      Numbers don't tell the full story. The daily log captures CONTEXT:
      "Today's trend signal was strong but we avoided it because FOMC is tomorrow."
      Reading this log helps you understand the system's logic and improve it.
    """
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    market_regime_summary = Column(Text)    # What is the market doing?
    top_opportunities = Column(JSON)        # Top 3 setups for the day
    macro_context = Column(Text)            # Relevant macro factors
    risk_alerts = Column(JSON)              # Any risk flags (events, high vol, etc.)
    strategy_notes = Column(Text)           # Which strategies are active and why
    no_trade_reasons = Column(Text)         # Why we skipped certain signals
    portfolio_exposure = Column(Float)      # % of capital currently deployed
    created_at = Column(DateTime, default=datetime.utcnow)
