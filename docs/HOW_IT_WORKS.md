# How the Trading System Works

A plain-English guide for anyone, even without trading experience.

---

## The Big Picture

Think of this system as a **weather forecast for the stock market**. Just like you dress differently on a sunny vs stormy day, you use *different trading strategies* depending on current market conditions.

Every day the system:
1. **Checks the weather** — detects the current market regime (uptrend, downtrend, choppy, volatile, etc.)
2. **Picks the right strategies** — uses strategies that work well in the detected conditions
3. **Scans your watchlist** — looks for specific setups in each stock
4. **Ranks the setups** — scores them by confidence and risk vs. reward
5. **Writes you a daily report** — tells you exactly what to do and *why*

---

## Market Regimes (The "Weather Forecast")

The system identifies 6 possible market conditions:

| Regime | What it means | Best strategies |
|--------|--------------|-----------------|
| **Uptrend** | Market climbing steadily, ADX > 25, price above 200-day avg | Trend Following, Breakout |
| **Downtrend** | Market falling, ADX > 25, price below 200-day avg | Short strategies (caution) |
| **Ranging** | Market stuck sideways, ADX < 25 | Mean Reversion |
| **High Volatility** | Wild swings, ATR in top 30% | Volatility strategies |
| **Risk Off** | Panic mode, ATR in top 10% | Stay in cash / minimal exposure |
| **Event** | Big gaps on news/earnings | Post-event drift plays |

**How regime is detected:** Using three key measurements on SPY (the S&P 500 ETF):
- **ADX (Average Directional Index)**: Is the market trending or flat? ADX > 25 = trending
- **EMA alignment**: Is price above or below its 20/50/200-day moving averages?
- **ATR Percentile**: How volatile is the market right now vs. historical levels?

---

## Risk Management Rules (Non-Negotiable)

1. **Never risk more than 1% of your account on a single trade**
2. **Always set a stop loss before entering any trade**
3. **Only take trades with Risk:Reward ratio of at least 1.5:1**
4. **In Risk-Off regime, go to cash — preserve capital**
5. **Maximum position size is 5% of portfolio per stock**
6. **Target 2:1 or better (risk $1 to potentially make $2)**

---

## The Daily Action Sheet Explained

Each morning you receive a list of setups. Here's how to read it:

```
Symbol: AAPL       → The stock to trade
Action: BUY        → Whether to buy (go long) or SELL SHORT (bet it falls)
Entry:  $185.00    → Buy at this price (usually next day's open)
Stop:   $181.00    → If it falls here, exit immediately (your max loss)
Target: $193.00    → Where you plan to sell for profit
R:R:    2.0:1      → For every $1 you risk, you could make $2
Conf:   72%        → How strongly the indicators agree on this setup
Size:   2.5%       → Put 2.5% of your portfolio into this trade
```

**Why these exact numbers?**
- Stop loss is placed below a recent support level or at 1.5× ATR below entry
- Target is 2× the distance from entry to stop (2:1 R:R)
- Position size is calculated so that if the stop is hit, you lose only ~1% of portfolio

---

## Walk-Forward Backtesting Explained

Before trusting any strategy with real money, we test it:

1. **In-sample period (70%)**: Train the strategy on older data (e.g. 2019-2022)
2. **Out-of-sample period (30%)**: Test it on newer data it has never seen (e.g. 2022-2024)
3. **Walk-forward efficiency**: Out-of-sample Sharpe ÷ In-sample Sharpe. We want ≥ 0.5

If a strategy has a Sharpe of 1.2 in training but only 0.4 out-of-sample, it was **overfitted** (memorized the past rather than learned real patterns). We flag it as "fails walk-forward."

---

## Free Data Sources Used

| Source | What it provides | Cost |
|--------|-----------------|------|
| **yfinance** | OHLCV price data for stocks/ETFs, going back years | Free, no key |
| **FRED** | Federal Reserve economic data (VIX, rates, inflation) | Free, API key required |

Get your free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html

---

## Glossary of Terms

- **OHLCV**: Open, High, Low, Close, Volume — the 5 basic data points for each trading day
- **EMA**: Exponential Moving Average — a smoothed average that weights recent prices more
- **ADX**: Average Directional Index — measures trend strength (not direction). >25 = trending
- **RSI**: Relative Strength Index — momentum oscillator. <30 = oversold, >70 = overbought
- **ATR**: Average True Range — measures daily volatility. Higher = more volatile
- **Bollinger Bands**: Price envelope using standard deviation. Price at lower band = potentially oversold
- **Sharpe Ratio**: Return per unit of risk. >1.0 is good, >2.0 is excellent
- **Max Drawdown**: Worst peak-to-trough loss. Smaller is better
- **Profit Factor**: Gross wins ÷ Gross losses. >1.5 is good
- **R:R**: Risk-to-Reward ratio. 2:1 means potential gain is 2× the potential loss
