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
import { useEffect, useRef } from 'react'
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

// tension 0–100 → point radius
function tensionToRadius(tension: number): number {
  return 0.3 + (tension / 100) * 1.2
}

// tension 0–100 → altitude
function tensionToAltitude(tension: number): number {
  return 0.01 + (tension / 100) * 0.2
}

export function GeoGlobe() {
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<any>(null)

  const { setSelectedRegion, setHoveredRegion, setGlobePoints, setGlobalTensionAvg } = useAppStore()

  const { data, isLoading } = useQuery({
    queryKey: ['globe'],
    queryFn: globeApi.getData,
    refetchInterval: 5 * 60 * 1000,
    staleTime: 4 * 60 * 1000,
  })

  // Initialise globe once on mount
  useEffect(() => {
    if (!containerRef.current) return

    import('globe.gl').then(({ default: Globe }) => {
      if (!containerRef.current) return
      const globe = new (Globe as any)()(containerRef.current)

      globe
        .globeImageUrl('//unpkg.com/three-globe/example/img/earth-dark.jpg')
        .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
        .showAtmosphere(false)
        // Native WebGL points — much faster than htmlElementsData
        .pointsData([])
        .pointLat((d: any) => d.lat)
        .pointLng((d: any) => d.lon)
        .pointColor((d: any) => tensionToColor(d.tension_index))
        .pointAltitude((d: any) => tensionToAltitude(d.tension_index))
        .pointRadius((d: any) => tensionToRadius(d.tension_index))
        .pointsMerge(false)
        .onPointClick((d: any) => setSelectedRegion(d.region_code))
        .onPointHover((d: any) => setHoveredRegion(d ? d.region_code : null))
        // Rings only for high-tension regions
        .ringsData([])
        .ringColor((d: any) => tensionToColor(d.tension_index))
        .ringLat((d: any) => d.lat)
        .ringLng((d: any) => d.lon)
        .ringMaxRadius(2)
        .ringPropagationSpeed(1)
        .ringRepeatPeriod(2000)

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
      observer.observe(containerRef.current!)

      return () => observer.disconnect()
    })
  }, [setSelectedRegion, setHoveredRegion])

  // Update globe data when API data changes
  useEffect(() => {
    if (!globeRef.current || !data) return

    setGlobePoints(data.points)
    setGlobalTensionAvg(data.global_tension_avg)

    // Update native WebGL points
    globeRef.current.pointsData(data.points)

    // Rings only for high-tension regions
    const highTensionPoints = data.points.filter((p: GlobeDataPoint) => p.tension_index > 60)
    globeRef.current.ringsData(highTensionPoints)

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