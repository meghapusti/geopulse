/**
 * SignalsDashboard
 * Shows the latest LightGBM market predictions:
 *   VIX direction, Gold bias, Oil bias, Macro risk quartile.
 * Also shows 30-day signal history sparklines.
 */
import { useQuery } from '@tanstack/react-query'
import { TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react'
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { format, parseISO } from 'date-fns'
import { signalsApi, type MarketSignal } from '../../services/api'
import { useAppStore } from '../../store/appStore'

type Direction = 'up' | 'down' | 'neutral' | 'bullish' | 'bearish' | null

function DirectionIcon({ dir }: { dir: Direction }) {
  if (dir === 'up' || dir === 'bullish') return <TrendingUp size={14} className="text-red-400" />
  if (dir === 'down' || dir === 'bearish') return <TrendingDown size={14} className="text-teal-400" />
  return <Minus size={14} className="text-gray-400" />
}

function directionColor(dir: Direction): string {
  if (dir === 'up' || dir === 'bullish') return 'text-red-400'
  if (dir === 'down' || dir === 'bearish') return 'text-teal-400'
  return 'text-gray-400'
}

function directionBg(dir: Direction): string {
  if (dir === 'up' || dir === 'bullish') return 'border-red-800/50 bg-red-950/30'
  if (dir === 'down' || dir === 'bearish') return 'border-teal-800/50 bg-teal-950/30'
  return 'border-gray-700/50 bg-gray-900/30'
}

function RiskQuartile({ q }: { q: number | null }) {
  if (!q) return <span className="text-gray-500">—</span>
  const colors = ['', 'text-teal-400', 'text-amber-400', 'text-orange-400', 'text-red-400']
  const labels = ['', 'Q1 Low', 'Q2 Moderate', 'Q3 Elevated', 'Q4 Critical']
  return (
    <span className={`font-semibold ${colors[q]}`}>{labels[q]}</span>
  )
}

function SignalCard({
  label,
  value,
  confidence,
  direction,
}: {
  label: string
  value: string
  confidence: number | null
  direction: Direction
}) {
  return (
    <div className={`rounded-lg border p-4 ${directionBg(direction)}`}>
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">{label}</div>
      <div className={`flex items-center gap-2 text-lg font-semibold ${directionColor(direction)}`}>
        <DirectionIcon dir={direction} />
        <span className="capitalize">{value}</span>
      </div>
      {confidence != null && (
        <div className="mt-2">
          <div className="flex justify-between text-xs text-gray-600 mb-0.5">
            <span>confidence</span>
            <span>{(confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-current opacity-60 transition-all duration-500"
              style={{ width: `${confidence * 100}%`, color: directionColor(direction) === 'text-red-400' ? '#E24B4A' : '#1D9E75' }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export function SignalsDashboard() {
  const { globalTensionAvg } = useAppStore()

  const { data: latest } = useQuery({
    queryKey: ['signals', 'latest'],
    queryFn: () => signalsApi.getLatest(24),
    refetchInterval: 5 * 60 * 1000,
  })

  const { data: history } = useQuery({
    queryKey: ['signals', 'history'],
    queryFn: () => signalsApi.getHistory(24, 30),
    staleTime: 10 * 60 * 1000,
  })

  const signal: MarketSignal | undefined = latest?.[0]

  const chartData = history?.map(s => ({
    t: format(parseISO(s.timestamp), 'MMM d'),
    risk: s.macro_risk_quartile ?? 0,
  })) ?? []

  return (
    <div className="p-5 space-y-5">

      {/* Global tension summary */}
      <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Global tension index</div>
            <div className="text-3xl font-bold tabular-nums text-white">{globalTensionAvg.toFixed(1)}</div>
          </div>
          <Activity size={24} className="text-gray-600" />
        </div>
      </div>

      {/* Signal cards */}
      {signal ? (
        <>
          <div>
            <div className="text-xs text-gray-600 mb-2">24h predictions</div>
            <div className="grid grid-cols-2 gap-3">
              <SignalCard
                label="VIX"
                value={signal.vix_direction ?? '—'}
                confidence={signal.vix_confidence}
                direction={signal.vix_direction as Direction}
              />
              <SignalCard
                label="Gold"
                value={signal.gold_bias ?? '—'}
                confidence={signal.gold_confidence}
                direction={signal.gold_bias as Direction}
              />
              <SignalCard
                label="Oil"
                value={signal.oil_bias ?? '—'}
                confidence={signal.oil_confidence}
                direction={signal.oil_bias as Direction}
              />
              <div className="rounded-lg border border-gray-700/50 bg-gray-900/30 p-4">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Macro risk</div>
                <RiskQuartile q={signal.macro_risk_quartile} />
              </div>
            </div>
          </div>

          {/* Risk history sparkline */}
          {chartData.length > 2 && (
            <div>
              <div className="text-xs text-gray-600 mb-2">30-day macro risk</div>
              <ResponsiveContainer width="100%" height={60}>
                <LineChart data={chartData}>
                  <Line type="monotone" dataKey="risk" stroke="#EF9F27" strokeWidth={1.5} dot={false} />
                  <XAxis dataKey="t" hide />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 11 }}
                    formatter={(v: number) => [`Q${v}`, 'Risk quartile']}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      ) : (
        <div className="text-gray-600 text-sm text-center py-4 animate-pulse">
          Awaiting first prediction run...
        </div>
      )}
    </div>
  )
}
