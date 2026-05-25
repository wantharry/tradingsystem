"""
base.py — Abstract base class that all trading strategies must implement.

ARCHITECTURE:
  Every strategy is a self-contained class with:
    1. A name and family (for the registry and UI)
    2. Configurable parameters (stored in DB, editable from UI)
    3. generate_signals(df) — the core logic that produces trading signals
    4. get_documentation() — human-readable explanation anyone can follow

  This design makes adding a new strategy trivial:
    - Create a file in this folder
    - Subclass BaseStrategy
    - Implement the two required methods
    - Register it in registry.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Signal:
    """
    A single trading signal for one symbol on one date.

    Fields:
        symbol:             The ticker (e.g. 'AAPL')
        date:               The signal date
        action:             BUY, SELL, HOLD, or AVOID
        entry_price:        Suggested entry price (typically current close or next-open)
        stop_price:         Where to exit if wrong (hard risk limit)
        target_price:       Where to take profit (reward target)
        position_size_pct:  % of portfolio to risk (not deploy — risk)
        confidence:         0.0–1.0 confidence score (based on signal strength)
        risk_reward_ratio:  (target - entry) / (entry - stop). Only take if >= 2.0
        reasoning:          Plain-English explanation of why this signal was generated
        strategy_name:      Which strategy generated this
        indicators:         Dict of indicator values used (for UI display)
    """
    symbol: str
    date: object
    action: str            # BUY | SELL | HOLD | AVOID
    entry_price: float
    stop_price: float
    target_price: float
    position_size_pct: float = 1.0
    confidence: float = 0.5
    risk_reward_ratio: float = 0.0
    reasoning: str = ""
    strategy_name: str = ""
    indicators: dict = field(default_factory=dict)

    def __post_init__(self):
        # Auto-calculate R:R if not provided
        if self.risk_reward_ratio == 0.0 and self.entry_price and self.stop_price and self.target_price:
            risk = abs(self.entry_price - self.stop_price)
            reward = abs(self.target_price - self.entry_price)
            self.risk_reward_ratio = reward / risk if risk > 0 else 0.0

    def is_actionable(self) -> bool:
        """A signal is worth acting on if it meets minimum quality thresholds."""
        return (
            self.action in ("BUY", "SELL")
            and self.confidence >= 0.4
            and self.risk_reward_ratio >= 1.5
        )

    def to_dict(self) -> dict:
        def _safe(v):
            """Convert numpy/pandas scalars to native Python types."""
            import numpy as np
            if isinstance(v, (np.bool_,)):
                return bool(v)
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return float(v)
            if isinstance(v, float) and (v != v):  # NaN check
                return None
            return v

        return {
            "symbol": self.symbol,
            "date": str(self.date),
            "action": self.action,
            "entry_price": round(self.entry_price, 4) if self.entry_price else None,
            "stop_price": round(self.stop_price, 4) if self.stop_price else None,
            "target_price": round(self.target_price, 4) if self.target_price else None,
            "position_size_pct": self.position_size_pct,
            "confidence": round(self.confidence, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "reasoning": self.reasoning,
            "strategy_name": self.strategy_name,
            "is_actionable": bool(self.is_actionable()),
            "indicators": {k: _safe(v) for k, v in self.indicators.items()},
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    Subclass this and implement generate_signals() and get_documentation().
    """

    # Required class attributes — set in each subclass
    name: str = "unnamed"
    family: str = "unknown"     # trend | mean_reversion | breakout | volatility | event
    description: str = ""

    def __init__(self, parameters: Optional[dict] = None):
        """
        parameters: Override default settings from the database or config.
        This allows strategy parameters to be edited from the UI without code changes.
        """
        self.parameters = {**self.default_parameters(), **(parameters or {})}

    def default_parameters(self) -> dict:
        """
        Override in subclasses to define strategy-specific defaults.
        These are the parameters shown in the UI for editing.
        """
        return {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """
        Core logic. Takes OHLCV DataFrame and returns a list of Signal objects.

        Input DataFrame columns:
            date, open, high, low, close, volume, adj_close

        The implementation should:
          1. Calculate indicators on the DataFrame
          2. Identify entry conditions
          3. Calculate entry, stop, and target levels
          4. Build Signal objects with full reasoning
          5. Return only valid signals (HOLD signals are optional)
        """
        pass

    @abstractmethod
    def get_documentation(self) -> dict:
        """
        Return a structured dict of human-readable documentation.

        Must include:
          overview:       What this strategy does in 2-3 sentences
          when_to_use:    Market conditions where this strategy performs best
          when_to_avoid:  Market conditions to skip this strategy
          entry_rules:    Numbered list of exact entry conditions
          exit_rules:     How to manage the trade once in
          risk_rules:     Position sizing and stop loss logic
          examples:       1-2 concrete examples of a setup
          common_mistakes: What new traders do wrong with this strategy
        """
        pass

    def calculate_position_size(
        self,
        portfolio_value: float,
        entry: float,
        stop: float,
        risk_pct: float = 1.0,
    ) -> dict:
        """
        Calculate position size using the fixed-risk method.

        PLAIN ENGLISH:
          "I want to lose no more than 1% of my account if this trade hits
          my stop loss. How many shares/contracts should I buy?"

        Formula:
          risk_amount = portfolio * risk_pct / 100
          shares = risk_amount / (entry - stop)
        """
        risk_amount = portfolio_value * (risk_pct / 100)
        price_risk = abs(entry - stop)
        if price_risk == 0:
            return {"shares": 0, "risk_amount": 0, "position_value": 0}

        shares = risk_amount / price_risk
        return {
            "shares": int(shares),
            "risk_amount": round(risk_amount, 2),
            "position_value": round(shares * entry, 2),
            "position_pct_of_portfolio": round((shares * entry / portfolio_value) * 100, 2),
        }

    def _add_base_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add common indicators used by most strategies.
        This avoids duplication — call this at the start of generate_signals().
        """
        import pandas_ta as ta

        df = df.copy()
        df = df.sort_values("date").reset_index(drop=True)

        # Trend indicators
        df["ema20"] = ta.ema(df["close"], length=20)
        df["ema50"] = ta.ema(df["close"], length=50)
        df["ema200"] = ta.ema(df["close"], length=200)

        # Momentum
        df["rsi"] = ta.rsi(df["close"], length=14)

        # Volatility
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        df["atr"] = atr

        # Trend strength
        adx_data = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx_data is not None and not adx_data.empty:
            df["adx"] = adx_data.iloc[:, 0]   # ADX column

        # Volume average
        df["vol_avg"] = df["volume"].rolling(20).mean()

        return df
