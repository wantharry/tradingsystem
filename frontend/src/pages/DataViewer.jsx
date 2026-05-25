import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPriceData, getRefreshStatus, triggerRefresh } from '../api/client'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine
} from 'recharts'
import { RefreshCw, Database } from 'lucide-react'

function PriceChart({ data }) {
  if (!data?.length) return null

  const chartData = data.slice(-120).map(d => ({
    date: d.date?.slice(5), // MM-DD
    close: +d.close?.toFixed(2),
    volume: d.volume,
    ema20: d.ema20 ? +d.ema20.toFixed(2) : null,
    ema50: d.ema50 ? +d.ema50.toFixed(2) : null,
    rsi: d.rsi ? +d.rsi.toFixed(1) : null,
  }))

  return (
    <div className="space-y-4">
      {/* Price + EMA */}
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ left: 0, right: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} />
          <YAxis
            yAxisId="price"
            tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} width={60}
          />
          <YAxis
            yAxisId="vol"
            orientation="right"
            tick={false} axisLine={false} tickLine={false}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#9ca3af', fontSize: 11 }}
          />
          <Bar yAxisId="vol" dataKey="volume" fill="#1f2937" opacity={0.6} />
          <Line yAxisId="price" type="monotone" dataKey="close" stroke="#e5e7eb" dot={false} strokeWidth={1.5} />
          <Line yAxisId="price" type="monotone" dataKey="ema20" stroke="#34d399" dot={false} strokeWidth={1} strokeDasharray="4 2" />
          <Line yAxisId="price" type="monotone" dataKey="ema50" stroke="#60a5fa" dot={false} strokeWidth={1} strokeDasharray="4 2" />
        </ComposedChart>
      </ResponsiveContainer>

      {/* RSI */}
      <ResponsiveContainer width="100%" height={100}>
        <ComposedChart data={chartData} margin={{ left: 0, right: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} width={60} tickLine={false} axisLine={false} />
          <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" />
          <ReferenceLine y={30} stroke="#34d399" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="rsi" stroke="#a78bfa" dot={false} strokeWidth={1.5} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-600 text-center">RSI — green line = 30 (oversold), red = 70 (overbought)</p>
    </div>
  )
}

export default function DataViewer() {
  const [symbol, setSymbol] = useState('SPY')
  const [activeSymbol, setActiveSymbol] = useState('SPY')

  const { data: priceResp, isLoading, refetch } = useQuery({
    queryKey: ['price-data', activeSymbol],
    queryFn: () => getPriceData(activeSymbol, { limit: 252 }),
    enabled: !!activeSymbol,
  })

  const { data: status } = useQuery({
    queryKey: ['refresh-status'],
    queryFn: getRefreshStatus,
    refetchInterval: 30_000,
  })

  const priceData = priceResp?.data || []

  const handleRefresh = async () => {
    await triggerRefresh([activeSymbol])
    refetch()
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Data Viewer</h1>
          <p className="text-sm text-gray-400 mt-1">Price chart with EMA 20/50 overlays and RSI indicator</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Database size={12} />
          {status?.running ? (
            <span className="text-amber-400">Refresh in progress…</span>
          ) : (
            <span>Auto-refresh: 4pm market close</span>
          )}
        </div>
      </div>

      {/* Symbol selector */}
      <div className="card flex items-center gap-3">
        <input
          value={symbol}
          onChange={e => setSymbol(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && setActiveSymbol(symbol)}
          placeholder="Enter symbol"
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono w-32"
        />
        <button
          onClick={() => setActiveSymbol(symbol)}
          className="btn-primary text-sm"
        >
          Load
        </button>
        <button
          onClick={handleRefresh}
          className="btn-ghost text-sm"
        >
          <RefreshCw size={13} /> Refresh Data
        </button>

        {/* Quick picks */}
        <div className="flex gap-1 ml-auto">
          {['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'GLD'].map(s => (
            <button
              key={s}
              onClick={() => { setSymbol(s); setActiveSymbol(s) }}
              className={`px-2 py-1 text-xs rounded ${
                activeSymbol === s ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">{activeSymbol} — Daily OHLCV (last 120 days)</h2>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-emerald-400 inline-block"></span> EMA 20
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-blue-400 inline-block"></span> EMA 50
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-gray-500">Loading price data…</div>
        ) : priceData.length === 0 ? (
          <div className="py-12 text-center text-gray-500">No data found for {activeSymbol}. Try refreshing.</div>
        ) : (
          <PriceChart data={priceData} />
        )}
      </div>

      {/* Summary stats */}
      {priceData.length > 0 && (() => {
        const last = priceData[priceData.length - 1]
        const prev = priceData[priceData.length - 2]
        const chg = prev ? ((last.close - prev.close) / prev.close * 100) : 0
        return (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {[
              ['Last', `$${last.close?.toFixed(2)}`],
              ['Change', `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`],
              ['High', `$${last.high?.toFixed(2)}`],
              ['Low', `$${last.low?.toFixed(2)}`],
              ['RSI', last.rsi?.toFixed(1) || '—'],
              ['Volume', (last.volume / 1e6).toFixed(1) + 'M'],
            ].map(([k, v]) => (
              <div key={k} className="card py-2">
                <p className="text-xs text-gray-500">{k}</p>
                <p className={`text-sm font-bold ${
                  k === 'Change'
                    ? chg >= 0 ? 'text-green-400' : 'text-red-400'
                    : 'text-white'
                }`}>{v}</p>
              </div>
            ))}
          </div>
        )
      })()}
    </div>
  )
}
