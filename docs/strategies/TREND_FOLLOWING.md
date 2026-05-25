# Strategy 1: EMA Pullback Trend Following

**Family:** Trend | **Best Regime:** Uptrend, Downtrend  
**Difficulty:** Beginner-friendly  
**Expected Win Rate:** ~45-55% | **Target R:R:** 2:1

---

## What Is This Strategy? (Plain English)

Imagine a river flowing steadily north. You want to get in a canoe and paddle with the current, not against it. This strategy does exactly that — it finds stocks in a **clear uptrend** and waits for a small dip (pullback) to enter, so you can ride the next wave up.

**The core idea:** Strong trends don't go straight up forever. They rise, pause, dip slightly, then continue. We buy during the dip.

---

## When Does It Work?

✅ Best when:
- The overall market is in an uptrend (SPY above its 200-day average)
- The stock has been climbing steadily for weeks/months
- The stock dips slightly but the trend remains intact
- Volume is normal or declining on the pullback (sellers not panicking)

❌ Avoid when:
- Market regime is "Ranging" or "Risk Off"
- ADX is below 25 (no real trend, just noise)
- The stock has broken below its 50-day moving average
- Recent earnings or major news catalyst (event risk)

---

## Entry Rules (Step by Step)

1. **Check the trend direction:**
   - EMA 20 > EMA 50 > EMA 200 (all pointing up — "EMA stack")
   - Current price is above EMA 200 (200-day moving average)
   
2. **Confirm trend strength:**
   - ADX ≥ 25 (the trend has force behind it)

3. **Wait for the pullback:**
   - Price has pulled back to near the EMA 20 (20-day average)
   - Specifically: price within 2% above or touching EMA 20

4. **Check momentum isn't collapsing:**
   - RSI is between 40 and 70 (not overbought, not in free-fall)

5. **Enter the trade:**
   - Buy at the next day's market open
   - Entry price ≈ current close (or tomorrow's open)

---

## Exit Rules

**Stop Loss (Protect yourself):**
- Stop placed at 1.5 × ATR below entry price
- Example: Entry $100, ATR = $2.50 → Stop at $100 - $3.75 = $96.25

**Profit Target:**
- Target is 2× the distance from entry to stop (2:1 risk-reward)
- Example: Entry $100, Stop $96.25 → Risk = $3.75 → Target = $100 + $7.50 = $107.50

**Time Stop:**
- If neither stop nor target is hit within 30 days, exit at market
- Stale trends lose momentum; free up capital for better setups

---

## Position Sizing

```
Max risk per trade = 1% of portfolio
Position size $ = (Portfolio × 0.01) ÷ (Entry - Stop)
Position size % = Position $ ÷ Portfolio × 100
```

Example with $10,000 portfolio:
- Max risk: $100
- Entry $100, Stop $96.25 → Risk per share: $3.75
- Shares to buy: $100 ÷ $3.75 = 26 shares
- Position value: 26 × $100 = $2,600 (26% of portfolio — check max 5% cap)

---

## Real Trade Example

**Setup:** AAPL in uptrend, pulled back to EMA 20

| Parameter | Value |
|-----------|-------|
| Entry | $185.00 |
| Stop Loss | $181.24 (1.5× ATR = $3.76 below) |
| Target | $192.52 ($7.52 above entry = 2× risk) |
| Risk per share | $3.76 |
| R:R Ratio | 2.0:1 |
| ADX | 32 (strong trend) |
| RSI | 51 (mid-range, healthy) |

**Why this works:** AAPL is in a clear uptrend (all EMAs aligned up), pulled back to the 20-day average on lower volume (normal consolidation), ADX confirms trend strength, RSI shows momentum is neutral — perfect pullback entry.

---

## Common Mistakes to Avoid

❌ **Buying into a falling trend** — Check EMA alignment first. If EMA 20 < EMA 50, it's not an uptrend.

❌ **Ignoring ADX** — A stock can be going up and still have ADX < 25 (just noise). Only trade with ADX ≥ 25.

❌ **Missing the pullback** — Don't chase. If the stock has run 5% above EMA 20, the pullback entry has passed.

❌ **RSI > 70** — Overbought momentum is a warning sign. Wait for RSI to cool below 70.

❌ **Skipping the stop loss** — Without a stop, a "small dip" can turn into a -30% loss.

---

## Why This Strategy Has Edge

Stocks in strong trends tend to **continue** in the same direction. Academic research shows momentum effects persist (Jegadeesh & Titman 1993, and confirmed many times since). By buying pullbacks to the EMA 20, we:
1. Enter at a better price than just "buying the trend"
2. Have a well-defined risk level (the stop)
3. Let profits run to 2× our risk (2:1 R:R)

Over many trades, even with a 45% win rate, a 2:1 R:R is **profitable**:
- 45 winners × 2 units = 90 units profit
- 55 losers × 1 unit = 55 units loss
- **Net: +35 units profit per 100 trades**
