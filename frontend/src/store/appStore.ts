/**
 * Global state — Zustand store.
 * Keeps selected region, active panel, and shared UI state.
 */
import { create } from 'zustand'
import type { GlobeDataPoint, MarketSignal, NarrativeCluster } from '../services/api'

interface AppState {
  // Globe
  selectedRegion: string | null
  hoveredRegion: string | null
  setSelectedRegion: (code: string | null) => void
  setHoveredRegion: (code: string | null) => void

  // Market signals
  latestSignals: MarketSignal[]
  setLatestSignals: (signals: MarketSignal[]) => void

  // Narratives
  narratives: NarrativeCluster[]
  setNarratives: (clusters: NarrativeCluster[]) => void

  // Globe data
  globePoints: GlobeDataPoint[]
  setGlobePoints: (points: GlobeDataPoint[]) => void
  globalTensionAvg: number
  setGlobalTensionAvg: (v: number) => void

  // UI
  activePanel: 'signals' | 'narratives' | 'articles' | 'backtest' | 'counterfactual'
  setActivePanel: (panel: AppState['activePanel']) => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void

  // Counterfactual
  counterfactualTension: number
  setCounterfactualTension: (v: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  selectedRegion: null,
  hoveredRegion: null,
  setSelectedRegion: (code) => set({ selectedRegion: code }),
  setHoveredRegion: (code) => set({ hoveredRegion: code }),

  latestSignals: [],
  setLatestSignals: (signals) => set({ latestSignals: signals }),

  narratives: [],
  setNarratives: (clusters) => set({ narratives: clusters }),

  globePoints: [],
  setGlobePoints: (points) => set({ globePoints: points }),
  globalTensionAvg: 0,
  setGlobalTensionAvg: (v) => set({ globalTensionAvg: v }),

  activePanel: 'signals',
  setActivePanel: (panel) => set({ activePanel: panel }),
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  counterfactualTension: 50,
  setCounterfactualTension: (v) => set({ counterfactualTension: v }),
}))
