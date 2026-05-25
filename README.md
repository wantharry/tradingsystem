# Stock Analysis & Trading System

A fully automated trading analysis platform that:
- Detects market regime every day (trending, ranging, high-vol, risk-off, event)
- Selects the best strategy family for the detected regime
- Backtests every strategy with walk-forward testing
- Generates a clear daily action sheet (what to trade, entry, stop, target, size)
- Stores all historical data and daily decisions with full reasoning
- Provides a friendly, easy-to-understand UI

> **Disclaimer**: This is an educational and analytical tool. It is NOT financial advice. Always apply your own judgment and risk management before trading.

---

## What This System Does — Plain English

Every morning the system:
1. Downloads fresh market data (prices, volume, macro indicators)
2. Asks: "What is the market doing right now?" — trending up, trending down, stuck in a range, or unstable?
3. Based on the answer, picks the best strategy family
4. Tells you: what to trade, which direction, where to enter, where to put your stop-loss, and how big your position should be
5. Logs all the reasoning so you understand WHY each trade is suggested

---

## Strategy Families (Plain English)

| Family | When to use | Core idea |
|---|---|---|
| Trend Following | Market is moving clearly in one direction | Ride the wave, buy pullbacks in uptrends, sell rallies in downtrends |
| Mean Reversion | Market is stuck in a range | Buy near the bottom of the range, sell near the top |
| Breakout Momentum | Market is about to break out of consolidation | Buy the breakout with confirmation, ride the expansion |
| Volatility / Event | Unusual volatility or major event expected | Use options to profit from big moves without betting direction |
| Event Driven | Earnings, FOMC, CPI, major news | Pre-defined setups around catalysts with strict risk limits |

---

## Quick Start

### Option 1: Docker (Recommended)
```bash
# Clone and setup
git clone <repo>
cd stock-analysis

# Copy and configure environment
cp .env.example .env

# Start everything
docker-compose up -d

# Open browser at http://localhost:3000
```

### Option 2: Manual Setup
```bash
# Run the setup script
bash setup.sh

# Start backend
cd backend && uvicorn app.main:app --reload --port 8000

# Start frontend (new terminal)
cd frontend && npm run dev
```

---

## Free Data Sources Used

| Source | What it provides | API Key Required |
|---|---|---|
| Yahoo Finance (yfinance) | Stock prices, OHLCV, fundamentals, options chains | No — free |
| FRED (Federal Reserve) | Macro data: rates, CPI, GDP, VIX | Yes — free at fred.stlouisfed.org |
| Alpha Vantage | Supplemental price and earnings data | Yes — free at alphavantage.co |

The system works **without any API keys** using just yfinance. FRED and Alpha Vantage add richer macro and earnings data.

---

## Project Structure

```
stock-analysis/
├── backend/               # Python FastAPI backend
│   ├── app/
│   │   ├── main.py        # Application entry point
│   │   ├── config.py      # All settings
│   │   ├── database/      # Database models and connection
│   │   ├── data/          # Data fetchers and storage
│   │   ├── strategies/    # All trading strategy implementations
│   │   ├── regime/        # Market regime detection
│   │   ├── backtest/      # Backtesting engine
│   │   ├── daily/         # Daily action generator
│   │   └── api/           # REST API routes
│   └── requirements.txt
├── frontend/              # React frontend UI
│   ├── src/
│   │   ├── pages/         # Dashboard, DailyActions, Strategies, Backtest, Data
│   │   ├── components/    # Reusable UI components
│   │   └── api/           # API client
│   └── package.json
├── data/                  # SQLite database and logs (auto-created)
├── docs/                  # Strategy documentation and daily logs
│   ├── strategies/        # One file per strategy with full explanation
│   └── HOW_IT_WORKS.md
├── .env.example           # Environment variable template
├── docker-compose.yml     # Docker setup
└── setup.sh               # Manual setup script
```

---

## How to Add a New Strategy

1. Create a new file in `backend/app/strategies/` extending `BaseStrategy`
2. Implement `generate_signals(df)` and `get_documentation()`
3. Register it in `backend/app/strategies/registry.py`
4. The system auto-discovers it and adds it to the UI

---

## Daily Workflow

```
9:00 AM ET  → System fetches pre-market data
9:15 AM ET  → Regime detection runs
9:20 AM ET  → Daily action sheet generated
9:30 AM ET  → You review the sheet and decide what to trade
4:00 PM ET  → End-of-day data stored, daily log written
```

---

## Risk Rules (Built-in)

- Max 1% portfolio risk per trade (configurable)
- Max 2% daily portfolio loss before system stops generating signals
- Max 5 concurrent positions
- No trading in blackout windows (30 min before major macro events)
- No new positions on days with unclear regime
