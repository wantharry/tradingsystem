import { useQuery } from '@tanstack/react-query'
import { getDailyActions, getMarketRegime, getAllRegimes } from '../api/client'
import {
  TrendingUp, TrendingDown, Minus, AlertTriangle,
  ChevronRight, BarChart2, Target, ShieldAlert
} from 'lucide-react'
import { format } from 'date-fns'

const REGIME_META = {
  uptrend:   { label: 'Uptrend',       color: 'green', bg: 'bg-green-900/30', border: 'border-green-700', text: 'text-green-400' },
  downtrend: { label: 'Downtrend',     color: 'red',   bg: 'bg-red-900/30',   border: 'border-red-700',   text: 'text-red-400' },
  ranging:   { label: 'Ranging',       color: 'blue',  bg: 'bg-blue-900/30',  border: 'border-blue-700',  text: 'text-blue-400' },
  high_vol:  { label: 'High Vol',      color: 'amber', bg: 'bg-amber-900/30', border: 'border-amber-700', text: 'text-amber-400' },
  risk_off:  { label: 'Risk Off ⚠',    color: 'red',   bg: 'bg-red-900/50',   border: 'border-red-600',   text: 'text-red-400' },
  event:     { label: 'Event',         color: 'purple',bg: 'bg-purple-900/30',border: 'border-purple-700',text: 'text-purple-400' },
  unknown:   { label: 'Unknown',       color: 'gray',  bg: 'bg-gray-800',     border: 'border-gray-700',  text: 'text-gray-400' },
}

function RegimeCard({ data }) {
  const meta = REGIME_META[data?.regime] || REGIME_META.unknown
  return (
    <div className={`card border ${meta.border} ${meta.bg}`}>
      <div className="flex justify-between items-start mb-3">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Market Regime</p>
          <p className={`text-2xl font-bold ${meta.text}`}>{meta.label}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400">Confidence</p>
          <p className="text-lg font-semibold text-white">
            {data ? Math.round(data.confidence * 100) : '—'}%
          </p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-gray-800">
        {[['ADX', data?.adx], ['RSI', data?.rsi], ['ATR %ile', data?.atr_percentile]].map(([k, v]) => (
          <div key={k}>
            <p className="text-xs text-gray-500">{k}</p>
            <p className="text-sm font-medium text-white">{v != null ? Number(v).toFixed(1) : '—'}</p>
          </div>
        ))}
      </div>
      {data?.notes && (
        <p className="mt-3 text-xs text-gray-400 leading-relaxed">{data.notes}</p>
      )}
    </div>
  )
}

function ActionCard({ action, rank }) {
  const isLong = action.action === 'BUY'
  const rr = action.risk_reward_ratio
  const conf = Math.round(action.confidence * 100)

  return (
    <div className="card hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono">#{rank}</span>
          <span className="font-bold text-white text-lg">{action.symbol}</span>
          <span className={`badge text-xs font-bold ${
            isLong ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
          }`}>
            {isLong ? '▲ BUY' : '▼ SELL'}
          </span>
          {action.sentiment && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
              action.sentiment.label === 'bullish'
                ? 'bg-emerald-900/40 text-emerald-300 border-emerald-700'
                : action.sentiment.label === 'bearish'
                ? 'bg-red-900/40 text-red-300 border-red-700'
                : 'bg-gray-700/40 text-gray-400 border-gray-600'
            }`}>
              {action.sentiment.label === 'bullish' ? '📰▲' : action.sentiment.label === 'bearish' ? '📰▼' : '📰—'}
              {' '}{action.sentiment.label}
            </span>
          )}
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500">Confidence</p>
          <p className="font-bold text-white">{conf}%</p>
        </div>
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-3 gap-2 mb-3 bg-gray-800/50 rounded-lg p-3">
        <div>
          <p className="text-xs text-gray-500 mb-1">Entry</p>
          <p className="font-mono text-sm text-white">${action.entry_price?.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Stop Loss</p>
          <p className="font-mono text-sm text-red-400">${action.stop_price?.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Target</p>
          <p className="font-mono text-sm text-green-400">${action.target_price?.toFixed(2)}</p>
        </div>
      </div>

      {/* R:R and strategy */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span className={`font-medium ${rr >= 2 ? 'text-green-400' : rr >= 1.5 ? 'text-amber-400' : 'text-red-400'}`}>
            R:R {rr?.toFixed(1)}:1
          </span>
          <span className="text-gray-500">•</span>
          <span className="text-gray-400">{action.strategy}</span>
        </div>
        <span className="text-gray-600 capitalize">{action.regime}</span>
      </div>

      {/* Reasoning */}
      <details className="mt-3">
        <summary className="text-xs text-green-400 cursor-pointer hover:text-green-300">
          Why this trade?
        </summary>
        <p className="mt-2 text-xs text-gray-400 leading-relaxed">{action.reasoning}</p>
      </details>
    </div>
  )
}

function StatTile({ label, value, sub, icon: Icon, color = 'text-white' }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-400 uppercase tracking-wide">{label}</p>
        {Icon && <Icon size={14} className="text-gray-600" />}
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const { data: actions, isLoading: actLoading } = useQuery({
    queryKey: ['daily-actions'],
    queryFn: () => getDailyActions(),
  })

  const { data: regime } = useQuery({
    queryKey: ['market-regime'],
    queryFn: getMarketRegime,
  })

  const { data: allRegimes } = useQuery({
    queryKey: ['all-regimes'],
    queryFn: getAllRegimes,
    staleTime: 10 * 60_000,
  })

  const topActions = (actions?.top_actions || []).slice(0, 20)  // dashboard shows top-20 summary
  const regimes = allRegimes?.regimes || []
  const uptrendCount = regimes.filter(r => r.regime === 'uptrend').length

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">
          {format(new Date(), 'EEEE, MMMM d, yyyy')} — Morning briefing
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Top Setups Today"
          value={topActions.length}
          sub="actionable signals"
          icon={BarChart2}
          color="text-green-400"
        />
        <StatTile
          label="Breadth"
          value={`${uptrendCount}/${regimes.length}`}
          sub="symbols in uptrend"
          icon={TrendingUp}
          color={uptrendCount / regimes.length > 0.5 ? 'text-green-400' : 'text-amber-400'}
        />
        <StatTile
          label="Market Regime"
          value={regime ? (REGIME_META[regime.regime]?.label || regime.regime) : '—'}
          sub={`ADX ${regime?.adx?.toFixed(0) || '—'}`}
          icon={Target}
          color={REGIME_META[regime?.regime]?.text || 'text-white'}
        />
        <StatTile
          label="Max Risk / Trade"
          value="1%"
          sub="of portfolio per setup"
          icon={ShieldAlert}
          color="text-blue-400"
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Regime card */}
        <div className="space-y-4">
          <RegimeCard data={regime} />

          {/* Regime explanation */}
          {actions?.regime_explanation && (
            <div className="card">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">Today's Context</p>
              <p className="text-sm text-gray-300 leading-relaxed">{actions.regime_explanation}</p>
            </div>
          )}

          {/* Risk rules */}
          {actions?.risk_rules?.length > 0 && (
            <div className="card border border-amber-800/50">
              <p className="text-xs text-amber-400 uppercase tracking-wide mb-2 flex items-center gap-1">
                <ShieldAlert size={12} /> Risk Rules Today
              </p>
              <ul className="space-y-1">
                {actions.risk_rules.map((r, i) => (
                  <li key={i} className="text-xs text-gray-300">{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right: Top actions */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white">Top Setups Today</h2>
            <a href="/daily" className="text-xs text-green-400 hover:text-green-300 flex items-center gap-1">
              View all <ChevronRight size={12} />
            </a>
          </div>

          {actLoading && (
            <div className="card text-center py-12 text-gray-500">
              Generating daily action sheet...
            </div>
          )}

          {!actLoading && topActions.length === 0 && (
            <div className="card text-center py-12">
              <AlertTriangle className="mx-auto text-amber-400 mb-3" size={32} />
              <p className="text-gray-400 font-medium">No actionable setups today</p>
              <p className="text-gray-500 text-sm mt-1">
                {actions?.no_trade_reasons?.[0] || 'Market conditions do not meet strategy thresholds.'}
              </p>
            </div>
          )}

          {topActions.map((action, i) => (
            <ActionCard key={`${action.symbol}-${i}`} action={action} rank={i + 1} />
          ))}
        </div>
      </div>

      {/* Regime breadth heatmap */}
      {regimes.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-white mb-4">Watchlist Regime Overview</h2>
          <div className="flex flex-wrap gap-2">
            {regimes.map(r => {
              const meta = REGIME_META[r.regime] || REGIME_META.unknown
              return (
                <div
                  key={r.symbol}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${meta.bg} ${meta.border} ${meta.text}`}
                  title={`ADX: ${r.adx?.toFixed(1)}, RSI: ${r.rsi?.toFixed(1)}`}
                >
                  {r.symbol}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
