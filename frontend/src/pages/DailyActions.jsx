import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getDailyActions, getDailyLogs, getLastTradingDay,
  verifyOutcomes, getPerformanceSummary
} from '../api/client'
import {
  RefreshCw, ChevronDown, ChevronUp, AlertTriangle, BookOpen,
  Calendar, Award, Target, ChevronRight, CheckCircle, XCircle,
  DollarSign, Shield, Info, ArrowRight, Clock
} from 'lucide-react'

const ACTION_COLOR = {
  BUY:        'bg-green-900/40 text-green-400 border-green-700',
  SELL_SHORT: 'bg-red-900/40 text-red-400 border-red-700',
  STRADDLE:   'bg-purple-900/40 text-purple-400 border-purple-700',
  CONDOR:     'bg-blue-900/40 text-blue-400 border-blue-700',
  default:    'bg-gray-800 text-gray-400 border-gray-700',
}

const OUTCOME_META = {
  WIN:            { label: 'WIN',        cls: 'bg-green-900/50 text-green-400 border-green-700' },
  LOSS:           { label: 'LOSS',       cls: 'bg-red-900/50 text-red-400 border-red-700' },
  EXPIRED_PROFIT: { label: 'PROFIT',     cls: 'bg-green-900/30 text-green-500 border-green-800' },
  EXPIRED_LOSS:   { label: 'LOSS (exp)', cls: 'bg-red-900/30 text-red-500 border-red-800' },
  SKIPPED:        { label: 'N/A',        cls: 'bg-gray-800 text-gray-500 border-gray-700' },
  NO_DATA:        { label: 'NO DATA',    cls: 'bg-gray-800 text-gray-500 border-gray-700' },
}

function todayStr() {
  const d = new Date()
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}
function isPast(dateStr) { return dateStr < todayStr() }

// ── Trade Blueprint ──────────────────────────────────────────────────────────
function TradeBlueprint({ blueprint, action }) {
  const [accountSize, setAccountSize] = useState('')
  if (!blueprint) return null

  const ps = blueprint.position_sizing
  const ep = blueprint.exit_plan
  const entryPrice = action.entry_price || 0

  const liveAccount = parseFloat(accountSize) || null
  const liveRisk    = liveAccount ? (liveAccount * ps.risk_pct / 100) : null
  const liveShares  = (liveRisk && ps.risk_per_share > 0)
    ? Math.max(0, Math.floor(liveRisk / ps.risk_per_share)) : null
  const liveValue   = liveShares ? (liveShares * entryPrice).toFixed(2) : null

  const styleColors = {
    'Swing Trade':                  'bg-blue-900/40 text-blue-300 border-blue-700',
    'Swing Trade (Mean Reversion)': 'bg-cyan-900/40 text-cyan-300 border-cyan-700',
    'Momentum Trade':               'bg-amber-900/40 text-amber-300 border-amber-700',
    'Options Volatility Trade':     'bg-purple-900/40 text-purple-300 border-purple-700',
    'Event-Driven Trade':           'bg-orange-900/40 text-orange-300 border-orange-700',
  }
  const styleColor = styleColors[blueprint.trade_style] || 'bg-gray-800 text-gray-300 border-gray-700'

  return (
    <div className="space-y-4 mt-4 pt-4 border-t border-gray-800">
      <div>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${styleColor}`}>
            {blueprint.trade_style}
          </span>
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Clock size={11} /> Hold: {blueprint.hold_days}
          </span>
        </div>
        <p className="text-sm text-gray-400 leading-relaxed">{blueprint.style_description}</p>
      </div>

      {/* STEP 1: Entry */}
      <div className="rounded-lg border border-gray-700 overflow-hidden">
        <div className="bg-gray-800/70 px-3 py-2 flex items-center gap-2">
          <span className="text-[10px] font-bold bg-green-700 text-white rounded-full w-4 h-4 flex items-center justify-center flex-shrink-0">1</span>
          <span className="text-xs font-semibold text-green-300 uppercase tracking-wide">Entry — When &amp; How to Enter</span>
        </div>
        <div className="px-3 py-3 space-y-1.5">
          {blueprint.entry_instructions.map((instr, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-gray-300">
              <ArrowRight size={13} className="text-green-600 mt-0.5 flex-shrink-0" />
              <span>{instr}</span>
            </div>
          ))}
        </div>
      </div>

      {/* STEP 2: Exit */}
      <div className="rounded-lg border border-gray-700 overflow-hidden">
        <div className="bg-gray-800/70 px-3 py-2 flex items-center gap-2">
          <span className="text-[10px] font-bold bg-blue-700 text-white rounded-full w-4 h-4 flex items-center justify-center flex-shrink-0">2</span>
          <span className="text-xs font-semibold text-blue-300 uppercase tracking-wide">Exit — When &amp; How to Get Out</span>
        </div>
        <div className="px-3 py-3 space-y-3">
          <div className="rounded-md bg-green-900/20 border border-green-800/50 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <CheckCircle size={13} className="text-green-400" />
              <span className="text-xs font-semibold text-green-300">Take Profit</span>
            </div>
            <p className="text-xs text-gray-300">{ep.take_profit?.instruction}</p>
            {ep.take_profit?.trailing_tip && (
              <p className="text-xs text-gray-500 mt-1 italic">{ep.take_profit.trailing_tip}</p>
            )}
          </div>
          <div className="rounded-md bg-red-900/20 border border-red-800/50 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <XCircle size={13} className="text-red-400" />
              <span className="text-xs font-semibold text-red-300">Stop Loss</span>
            </div>
            <p className="text-xs text-gray-300">{ep.stop_loss?.instruction}</p>
            {ep.stop_loss?.setup_tip && (
              <p className="text-xs text-gray-500 mt-1 italic">{ep.stop_loss.setup_tip}</p>
            )}
          </div>
          <div className="rounded-md bg-amber-900/20 border border-amber-800/50 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <Clock size={13} className="text-amber-400" />
              <span className="text-xs font-semibold text-amber-300">Time Exit — {ep.time_exit?.days}</span>
            </div>
            <p className="text-xs text-gray-300">{ep.time_exit?.instruction}</p>
          </div>
        </div>
      </div>

      {/* STEP 3: Position sizing */}
      <div className="rounded-lg border border-gray-700 overflow-hidden">
        <div className="bg-gray-800/70 px-3 py-2 flex items-center gap-2">
          <span className="text-[10px] font-bold bg-amber-700 text-white rounded-full w-4 h-4 flex items-center justify-center flex-shrink-0">3</span>
          <span className="text-xs font-semibold text-amber-300 uppercase tracking-wide">Position Sizing — How Much to Buy</span>
        </div>
        <div className="px-3 py-3 space-y-3">
          <p className="text-xs text-gray-400">{ps.explanation}</p>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 max-w-xs">
              <DollarSign size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="number" min={100} step={1000}
                placeholder="Your account size"
                value={accountSize}
                onChange={e => setAccountSize(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-sm text-white pl-7 pr-3 py-1.5 focus:outline-none focus:border-green-500"
              />
            </div>
            {liveShares !== null && (
              <div className="text-sm text-white">
                <span className="font-bold text-green-400">{liveShares} shares</span>
                <span className="text-gray-500 text-xs ml-2">(${liveValue} deployed, ${liveRisk?.toFixed(0)} at risk)</span>
              </div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-1 font-normal">Account</th>
                  <th className="text-right py-1 font-normal">1% Risk</th>
                  <th className="text-right py-1 font-normal">Shares</th>
                  <th className="text-right py-1 font-normal">Capital</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {ps.examples.map(ex => (
                  <tr key={ex.account} className="text-gray-300 hover:bg-gray-800/30">
                    <td className="py-1.5 font-mono">${ex.account.toLocaleString()}</td>
                    <td className="py-1.5 text-right font-mono text-red-300">${ex.risk_dollars}</td>
                    <td className="py-1.5 text-right font-bold text-green-400">{ex.shares}</td>
                    <td className="py-1.5 text-right font-mono text-gray-400">${ex.position_value.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-gray-600 italic">Formula: {ps.formula}</p>
        </div>
      </div>

      {/* STEP 4: Checklist */}
      <div className="rounded-lg border border-gray-700 overflow-hidden">
        <div className="bg-gray-800/70 px-3 py-2 flex items-center gap-2">
          <span className="text-[10px] font-bold bg-purple-700 text-white rounded-full w-4 h-4 flex items-center justify-center flex-shrink-0">4</span>
          <span className="text-xs font-semibold text-purple-300 uppercase tracking-wide">Pre-Trade Checklist</span>
        </div>
        <div className="px-3 py-3 space-y-1.5">
          {blueprint.checklist.map((item, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-300">
              <Shield size={11} className="text-purple-500 mt-0.5 flex-shrink-0" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Action row ───────────────────────────────────────────────────────────────
function ActionRow({ action, outcomeMap = {} }) {
  const [expanded, setExpanded] = useState(false)
  const color = ACTION_COLOR[action.action] || ACTION_COLOR.default
  const rr = action.risk_reward_ratio?.toFixed(1)
  const conf = Math.round((action.confidence || 0) * 100)
  const outcome = outcomeMap[action.symbol]
  const om = outcome ? OUTCOME_META[outcome.outcome] : null

  return (
    <div className="card mb-3">
      <div className="flex items-center gap-4 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        <div className="w-28 flex-shrink-0">
          <p className="font-bold text-white text-base">{action.symbol}</p>
          <div className="flex items-center gap-1 mt-0.5">
            <span className={`badge border text-[10px] ${color}`}>{action.action}</span>
            {om && <span className={`badge border text-[10px] ${om.cls}`}>{om.label}</span>}
          </div>
        </div>
        <div className="flex-1 grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-gray-500 text-xs">Entry</p>
            <p className="font-mono text-white">${action.entry_price?.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Stop</p>
            <p className="font-mono text-red-400">${action.stop_price?.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Target</p>
            <p className="font-mono text-green-400">${action.target_price?.toFixed(2)}</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm flex-shrink-0">
          {outcome?.actual_pnl_pct != null ? (
            <div className="text-right">
              <p className="text-gray-500 text-xs">Actual PnL</p>
              <p className={`font-bold ${outcome.actual_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {outcome.actual_pnl_pct >= 0 ? '+' : ''}{outcome.actual_pnl_pct?.toFixed(2)}%
              </p>
            </div>
          ) : (
            <div className="text-right">
              <p className="text-gray-500 text-xs">R:R</p>
              <p className={`font-medium ${rr >= 2 ? 'text-green-400' : 'text-amber-400'}`}>{rr}:1</p>
            </div>
          )}
          <div className="text-right">
            <p className="text-gray-500 text-xs">Conf.</p>
            <p className="font-medium text-white">{conf}%</p>
          </div>
          {expanded
            ? <ChevronUp size={14} className="text-gray-500" />
            : <ChevronDown size={14} className="text-gray-500" />}
        </div>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-800 space-y-3">
          {outcome && outcome.outcome !== 'SKIPPED' && (
            <div className={`rounded-lg p-3 border ${om?.cls || 'border-gray-700'} bg-opacity-20`}>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1">
                {(outcome.outcome === 'WIN' || outcome.outcome === 'EXPIRED_PROFIT')
                  ? '✓ What actually happened' : '✗ What actually happened'}
              </p>
              <p className="text-sm text-gray-300">
                {outcome.hit_day
                  ? `${outcome.outcome === 'WIN' ? 'Target' : 'Stop'} hit on day ${outcome.hit_day}.`
                  : `Checked ${outcome.days_checked} trading days — neither target nor stop was hit.`}
                {' '}
                {outcome.actual_pnl_pct != null
                  ? `Actual result: ${outcome.actual_pnl_pct >= 0 ? '+' : ''}${outcome.actual_pnl_pct?.toFixed(2)}%.`
                  : ''}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Entry ${outcome.entry_price?.toFixed(2)} → Stop ${outcome.stop_price?.toFixed(2)} / Target ${outcome.target_price?.toFixed(2)}
              </p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1 flex items-center gap-1">
              <BookOpen size={10} /> Why this trade (plain English)
            </p>
            <p className="text-sm text-gray-300 leading-relaxed">{action.reasoning}</p>
          </div>
          {action.trade_blueprint && (
            <TradeBlueprint blueprint={action.trade_blueprint} action={action} />
          )}
          {action.indicators && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Technical Indicators</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(action.indicators).map(([k, v]) => (
                  <div key={k} className="bg-gray-800 px-2 py-1 rounded text-xs">
                    <span className="text-gray-500">{k}: </span>
                    <span className="text-gray-200">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Performance panel ─────────────────────────────────────────────────────────
function PerformancePanel() {
  const { data } = useQuery({
    queryKey: ['performance'],
    queryFn: () => getPerformanceSummary(90),
    staleTime: 10 * 60_000,
  })
  if (!data || data.total_verified === 0) {
    return (
      <div className="card text-center py-8 text-gray-500 text-sm">
        No verified outcomes yet. Run analysis on past dates to build the feedback loop.
      </div>
    )
  }
  const wr = data.win_rate
  const wrColor = wr >= 55 ? 'text-green-400' : wr >= 45 ? 'text-amber-400' : 'text-red-400'
  return (
    <div className="card space-y-4">
      <p className="text-xs text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
        <Award size={12} /> 90-Day Verified Performance
      </p>
      <div className="grid grid-cols-4 gap-3">
        {[
          ['Verified', data.total_verified, 'text-white'],
          ['Win Rate', wr != null ? `${wr}%` : '—', wrColor],
          ['Avg PnL',
            data.avg_pnl_pct != null
              ? `${data.avg_pnl_pct >= 0 ? '+' : ''}${data.avg_pnl_pct}%`
              : '—',
            (data.avg_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'],
          ['Best', data.best_trade != null ? `+${data.best_trade?.toFixed(1)}%` : '—', 'text-green-400'],
        ].map(([label, val, cls]) => (
          <div key={label} className="bg-gray-800/50 rounded-lg p-3 text-center">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`font-bold text-lg ${cls}`}>{val}</p>
          </div>
        ))}
      </div>
      {data.insights?.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Learning Insights</p>
          {data.insights.map((ins, i) => (
            <p key={i} className="text-sm text-gray-300 flex items-start gap-2">
              <ChevronRight size={14} className="text-gray-600 mt-0.5 flex-shrink-0" />
              {ins}
            </p>
          ))}
        </div>
      )}
      {data.regime_stats && Object.keys(data.regime_stats).length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">By Regime</p>
          <div className="space-y-1.5">
            {Object.entries(data.regime_stats)
              .sort((a, b) => b[1].total - a[1].total)
              .map(([regime, stats]) => {
                const rwr = (stats.wins / Math.max(stats.total, 1) * 100).toFixed(0)
                return (
                  <div key={regime} className="flex items-center gap-3 text-sm">
                    <span className="w-24 text-gray-400 capitalize">{regime}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                      <div
                        className={`h-full rounded-full ${Number(rwr) >= 50 ? 'bg-green-500' : 'bg-red-500'}`}
                        style={{ width: `${rwr}%` }}
                      />
                    </div>
                    <span className={`w-12 text-right font-mono ${Number(rwr) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                      {rwr}%
                    </span>
                    <span className="text-gray-600 text-xs w-14 text-right">{stats.total} trades</span>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Log card ──────────────────────────────────────────────────────────────────
function LogCard({ log }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card mb-2">
      <div className="flex items-center justify-between cursor-pointer" onClick={() => setOpen(o => !o)}>
        <div>
          <span className="font-mono text-sm text-green-400">{log.date}</span>
          <span className="ml-3 text-xs text-gray-400">{log.regime_summary}</span>
        </div>
        {open
          ? <ChevronUp size={14} className="text-gray-500" />
          : <ChevronDown size={14} className="text-gray-500" />}
      </div>
      {open && (
        <div className="mt-3 pt-3 border-t border-gray-800 text-sm text-gray-300 space-y-2">
          {log.strategy_notes && <p><span className="text-gray-500">Notes: </span>{log.strategy_notes}</p>}
          {log.risk_alerts && <p className="text-amber-400"><span className="text-gray-500">Risk: </span>{log.risk_alerts}</p>}
          {log.no_trade_reasons && <p className="text-gray-400"><span className="text-gray-500">No-trade: </span>{log.no_trade_reasons}</p>}
        </div>
      )}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DailyActions() {
  const [tab, setTab] = useState('actions')
  const [selectedDate, setSelectedDate] = useState(todayStr())
  const [outcomeMap, setOutcomeMap] = useState({})
  const [verifying, setVerifying] = useState(false)
  const queryClient = useQueryClient()

  const { data: lastTradingDay } = useQuery({
    queryKey: ['last-trading-day'],
    queryFn: getLastTradingDay,
    staleTime: 5 * 60_000,
  })

  const analysisDate = selectedDate

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['daily-actions', analysisDate],
    queryFn: () => getDailyActions({ date: analysisDate }),
    staleTime: 5 * 60_000,
  })

  const { mutate: regen, isPending: regenning } = useMutation({
    mutationFn: () => getDailyActions({ date: analysisDate, regenerate: true }),
    onSuccess: (d) => {
      queryClient.setQueryData(['daily-actions', analysisDate], d)
      setOutcomeMap({})
    },
  })

  const { data: logs } = useQuery({
    queryKey: ['daily-logs'],
    queryFn: getDailyLogs,
    enabled: tab === 'logs',
  })

  useEffect(() => {
    if (data?.top_actions && isPast(analysisDate)) {
      const acts = data.all_actions || data.top_actions || []
      const existing = {}
      for (const a of acts) {
        if (a.outcome) existing[a.symbol] = { outcome: a.outcome, actual_pnl_pct: a.actual_pnl_pct }
      }
      if (Object.keys(existing).length > 0) setOutcomeMap(existing)
    }
  }, [data, analysisDate])

  const handleVerify = async () => {
    setVerifying(true)
    try {
      const result = await verifyOutcomes(analysisDate, 15)
      const map = {}
      for (const o of result.outcomes) map[o.symbol] = o
      setOutcomeMap(map)
      queryClient.invalidateQueries(['performance'])
    } catch (e) {
      console.error('Verify failed:', e)
    } finally {
      setVerifying(false)
    }
  }

  const shiftDate = (days) => {
    const d = new Date(selectedDate + 'T12:00:00')
    d.setDate(d.getDate() + days)
    const s = d.getFullYear() + '-'
      + String(d.getMonth() + 1).padStart(2, '0') + '-'
      + String(d.getDate()).padStart(2, '0')
    setSelectedDate(s)
    setOutcomeMap({})
  }

  const actions = data?.all_actions || data?.top_actions || []
  const isHistorical = isPast(analysisDate)
  const isFuture = analysisDate > todayStr()
  const hasOutcomes = Object.keys(outcomeMap).length > 0

  const lastDay = lastTradingDay?.last_trading_day
  let contextNote = null
  if (isFuture)
    contextNote = `Future date — analysis uses data through ${lastDay || 'last available session'}.`
  else if (analysisDate === todayStr() && lastTradingDay?.market_closed)
    contextNote = `Market closed — analysis uses data through ${lastDay}.`

  return (
    <div className="max-w-5xl mx-auto space-y-5">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-start gap-4 justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Daily Action Sheet</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data?.date ? `Generated for ${data.date}` : 'Select a date for analysis'}
          </p>
          {contextNote && (
            <p className="text-xs text-amber-400 mt-1 flex items-center gap-1">
              <AlertTriangle size={11} /> {contextNote}
            </p>
          )}
        </div>

        {/* Date controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => shiftDate(-1)} className="btn-secondary text-sm px-2" title="Previous day">‹</button>
          <div className="relative flex items-center">
            <Calendar size={14} className="absolute left-2.5 text-gray-500 pointer-events-none" />
            <input
              type="date"
              value={selectedDate}
              max={todayStr()}
              onChange={e => { setSelectedDate(e.target.value); setOutcomeMap({}) }}
              className="bg-gray-800 border border-gray-700 text-white text-sm rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-green-500"
            />
          </div>
          <button
            onClick={() => shiftDate(1)}
            disabled={analysisDate >= todayStr()}
            className="btn-secondary text-sm px-2 disabled:opacity-40"
            title="Next day"
          >›</button>
          <button
            onClick={() => { setSelectedDate(todayStr()); setOutcomeMap({}) }}
            className="btn-secondary text-sm"
          >Today</button>
          {isHistorical && (
            <button
              onClick={handleVerify}
              disabled={verifying}
              className="btn-secondary text-sm flex items-center gap-1.5"
            >
              <Target size={13} className={verifying ? 'animate-spin' : ''} />
              {verifying ? 'Verifying…' : 'Verify Outcomes'}
            </button>
          )}
          <button
            onClick={() => regen()}
            disabled={regenning || isFetching}
            className="btn-secondary text-sm flex items-center gap-1.5"
          >
            <RefreshCw size={13} className={(regenning || isFetching) ? 'animate-spin' : ''} />
            {regenning || isFetching ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-1 border-b border-gray-800">
        {[['actions', 'Trade Actions'], ['logs', 'Logs'], ['performance', 'Performance']].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === key
                ? 'bg-gray-800 text-white border-b-2 border-green-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >{label}</button>
        ))}
      </div>

      {/* ── Trade Actions tab ── */}
      {tab === 'actions' && (
        <>
          {/* How This System Trades */}
          <div className="rounded-lg border border-blue-800/40 bg-blue-900/10 px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <Info size={14} className="text-blue-400" />
              <span className="text-xs font-semibold text-blue-300 uppercase tracking-wide">How This System Trades</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <p className="font-semibold text-white mb-0.5">Style: Swing Trading</p>
                <p className="text-gray-400">Hold 3–15 days. Not day trading, not value investing. Catching a short-term move then getting out.</p>
              </div>
              <div>
                <p className="font-semibold text-white mb-0.5">Risk: 1% per trade</p>
                <p className="text-gray-400">Each trade risks exactly 1% of your account. Max 5 open positions. Stop for the day if down 2%.</p>
              </div>
              <div>
                <p className="font-semibold text-white mb-0.5">Edge: R:R ≥ 1.5:1</p>
                <p className="text-gray-400">Only enter when reward ≥ 1.5× risk. Expand any card below for the full step-by-step plan.</p>
              </div>
            </div>
          </div>

          {/* Outcome summary banner */}
          {hasOutcomes && (
            <div className="rounded-lg border border-gray-700 bg-gray-800/50 px-4 py-3 flex flex-wrap gap-3">
              {['WIN', 'LOSS', 'EXPIRED_PROFIT', 'EXPIRED_LOSS', 'SKIPPED', 'NO_DATA'].map(key => {
                const count = Object.values(outcomeMap).filter(o => o.outcome === key).length
                if (!count) return null
                const m = OUTCOME_META[key]
                return (
                  <span key={key} className={`px-2 py-0.5 rounded border text-xs font-medium ${m.cls}`}>
                    {m.label}: {count}
                  </span>
                )
              })}
            </div>
          )}

          {/* Loading */}
          {(isLoading || isFetching) && !actions.length && (
            <div className="text-center py-10 text-gray-500 text-sm">
              <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
              Generating analysis…
            </div>
          )}

          {/* Action rows */}
          {actions.map((action, i) => (
            <ActionRow key={action.symbol || i} action={action} outcomeMap={outcomeMap} />
          ))}

          {!isLoading && !isFetching && actions.length === 0 && (
            <div className="card text-center py-10 text-gray-500 text-sm">
              No trade signals for this date.
            </div>
          )}
        </>
      )}

      {/* ── Logs tab ── */}
      {tab === 'logs' && (
        <div className="space-y-2">
          {(logs || []).length > 0
            ? (logs || []).map((log, i) => <LogCard key={log.date || i} log={log} />)
            : <div className="card text-center py-8 text-gray-500 text-sm">No logs yet.</div>
          }
        </div>
      )}

      {/* ── Performance tab ── */}
      {tab === 'performance' && <PerformancePanel />}

    </div>
  )
}
