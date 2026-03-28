/**
 * BacktestPanel
 * Shows how the tension index correlated with real VIX historically.
 * Portfolio-proof section — demonstrates signal validity.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart2, CheckCircle, XCircle } from 'lucide-react'
import { backtestApi } from '../../services/api'
import { format, subMonths } from 'date-fns'

function MetricCard({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-900/30 p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-bold tabular-nums text-white">{value}</div>
      {subtext && <div className="text-xs text-gray-600 mt-0.5">{subtext}</div>}
    </div>
  )
}

export function BacktestPanel() {
  const [months, setMonths] = useState(3)

  const endDate = new Date()
  const startDate = subMonths(endDate, months)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['backtest', months],
    queryFn: () =>
      backtestApi.run(
        startDate.toISOString(),
        endDate.toISOString(),
        24,
      ),
    enabled: false,  // only run when user clicks
    staleTime: Infinity,
  })

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center gap-2">
        <BarChart2 size={14} className="text-purple-400" />
        <div className="text-xs text-gray-500 uppercase tracking-wider">Historical validation</div>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        Validates the tension index against actual VIX outcomes.
        Shows whether rising tension preceded real volatility spikes.
      </div>

      {/* Controls */}
      <div className="space-y-3">
        <div>
          <div className="text-xs text-gray-500 mb-2">Lookback period</div>
          <div className="flex gap-2">
            {[1, 3, 6, 12].map(m => (
              <button
                key={m}
                onClick={() => setMonths(m)}
                className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                  months === m
                    ? 'border-purple-600 bg-purple-900/30 text-purple-300'
                    : 'border-gray-700 bg-gray-900/20 text-gray-500 hover:text-gray-300'
                }`}
              >
                {m}M
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="w-full text-xs py-2 rounded bg-purple-900/30 hover:bg-purple-900/50 text-purple-300 border border-purple-700/50 transition-colors disabled:opacity-50"
        >
          {isLoading ? 'Running backtest...' : 'Run backtest'}
        </button>
      </div>

      {data && (
        <div className="space-y-4">
          {/* Metrics grid */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Accuracy" value={`${(data.accuracy * 100).toFixed(1)}%`} subtext="VIX direction" />
            <MetricCard label="F1 score" value={data.f1.toFixed(3)} subtext="precision/recall" />
            <MetricCard label="Correlation" value={data.correlation_with_vix.toFixed(3)} subtext="tension vs VIX" />
            <MetricCard label="Precision" value={`${(data.precision * 100).toFixed(1)}%`} subtext="true positives" />
          </div>

          {/* Notable hits */}
          {data.notable_hits.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <CheckCircle size={11} className="text-teal-400" />
                <div className="text-xs text-gray-500">Notable hits</div>
              </div>
              <div className="space-y-1.5">
                {data.notable_hits.slice(0, 3).map((h, i) => (
                  <div key={i} className="text-xs text-gray-400 rounded bg-gray-900/40 px-3 py-2 border border-gray-800">
                    {String(h.date).split('T')[0]} · VIX {Number(h.vix_actual).toFixed(1)} · Risk Q{String(h.macro_risk_quartile)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Notable misses */}
          {data.notable_misses.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <XCircle size={11} className="text-red-400" />
                <div className="text-xs text-gray-500">Misses</div>
              </div>
              <div className="space-y-1.5">
                {data.notable_misses.slice(0, 3).map((m, i) => (
                  <div key={i} className="text-xs text-gray-400 rounded bg-gray-900/40 px-3 py-2 border border-gray-800">
                    {String(m.date).split('T')[0]} · VIX {Number(m.vix_actual).toFixed(1)} · predicted {String(m.prediction)}
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
