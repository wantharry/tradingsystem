import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listStrategies, getStrategyDocs, getSignals } from '../api/client'
import { BookOpen, Zap, ChevronDown, ChevronRight, TrendingUp, Shield, Zap as ZapIcon } from 'lucide-react'

// ── Asset-class colour palettes ──────────────────────────────────────────────
const ASSET_STYLES = {
  equity:  { border: 'border-green-600',  bg: 'bg-green-900/20',  text: 'text-green-400',  badge: 'bg-green-900/40 text-green-300 border-green-700' },
  options: { border: 'border-purple-600', bg: 'bg-purple-900/20', text: 'text-purple-400', badge: 'bg-purple-900/40 text-purple-300 border-purple-700' },
  futures: { border: 'border-amber-600',  bg: 'bg-amber-900/20',  text: 'text-amber-400',  badge: 'bg-amber-900/40 text-amber-300 border-amber-700' },
}

// ── Strategy-type colour palettes ─────────────────────────────────────────────
const TYPE_STYLES = {
  trend_following:  { text: 'text-green-300',  bg: 'bg-green-800/30',  border: 'border-green-700/50' },
  hedge_equity:     { text: 'text-blue-300',   bg: 'bg-blue-800/30',   border: 'border-blue-700/50' },
  short_volatility: { text: 'text-purple-300', bg: 'bg-purple-800/30', border: 'border-purple-700/50' },
  covered_calls:    { text: 'text-teal-300',   bg: 'bg-teal-800/30',   border: 'border-teal-700/50' },
  dispersion:       { text: 'text-rose-300',   bg: 'bg-rose-800/30',   border: 'border-rose-700/50' },
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

// ── Level 3: Individual strategy card ────────────────────────────────────────
function StrategyCard({ strat, assetStyle }) {
  const [showDocs, setShowDocs] = useState(false)
  const [showSignals, setShowSignals] = useState(false)
  const [signalSymbol, setSignalSymbol] = useState('SPY')

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
    <div className={`rounded-lg border ${assetStyle.border} bg-gray-900/60 p-4 space-y-3`}>
      {/* Strategy name + description */}
      <div>
        <h4 className="font-semibold text-white text-sm">{strat.name}</h4>
        <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{strat.description}</p>
      </div>

      {/* Best regimes */}
      {strat.best_regimes?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-xs text-gray-500">Best in:</span>
          {strat.best_regimes.map(r => (
            <span key={r} className="text-xs px-2 py-0.5 bg-gray-800 rounded text-gray-300">{r}</span>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 pt-1 border-t border-gray-800">
        <button onClick={() => setShowDocs(d => !d)} className="btn-ghost text-xs gap-1">
          <BookOpen size={11} />
          {showDocs ? 'Hide Docs' : 'Read Docs'}
        </button>
        <button onClick={() => setShowSignals(s => !s)} className="btn-ghost text-xs gap-1">
          <Zap size={11} />
          {showSignals ? 'Hide Signals' : 'Get Signals'}
        </button>
      </div>

      {/* Documentation */}
      {showDocs && docs?.documentation && (
        <div className="border-t border-gray-800 pt-3 space-y-4">
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
        <div className="border-t border-gray-800 pt-3">
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
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`font-bold ${sig.action === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>{sig.action}</span>
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

// ── Level 2: Strategy-type section ────────────────────────────────────────────
function StrategyTypeSection({ typeKey, typeMeta, strategies, assetStyle }) {
  const [open, setOpen] = useState(true)
  const ts = TYPE_STYLES[typeKey] || { text: 'text-gray-300', bg: 'bg-gray-800/30', border: 'border-gray-700/50' }
  const isPlaceholder = strategies.length === 0

  return (
    <div className={`rounded-lg border ${ts.border} ${ts.bg}`}>
      {/* Type header — Level 2 */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 p-3 text-left"
      >
        <span className="text-gray-500">{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-semibold ${ts.text}`}>{typeMeta.label}</span>
            {isPlaceholder && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 border border-gray-600">Coming soon</span>
            )}
            {!isPlaceholder && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{strategies.length} strategy</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{typeMeta.description}</p>
        </div>
        <div className="flex flex-wrap gap-1 justify-end">
          {typeMeta.best_regimes?.slice(0, 3).map(r => (
            <span key={r} className="text-xs px-1.5 py-0.5 bg-gray-800/80 rounded text-gray-400">{r}</span>
          ))}
        </div>
      </button>

      {/* Strategy cards — Level 3 */}
      {open && (
        <div className="px-3 pb-3 space-y-2 border-t border-gray-800/50 pt-2">
          {isPlaceholder ? (
            <div className="text-center py-4 text-gray-600 text-xs">
              No strategies implemented yet — check back soon.
            </div>
          ) : (
            strategies.map(strat => (
              <StrategyCard key={strat.key} strat={strat} assetStyle={assetStyle} />
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Level 1: Asset-class section ──────────────────────────────────────────────
function AssetClassSection({ assetKey, assetMeta, strategiesByKey }) {
  const [open, setOpen] = useState(true)
  const as_ = ASSET_STYLES[assetKey] || ASSET_STYLES.equity

  const totalStrategies = Object.values(assetMeta.strategy_types)
    .flatMap(t => t.strategies).length

  return (
    <div className={`card border-l-4 ${as_.border} space-y-3`}>
      {/* Asset class header — Level 1 */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 text-left"
      >
        <span className="text-2xl">{assetMeta.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h2 className={`text-lg font-bold ${as_.text}`}>{assetMeta.label}</h2>
            <span className={`text-xs px-2 py-0.5 rounded border ${as_.badge}`}>
              {totalStrategies} active
            </span>
          </div>
          <p className="text-sm text-gray-400">{assetMeta.description}</p>
        </div>
        <span className="text-gray-500">{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
      </button>

      {/* Strategy types — Level 2 */}
      {open && (
        <div className="space-y-2 pl-8">
          {Object.entries(assetMeta.strategy_types).map(([typeKey, typeMeta]) => {
            const strategies = typeMeta.strategies
              .map(k => strategiesByKey[k])
              .filter(Boolean)
            return (
              <StrategyTypeSection
                key={typeKey}
                typeKey={typeKey}
                typeMeta={typeMeta}
                strategies={strategies}
                assetStyle={as_}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Page root ─────────────────────────────────────────────────────────────────
export default function Strategies() {
  const { data, isLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: listStrategies,
  })

  const strategies = data?.strategies || []
  const taxonomy = data?.taxonomy || {}

  const strategiesByKey = Object.fromEntries(strategies.map(s => [s.key, s]))

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Trading Strategies</h1>
        <p className="text-sm text-gray-400 mt-1">
          Three-level taxonomy: <span className="text-gray-300">Asset Class</span>
          {' → '}
          <span className="text-gray-300">Strategy Type</span>
          {' → '}
          <span className="text-gray-300">Strategy</span>.
          Know what you're trading, how you're trading it, and exactly which rules to follow.
        </p>
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-gray-400 p-3 bg-gray-900 rounded-lg border border-gray-800">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-green-500 inline-block"/> Equity</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-purple-500 inline-block"/> Options</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block"/> Futures</span>
        <span className="ml-auto text-gray-600">Click any header to collapse</span>
      </div>

      {isLoading && (
        <div className="card text-center py-12 text-gray-500">Loading strategies…</div>
      )}

      {Object.entries(taxonomy).map(([assetKey, assetMeta]) => (
        <AssetClassSection
          key={assetKey}
          assetKey={assetKey}
          assetMeta={assetMeta}
          strategiesByKey={strategiesByKey}
        />
      ))}
    </div>
  )
}

