"""
registry.py — Central strategy registry.

HOW TO ADD A NEW STRATEGY:
  1. Create a new file in this folder, subclass BaseStrategy
  2. Import it here and add it to STRATEGY_REGISTRY
  3. That's it. The UI and API auto-discover it.

STRATEGY TAXONOMY (3 levels):
  Level 1 — Asset Class:    Equity | Options | Futures
  Level 2 — Strategy Type:  trend_following | hedge_equity | short_volatility |
                             covered_calls | dispersion
  Level 3 — Strategy:       The individual implementation (e.g. EMA Pullback Trend)
"""

from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.breakout_momentum import BreakoutMomentumStrategy
from app.strategies.volatility_event import VolatilityEventStrategy
from app.strategies.event_driven import EventDrivenStrategy
from app.strategies.dual_momentum import DualMomentumStrategy
from app.strategies.pairs_trade import PairsTradeStrategy
from app.strategies.covered_call import CoveredCallStrategy
from app.strategies.dispersion import DispersionStrategy
from app.strategies.cta_trend import CTATrendStrategy

# ── Registry: key → strategy class ──────────────────────────────────────────
# Add new strategies here. The key is stored in the database and used in URLs.
STRATEGY_REGISTRY: dict = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout_momentum": BreakoutMomentumStrategy,
    "volatility_event": VolatilityEventStrategy,
    "event_driven": EventDrivenStrategy,
    "dual_momentum": DualMomentumStrategy,
    "pairs_trade": PairsTradeStrategy,
    "covered_call": CoveredCallStrategy,
    "dispersion": DispersionStrategy,
    "cta_trend": CTATrendStrategy,
}

# ── 3-Level Taxonomy ─────────────────────────────────────────────────────────
# Level 1 → Level 2 → [strategy keys]
# This drives the tree display in the UI so you can see:
#   WHAT you're trading (asset class), HOW you're trading (strategy type),
#   and WHICH specific strategy is doing it.
STRATEGY_TAXONOMY = {
    "equity": {
        "label": "Equity",
        "icon": "📈",
        "description": "Stocks and ETFs — directional and mean-reversion plays",
        "color": "#22c55e",   # green
        "strategy_types": {
            "trend_following": {
                "label": "Trend Following",
                "description": "Ride confirmed price trends — enter on pullbacks or breakouts",
                "best_regimes": ["uptrend", "downtrend"],
                "strategies": ["trend_following", "breakout_momentum", "dual_momentum"],
            },
            "hedge_equity": {
                "label": "Hedge Equity",
                "description": "Defensive plays — fade extremes or trade catalysts to reduce net exposure",
                "best_regimes": ["ranging", "event", "risk_off"],
                "strategies": ["mean_reversion", "event_driven", "pairs_trade"],
            },
        },
    },
    "options": {
        "label": "Options",
        "icon": "⚡",
        "description": "Options strategies — trade volatility and premium",
        "color": "#8b5cf6",   # purple
        "strategy_types": {
            "short_volatility": {
                "label": "Short Volatility",
                "description": "Sell premium when IV is elevated; profit from IV contraction",
                "best_regimes": ["ranging", "high_vol"],
                "strategies": ["volatility_event"],
            },
            "covered_calls": {
                "label": "Covered Calls",
                "description": "Generate income on long equity positions by selling upside",
                "best_regimes": ["ranging", "uptrend"],
                "strategies": ["covered_call"],
            },
            "dispersion": {
                "label": "Dispersion",
                "description": "Long single-stock vol, short index vol when correlation is elevated",
                "best_regimes": ["high_vol", "event"],
                "strategies": ["dispersion"],
            },
        },
    },
    "futures": {
        "label": "Futures",
        "icon": "🔄",
        "description": "Futures contracts — systematic trend following across asset classes",
        "color": "#f59e0b",   # amber
        "strategy_types": {
            "trend_following": {
                "label": "Trend Following",
                "description": "Systematic CTA-style trend following across equity, rates, FX, and commodities",
                "best_regimes": ["uptrend", "downtrend"],
                "strategies": ["cta_trend"],
            },
        },
    },
}

# ── Family groupings (for regime routing — kept for backward compat) ─────────
STRATEGY_FAMILIES = {
    "trend": {
        "label": "Trend Following",
        "description": "Strategies that ride established price trends",
        "best_regime": ["uptrend", "downtrend"],
        "color": "#22c55e",
        "strategies": ["trend_following"],
    },
    "mean_reversion": {
        "label": "Mean Reversion",
        "description": "Strategies that fade extremes in range-bound markets",
        "best_regime": ["ranging"],
        "color": "#3b82f6",
        "strategies": ["mean_reversion"],
    },
    "breakout": {
        "label": "Breakout / Momentum",
        "description": "Strategies that enter on confirmed range expansions",
        "best_regime": ["high_vol", "uptrend", "downtrend"],
        "color": "#f59e0b",
        "strategies": ["breakout_momentum"],
    },
    "volatility": {
        "label": "Volatility",
        "description": "Strategies that trade the level of volatility itself",
        "best_regime": ["high_vol", "event", "ranging"],
        "color": "#8b5cf6",
        "strategies": ["volatility_event"],
    },
    "event": {
        "label": "Event Driven",
        "description": "Strategies based on known catalysts and their aftermath",
        "best_regime": ["event"],
        "color": "#ef4444",
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


def _get_best_regimes(key: str) -> list[str]:
    """Look up best regimes for a strategy key from the taxonomy."""
    for asset in STRATEGY_TAXONOMY.values():
        for stype in asset["strategy_types"].values():
            if key in stype["strategies"]:
                return stype["best_regimes"]
    return []


# ── Reverse map: strategy_key → (asset_class, strategy_type) ────────────────
# Built automatically from STRATEGY_TAXONOMY so it stays in sync.
STRATEGY_CLASS_MAP: dict[str, dict] = {}
for _ac, _ac_data in STRATEGY_TAXONOMY.items():
    for _st, _st_data in _ac_data["strategy_types"].items():
        for _sk in _st_data["strategies"]:
            STRATEGY_CLASS_MAP[_sk] = {
                "asset_class": _ac,
                "asset_class_label": _ac_data["label"],
                "strategy_type": _st,
                "strategy_type_label": _st_data["label"],
            }


def get_all_strategy_metadata() -> list[dict]:
    """Return metadata for all registered strategies (for the UI)."""
    result = []
    for key, cls in STRATEGY_REGISTRY.items():
        instance = cls()
        result.append({
            "key": key,
            "name": instance.name,
            "family": instance.family,
            "asset_class": getattr(instance, "asset_class", "equity"),
            "strategy_type": getattr(instance, "strategy_type", "unknown"),
            "description": instance.description,
            "best_regimes": _get_best_regimes(key),
            "parameters": instance.parameters,
        })
    return result


def get_strategies_for_regime(regime: str) -> list[str]:
    """Return recommended strategy keys for a given market regime."""
    return REGIME_TO_STRATEGIES.get(regime, [])
