"""
router.py — Master API router. Includes all route modules.
"""

from fastapi import APIRouter
from app.api.routes import data, strategies, regime, backtest, daily, watchlist, screener as screener_routes

api_router = APIRouter()

api_router.include_router(data.router, prefix="/data", tags=["Data"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
api_router.include_router(regime.router, prefix="/regime", tags=["Regime"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
api_router.include_router(daily.router, prefix="/daily", tags=["Daily Actions"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["Watchlist"])
api_router.include_router(screener_routes.router, prefix="/screener", tags=["Screener"])
