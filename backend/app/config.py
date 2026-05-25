"""
config.py — Central configuration for the entire system.

WHY THIS EXISTS:
  All tunable parameters live here. When you want to change how the
  system behaves (e.g. tighten risk, change indicator thresholds, add
  new symbols), you change ONE place — either this file or the .env file.
  Nothing is hard-coded inside strategy or backtest files.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────
    APP_NAME: str = "Stock Analysis Trading System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./data/trading.db"

    # ── Free Data API Keys ───────────────────────────────────────────
    FRED_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None

    # ── Default Watchlist ────────────────────────────────────────────
    DEFAULT_SYMBOLS: str = (
        "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,"
        "SPY,QQQ,IWM,GLD,TLT,"
        "ES=F,NQ=F,CL=F,GC=F"
    )

    @property
    def symbols_list(self) -> List[str]:
        return [s.strip() for s in self.DEFAULT_SYMBOLS.split(",") if s.strip()]

    # ── Risk Parameters ──────────────────────────────────────────────
    # 1% of portfolio per trade. Conservative default.
    DEFAULT_RISK_PER_TRADE_PCT: float = 1.0
    # Stop generating signals for the day once we lose 2% of portfolio.
    MAX_DAILY_LOSS_PCT: float = 2.0
    MAX_CONCURRENT_POSITIONS: int = 5

    # ── Trend Following Thresholds ───────────────────────────────────
    # ADX > 25 = trend is present. ADX > 40 = strong trend.
    ADX_TREND_THRESHOLD: int = 25
    ADX_STRONG_TREND_THRESHOLD: int = 40
    # Short-term EMA and long-term EMA for trend direction.
    EMA_SHORT: int = 20
    EMA_LONG: int = 50
    EMA_VERY_LONG: int = 200

    # ── Mean Reversion Thresholds ────────────────────────────────────
    # RSI below 30 = oversold (potential buy). Above 70 = overbought (potential sell).
    RSI_OVERSOLD: int = 30
    RSI_OVERBOUGHT: int = 70
    RSI_PERIOD: int = 14
    BB_PERIOD: int = 20
    BB_STD: float = 2.0

    # ── Breakout Thresholds ──────────────────────────────────────────
    BREAKOUT_PERIOD: int = 20        # Look for 20-period highs/lows
    VOLUME_BREAKOUT_MULTIPLIER: float = 1.5   # Volume must be 1.5x average

    # ── Volatility Thresholds ────────────────────────────────────────
    # IV percentile above 80 = expensive options, consider selling volatility.
    # IV percentile below 20 = cheap options, consider buying volatility.
    IV_HIGH_PERCENTILE: int = 80
    IV_LOW_PERCENTILE: int = 20
    ATR_PERIOD: int = 14

    # ── Regime Detection ─────────────────────────────────────────────
    # How many bars of lookback for ATR percentile calculation.
    REGIME_ATR_LOOKBACK: int = 252   # ~1 year of trading days

    # ── Backtest Settings ────────────────────────────────────────────
    BACKTEST_PERIOD_YEARS: int = 3
    WALK_FORWARD_TRAIN_RATIO: float = 0.7
    MIN_TRADES_FOR_VALIDITY: int = 30
    # Transaction cost: 0.1% per trade round-trip (covers spread + commission)
    TRANSACTION_COST_PCT: float = 0.001

    # ── Scheduler (times in ET) ───────────────────────────────────────
    DATA_REFRESH_HOUR: int = 16   # 4 PM — after market close
    DAILY_ACTION_HOUR: int = 9    # 9 AM — before market open
    DAILY_ACTION_MINUTE: int = 0

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global singleton — import this everywhere you need settings.
settings = Settings()
