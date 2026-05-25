"""watchlist.py — API routes for managing the symbol watchlist."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Symbol
from app.data.storage import upsert_symbol, get_active_symbols

router = APIRouter()


class AddSymbolRequest(BaseModel):
    symbol: str


@router.get("/")
def get_watchlist(db: Session = Depends(get_db)):
    """Get all active watchlist symbols."""
    symbols = db.query(Symbol).filter(Symbol.is_active == True).order_by(Symbol.symbol).all()
    return {
        "symbols": [
            {
                "symbol": s.symbol, "name": s.name,
                "asset_type": s.asset_type, "sector": s.sector,
                "exchange": s.exchange, "is_active": s.is_active,
            }
            for s in symbols
        ]
    }


@router.post("/add")
def add_symbol(request: AddSymbolRequest, db: Session = Depends(get_db)):
    """Add a symbol to the watchlist and fetch its initial data."""
    symbol = request.symbol.upper().strip()
    sym = upsert_symbol(db, symbol)

    # Fetch initial price data in the background
    from app.data.market_data import fetch_ohlcv
    from app.data.storage import store_price_data
    df = fetch_ohlcv(symbol, period="3y")
    if not df.empty:
        store_price_data(db, df)

    return {"status": "added", "symbol": symbol, "name": sym.name}


@router.delete("/{symbol}")
def remove_symbol(symbol: str, db: Session = Depends(get_db)):
    """Deactivate a symbol from the watchlist (data is kept)."""
    sym = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
    if not sym:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    sym.is_active = False
    db.commit()
    return {"status": "removed", "symbol": symbol.upper()}


@router.get("/search/{query}")
def search_symbols(query: str):
    """Search for symbols by name or ticker (uses yfinance)."""
    import yfinance as yf
    try:
        results = yf.Search(query, max_results=10).quotes
        return {
            "query": query,
            "results": [
                {"symbol": r.get("symbol", ""), "name": r.get("longname") or r.get("shortname", "")}
                for r in results
                if r.get("symbol")
            ],
        }
    except Exception:
        return {"query": query, "results": []}
