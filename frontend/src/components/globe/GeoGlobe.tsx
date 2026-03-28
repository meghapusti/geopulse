/**
 * GeoGlobe — 3D interactive world map.
 * Uses globe.gl polygonsData to colour countries by tension index.
 * Much more performant than HTML markers — single WebGL draw call per frame.
 */
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { globeApi, type GlobeDataPoint } from '../../services/api'
import { useAppStore } from '../../store/appStore'

// tension 0–100 → fill colour with alpha
function tensionToColor(tension: number | undefined): string {
  if (tension === undefined) return 'rgba(255,255,255,0.03)'
  if (tension < 15)  return 'rgba(29,158,117,0.25)'   // teal — calm
  if (tension < 35)  return 'rgba(29,158,117,0.45)'   // teal — low
  if (tension < 55)  return 'rgba(239,159,39,0.55)'   // amber — elevated
  if (tension < 70)  return 'rgba(216,90,48,0.70)'    // coral — high
  return 'rgba(226,75,74,0.85)'                         // red — critical
}

function tensionToSideColor(tension: number | undefined): string {
  if (tension === undefined) return 'rgba(255,255,255,0.0)'
  if (tension < 35)  return 'rgba(29,158,117,0.15)'
  if (tension < 55)  return 'rgba(239,159,39,0.3)'
  if (tension < 70)  return 'rgba(216,90,48,0.4)'
  return 'rgba(226,75,74,0.5)'
}

// GeoJSON URL with ISO-A3 country codes
const COUNTRIES_GEOJSON = '//unpkg.com/world-atlas@2/countries-110m.json'
const GEOJSON_URL = 'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson'

export function GeoGlobe() {
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<any>(null)
  const tensionMapRef = useRef<Map<string, number>>(new Map())

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

    // Load country GeoJSON
    fetch(GEOJSON_URL)
      .then(r => r.json())
      .then(geoJson => {
        if (!containerRef.current) return

        import('globe.gl').then(({ default: Globe }) => {
          if (!containerRef.current) return
          const globe = new (Globe as any)()(containerRef.current)

          globe
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-dark.jpg')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .showAtmosphere(true)
            .atmosphereColor('#1a3a5c')
            .atmosphereAltitude(0.1)
            // Country polygons coloured by tension
            .polygonsData(geoJson.features)
            .polygonAltitude((d: any) => {
              const code = d.properties?.iso_a3 || d.properties?.ISO_A3
              const tension = tensionMapRef.current.get(code)
              return tension && tension > 55 ? 0.02 : 0.005
            })
            .polygonCapColor((d: any) => {
              const code = d.properties?.iso_a3 || d.properties?.ISO_A3
              return tensionToColor(tensionMapRef.current.get(code))
            })
            .polygonSideColor((d: any) => {
              const code = d.properties?.iso_a3 || d.properties?.ISO_A3
              return tensionToSideColor(tensionMapRef.current.get(code))
            })
            .polygonStrokeColor(() => 'rgba(255,255,255,0.06)')
            .onPolygonClick((d: any) => {
              const code = d.properties?.iso_a3 || d.properties?.ISO_A3
              if (code && tensionMapRef.current.has(code)) {
                setSelectedRegion(code)
              }
            })
            .onPolygonHover((d: any) => {
              const code = d?.properties?.iso_a3 || d?.properties?.ISO_A3
              setHoveredRegion(code && tensionMapRef.current.has(code) ? code : null)
            })

          // Controls
          globe.controls().autoRotate = false
          globe.controls().enableZoom = true
          globe.controls().minDistance = 150
          globe.controls().maxDistance = 600

          globeRef.current = globe

          const observer = new ResizeObserver(() => {
            if (containerRef.current) {
              globe.width(containerRef.current.clientWidth)
              globe.height(containerRef.current.clientHeight)
            }
          })
          observer.observe(containerRef.current!)

          return () => observer.disconnect()
        })
      })
  }, [setSelectedRegion, setHoveredRegion])

  // Update colours when API data changes
  useEffect(() => {
    if (!globeRef.current || !data) return

    setGlobePoints(data.points)
    setGlobalTensionAvg(data.global_tension_avg)

    // Rebuild tension lookup map
    tensionMapRef.current = new Map(
      data.points.map((p: GlobeDataPoint) => [p.region_code, p.tension_index])
    )

    // Trigger polygon colour refresh
    globeRef.current.polygonCapColor((d: any) => {
      const code = d.properties?.iso_a3 || d.properties?.ISO_A3
      return tensionToColor(tensionMapRef.current.get(code))
    })
    globeRef.current.polygonSideColor((d: any) => {
      const code = d.properties?.iso_a3 || d.properties?.ISO_A3
      return tensionToSideColor(tensionMapRef.current.get(code))
    })
    globeRef.current.polygonAltitude((d: any) => {
      const code = d.properties?.iso_a3 || d.properties?.ISO_A3
      const tension = tensionMapRef.current.get(code)
      return tension && tension > 55 ? 0.02 : 0.005
    })

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