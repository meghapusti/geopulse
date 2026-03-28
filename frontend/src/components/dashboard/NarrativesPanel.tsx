/**
 * NarrativesPanel
 * Displays HDBSCAN-detected macro narrative clusters.
 * Shows emerging clusters with drift indicators.
 */
import { useQuery } from '@tanstack/react-query'
import { Flame, TrendingUp, TrendingDown } from 'lucide-react'
import { narrativesApi, type NarrativeCluster } from '../../services/api'

function StressBar({ value }: { value: number | null }) {
  if (value == null) return null
  const pct = Math.round(value * 100)
  const color = pct > 70 ? '#E24B4A' : pct > 45 ? '#EF9F27' : '#1D9E75'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs tabular-nums text-gray-500">{pct}</span>
    </div>
  )
}

function DriftBadge({ delta }: { delta: number | null }) {
  if (delta == null || Math.abs(delta) < 0.02) return null
  const rising = delta > 0
  return (
    <span className={`flex items-center gap-0.5 text-xs ${rising ? 'text-red-400' : 'text-teal-400'}`}>
      {rising ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {rising ? '+' : ''}{(delta * 100).toFixed(0)}
    </span>
  )
}

function ClusterCard({ cluster }: { cluster: NarrativeCluster }) {
  return (
    <div className={`rounded-lg border p-4 space-y-3 ${cluster.is_emerging ? 'border-amber-700/50 bg-amber-950/20' : 'border-gray-700/50 bg-gray-900/20'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-1.5 mb-1">
            {cluster.is_emerging && <Flame size={11} className="text-amber-400" />}
            <span className="text-sm text-gray-100 font-medium leading-snug">{cluster.label}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600">{cluster.article_count} articles</span>
            <DriftBadge delta={cluster.stress_delta_7d} />
          </div>
        </div>
      </div>

      {/* Stress bar */}
      <StressBar value={cluster.avg_stress} />

      {/* Countries */}
      {cluster.countries && cluster.countries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {cluster.countries.slice(0, 6).map(c => (
            <span key={c} className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">
              {c}
            </span>
          ))}
          {cluster.countries.length > 6 && (
            <span className="text-xs text-gray-600">+{cluster.countries.length - 6}</span>
          )}
        </div>
      )}

      {/* Keywords */}
      {cluster.keywords && cluster.keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {cluster.keywords.slice(0, 5).map(k => (
            <span key={k} className="text-xs text-gray-600 italic">{k}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export function NarrativesPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['narratives'],
    queryFn: () => narrativesApi.getAll(),
    refetchInterval: 10 * 60 * 1000,
  })

  const emerging = data?.filter(c => c.is_emerging) ?? []
  const rest = data?.filter(c => !c.is_emerging) ?? []

  return (
    <div className="p-5 space-y-5">

      {isLoading && (
        <div className="text-gray-600 text-sm animate-pulse">Detecting narratives...</div>
      )}

      {emerging.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-3">
            <Flame size={12} className="text-amber-400" />
            <div className="text-xs text-amber-500 uppercase tracking-wider">Emerging</div>
          </div>
          <div className="space-y-3">
            {emerging.map(c => <ClusterCard key={c.id} cluster={c} />)}
          </div>
        </div>
      )}

      {rest.length > 0 && (
        <div>
          <div className="text-xs text-gray-600 uppercase tracking-wider mb-3">Active narratives</div>
          <div className="space-y-3">
            {rest.slice(0, 8).map(c => <ClusterCard key={c.id} cluster={c} />)}
          </div>
        </div>
      )}

      {!isLoading && !data?.length && (
        <div className="text-gray-600 text-sm text-center py-8">
          Clustering runs after sufficient articles are ingested.
        </div>
      )}
    </div>
  )
}
