"""
sentiment.py  —  News sentiment scoring using VADER + Google News RSS headlines.
Results are cached in-memory for 1 hour to avoid excessive network calls.
"""
from __future__ import annotations
import time
import logging
import requests
from xml.etree import ElementTree as ET
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── In-memory TTL cache ───────────────────────────────────────────────────────
_CACHE: Dict[str, tuple[float, dict]] = {}   # symbol -> (timestamp, result)
_TTL = 3600  # 1 hour

def _cached(symbol: str) -> dict | None:
    entry = _CACHE.get(symbol)
    if entry and (time.time() - entry[0]) < _TTL:
        return entry[1]
    return None

def _store(symbol: str, result: dict) -> None:
    _CACHE[symbol] = (time.time(), result)

# ── VADER analyser (lazy-loaded) ──────────────────────────────────────────────
_analyser = None

def _get_analyser():
    global _analyser
    if _analyser is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _analyser = SentimentIntensityAnalyzer()
    return _analyser

# ── RSS fetch ─────────────────────────────────────────────────────────────────
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"}

def _fetch_google_news_titles(symbol: str, max_articles: int) -> list[str]:
    """Return headline strings for *symbol* from Google News RSS."""
    url = (
        f"https://news.google.com/rss/search"
        f"?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        resp = requests.get(url, timeout=8, headers=_HEADERS)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        return [item.findtext("title") or "" for item in items[:max_articles]]
    except Exception as exc:
        logger.debug("Google News RSS fetch failed for %s: %s", symbol, exc)
        return []

# ── Main public function ──────────────────────────────────────────────────────
def get_news_sentiment(symbol: str, max_articles: int = 15) -> Dict[str, Any]:
    """
    Return a sentiment dict for *symbol* based on recent Google News headlines.

    Returns:
        {
          "score": float,          # compound VADER score, -1 to +1
          "label": str,            # "bullish" | "bearish" | "neutral"
          "article_count": int,
        }
    """
    cached = _cached(symbol)
    if cached:
        return cached

    neutral = {"score": 0.0, "label": "neutral", "article_count": 0}

    titles = _fetch_google_news_titles(symbol, max_articles)
    if not titles:
        _store(symbol, neutral)
        return neutral

    analyser = _get_analyser()
    scores: list[float] = []
    for title in titles:
        if title.strip():
            compound = analyser.polarity_scores(title)["compound"]
            scores.append(compound)

    if not scores:
        _store(symbol, neutral)
        return neutral

    avg = sum(scores) / len(scores)
    label = "bullish" if avg >= 0.05 else "bearish" if avg <= -0.05 else "neutral"
    result = {"score": round(avg, 3), "label": label, "article_count": len(scores)}
    _store(symbol, result)
    return result
