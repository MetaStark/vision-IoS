'use client'

/**
 * Cinematic Viewer Component
 * ADR-022/023/024: Visual State Vector Display
 *
 * Displays pre-computed animation parameters from the database.
 * This is a "dumb glass" component - all computation happens server-side.
 * Now with full WebGL 3D visualization!
 */

import { useState, useEffect, useCallback } from 'react'
import dynamic from 'next/dynamic'
import {
  RefreshCw,
  AlertCircle,
  Activity,
  Waves,
  Cloud,
  Zap,
  Camera,
  Sparkles,
  Shield,
  Hash,
  TrendingUp,
  TrendingDown,
  Maximize2,
  Minimize2,
  Eye,
  EyeOff,
} from 'lucide-react'

// Dynamic import for WebGL canvas (client-side only)
const CinematicCanvas = dynamic(
  () => import('./CinematicCanvas').then((mod) => mod.CinematicCanvas),
  {
    ssr: false,
    loading: () => (
      <div
        className="w-full h-full min-h-[400px] flex items-center justify-center"
        style={{ background: 'linear-gradient(180deg, #0a0a12 0%, #141428 50%, #0a0a12 100%)' }}
      >
        <div className="text-center">
          <RefreshCw className="w-12 h-12 mx-auto animate-spin" style={{ color: '#666' }} />
          <p className="mt-4 text-sm" style={{ color: '#666' }}>
            Initializing WebGL Engine...
          </p>
        </div>
      </div>
    ),
  }
)

interface VSVData {
  vsv_id: string
  asset_id: string
  vsv_timestamp: string
  trend: {
    flowSpeed: number
    flowDirection: number
    intensity: number
    colorHue: number
  }
  momentum: {
    amplitude: number
    frequency: number
    phase: number
    colorSaturation: number
  }
  volatility: {
    density: number
    turbulence: number
    colorLightness: number
  }
  volume: {
    particleCount: number
    particleSpeed: number
    glowIntensity: number
  }
  camera: {
    shakeIntensity: number
    zoomLevel: number
  }
  post_processing: {
    bloomIntensity: number
    vignetteIntensity: number
    filmGrain: number
  }
  regime: {
    label: string | null
    confidence: number | null
  }
  defcon: {
    level: string
    degradationFactor: number
  }
  metadata: {
    computedAt: string
    computedBy: string
    mappingVersion: string
    sourceHash: string
  }
}

interface DEFCONRules {
  defcon_level: string
  max_particle_count: number
  max_bloom_intensity: number
  allow_camera_shake: boolean
  allow_post_processing: boolean
  color_desaturation: number
  force_static_render: boolean
  emergency_message: string | null
}

interface CinematicEvent {
  event_id: string
  asset_id: string
  event_type: string
  event_timestamp: string
  event_intensity: number
  event_duration_ms: number
  camera_animation: string | null
  particle_burst: boolean
  flash_color: string | null
}

interface CinematicState {
  vsv: VSVData | null
  defcon_rules: DEFCONRules | null
  events: CinematicEvent[]
  available_assets: { asset_id: string; latest_timestamp: string }[]
  fallback?: boolean
  error?: string
}

const DEFCON_COLORS: Record<string, string> = {
  GREEN: 'hsl(142 76% 36%)',
  YELLOW: 'hsl(48 96% 53%)',
  ORANGE: 'hsl(25 95% 53%)',
  RED: 'hsl(0 84% 60%)',
  BLACK: 'hsl(0 0% 20%)',
}

export function CinematicViewer() {
  const [state, setState] = useState<CinematicState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAsset, setSelectedAsset] = useState('BTC-USD')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showParameters, setShowParameters] = useState(true)

  const fetchState = useCallback(async () => {
    try {
      const response = await fetch(`/api/cinematic/state?asset_id=${selectedAsset}`)
      if (!response.ok) throw new Error('Failed to fetch cinematic state')
      const data = await response.json()
      setState(data)
      setError(data.error || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [selectedAsset])

  useEffect(() => {
    fetchState()
    if (autoRefresh) {
      const interval = setInterval(fetchState, 10000)
      return () => clearInterval(interval)
    }
  }, [fetchState, autoRefresh])

  if (loading && !state) {
    return <LoadingState />
  }

  const vsv = state?.vsv
  const events = state?.events || []

  return (
    <div className={`space-y-6 ${isFullscreen ? 'fixed inset-0 z-50 bg-black p-4' : ''}`}>
      {/* Controls Bar */}
      <div
        className="p-4 rounded-lg flex items-center justify-between flex-wrap gap-4"
        style={{ backgroundColor: 'hsl(var(--card))' }}
      >
        <div className="flex items-center gap-4 flex-wrap">
          {/* Asset Selector */}
          <select
            value={selectedAsset}
            onChange={(e) => setSelectedAsset(e.target.value)}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--foreground))',
              border: '1px solid hsl(var(--border))',
            }}
          >
            <option value="BTC-USD">BTC-USD</option>
            <option value="ETH-USD">ETH-USD</option>
            <option value="SPY">SPY</option>
            <option value="GLD">GLD</option>
            {state?.available_assets?.map((asset) => (
              !['BTC-USD', 'ETH-USD', 'SPY', 'GLD'].includes(asset.asset_id) && (
                <option key={asset.asset_id} value={asset.asset_id}>
                  {asset.asset_id}
                </option>
              )
            ))}
          </select>

          {/* Refresh Button */}
          <button
            onClick={fetchState}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
            style={{
              backgroundColor: 'hsl(var(--primary))',
              color: 'white',
              opacity: loading ? 0.5 : 1,
            }}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {/* Auto-refresh Toggle */}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            <span style={{ color: 'hsl(var(--muted-foreground))' }}>Auto-refresh (10s)</span>
          </label>

          {/* Show Parameters Toggle */}
          <button
            onClick={() => setShowParameters(!showParameters)}
            className="px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--foreground))',
            }}
          >
            {showParameters ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {showParameters ? 'Hide' : 'Show'} Params
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--foreground))',
            }}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            {isFullscreen ? 'Exit' : 'Fullscreen'}
          </button>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-4">
          {vsv && (
            <div
              className="px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-2"
              style={{
                backgroundColor: `${DEFCON_COLORS[vsv.defcon.level]}20`,
                color: DEFCON_COLORS[vsv.defcon.level],
                border: `1px solid ${DEFCON_COLORS[vsv.defcon.level]}40`,
              }}
            >
              <Shield className="w-3 h-3" />
              DEFCON {vsv.defcon.level}
            </div>
          )}

          {vsv?.regime?.label && (
            <div
              className="px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2"
              style={{
                backgroundColor: 'hsl(var(--secondary))',
                color: 'hsl(var(--foreground))',
              }}
            >
              {vsv.trend.flowDirection > 0 ? (
                <TrendingUp className="w-3 h-3 text-green-500" />
              ) : (
                <TrendingDown className="w-3 h-3 text-red-500" />
              )}
              {vsv.regime.label}
            </div>
          )}

          {state?.fallback && (
            <div
              className="px-3 py-1.5 rounded-full text-xs font-medium flex items-center gap-2"
              style={{
                backgroundColor: 'hsl(48 96% 53% / 0.2)',
                color: 'hsl(48 96% 40%)',
              }}
            >
              <AlertCircle className="w-3 h-3" />
              Fallback Mode
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div
          className="p-4 rounded-lg flex items-center gap-3"
          style={{
            backgroundColor: 'hsl(0 84% 60% / 0.1)',
            border: '1px solid hsl(0 84% 60% / 0.3)',
          }}
        >
          <AlertCircle className="w-5 h-5" style={{ color: 'hsl(0 84% 60%)' }} />
          <span style={{ color: 'hsl(0 84% 60%)' }}>{error}</span>
        </div>
      )}

      {/* WebGL 3D Canvas */}
      <div
        className="rounded-lg overflow-hidden relative"
        style={{
          aspectRatio: isFullscreen ? undefined : '16/9',
          minHeight: isFullscreen ? 'calc(100vh - 200px)' : '500px',
        }}
      >
        {vsv && <CinematicCanvas vsv={vsv} />}

        {/* Overlay: Asset Name */}
        <div className="absolute top-4 left-4 pointer-events-none">
          <h2
            className="text-4xl font-bold drop-shadow-lg"
            style={{ color: 'rgba(255,255,255,0.9)', textShadow: '0 2px 10px rgba(0,0,0,0.5)' }}
          >
            {selectedAsset}
          </h2>
          {vsv?.regime?.label && (
            <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.7)' }}>
              Regime: {vsv.regime.label} ({((vsv.regime.confidence || 0) * 100).toFixed(0)}%)
            </p>
          )}
        </div>

        {/* Overlay: Bottom Info */}
        <div className="absolute bottom-4 left-4 right-4 flex justify-between pointer-events-none">
          <div
            className="px-3 py-2 rounded text-xs backdrop-blur-sm"
            style={{
              backgroundColor: 'rgba(0,0,0,0.5)',
              color: 'rgba(255,255,255,0.8)',
            }}
          >
            <Hash className="w-3 h-3 inline mr-1" />
            {vsv?.metadata?.sourceHash?.slice(0, 12) || 'N/A'}
          </div>
          <div
            className="px-3 py-2 rounded text-xs backdrop-blur-sm"
            style={{
              backgroundColor: 'rgba(0,0,0,0.5)',
              color: 'rgba(255,255,255,0.8)',
            }}
          >
            Mapping: {vsv?.metadata?.mappingVersion || 'N/A'}
          </div>
        </div>
      </div>

      {/* VSV Parameter Cards - Collapsible */}
      {vsv && showParameters && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <ParameterCard
              title="The Current"
              subtitle="Trend"
              icon={<Waves className="w-5 h-5" />}
              color="hsl(217 91% 60%)"
              parameters={[
                { label: 'Flow Speed', value: vsv.trend.flowSpeed.toFixed(2) },
                { label: 'Direction', value: vsv.trend.flowDirection.toFixed(2) },
                { label: 'Intensity', value: vsv.trend.intensity.toFixed(2) },
                { label: 'Color Hue', value: `${(vsv.trend.colorHue * 360).toFixed(0)}°` },
              ]}
            />

            <ParameterCard
              title="The Pulse"
              subtitle="Momentum"
              icon={<Activity className="w-5 h-5" />}
              color="hsl(142 76% 45%)"
              parameters={[
                { label: 'Amplitude', value: vsv.momentum.amplitude.toFixed(2) },
                { label: 'Frequency', value: `${vsv.momentum.frequency.toFixed(1)} Hz` },
                { label: 'Phase', value: `${vsv.momentum.phase.toFixed(2)} rad` },
                { label: 'Saturation', value: vsv.momentum.colorSaturation.toFixed(2) },
              ]}
            />

            <ParameterCard
              title="The Weather"
              subtitle="Volatility"
              icon={<Cloud className="w-5 h-5" />}
              color="hsl(280 60% 50%)"
              parameters={[
                { label: 'Density', value: vsv.volatility.density.toFixed(2) },
                { label: 'Turbulence', value: vsv.volatility.turbulence.toFixed(2) },
                { label: 'Lightness', value: vsv.volatility.colorLightness.toFixed(2) },
              ]}
            />

            <ParameterCard
              title="The Force"
              subtitle="Volume"
              icon={<Zap className="w-5 h-5" />}
              color="hsl(48 96% 50%)"
              parameters={[
                { label: 'Particles', value: vsv.volume.particleCount.toLocaleString() },
                { label: 'Speed', value: vsv.volume.particleSpeed.toFixed(2) },
                { label: 'Glow', value: vsv.volume.glowIntensity.toFixed(2) },
              ]}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ParameterCard
              title="Camera"
              subtitle="View Controls"
              icon={<Camera className="w-5 h-5" />}
              color="hsl(200 80% 50%)"
              parameters={[
                { label: 'Shake Intensity', value: vsv.camera.shakeIntensity.toFixed(2) },
                { label: 'Zoom Level', value: `${vsv.camera.zoomLevel.toFixed(1)}x` },
              ]}
            />

            <ParameterCard
              title="Post-Processing"
              subtitle="Effects"
              icon={<Sparkles className="w-5 h-5" />}
              color="hsl(330 80% 60%)"
              parameters={[
                { label: 'Bloom', value: vsv.post_processing.bloomIntensity.toFixed(2) },
                { label: 'Vignette', value: vsv.post_processing.vignetteIntensity.toFixed(2) },
                { label: 'Film Grain', value: vsv.post_processing.filmGrain.toFixed(2) },
              ]}
            />
          </div>
        </>
      )}

      {/* Recent Events */}
      {events.length > 0 && showParameters && (
        <div
          className="p-4 rounded-lg"
          style={{ backgroundColor: 'hsl(var(--card))' }}
        >
          <h3
            className="text-sm font-semibold mb-3"
            style={{ color: 'hsl(var(--foreground))' }}
          >
            Recent Cinematic Events
          </h3>
          <div className="space-y-2">
            {events.map((event) => (
              <div
                key={event.event_id}
                className="flex items-center justify-between p-2 rounded"
                style={{ backgroundColor: 'hsl(var(--secondary))' }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{
                      backgroundColor:
                        event.event_type === 'REGIME_SHIFT'
                          ? 'hsl(280 60% 50%)'
                          : event.event_type === 'VOLATILITY_STORM'
                          ? 'hsl(0 84% 60%)'
                          : 'hsl(48 96% 50%)',
                    }}
                  />
                  <span
                    className="text-sm font-medium"
                    style={{ color: 'hsl(var(--foreground))' }}
                  >
                    {event.event_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <span
                  className="text-xs"
                  style={{ color: 'hsl(var(--muted-foreground))' }}
                >
                  Intensity: {event.event_intensity.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ParameterCard({
  title,
  subtitle,
  icon,
  color,
  parameters,
}: {
  title: string
  subtitle: string
  icon: React.ReactNode
  color: string
  parameters: { label: string; value: string }[]
}) {
  return (
    <div
      className="p-4 rounded-lg"
      style={{ backgroundColor: 'hsl(var(--card))' }}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className="p-2 rounded-lg"
          style={{ backgroundColor: `${color}20`, color: color }}
        >
          {icon}
        </div>
        <div>
          <h3
            className="text-sm font-semibold"
            style={{ color: 'hsl(var(--foreground))' }}
          >
            {title}
          </h3>
          <p
            className="text-xs"
            style={{ color: 'hsl(var(--muted-foreground))' }}
          >
            {subtitle}
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {parameters.map((param) => (
          <div key={param.label} className="flex justify-between items-center">
            <span
              className="text-xs"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            >
              {param.label}
            </span>
            <span
              className="text-sm font-mono font-medium"
              style={{ color: 'hsl(var(--foreground))' }}
            >
              {param.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="space-y-6">
      <div
        className="p-4 rounded-lg animate-pulse"
        style={{ backgroundColor: 'hsl(var(--card))' }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className="h-10 w-40 rounded"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
            <div
              className="h-10 w-32 rounded"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
          </div>
        </div>
      </div>

      <div
        className="rounded-lg overflow-hidden flex items-center justify-center"
        style={{
          background: 'linear-gradient(180deg, #0a0a12 0%, #141428 50%, #0a0a12 100%)',
          aspectRatio: '16/9',
          minHeight: '500px',
        }}
      >
        <div className="text-center">
          <RefreshCw
            className="w-12 h-12 mx-auto animate-spin"
            style={{ color: '#666' }}
          />
          <p className="mt-4 text-sm" style={{ color: '#666' }}>
            Initializing Cinematic Engine...
          </p>
        </div>
      </div>
    </div>
  )
}
