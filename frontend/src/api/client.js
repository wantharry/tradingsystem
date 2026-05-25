import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
})

// ── Daily Actions ──────────────────────────────────────────────────────────
// opts: { date: 'YYYY-MM-DD' | null, regenerate: bool }
export const getDailyActions = ({ date = null, regenerate = false } = {}) =>
  api.get('/daily/actions', {
    params: { target_date: date || undefined, regenerate }
  }).then(r => r.data)

export const getDailyLogs = (limit = 30) =>
  api.get('/daily/logs', { params: { limit } }).then(r => r.data)

export const getDailyLog = (date) =>
  api.get(`/daily/logs/${date}`).then(r => r.data)

export const getLastTradingDay = () =>
  api.get('/daily/last-trading-day').then(r => r.data)

export const verifyOutcomes = (date, forwardDays = 15) =>
  api.get(`/daily/verify/${date}`, { params: { forward_days: forwardDays } }).then(r => r.data)

export const getPerformanceSummary = (days = 90) =>
  api.get('/daily/performance', { params: { days } }).then(r => r.data)

// ── Regime ─────────────────────────────────────────────────────────────────
export const getMarketRegime = () =>
  api.get('/regime/market').then(r => r.data)

export const getSymbolRegime = (symbol) =>
  api.get(`/regime/symbol/${symbol}`).then(r => r.data)

export const getAllRegimes = () =>
  api.get('/regime/all').then(r => r.data)

export const getRegimeHistory = (symbol, limit = 90) =>
  api.get(`/regime/history/${symbol}`, { params: { limit } }).then(r => r.data)

// ── Strategies ─────────────────────────────────────────────────────────────
export const listStrategies = () =>
  api.get('/strategies/').then(r => r.data)

export const getStrategyDocs = (key) =>
  api.get(`/strategies/${key}/documentation`).then(r => r.data)

export const getSignals = (strategyKey, symbol) =>
  api.get(`/strategies/${strategyKey}/signals/${symbol}`).then(r => r.data)

// ── Backtest ───────────────────────────────────────────────────────────────
export const runBacktest = (payload) =>
  api.post('/backtest/run', payload).then(r => r.data)

export const getBacktestHistory = (symbol) =>
  api.get(`/backtest/history/${symbol}`).then(r => r.data)

// ── Data ───────────────────────────────────────────────────────────────────
export const getPriceData = (symbol, params = {}) =>
  api.get(`/data/price/${symbol}`, { params }).then(r => r.data)

export const triggerRefresh = (symbols = null) =>
  api.post('/data/refresh', symbols ? { symbols } : {}).then(r => r.data)

export const getRefreshStatus = () =>
  api.get('/data/refresh/status').then(r => r.data)

// ── Watchlist ──────────────────────────────────────────────────────────────
export const getWatchlist = () =>
  api.get('/watchlist/').then(r => r.data)

export const addSymbol = (symbol) =>
  api.post('/watchlist/add', { symbol }).then(r => r.data)

export const removeSymbol = (symbol) =>
  api.delete(`/watchlist/${symbol}`).then(r => r.data)

export const searchSymbols = (query) =>
  api.get(`/watchlist/search/${query}`).then(r => r.data)
