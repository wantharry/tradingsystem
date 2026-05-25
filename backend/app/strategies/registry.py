"""
registry.py — Central strategy registry.

HOW TO ADD A NEW STRATEGY:
  1. Create a new file in this folder, subclass BaseStrategy
  2. Import it here and add it to STRATEGY_REGISTRY
  3. That's it. The UI and API auto-discover it.

DESIGN:
  The registry maps a strategy key to its class.
  This lets us instantiate strategies by name from the DB or API.
"""

from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.breakout_momentum import BreakoutMomentumStrategy
from app.strategies.volatility_event import VolatilityEventStrategy
from app.strategies.event_driven import EventDrivenStrategy

# ── Registry: key → strategy class ──────────────────────────────────────────
# Add new strategies here. The key is stored in the database and used in URLs.
STRATEGY_REGISTRY: dict = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout_momentum": BreakoutMomentumStrategy,
    "volatility_event": VolatilityEventStrategy,
    "event_driven": EventDrivenStrategy,
}

# ── Family groupings (for UI display and regime routing) ────────────────────
STRATEGY_FAMILIES = {
    "trend": {
        "label": "Trend Following",
        "description": "Strategies that ride established price trends",
        "best_regime": ["uptrend", "downtrend"],
        "color": "#22c55e",   # green
        "strategies": ["trend_following"],
    },
    "mean_reversion": {
        "label": "Mean Reversion",
        "description": "Strategies that fade extremes in range-bound markets",
        "best_regime": ["ranging"],
        "color": "#3b82f6",   # blue
        "strategies": ["mean_reversion"],
    },
    "breakout": {
        "label": "Breakout / Momentum",
        "description": "Strategies that enter on confirmed range expansions",
        "best_regime": ["high_vol", "uptrend", "downtrend"],
        "color": "#f59e0b",   # amber
        "strategies": ["breakout_momentum"],
    },
    "volatility": {
        "label": "Volatility",
        "description": "Strategies that trade the level of volatility itself",
        "best_regime": ["high_vol", "event", "ranging"],
        "color": "#8b5cf6",   # purple
        "strategies": ["volatility_event"],
    },
    "event": {
        "label": "Event Driven",
        "description": "Strategies based on known catalysts and their aftermath",
        "best_regime": ["event"],
        "color": "#ef4444",   # red
        "strategies": ["event_driven"],
    },
}

# ── Regime → recommended strategy keys ──────────────────────────────────────
REGIME_TO_STRATEGIES = {
    "uptrend":   ["trend_following", "breakout_momentum"],
    "downtrend": ["trend_following", "breakout_momentum"],
    "ranging":   ["mean_reversion", "volatility_event"],
    "high_vol":  ["breakout_momentum", "volatility_event"],
    "event":     ["event_driven", "volatility_event"],
    "risk_off":  [],   # No new positions in risk-off
}


def get_strategy(key: str, parameters: dict = None):
    """Instantiate a strategy by key. Returns None if key is unknown."""
    cls = STRATEGY_REGISTRY.get(key)
    if cls is None:
        return None
    return cls(parameters=parameters)


def get_all_strategy_metadata() -> list[dict]:
    """Return metadata for all registered strategies (for the UI)."""
    result = []
    for key, cls in STRATEGY_REGISTRY.items():
        instance = cls()
        result.append({
            "key": key,
            "name": instance.name,
            "family": instance.family,
            "description": instance.description,
            "parameters": instance.parameters,
        })
    return result


def get_strategies_for_regime(regime: str) -> list[str]:
    """Return recommended strategy keys for a given market regime."""
    return REGIME_TO_STRATEGIES.get(regime, [])
