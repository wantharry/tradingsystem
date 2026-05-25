# Strategy 2: Bollinger RSI Mean Reversion

**Family:** Mean Reversion | **Best Regime:** Ranging  
**Difficulty:** Beginner-friendly  
**Expected Win Rate:** ~55-65% | **Target R:R:** 1.5:1

---

## What Is This Strategy? (Plain English)

Think of a rubber band. Stretch it too far in one direction and it snaps back. Stocks do the same — when they get oversold (stretched too far down), they tend to bounce back toward normal. This strategy **buys when stocks are unfairly beaten up** and **sells short when they're irrationally pumped up**.

**The core idea:** In sideways (ranging) markets, prices oscillate around a mean. We profit from this natural "snap-back" effect.

---

## When Does It Work?

✅ Best when:
- Market is in "Ranging" regime (no clear trend)
- ADX is below 30 (no strong directional force)
- The stock has been trading in a band for weeks
- No major news or earnings coming up

❌ Avoid when:
- ADX > 30 (trending market — mean reversion fights the trend)
- Market is in "Risk Off" or "High Volatility" regime
- Stock has just broken out of a long range (new trend starting)

---

## Entry Rules (Long / Buy)

1. **Confirm ranging market:** ADX < 30
2. **Price at lower Bollinger Band:** Close ≤ lower band (2 standard deviations below 20-day avg)
3. **RSI confirms oversold:** RSI ≤ 30
4. **Enter:** Buy next day open

---

## Entry Rules (Short / Sell)

1. **Confirm ranging market:** ADX < 30
2. **Price at upper Bollinger Band:** Close ≥ upper band
3. **RSI confirms overbought:** RSI ≥ 70
4. **Enter:** Short sell next day open

---

## Exit Rules

**Stop Loss:** 1.0 × ATR beyond the Bollinger Band (opposite direction from entry)
**Target:** Middle Bollinger Band (the 20-day moving average)  
**R:R:** Typically 1.5:1 to 2.0:1 depending on band width  
**Time Stop:** 20 days maximum hold

---

## Why This Strategy Has Edge

Statistically, prices more than 2 standard deviations from the mean only stay there ~5% of the time. That's what Bollinger Bands measure. Combining this with RSI confirmation means:
- Bollinger Band at lower 2σ: "Price is statistically stretched low"
- RSI ≤ 30: "Momentum is signaling extreme weakness"
- Together = high probability of bounce back to the mean
