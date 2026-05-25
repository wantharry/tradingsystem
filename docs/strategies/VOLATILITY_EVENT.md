# Strategy 4: IV Percentile Volatility

**Family:** Volatility | **Best Regime:** High Volatility, Ranging  
**Difficulty:** Advanced (options required)  
**Expected Win Rate:** ~55-65% | **Target R:R:** 1.5:1

---

## What Is This Strategy? (Plain English)

Options prices are driven by expected volatility. When traders are *very scared*, they overpay for options — implied volatility (IV) is high. When markets are calm, options are cheap. This strategy:

- **Buys volatility** (straddle) when it's historically cheap → bet volatility will expand
- **Sells volatility** (iron condor) when it's historically expensive → bet volatility will contract

We use ATR percentile as a proxy for implied volatility when options data is unavailable.

---

## Long Volatility (Straddle) — Buy when vol is cheap

**Setup:**
- ATR percentile rank ≤ 20th percentile (volatility near historic lows)
- Volume declining (calm before the storm)

**Trade:**
- Buy ATM call + ATM put (straddle)
- Profit if stock moves significantly in either direction
- Loss if stock stays flat and time decay erodes options value

---

## Short Volatility (Iron Condor) — Sell when vol is expensive

**Setup:**
- ATR percentile rank ≥ 80th percentile (volatility near historic highs)
- Volume calming down from spike (volatility contracting)

**Trade:**
- Sell OTM call spread + OTM put spread (iron condor)
- Profit if stock stays within a range until expiration
- Loss if stock makes a big move beyond the condor wings

---

## Why This Strategy Has Edge

Implied volatility **mean-reverts** more reliably than price. The VIX (market fear gauge) has averaged around 20 over decades. When it spikes to 40+, it almost always comes back down. When it sits at 12, it almost always rises. This predictable oscillation creates a reliable edge.
