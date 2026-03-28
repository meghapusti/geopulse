/**
 * App layout.
 * ┌────────────────────────────────────────────────────┐
 * │  sidebar (left 340px)  │  globe (fill)             │
 * │  ┌──────────────────┐  │                           │
 * │  │ nav tabs         │  │  [3D globe]               │
 * │  │ panel content    │  │                           │
 * │  └──────────────────┘  │  [region panel slides in] │
 * └────────────────────────────────────────────────────┘
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Activity, GitBranch, BarChart2, Globe, Bell } from 'lucide-react'
import { GeoGlobe } from './components/globe/GeoGlobe'
import { RegionPanel } from './components/cards/RegionPanel'
import { SignalsDashboard } from './components/dashboard/SignalsDashboard'
import { NarrativesPanel } from './components/dashboard/NarrativesPanel'
import { BacktestPanel } from './components/dashboard/BacktestPanel'
import { useAppStore } from './store/appStore'
import TopBar from './components/layout/TopBar'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 2 * 60 * 1000 },
  },
})

type Panel = 'signals' | 'narratives' | 'backtest'

const TABS: { id: Panel; label: string; Icon: React.FC<{ size: number }> }[] = [
  { id: 'signals', label: 'Signals', Icon: Activity },
  { id: 'narratives', label: 'Narratives', Icon: GitBranch },
  { id: 'backtest', label: 'Backtest', Icon: BarChart2 },
]

function Sidebar() {
  const { activePanel, setActivePanel } = useAppStore()

  return (
    <div className="w-[340px] shrink-0 flex flex-col bg-gray-950 border-r border-gray-800 z-10 h-full">
      <div className="px-5 py-4 border-b border-gray-800 flex items-center gap-2.5">
        <Globe size={16} className="text-teal-400" />
        <span className="text-sm font-semibold text-white tracking-tight">GeoPulse</span>
        <span className="ml-auto text-xs text-gray-600 font-mono">LIVE</span>
        <div className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
      </div>

      <div className="flex border-b border-gray-800">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setActivePanel(id as any)}
            className={`flex-1 flex flex-col items-center gap-1 py-3 text-xs transition-colors ${
              activePanel === id
                ? 'text-white border-b-2 border-teal-500'
                : 'text-gray-600 hover:text-gray-400 border-b-2 border-transparent'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {activePanel === 'signals' && <SignalsDashboard />}
        {activePanel === 'narratives' && <NarrativesPanel />}
        {activePanel === 'backtest' && <BacktestPanel />}
      </div>

      <div className="px-5 py-3 border-t border-gray-800 text-xs text-gray-700 flex items-center justify-between">
        <span>Updates every 15 min</span>
        <button className="flex items-center gap-1 text-gray-600 hover:text-gray-300 transition-colors">
          <Bell size={11} />
          Alerts
        </button>
      </div>
    </div>
  )
}

function AppInner() {
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-gray-950 text-gray-100">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex-1 relative overflow-hidden">
          <GeoGlobe />
          <RegionPanel />
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  )
}
