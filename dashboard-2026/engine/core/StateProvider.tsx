'use client';

/**
 * Visual State Provider
 * ADR-022: Dumb Glass - State comes from backend, no client computation
 * ADR-023: Visual State Vector - Canonical state interface
 *
 * Provides Visual State Vector context to all engine components.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import type {
  VisualStateVector,
  AnimationParameters,
  VisualProperties,
  EventTrigger,
  DEFCONLevel,
  MarketRegime,
  DEFAULT_ANIMATION_PARAMS,
  DEFAULT_VISUAL_PROPS,
} from './types';

// =============================================================================
// CONTEXT TYPES
// =============================================================================

interface VisualStateContextType {
  // Current state
  vsv: VisualStateVector | null;
  loading: boolean;
  error: string | null;

  // Derived state (for convenience)
  animation: AnimationParameters;
  visuals: VisualProperties;
  events: EventTrigger[];
  regime: MarketRegime;
  defcon: DEFCONLevel;

  // Verification
  isVerified: boolean;
  stateHash: string | null;

  // Actions
  refresh: () => Promise<void>;
  setAssetId: (assetId: string) => void;
}

// =============================================================================
// DEFAULT VALUES
// =============================================================================

const defaultAnimation: AnimationParameters = {
  flow_speed: 1.0,
  flow_direction: 0.0,
  flow_turbulence: 0.3,
  flow_thickness: 1.0,
  flow_glow_intensity: 0.5,
  pulse_amplitude: 0.5,
  pulse_frequency: 1.0,
  pulse_wavelength: 5.0,
  pulse_spark_rate: 0.0,
  cloud_density: 0.3,
  cloud_turbulence: 0.3,
  cloud_height: 1.0,
  lightning_frequency: 0.0,
  lightning_intensity: 0.0,
  particle_density: 0.5,
  particle_speed: 1.0,
  channel_glow: 0.5,
  shockwave_intensity: 0.0,
  camera_shake_amplitude: 0.0,
  camera_shake_frequency: 0.0,
  global_intensity: 0.5,
  core_pulse_rate: 1.0,
  core_glow_intensity: 0.5,
  core_rotation_speed: 0.1,
};

const defaultVisuals: VisualProperties = {
  primary_color: '#4488FF',
  accent_color: '#88BBFF',
  background_color: '#0A0E1F',
  trend_color: '#00FF88',
  momentum_color: '#00FFFF',
  volatility_color: '#8844FF',
  volume_color: '#44FF44',
  emission_intensity: 1.0,
  emission_color: '#4488FF',
  bloom_intensity: 0.5,
  bloom_threshold: 0.5,
  vignette_intensity: 0.2,
  film_grain_intensity: 0.02,
  chromatic_aberration: 0.0,
  dof_focus_distance: 10,
  dof_aperture: 0.5,
  trend_label: 'TREND (The Current)',
  momentum_label: 'MOMENTUM (The Pulse)',
  volatility_label: 'VOLATILITY (The Weather)',
  volume_label: 'VOLUME (The Force)',
  regime_label: 'REGIME: RANGE',
  defcon_label: 'DEFCON: GREEN',
};

const defaultContextValue: VisualStateContextType = {
  vsv: null,
  loading: true,
  error: null,
  animation: defaultAnimation,
  visuals: defaultVisuals,
  events: [],
  regime: 'RANGE',
  defcon: 'GREEN',
  isVerified: false,
  stateHash: null,
  refresh: async () => {},
  setAssetId: () => {},
};

// =============================================================================
// CONTEXT
// =============================================================================

const VisualStateContext = createContext<VisualStateContextType>(defaultContextValue);

// =============================================================================
// PROVIDER
// =============================================================================

interface StateProviderProps {
  children: ReactNode;
  initialAssetId?: string;
  refreshInterval?: number; // ms, 0 to disable auto-refresh
}

export function StateProvider({
  children,
  initialAssetId = 'BTC-USD',
  refreshInterval = 5000,
}: StateProviderProps) {
  const [assetId, setAssetId] = useState(initialAssetId);
  const [vsv, setVsv] = useState<VisualStateVector | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch Visual State Vector from API
  const fetchVSV = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/visual/state?asset_id=${encodeURIComponent(assetId)}`);

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || 'Unknown error');
      }

      setVsv(data.data);
    } catch (err) {
      console.error('[StateProvider] Fetch error:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch state');
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  // Initial fetch
  useEffect(() => {
    fetchVSV();
  }, [fetchVSV]);

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval <= 0) return;

    const interval = setInterval(fetchVSV, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchVSV, refreshInterval]);

  // Derived values
  const animation = vsv?.animation || defaultAnimation;
  const visuals = vsv?.visuals || defaultVisuals;
  const events = vsv?.events || [];
  const regime = vsv?.regime || 'RANGE';
  const defcon = vsv?.defcon_level || 'GREEN';
  const stateHash = vsv?.state_snapshot_hash || null;
  const isVerified = !!vsv?.signature;

  const contextValue: VisualStateContextType = {
    vsv,
    loading,
    error,
    animation,
    visuals,
    events,
    regime,
    defcon,
    isVerified,
    stateHash,
    refresh: fetchVSV,
    setAssetId,
  };

  return (
    <VisualStateContext.Provider value={contextValue}>
      {children}
    </VisualStateContext.Provider>
  );
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to access the full Visual State context
 */
export function useVisualState() {
  const context = useContext(VisualStateContext);
  if (!context) {
    throw new Error('useVisualState must be used within a StateProvider');
  }
  return context;
}

/**
 * Hook for animation parameters only
 */
export function useAnimation(): AnimationParameters {
  const { animation } = useVisualState();
  return animation;
}

/**
 * Hook for visual properties only
 */
export function useVisuals(): VisualProperties {
  const { visuals } = useVisualState();
  return visuals;
}

/**
 * Hook for active events
 */
export function useEvents(): EventTrigger[] {
  const { events } = useVisualState();
  return events;
}

/**
 * Hook for regime and DEFCON
 */
export function useSystemState(): { regime: MarketRegime; defcon: DEFCONLevel } {
  const { regime, defcon } = useVisualState();
  return { regime, defcon };
}

/**
 * Hook for verification status
 */
export function useVerification(): { isVerified: boolean; stateHash: string | null } {
  const { isVerified, stateHash } = useVisualState();
  return { isVerified, stateHash };
}

export default StateProvider;
