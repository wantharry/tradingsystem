import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { runBacktest, listStrategies, getBacktestHistory } from '../api/client'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid
} from 'recharts'
import { FlaskConical, CheckCircle, XCircle } from 'lucide-react'

function MetricGrid({ metrics }) {
  if (!metrics) return null
  const pairs = [
    ['Total Return', `${metrics.total_return_pct?.toFixed(1)}%`],
    ['Ann. Return',  `${metrics.annualized_return_pct?.toFixed(1)}%`],
    ['Sharpe Ratio', metrics.sharpe_ratio?.toFixed(2)],
    ['Sortino',      metrics.sortino_ratio?.toFixed(2)],
    ['Max Drawdown', `${metrics.max_drawdown_pct?.toFixed(1)}%`],
    ['Win Rate',     `${metrics.win_rate_pct?.toFixed(1)}%`],
    ['Profit Factor',metrics.profit_factor?.toFixed(2)],
    ['Expectancy',   `${metrics.expectancy?.toFixed(1)}%`],
    ['Trades',       metrics.total_trades],
    ['Avg Hold',     `${metrics.avg_hold_days?.toFixed(0)}d`],
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {pairs.map(([label, value]) => (
        <div key={label} className="bg-gray-800 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">{label}</p>
          <p className="text-sm font-bold text-white">{value ?? '—'}</p>
        </div>
      ))}
    </div>
  )
}

function EquityChart({ equity }) {
  if (!equity?.length) return null
  const data = equity.map(p => ({ ...p, equity: +(p.equity || 0).toFixed(2) }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: 0, right: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} />
        <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} width={55} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
          labelStyle={{ color: '#9ca3af', fontSize: 11 }}
          itemStyle={{ color: '#34d399' }}
        />
        <ReferenceLine y={10000} stroke="#374151" strokeDasharray="4 4" />
        <Line type="monotone" dataKey="equity" stroke="#34d399" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default function Backtest() {
  const [form, setForm] = useState({
    strategy_key: 'trend_following',
    symbol: 'SPY',
    walk_forward: true,
    parameters: {},
  })
  const [result, setResult] = useState(null)

  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: listStrategies })

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: runBacktest,
    onSuccess: d => setResult(d),
  })

  const wf = result?.walk_forward_summary

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white">Backtest Engine</h1>
        <p className="text-sm text-gray-400 mt-1">
          Walk-forward test: 70% in-sample training, 30% out-of-sample validation.
          Only robust strategies pass both.
        </p>
      </div>

      {/* Form */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Configure Backtest</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Strategy</label>
            <select
              value={form.strategy_key}
              onChange={e => setForm(f => ({ ...f, strategy_key: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            >
              {(strategies?.strategies || []).map(s => (
                <option key={s.key} value={s.key}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Symbol</label>
            <input
              value={form.symbol}
              onChange={e => setForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono"
              placeholder="SPY"
            />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={form.walk_forward}
            onChange={e => setForm(f => ({ ...f, walk_forward: e.target.checked }))}
            className="rounded"
          />
          <span className="text-sm text-gray-300">Walk-forward validation (recommended)</span>
        </label>
        <button
          onClick={() => mutate(form)}
          disabled={isPending}
          className="btn-primary"
        >
          <FlaskConical size={14} />
          {isPending ? 'Running…' : 'Run Backtest'}
        </button>
      </div>

      {isError && (
        <div className="card border border-red-700 bg-red-900/20 text-red-400 text-sm">
          {error?.response?.data?.detail || error?.message || 'Backtest failed.'}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Walk-forward verdict */}
          {wf && (
            <div className={`card border ${wf.is_robust ? 'border-green-700 bg-green-900/20' : 'border-red-700 bg-red-900/20'}`}>
              <div className="flex items-center gap-3">
                {wf.is_robust
                  ? <CheckCircle size={20} className="text-green-400" />
                  : <XCircle size={20} className="text-red-400" />}
                <div>
                  <p className={`font-bold ${wf.is_robust ? 'text-green-400' : 'text-red-400'}`}>
                    {wf.is_robust ? 'Strategy Passes Walk-Forward Test' : 'Strategy Fails Walk-Forward Test'}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    WF Efficiency: {(wf.wf_efficiency * 100).toFixed(0)}% |
                    In-sample Sharpe: {wf.in_sample?.sharpe_ratio?.toFixed(2)} |
                    Out-of-sample Sharpe: {wf.out_of_sample?.sharpe_ratio?.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Equity curve */}
          {result.in_sample?.equity_curve?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-white mb-4">Equity Curve (In-Sample)</h3>
              <EquityChart equity={result.in_sample.equity_curve} />
            </div>
          )}

          {/* In-sample metrics */}
          {result.in_sample && (
            <div className="card">
              <h3 className="font-semibold text-white mb-3">In-Sample Metrics (Training)</h3>
              <MetricGrid metrics={result.in_sample} />
            </div>
          )}

          {/* Out-of-sample metrics */}
          {result.out_of_sample && (
            <div className="card">
              <h3 className="font-semibold text-white mb-3">Out-of-Sample Metrics (Validation)</h3>
              <EquityChart equity={result.out_of_sample.equity_curve} />
              <div className="mt-4">
                <MetricGrid metrics={result.out_of_sample} />
              </div>
            </div>
          )}

          {/* Simple backtest (no walk-forward) */}
          {result.metrics && !wf && (
            <div className="card">
              <h3 className="font-semibold text-white mb-3">Backtest Results</h3>
              <EquityChart equity={result.metrics.equity_curve} />
              <div className="mt-4">
                <MetricGrid metrics={result.metrics} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
