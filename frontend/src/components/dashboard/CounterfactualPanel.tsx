/**
 * CounterfactualPanel
 * Interactive slider: drag to set a hypothetical tension level for a region
 * and see how market predictions shift in real time.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { counterfactualApi, type CounterfactualResult } from '../../services/api'

interface Props {
  regionCode: string
}

function BiasChip({ label, value, changed }: { label: string; value: string; changed: boolean }) {
  const isUp = value === 'up' || value === 'bullish'
  const isDown = value === 'down' || value === 'bearish'
  const color = isUp ? 'text-red-400' : isDown ? 'text-teal-400' : 'text-gray-400'
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus

  return (
    <div className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs ${changed ? 'bg-amber-900/30 border border-amber-700/40' : 'bg-gray-900/30 border border-gray-700/30'}`}>
      <Icon size={11} className={color} />
      <span className="text-gray-400">{label}</span>
      <span className={`capitalize font-medium ${color}`}>{value}</span>
      {changed && <span className="text-amber-500 text-xs">↑</span>}
    </div>
  )
}

export function CounterfactualPanel({ regionCode }: Props) {
  const [tension, setTension] = useState(50)
  const [result, setResult] = useState<CounterfactualResult | null>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => counterfactualApi.predict(regionCode, tension),
    onSuccess: (data) => setResult(data),
  })

  function tensionLabel(v: number) {
    if (v < 25) return 'Calm'
    if (v < 45) return 'Elevated'
    if (v < 65) return 'High'
    if (v < 80) return 'Critical'
    return 'Extreme'
  }

  function sliderColor(v: number) {
    if (v < 25) return '#1D9E75'
    if (v < 45) return '#EF9F27'
    if (v < 65) return '#D85A30'
    return '#E24B4A'
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-500">Hypothetical tension</span>
          <span className="text-sm font-semibold tabular-nums" style={{ color: sliderColor(tension) }}>
            {tension} — {tensionLabel(tension)}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={tension}
          onChange={e => setTension(Number(e.target.value))}
          className="w-full accent-amber-400 cursor-pointer"
          style={{ accentColor: sliderColor(tension) }}
        />
        <div className="flex justify-between text-xs text-gray-700 mt-1">
          <span>0</span>
          <span>50</span>
          <span>100</span>
        </div>
      </div>

      <button
        onClick={() => mutate()}
        disabled={isPending}
        className="w-full text-xs py-2 px-4 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border border-gray-700 transition-colors disabled:opacity-50"
      >
        {isPending ? 'Predicting...' : 'Run scenario'}
      </button>

      {result && (
        <div className="space-y-2">
          <div className="text-xs text-gray-600 uppercase tracking-wider">Predicted outcomes</div>
          <div className="grid grid-cols-1 gap-1.5">
            <BiasChip
              label="VIX"
              value={result.predicted_vix_direction}
              changed={result.delta_vs_current.vix_direction_changed}
            />
            <BiasChip
              label="Gold"
              value={result.predicted_gold_bias}
              changed={result.delta_vs_current.gold_bias_changed}
            />
            <BiasChip
              label="Oil"
              value={result.predicted_oil_bias}
              changed={result.delta_vs_current.oil_bias_changed}
            />
          </div>
          <div className="text-xs text-gray-600">
            Macro risk:{' '}
            <span className="text-amber-400 font-medium">Q{result.macro_risk_quartile}</span>
            {result.delta_vs_current.risk_quartile_delta !== 0 && (
              <span className={result.delta_vs_current.risk_quartile_delta > 0 ? 'text-red-400 ml-1' : 'text-teal-400 ml-1'}>
                ({result.delta_vs_current.risk_quartile_delta > 0 ? '+' : ''}{result.delta_vs_current.risk_quartile_delta})
              </span>
            )}
          </div>
          <div className="text-xs text-gray-700">
            Confidence: {(result.confidence * 100).toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  )
}
