import { useQuery } from '@tanstack/react-query'
import { getMarketRegime } from '../../api/client'
import { RefreshCw, Circle } from 'lucide-react'
import { format } from 'date-fns'

const REGIME_COLORS = {
  uptrend:   'text-green-400',
  downtrend: 'text-red-400',
  ranging:   'text-blue-400',
  high_vol:  'text-amber-400',
  risk_off:  'text-red-500',
  event:     'text-purple-400',
  unknown:   'text-gray-400',
}

const REGIME_LABELS = {
  uptrend:   'Uptrend',
  downtrend: 'Downtrend',
  ranging:   'Ranging',
  high_vol:  'High Volatility',
  risk_off:  'Risk Off ⚠',
  event:     'Event',
  unknown:   'Unknown',
}

export default function Header() {
  const { data, refetch, isFetching } = useQuery({
    queryKey: ['market-regime'],
    queryFn: getMarketRegime,
    staleTime: 5 * 60_000,
  })

  const regime = data?.regime || 'unknown'
  const color = REGIME_COLORS[regime]

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6">
      {/* Market regime pill */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <Circle size={8} className={`fill-current ${color}`} />
          <span className="text-gray-400">Market:</span>
          <span className={`font-semibold ${color}`}>{REGIME_LABELS[regime]}</span>
          {data?.confidence && (
            <span className="text-gray-500 text-xs">
              ({Math.round(data.confidence * 100)}% confidence)
            </span>
          )}
        </div>
        {data?.adx && (
          <span className="text-xs text-gray-500">
            ADX {data.adx} | RSI {data.rsi} | ATR rank {data.atr_percentile}%ile
          </span>
        )}
      </div>

      {/* Date + refresh */}
      <div className="flex items-center gap-3 text-sm text-gray-400">
        <span>{format(new Date(), 'EEE, MMM d yyyy')}</span>
        <button
          onClick={() => refetch()}
          className="p-1.5 rounded hover:bg-gray-800 transition-colors"
          title="Refresh regime"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin text-green-400' : ''} />
        </button>
      </div>
    </header>
  )
}
