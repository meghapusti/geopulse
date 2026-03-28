import { useAppStore } from '../../store/appStore'
import { Activity, Globe, Menu } from 'lucide-react'

function tensionLabel(avg: number): { label: string; cls: string } {
  if (avg >= 65) return { label: 'CRITICAL', cls: 'tension-high' }
  if (avg >= 45) return { label: 'ELEVATED', cls: 'tension-medium' }
  return { label: 'STABLE', cls: 'tension-low' }
}

export default function TopBar() {
  const { globalTensionAvg, setSidebarOpen, sidebarOpen } = useAppStore()
  const { label, cls } = tensionLabel(globalTensionAvg)

  return (
    <header style={{
      height: 48,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      background: 'rgba(8,12,20,0.95)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      backdropFilter: 'blur(8px)',
      zIndex: 100,
      flexShrink: 0,
    }}>
      {/* Left — branding */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: 4 }}
        >
          <Menu size={16} />
        </button>
        <Globe size={16} color="#3b82f6" />
        <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>
          Geo<span style={{ color: '#3b82f6' }}>Pulse</span>
        </span>
        <span style={{
          fontSize: 10,
          color: 'var(--text-muted)',
          background: 'var(--bg-elevated)',
          padding: '1px 6px',
          borderRadius: 4,
          border: '1px solid var(--border)',
        }}>
          BETA
        </span>
      </div>

      {/* Centre — global tension indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Activity size={13} color="var(--text-secondary)" />
        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Global tension</span>
        <span style={{
          fontWeight: 700,
          fontSize: 14,
          fontVariantNumeric: 'tabular-nums',
        }}>
          {globalTensionAvg.toFixed(1)}
        </span>
        <span className={`badge ${cls === 'tension-high' ? 'badge-bearish' : cls === 'tension-medium' ? 'badge-up' : 'badge-bullish'}`}>
          {label}
        </span>
      </div>

      {/* Right — live indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 6, height: 6,
          borderRadius: '50%',
          background: '#22c55e',
          boxShadow: '0 0 6px #22c55e',
          animation: 'pulse 2s infinite',
        }} />
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>LIVE</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
          Updates every 15 min
        </span>
      </div>
    </header>
  )
}
