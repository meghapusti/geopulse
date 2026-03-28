/**
 * GeoGlobe — 3D interactive world map.
 * Uses globe.gl (Three.js under the hood) to render a rotating Earth
 * with per-country tension markers.
 *
 * Tension index → colour mapping:
 *   0–25   = teal   (calm)
 *   25–50  = yellow (elevated)
 *   50–75  = orange (high)
 *   75–100 = red    (critical)
 *
 * Click a country marker → sets selectedRegion in Zustand store
 * which triggers the RegionPanel to open.
 */
import { useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { globeApi, type GlobeDataPoint } from '../../services/api'
import { useAppStore } from '../../store/appStore'

// tension 0–100 → hex colour
function tensionToColor(tension: number): string {
  if (tension < 25) return '#1D9E75'   // teal — calm
  if (tension < 45) return '#EF9F27'   // amber — elevated
  if (tension < 65) return '#D85A30'   // coral — high
  return '#E24B4A'                      // red — critical
}

// tension 0–100 → ring radius (bigger = more prominent)
function tensionToRadius(tension: number): number {
  return 0.4 + (tension / 100) * 1.8
}

// tension 0–100 → altitude (taller spike = more prominent)
function tensionToAltitude(tension: number): number {
  return 0.01 + (tension / 100) * 0.25
}

export function GeoGlobe() {
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<any>(null)

  const { setSelectedRegion, setHoveredRegion, setGlobePoints, setGlobalTensionAvg } = useAppStore()

  const { data, isLoading } = useQuery({
    queryKey: ['globe'],
    queryFn: globeApi.getData,
    refetchInterval: 5 * 60 * 1000,  // refresh every 5 minutes
    staleTime: 4 * 60 * 1000,
  })

  // Initialise globe once on mount
  useEffect(() => {
    if (!containerRef.current) return

    // Dynamic import to avoid SSR issues and keep initial bundle small
    import('globe.gl').then(({ default: Globe }) => {
      const globe = Globe()(containerRef.current!)

      globe
        .globeImageUrl('//unpkg.com/three-globe/example/img/earth-dark.jpg')
        .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
        .showAtmosphere(true)
        .atmosphereColor('#1a3a5c')
        .atmosphereAltitude(0.15)
        // Hex bin / ring layer for tension markers
        .ringsData([])
        .ringColor(() => '#ffffff')
        .ringMaxRadius(3)
        .ringPropagationSpeed(2)
        .ringRepeatPeriod(1200)
        // Custom HTML markers per point
        .htmlElementsData([])
        .htmlElement((d: any) => {
          const el = document.createElement('div')
          el.style.cssText = `
            width: ${6 + d.tension_index * 0.14}px;
            height: ${6 + d.tension_index * 0.14}px;
            border-radius: 50%;
            background: ${tensionToColor(d.tension_index)};
            opacity: 0.85;
            cursor: pointer;
            box-shadow: 0 0 ${d.tension_index * 0.2}px ${tensionToColor(d.tension_index)};
            transition: transform 0.15s;
          `
          el.addEventListener('mouseenter', () => {
            el.style.transform = 'scale(1.6)'
            setHoveredRegion(d.region_code)
          })
          el.addEventListener('mouseleave', () => {
            el.style.transform = 'scale(1)'
            setHoveredRegion(null)
          })
          el.addEventListener('click', () => {
            setSelectedRegion(d.region_code)
          })
          return el
        })
        .htmlLat((d: any) => d.lat)
        .htmlLng((d: any) => d.lon)
        .htmlAltitude(0.01)

      // Auto-rotate slowly
      globe.controls().autoRotate = true
      globe.controls().autoRotateSpeed = 0.4
      globe.controls().enableZoom = true
      globe.controls().minDistance = 150
      globe.controls().maxDistance = 600

      globeRef.current = globe

      // Handle resize
      const observer = new ResizeObserver(() => {
        if (containerRef.current) {
          globe.width(containerRef.current.clientWidth)
          globe.height(containerRef.current.clientHeight)
        }
      })
      observer.observe(containerRef.current)

      return () => observer.disconnect()
    })
  }, [setSelectedRegion, setHoveredRegion])

  // Update globe data when API data changes
  useEffect(() => {
    if (!globeRef.current || !data) return

    setGlobePoints(data.points)
    setGlobalTensionAvg(data.global_tension_avg)

    globeRef.current.htmlElementsData(data.points)

    // Add pulse rings for high-tension regions
    const highTensionPoints = data.points.filter(p => p.tension_index > 60)
    globeRef.current.ringsData(highTensionPoints)
    globeRef.current.ringColor((d: GlobeDataPoint) => tensionToColor(d.tension_index))
    globeRef.current.ringLat((d: GlobeDataPoint) => d.lat)
    globeRef.current.ringLng((d: GlobeDataPoint) => d.lon)
    globeRef.current.ringMaxRadius((d: GlobeDataPoint) => tensionToRadius(d.tension_index))
    globeRef.current.ringAltitude((d: GlobeDataPoint) => tensionToAltitude(d.tension_index))

  }, [data, setGlobePoints, setGlobalTensionAvg])

  return (
    <div className="relative w-full h-full bg-gray-950">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
          <div className="text-gray-400 text-sm animate-pulse">Loading geopolitical data...</div>
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  )
}
