import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listStrategies, getStrategyDocs, getSignals } from '../api/client'
import { BookOpen, Zap, ChevronDown, ChevronUp } from 'lucide-react'

const FAMILY_COLORS = {
  trend:          'text-green-400 bg-green-900/30 border-green-700',
  mean_reversion: 'text-blue-400 bg-blue-900/30 border-blue-700',
  breakout:       'text-amber-400 bg-amber-900/30 border-amber-700',
  volatility:     'text-purple-400 bg-purple-900/30 border-purple-700',
  event:          'text-pink-400 bg-pink-900/30 border-pink-700',
}

function DocSection({ title, content }) {
  if (!content) return null
  const items = Array.isArray(content) ? content : [content]
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium mb-2">{title}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-gray-300 leading-relaxed flex gap-2">
            <span className="text-green-400 flex-shrink-0">›</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function StrategyCard({ strat }) {
  const [showDocs, setShowDocs] = useState(false)
  const [showSignals, setShowSignals] = useState(false)
  const [signalSymbol, setSignalSymbol] = useState('SPY')

  const fc = FAMILY_COLORS[strat.family] || 'text-gray-400 bg-gray-800 border-gray-700'

  const { data: docs } = useQuery({
    queryKey: ['strategy-docs', strat.key],
    queryFn: () => getStrategyDocs(strat.key),
    enabled: showDocs,
  })

  const { data: signalData, isLoading: signalLoading } = useQuery({
    queryKey: ['signals', strat.key, signalSymbol],
    queryFn: () => getSignals(strat.key, signalSymbol),
    enabled: showSignals,
  })

  return (
    <div className="card space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`badge border text-xs ${fc}`}>{strat.family}</span>
          </div>
          <h3 className="font-bold text-white text-base">{strat.name}</h3>
          <p className="text-sm text-gray-400 mt-1">{strat.description}</p>
        </div>
      </div>

      {/* Best regime */}
      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-gray-500">Best in:</span>
        {(strat.best_regimes || []).map(r => (
          <span key={r} className="text-xs px-2 py-0.5 bg-gray-800 rounded text-gray-300">{r}</span>
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2 pt-1 border-t border-gray-800">
        <button
          onClick={() => setShowDocs(d => !d)}
          className="btn-ghost text-xs gap-1"
        >
          <BookOpen size={12} />
          {showDocs ? 'Hide Docs' : 'Read Docs'}
        </button>
        <button
          onClick={() => setShowSignals(s => !s)}
          className="btn-ghost text-xs gap-1"
        >
          <Zap size={12} />
          {showSignals ? 'Hide Signals' : 'Get Signals'}
        </button>
      </div>

      {/* Documentation */}
      {showDocs && docs?.documentation && (
        <div className="border-t border-gray-800 pt-4 space-y-5">
          {docs.documentation.overview && (
            <div className="p-3 bg-blue-900/20 border border-blue-800/40 rounded-lg">
              <p className="text-sm text-blue-200 leading-relaxed">{docs.documentation.overview}</p>
            </div>
          )}
          <DocSection title="When to use" content={docs.documentation.when_to_use} />
          <DocSection title="Entry rules" content={docs.documentation.entry_rules} />
          <DocSection title="Exit rules" content={docs.documentation.exit_rules} />
          <DocSection title="Risk rules" content={docs.documentation.risk_rules} />
          {docs.documentation.common_mistakes && (
            <div>
              <p className="text-xs text-red-400 uppercase tracking-wide font-medium mb-2">Common mistakes to avoid</p>
              <ul className="space-y-1">
                {docs.documentation.common_mistakes.map((m, i) => (
                  <li key={i} className="text-sm text-gray-300 flex gap-2">
                    <span className="text-red-400 flex-shrink-0">✗</span>
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Live signals */}
      {showSignals && (
        <div className="border-t border-gray-800 pt-4">
          <div className="flex items-center gap-2 mb-3">
            <input
              value={signalSymbol}
              onChange={e => setSignalSymbol(e.target.value.toUpperCase())}
              placeholder="SYMBOL"
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white w-24 font-mono"
            />
            <span className="text-xs text-gray-500">signals as of today</span>
          </div>
          {signalLoading ? (
            <p className="text-xs text-gray-500">Loading signals…</p>
          ) : signalData?.signals?.length ? (
            signalData.signals.map((sig, i) => (
              <div key={i} className="bg-gray-800 rounded-lg p-3 text-sm mb-2">
                <div className="flex items-center gap-3">
                  <span className={`font-bold ${sig.action === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                    {sig.action}
                  </span>
                  <span className="text-gray-300">Entry: ${sig.entry_price?.toFixed(2)}</span>
                  <span className="text-red-400">Stop: ${sig.stop_price?.toFixed(2)}</span>
                  <span className="text-green-400">Target: ${sig.target_price?.toFixed(2)}</span>
                  <span className="text-gray-400">R:R {sig.risk_reward_ratio?.toFixed(1)}</span>
                </div>
                <p className="text-xs text-gray-400 mt-2">{sig.reasoning}</p>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-500">No signals for {signalSymbol} right now.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function Strategies() {
  const { data, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: listStrategies,
  })

  const strategies = data?.strategies || []

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white">Trading Strategies</h1>
        <p className="text-sm text-gray-400 mt-1">
          Five strategy families — each with full documentation and live signals.
          Even a beginner can follow these step-by-step.
        </p>
      </div>

      {isLoading && (
        <div className="card text-center py-12 text-gray-500">Loading strategies…</div>
      )}

      {strategies.map(s => <StrategyCard key={s.key} strat={s} />)}
    </div>
  )
}
