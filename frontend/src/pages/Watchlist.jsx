import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getWatchlist, addSymbol, removeSymbol, searchSymbols, getAllRegimes } from '../api/client'
import { Plus, Trash2, Search, Star, TrendingUp, TrendingDown, Minus } from 'lucide-react'

const REGIME_DISPLAY = {
  uptrend:   { label: 'Uptrend',   color: 'text-green-400 bg-green-900/30 border-green-700' },
  downtrend: { label: 'Downtrend', color: 'text-red-400 bg-red-900/30 border-red-700' },
  ranging:   { label: 'Ranging',   color: 'text-blue-400 bg-blue-900/30 border-blue-700' },
  high_vol:  { label: 'High Vol',  color: 'text-amber-400 bg-amber-900/30 border-amber-700' },
  risk_off:  { label: 'Risk Off',  color: 'text-red-400 bg-red-900/40 border-red-600' },
  event:     { label: 'Event',     color: 'text-purple-400 bg-purple-900/30 border-purple-700' },
  unknown:   { label: '—',         color: 'text-gray-500 bg-gray-800 border-gray-700' },
}

function RegimeBadge({ regime }) {
  const d = REGIME_DISPLAY[regime] || REGIME_DISPLAY.unknown
  return (
    <span className={`badge border text-xs ${d.color}`}>{d.label}</span>
  )
}

export default function Watchlist() {
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const queryClient = useQueryClient()

  const { data: watchlistData } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
  })

  const { data: regimesData } = useQuery({
    queryKey: ['all-regimes'],
    queryFn: getAllRegimes,
  })

  const { mutate: add, isPending: adding } = useMutation({
    mutationFn: addSymbol,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      queryClient.invalidateQueries({ queryKey: ['all-regimes'] })
      setSearch('')
      setSearchResults([])
    },
  })

  const { mutate: remove } = useMutation({
    mutationFn: removeSymbol,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const handleSearch = async () => {
    if (!search.trim()) return
    setSearching(true)
    try {
      const r = await searchSymbols(search.trim())
      setSearchResults(r.results || [])
    } finally {
      setSearching(false)
    }
  }

  const symbols = watchlistData?.symbols || []
  const regimes = regimesData?.regimes || []
  const regimeMap = Object.fromEntries(regimes.map(r => [r.symbol, r]))

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white">Watchlist</h1>
        <p className="text-sm text-gray-400 mt-1">
          Manage the symbols you track. Each symbol gets daily regime detection and signals.
        </p>
      </div>

      {/* Add symbol */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <Plus size={16} /> Add Symbol
        </h2>
        <div className="flex gap-2">
          <input
            value={search}
            onChange={e => setSearch(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Search ticker or company name…"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
          />
          <button onClick={handleSearch} disabled={searching} className="btn-ghost text-sm">
            <Search size={13} /> {searching ? 'Searching…' : 'Search'}
          </button>
          <button
            onClick={() => add(search)}
            disabled={!search || adding}
            className="btn-primary text-sm"
          >
            <Plus size={13} /> {adding ? 'Adding…' : 'Add Direct'}
          </button>
        </div>

        {/* Search results */}
        {searchResults.length > 0 && (
          <div className="border border-gray-700 rounded-lg overflow-hidden">
            {searchResults.map(r => (
              <div
                key={r.symbol}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-800 transition-colors border-b border-gray-800 last:border-0"
              >
                <div>
                  <span className="font-mono font-bold text-white text-sm">{r.symbol}</span>
                  <span className="ml-3 text-sm text-gray-400">{r.name}</span>
                </div>
                <button
                  onClick={() => { add(r.symbol); setSearchResults([]) }}
                  className="btn-primary text-xs py-1"
                >
                  <Plus size={12} /> Add
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Symbol table */}
      <div className="card">
        <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
          <Star size={14} className="text-green-400" />
          Active Watchlist ({symbols.length})
        </h2>

        {symbols.length === 0 ? (
          <div className="text-center py-10 text-gray-500">
            <Star className="mx-auto mb-3 text-gray-700" size={32} />
            <p>No symbols yet. Add some above.</p>
          </div>
        ) : (
          <div className="space-y-1">
            {/* Header */}
            <div className="grid grid-cols-12 px-3 pb-2 text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
              <div className="col-span-2">Symbol</div>
              <div className="col-span-4">Name</div>
              <div className="col-span-2">Regime</div>
              <div className="col-span-1 text-right">ADX</div>
              <div className="col-span-1 text-right">RSI</div>
              <div className="col-span-1 text-right">Above 200d</div>
              <div className="col-span-1 text-right">Actions</div>
            </div>

            {symbols.map(sym => {
              const reg = regimeMap[sym.symbol]
              return (
                <div
                  key={sym.symbol}
                  className="grid grid-cols-12 px-3 py-3 rounded-lg hover:bg-gray-800/50 transition-colors items-center"
                >
                  <div className="col-span-2">
                    <span className="font-mono font-bold text-white">{sym.symbol}</span>
                  </div>
                  <div className="col-span-4 text-sm text-gray-400 truncate">{sym.name || '—'}</div>
                  <div className="col-span-2">
                    <RegimeBadge regime={reg?.regime || 'unknown'} />
                  </div>
                  <div className="col-span-1 text-right text-sm text-gray-300">
                    {reg?.adx != null ? reg.adx.toFixed(0) : '—'}
                  </div>
                  <div className="col-span-1 text-right text-sm">
                    {reg?.rsi != null ? (
                      <span className={
                        reg.rsi >= 70 ? 'text-red-400' :
                        reg.rsi <= 30 ? 'text-green-400' : 'text-gray-300'
                      }>
                        {reg.rsi.toFixed(0)}
                      </span>
                    ) : '—'}
                  </div>
                  <div className="col-span-1 text-right text-sm">
                    {reg?.above_200ema === true
                      ? <TrendingUp size={14} className="inline text-green-400" />
                      : reg?.above_200ema === false
                      ? <TrendingDown size={14} className="inline text-red-400" />
                      : <Minus size={14} className="inline text-gray-600" />}
                  </div>
                  <div className="col-span-1 text-right">
                    <button
                      onClick={() => remove(sym.symbol)}
                      className="p-1.5 rounded hover:bg-red-900/30 text-gray-600 hover:text-red-400 transition-colors"
                      title={`Remove ${sym.symbol}`}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
