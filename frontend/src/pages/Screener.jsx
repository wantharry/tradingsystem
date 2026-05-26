import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Search, RefreshCw, Download, TrendingUp, TrendingDown,
  Clock, BarChart2, AlertCircle, CheckCircle, Loader2,
  Filter, ChevronUp, ChevronDown
} from 'lucide-react'

const API = 'http://localhost:8001/api/v1'

const ASSET_CLASS_STYLES = {
  equity:  { bg: 'bg-green-500/15',  text: 'text-green-400',  border: 'border-green-500/30',  label: 'Equity'  },
  options: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30', label: 'Options' },
  futures: { bg: 'bg-amber-500/15',  text: 'text-amber-400',  border: 'border-amber-500/30',  label: 'Futures' },
}

function AssetBadge({ assetClass, label }) {
  const s = ASSET_CLASS_STYLES[assetClass] || ASSET_CLASS_STYLES.equity
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${s.bg} ${s.text} ${s.border}`}>
      {label || s.label}
    </span>
  )
}

function ActionBadge({ action }) {
  const isBuy = action?.toUpperCase().includes('BUY') || action?.toUpperCase().includes('LONG')
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold ${
      isBuy ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
    }`}>
      {isBuy ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
      {action}
    </span>
  )
}

function ScoreBar({ score }) {
  const pct = Math.min(score * 100, 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-gray-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-gray-300">{score.toFixed(2)}</span>
    </div>
  )
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function timeAgo(iso) {
  if (!iso) return 'never'
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function Screener() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(null)
  const [assetFilter, setAssetFilter] = useState('all')
  const [actionFilter, setActionFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [sortKey, setSortKey] = useState('composite_score')
  const [sortDir, setSortDir] = useState('desc')
  const [expanded, setExpanded] = useState(null)
  const [universeStatus, setUniverseStatus] = useState(null)
  const [, setTick] = useState(0)  // for "X ago" re-render

  // Re-render every 30s so "last updated" stays fresh
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 30000)
    return () => clearInterval(id)
  }, [])

  const fetchResults = useCallback(async (force = false) => {
    try {
      const url = `${API}/screener/results?limit=100${force ? '&force=true' : ''}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  const fetchUniverseStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/screener/universe/status`)
      if (res.ok) setUniverseStatus(await res.json())
    } catch (_) {}
  }, [])

  // Initial load
  useEffect(() => {
    Promise.all([fetchResults(), fetchUniverseStatus()]).finally(() => setLoading(false))
  }, [fetchResults, fetchUniverseStatus])

  // Auto-refresh every 60 seconds (polls for new results)
  useEffect(() => {
    const id = setInterval(() => fetchResults(), 60000)
    return () => clearInterval(id)
  }, [fetchResults])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      // Trigger background refresh
      await fetch(`${API}/screener/refresh`, { method: 'POST' })
      // Poll until results are updated (up to 90s)
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        await fetchResults()
        if (attempts >= 18) clearInterval(poll) // max 18 * 5s = 90s
      }, 5000)
      setTimeout(() => clearInterval(poll), 90000)
    } catch (e) {
      setError(e.message)
    } finally {
      setTimeout(() => setRefreshing(false), 3000)
    }
  }

  const handleDownloadUniverse = async () => {
    setDownloading(true)
    try {
      await fetch(`${API}/screener/universe/download`, { method: 'POST' })
      await fetchUniverseStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setTimeout(() => setDownloading(false), 2000)
    }
  }

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <ChevronUp size={12} className="text-gray-600" />
    return sortDir === 'asc' ? <ChevronUp size={12} className="text-green-400" /> : <ChevronDown size={12} className="text-green-400" />
  }

  const results = data?.results || []
  const filtered = results
    .filter(r => assetFilter === 'all' || r.asset_class === assetFilter)
    .filter(r => {
      if (actionFilter === 'all') return true
      const isBuy = r.action?.toUpperCase().includes('BUY') || r.action?.toUpperCase().includes('LONG')
      return actionFilter === 'buy' ? isBuy : !isBuy
    })
    .filter(r => !searchQuery || r.symbol?.toLowerCase().includes(searchQuery.toLowerCase()) || r.strategy?.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      const aVal = a[sortKey] ?? 0
      const bVal = b[sortKey] ?? 0
      const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal) : aVal - bVal
      return sortDir === 'desc' ? -cmp : cmp
    })

  const regimeColors = {
    uptrend: 'text-green-400', downtrend: 'text-red-400',
    ranging: 'text-blue-400', high_vol: 'text-amber-400',
    risk_off: 'text-red-500', unknown: 'text-gray-400',
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      <Loader2 className="animate-spin mr-3" size={24} />
      Running screener…
    </div>
  )

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-white">Stock Screener</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data?.total_screened ?? 0} symbols screened ·{' '}
            {data?.total_results ?? 0} signals found ·{' '}
            <span className={regimeColors[data?.regime] || 'text-gray-400'}>
              {data?.regime ?? 'unknown'} regime
            </span>
            {data?.last_updated && (
              <span className="ml-2 text-gray-500">· updated {timeAgo(data.last_updated)}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleDownloadUniverse}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white disabled:opacity-50 transition-colors border border-gray-700"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {downloading ? 'Downloading…' : 'Download Universe'}
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-lg bg-green-600 hover:bg-green-500 text-white font-semibold disabled:opacity-60 transition-colors"
          >
            {refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {refreshing ? 'Refreshing…' : 'Refresh Now'}
          </button>
        </div>
      </div>

      {/* Universe status bar */}
      {universeStatus && (
        <div className="flex flex-wrap gap-4 text-xs text-gray-400 bg-gray-900/50 border border-gray-800 rounded-lg px-4 py-2">
          <span><span className="text-white font-semibold">{universeStatus.universe?.symbols ?? '—'}</span> symbols in universe</span>
          <span><span className="text-green-400 font-semibold">{universeStatus.symbols_ready_to_screen}</span> ready to screen</span>
          <span><span className="text-gray-500 font-semibold">{universeStatus.symbols_with_insufficient_data}</span> need more data</span>
          {universeStatus.universe?.cached_at && (
            <span className="flex items-center gap-1"><Clock size={11} /> universe list: {timeAgo(universeStatus.universe.cached_at)}</span>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* No data state */}
      {data?.status === 'no_data' && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
          <BarChart2 size={40} className="mx-auto text-gray-600 mb-3" />
          <p className="text-gray-300 font-semibold mb-1">No price data available</p>
          <p className="text-gray-500 text-sm mb-4">{data.message}</p>
          <button
            onClick={handleDownloadUniverse}
            disabled={downloading}
            className="inline-flex items-center gap-2 px-5 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-semibold text-sm transition-colors disabled:opacity-60"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Download Universe Data
          </button>
        </div>
      )}

      {/* Filters + search */}
      {results.length > 0 && (
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Search symbol or strategy…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:border-gray-500 w-52"
            />
          </div>
          <div className="flex items-center gap-1 bg-gray-900 border border-gray-700 rounded-lg p-1">
            {['all', 'equity', 'options', 'futures'].map(f => (
              <button
                key={f}
                onClick={() => setAssetFilter(f)}
                className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
                  assetFilter === f ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 bg-gray-900 border border-gray-700 rounded-lg p-1">
            {[['all', 'All'], ['buy', 'Long'], ['sell', 'Short']].map(([val, lbl]) => (
              <button
                key={val}
                onClick={() => setActionFilter(val)}
                className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
                  actionFilter === val ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
          <span className="text-xs text-gray-500 ml-auto">{filtered.length} results</span>
        </div>
      )}

      {/* Results table */}
      {filtered.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs">
                <th className="text-left px-4 py-3 w-10">#</th>
                <th
                  className="text-left px-3 py-3 cursor-pointer hover:text-white select-none"
                  onClick={() => toggleSort('symbol')}
                >
                  <span className="flex items-center gap-1">Symbol <SortIcon col="symbol" /></span>
                </th>
                <th className="text-left px-3 py-3">Action</th>
                <th className="text-left px-3 py-3">Strategy</th>
                <th className="text-left px-3 py-3">Asset Class</th>
                <th
                  className="text-left px-3 py-3 cursor-pointer hover:text-white select-none"
                  onClick={() => toggleSort('composite_score')}
                >
                  <span className="flex items-center gap-1">Score <SortIcon col="composite_score" /></span>
                </th>
                <th
                  className="text-right px-3 py-3 cursor-pointer hover:text-white select-none"
                  onClick={() => toggleSort('entry_price')}
                >
                  <span className="flex items-center justify-end gap-1">Entry <SortIcon col="entry_price" /></span>
                </th>
                <th className="text-right px-3 py-3">Stop</th>
                <th className="text-right px-3 py-3">Target</th>
                <th
                  className="text-right px-3 py-3 cursor-pointer hover:text-white select-none"
                  onClick={() => toggleSort('risk_reward_ratio')}
                >
                  <span className="flex items-center justify-end gap-1">R:R <SortIcon col="risk_reward_ratio" /></span>
                </th>
                <th className="text-right px-3 py-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const isExp = expanded === `${row.symbol}-${row.strategy_key}`
                return (
                  <>
                    <tr
                      key={`${row.symbol}-${row.strategy_key}-${i}`}
                      className={`border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer transition-colors ${isExp ? 'bg-gray-800/30' : ''}`}
                      onClick={() => setExpanded(isExp ? null : `${row.symbol}-${row.strategy_key}`)}
                    >
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">{row.rank}</td>
                      <td className="px-3 py-3">
                        <span className="font-bold text-white font-mono">{row.symbol}</span>
                      </td>
                      <td className="px-3 py-3"><ActionBadge action={row.action} /></td>
                      <td className="px-3 py-3 text-gray-300 text-xs">{row.strategy}</td>
                      <td className="px-3 py-3"><AssetBadge assetClass={row.asset_class} label={row.asset_class_label} /></td>
                      <td className="px-3 py-3"><ScoreBar score={row.composite_score} /></td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-white">{fmt(row.entry_price)}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-red-400">{fmt(row.stop_price)}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-green-400">{fmt(row.target_price)}</td>
                      <td className="px-3 py-3 text-right">
                        <span className={`font-mono text-xs font-semibold ${
                          row.risk_reward_ratio >= 2 ? 'text-green-400' :
                          row.risk_reward_ratio >= 1.5 ? 'text-amber-400' : 'text-gray-400'
                        }`}>
                          {row.risk_reward_ratio?.toFixed(1) ?? '—'}x
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <span className="font-mono text-xs text-gray-300">
                          {row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : '—'}
                        </span>
                      </td>
                    </tr>
                    {isExp && (
                      <tr key={`${row.symbol}-${row.strategy_key}-detail`} className="bg-gray-800/20 border-b border-gray-800">
                        <td colSpan={11} className="px-6 py-4">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide mb-1">Signal Reasoning</p>
                              <p className="text-sm text-gray-300">{row.reasoning || 'No reasoning provided.'}</p>
                            </div>
                            <div className="grid grid-cols-2 gap-3 text-xs">
                              <div>
                                <p className="text-gray-500 mb-0.5">Symbol Regime</p>
                                <p className="text-white font-semibold">{row.regime || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500 mb-0.5">Strategy Type</p>
                                <p className="text-white font-semibold">{row.strategy_type_label || row.strategy_type || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500 mb-0.5">Risk ($100k acct, 1%)</p>
                                <p className="text-white font-semibold">
                                  {row.entry_price && row.stop_price
                                    ? `$${Math.abs(((row.entry_price - row.stop_price) / row.entry_price) * 1000).toFixed(0)} risk`
                                    : '—'}
                                </p>
                              </div>
                              <div>
                                <p className="text-gray-500 mb-0.5">Composite Score</p>
                                <p className="text-white font-semibold">{row.composite_score}</p>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Stats footer */}
      {data?.status === 'ok' && (
        <div className="flex flex-wrap gap-6 text-xs text-gray-500 px-1">
          <span className="flex items-center gap-1.5">
            <CheckCircle size={12} className="text-green-500" />
            Scan took {data.elapsed_seconds}s
          </span>
          <span className="flex items-center gap-1.5">
            <Clock size={12} />
            Auto-refreshes every hour during market hours
          </span>
          {data.strategies_used?.length > 0 && (
            <span>Strategies: {data.strategies_used.join(', ')}</span>
          )}
        </div>
      )}
    </div>
  )
}
