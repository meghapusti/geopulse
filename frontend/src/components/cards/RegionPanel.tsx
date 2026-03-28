/**
 * RegionPanel
 * Slides in from the right when the user clicks a country.
 * Shows: tension sparkline, recent articles, event type breakdown,
 * market signal for this region, and the counterfactual slider.
 */
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { X, TrendingUp, TrendingDown, Minus, ExternalLink, AlertTriangle } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { format, parseISO } from 'date-fns'
import { globeApi } from '../../services/api'
import { useAppStore } from '../../store/appStore'
import { CounterfactualPanel } from '../dashboard/CounterfactualPanel'

function tensionColor(v: number) {
  if (v < 25) return 'text-teal-400'
  if (v < 45) return 'text-amber-400'
  if (v < 65) return 'text-orange-400'
  return 'text-red-400'
}

function tensionBg(v: number) {
  if (v < 25) return 'bg-teal-900/40 border-teal-700/40'
  if (v < 45) return 'bg-amber-900/40 border-amber-700/40'
  if (v < 65) return 'bg-orange-900/40 border-orange-700/40'
  return 'bg-red-900/40 border-red-700/40'
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return null
  const abs = Math.abs(delta).toFixed(1)
  if (delta > 2) return <span className="flex items-center gap-1 text-red-400 text-xs"><TrendingUp size={12} />+{abs}</span>
  if (delta < -2) return <span className="flex items-center gap-1 text-teal-400 text-xs"><TrendingDown size={12} />-{abs}</span>
  return <span className="flex items-center gap-1 text-gray-400 text-xs"><Minus size={12} />{abs}</span>
}

function EventTypeBadge({ type }: { type: string | null }) {
  if (!type) return null
  const labels: Record<string, string> = {
    armed_conflict: '⚔ Armed Conflict',
    sanctions: '🚫 Sanctions',
    political_crisis: '🏛 Political Crisis',
    protest: '✊ Protest',
    diplomacy: '🕊 Diplomacy',
    humanitarian: '🆘 Humanitarian',
    economic_shock: '📉 Economic Shock',
    energy: '⚡ Energy',
    terrorism: '💥 Terrorism',
    other: '• Other',
  }
  return (
    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
      {labels[type] ?? type}
    </span>
  )
}

export function RegionPanel() {
  const { selectedRegion, setSelectedRegion } = useAppStore()

  const { data, isLoading } = useQuery({
    queryKey: ['region', selectedRegion],
    queryFn: () => globeApi.getRegion(selectedRegion!),
    enabled: !!selectedRegion,
    staleTime: 2 * 60 * 1000,
  })

  const chartData = data?.tension_history.map(h => ({
    t: format(parseISO(h.timestamp), 'MMM d HH:mm'),
    v: h.tension_index,
  })) ?? []

  const latestTension = chartData.at(-1)?.v ?? 0
  const oldestTension = chartData.at(0)?.v ?? 0
  const overallDelta = latestTension - oldestTension

  return (
    <AnimatePresence>
      {selectedRegion && (
        <motion.div
          key="region-panel"
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 30 }}
          className="absolute top-0 right-0 h-full w-[420px] bg-gray-950/95 backdrop-blur-sm border-l border-gray-800 z-20 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className={`p-5 border-b border-gray-800 ${tensionBg(latestTension)}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-gray-400 font-mono uppercase tracking-widest">{selectedRegion}</span>
                  <DeltaBadge delta={overallDelta} />
                </div>
                <div className={`text-4xl font-bold tabular-nums ${tensionColor(latestTension)}`}>
                  {latestTension.toFixed(1)}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">tension index</div>
              </div>
              <button
                onClick={() => setSelectedRegion(null)}
                className="text-gray-500 hover:text-gray-200 transition-colors p-1 rounded"
              >
                <X size={18} />
              </button>
            </div>

            {data?.recent_articles[0]?.event_type && (
              <div className="mt-3">
                <EventTypeBadge type={data.recent_articles[0].event_type} />
              </div>
            )}
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto">

            {/* Tension sparkline */}
            {chartData.length > 1 && (
              <div className="p-5 border-b border-gray-800/60">
                <div className="text-xs text-gray-500 mb-3 uppercase tracking-wider">7-day tension history</div>
                <ResponsiveContainer width="100%" height={80}>
                  <LineChart data={chartData}>
                    <Line
                      type="monotone"
                      dataKey="v"
                      stroke={latestTension > 60 ? '#E24B4A' : latestTension > 40 ? '#EF9F27' : '#1D9E75'}
                      strokeWidth={1.5}
                      dot={false}
                    />
                    <XAxis dataKey="t" hide />
                    <YAxis domain={[0, 100]} hide />
                    <Tooltip
                      contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 11 }}
                      formatter={(v: number) => [v.toFixed(1), 'Tension']}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {isLoading && (
              <div className="p-5 text-gray-500 text-sm animate-pulse">Loading regional data...</div>
            )}

            {/* Recent articles */}
            {data && data.recent_articles.length > 0 && (
              <div className="p-5 border-b border-gray-800/60">
                <div className="text-xs text-gray-500 mb-3 uppercase tracking-wider">Recent events</div>
                <div className="space-y-3">
                  {data.recent_articles.slice(0, 5).map((art, i) => (
                    <div key={i} className="group">
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm text-gray-200 hover:text-white leading-snug group-hover:underline flex items-start gap-1.5"
                      >
                        <span className="flex-1">{art.title}</span>
                        <ExternalLink size={11} className="mt-0.5 shrink-0 text-gray-600 group-hover:text-gray-400" />
                      </a>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-600">{art.source}</span>
                        {art.event_type && <EventTypeBadge type={art.event_type} />}
                        {art.geopolitical_stress != null && (
                          <span className={`text-xs tabular-nums ${art.geopolitical_stress > 0.6 ? 'text-red-400' : 'text-gray-500'}`}>
                            stress {(art.geopolitical_stress * 100).toFixed(0)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Counterfactual */}
            <div className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={12} className="text-amber-400" />
                <div className="text-xs text-gray-500 uppercase tracking-wider">What-if scenario</div>
              </div>
              <CounterfactualPanel regionCode={selectedRegion} />
            </div>

          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
