/**
 * Visual State Vector API Route
 * ADR-022: Dumb Glass - All state comes pre-computed and signed from backend
 * ADR-023: Visual State Vector Specification
 *
 * GET /api/visual/state?asset_id=BTC-USD
 *
 * Returns the current Visual State Vector for an asset, including:
 * - Pre-computed animation parameters
 * - Visual properties (colors, effects)
 * - Active events
 * - Verification data (hash, signature)
 */

import { NextRequest, NextResponse } from 'next/server';
import { createHash } from 'crypto';
import type {
  VisualStateVector,
  AnimationParameters,
  VisualProperties,
  EventTrigger,
  MarketRegime,
  VolatilityRegime,
  DEFCONLevel,
} from '@/engine/core/types';
import {
  generateFullAnimationParams,
  mapRegimeToColors,
  mapPostProcessing,
  MAPPING_VERSION,
} from '@/engine/core/mapping';

export const dynamic = 'force-dynamic';

// =============================================================================
// MOCK DATA GENERATOR (Replace with actual DB queries in production)
// =============================================================================

function generateMockIndicatorData() {
  // Simulate indicator values with some randomness
  const now = Date.now();
  const seed = Math.sin(now / 10000);

  return {
    // Trend indicators
    ema_cross: 0.3 + seed * 0.4,         // -1 to +1
    macd_histogram: 0.2 + seed * 0.3,    // normalized
    adx_strength: 0.4 + Math.abs(seed) * 0.3, // 0-1
    trend_stability: 0.6 + seed * 0.2,   // 0-1

    // Momentum indicators
    rsi: 50 + seed * 20,                 // 0-100
    stochastic_k: 50 + seed * 25,        // 0-100
    roc: seed * 0.5,                     // normalized rate of change
    momentum_strength: 0.5 + seed * 0.3, // 0-1

    // Volatility indicators
    atr_percentile: 0.4 + Math.abs(seed) * 0.3, // 0-1
    bb_width_percentile: 0.35 + Math.abs(seed) * 0.35, // 0-1
    volatility_regime: (seed > 0.3 ? 'HIGH' : seed > 0 ? 'NORMAL' : 'LOW') as VolatilityRegime,
    volatility_intensity: 0.4 + Math.abs(seed) * 0.4, // 0-1

    // Volume indicators
    volume_ratio: 1.0 + seed * 0.5,      // relative to average
    obv_momentum: seed * 0.6,            // -1 to +1
    vwap_deviation: seed * 0.1,          // normalized
    volume_strength: 0.5 + Math.abs(seed) * 0.3, // 0-1

    // Regime
    regime: (seed > 0.2 ? 'BULL' : seed > -0.2 ? 'RANGE' : 'BEAR') as MarketRegime,
    regime_confidence: 0.6 + Math.abs(seed) * 0.3, // 0-1

    // DEFCON (normally from system_state table)
    defcon_level: 'GREEN' as DEFCONLevel,
  };
}

function generateStateHash(data: Record<string, unknown>): string {
  const canonical = JSON.stringify(data, Object.keys(data).sort());
  return createHash('sha256').update(canonical).digest('hex');
}

function generateSignature(hash: string, signerId: string): string {
  // In production, use Ed25519 signing
  // For now, return a placeholder signature
  return `ed25519:${signerId}:${hash.substring(0, 16)}:STUB_SIGNATURE`;
}

// =============================================================================
// VISUAL PROPERTIES GENERATOR
// =============================================================================

function generateVisualProperties(
  regime: MarketRegime,
  confidence: number,
  defcon: DEFCONLevel,
  volatility: number
): VisualProperties {
  const colors = mapRegimeToColors(regime, confidence);
  const postProcess = mapPostProcessing(regime, defcon, volatility);

  return {
    primary_color: colors.primary_color,
    accent_color: colors.accent_color,
    background_color: colors.background_color,
    trend_color: '#00FF88',
    momentum_color: '#00FFFF',
    volatility_color: '#8844FF',
    volume_color: '#44FF44',
    emission_intensity: 1.0,
    emission_color: colors.emission_color,
    bloom_intensity: postProcess.bloom_intensity,
    bloom_threshold: postProcess.bloom_threshold,
    vignette_intensity: postProcess.vignette_intensity,
    film_grain_intensity: postProcess.film_grain_intensity,
    chromatic_aberration: postProcess.chromatic_aberration,
    dof_focus_distance: 10,
    dof_aperture: 0.5,
    trend_label: 'TREND (The Current) // EMA, MACD, ADX',
    momentum_label: 'MOMENTUM (The Pulse) // RSI, STOCH, ROC',
    volatility_label: 'VOLATILITY (The Weather) // ATR, BB',
    volume_label: 'VOLUME (The Force) // OBV, VWAP',
    regime_label: `REGIME: ${regime}`,
    defcon_label: `DEFCON: ${defcon}`,
  };
}

// =============================================================================
// EVENT DETECTION
// =============================================================================

function detectEvents(
  currentData: ReturnType<typeof generateMockIndicatorData>,
  previousRegime?: MarketRegime
): EventTrigger[] {
  const events: EventTrigger[] = [];
  const now = new Date().toISOString();

  // Regime shift detection
  if (previousRegime && previousRegime !== currentData.regime) {
    events.push({
      event_type: 'REGIME_SHIFT',
      event_id: `evt-${Date.now()}-regime`,
      triggered_at: now,
      severity: 'HIGH',
      duration_ms: 10000,
      parameters: {
        from_state: previousRegime,
        to_state: currentData.regime,
        magnitude: currentData.regime_confidence,
        camera_preset: 'REGIME_SHIFT_ZOOM',
        overlay_text: 'REGIME SHIFT DETECTED',
        overlay_subtext: `${previousRegime} → ${currentData.regime}`,
      },
    });
  }

  // Volatility storm detection
  if (currentData.volatility_regime === 'EXTREME' || currentData.volatility_intensity > 0.85) {
    events.push({
      event_type: 'VOLATILITY_STORM',
      event_id: `evt-${Date.now()}-volstorm`,
      triggered_at: now,
      severity: 'CRITICAL',
      duration_ms: 8000,
      parameters: {
        magnitude: currentData.volatility_intensity,
        camera_preset: 'VOLATILITY_SHAKE',
        overlay_text: 'VOLATILITY STORM',
        overlay_subtext: 'PROCEED WITH CAUTION',
      },
    });
  }

  // Volume surge detection
  if (currentData.volume_ratio > 2.5) {
    events.push({
      event_type: 'VOLUME_SURGE',
      event_id: `evt-${Date.now()}-volsurge`,
      triggered_at: now,
      severity: 'MEDIUM',
      duration_ms: 5000,
      parameters: {
        magnitude: Math.min(currentData.volume_ratio / 5.0, 1.0),
        camera_preset: 'VOLUME_PULSE',
      },
    });
  }

  return events;
}

// =============================================================================
// API HANDLER
// =============================================================================

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const assetId = searchParams.get('asset_id') || 'BTC-USD';

    // In production, fetch from database:
    // const vsv = await cinematic.getCurrentVSV(assetId);
    // const defconRules = await cinematic.getDEFCONRules(defconLevel);

    // Generate mock data (replace with DB queries)
    const indicatorData = generateMockIndicatorData();

    // Generate animation parameters using deterministic mapping
    const animation = generateFullAnimationParams({
      ...indicatorData,
    });

    // Generate visual properties
    const visuals = generateVisualProperties(
      indicatorData.regime,
      indicatorData.regime_confidence,
      indicatorData.defcon_level,
      indicatorData.volatility_intensity
    );

    // Detect events
    const events = detectEvents(indicatorData);

    // Build the Visual State Vector
    const vsvData: Omit<VisualStateVector, 'state_snapshot_hash' | 'signature'> = {
      vsv_id: `vsv-${Date.now()}`,
      asset_id: assetId,
      timestamp: new Date().toISOString(),

      // Source references (would be actual IDs in production)
      ios_002_snapshot_id: `ios002-${Date.now()}`,
      ios_003_snapshot_id: `ios003-${Date.now()}`,

      // Trend
      trend_level: indicatorData.adx_strength,
      trend_direction: indicatorData.ema_cross,
      trend_stability: indicatorData.trend_stability,

      // Momentum
      momentum_strength: indicatorData.momentum_strength,
      momentum_change_rate: Math.abs(indicatorData.roc),
      momentum_divergence: indicatorData.roc,

      // Volatility
      volatility_intensity: indicatorData.volatility_intensity,
      volatility_regime: indicatorData.volatility_regime,
      volatility_trend: indicatorData.atr_percentile - 0.5, // Normalized to -0.5 to +0.5

      // Volume
      volume_strength: indicatorData.volume_strength,
      volume_anomaly: Math.max(0, indicatorData.volume_ratio - 1),
      volume_momentum: indicatorData.obv_momentum,

      // Regime
      regime: indicatorData.regime,
      regime_confidence: indicatorData.regime_confidence,
      regime_duration_bars: Math.floor(Math.random() * 100) + 1, // Mock

      // DEFCON
      defcon_level: indicatorData.defcon_level,
      defcon_degradation_mask: [],

      // Pre-computed parameters
      animation,
      visuals,
      events,

      // Mapping version
      mapping_version: MAPPING_VERSION,
      signer_id: 'FINN',
    };

    // Generate hash and signature
    const state_snapshot_hash = generateStateHash(vsvData);
    const signature = generateSignature(state_snapshot_hash, 'FINN');

    const vsv: VisualStateVector = {
      ...vsvData,
      state_snapshot_hash,
      signature,
    };

    return NextResponse.json({
      success: true,
      data: vsv,
      meta: {
        generated_at: new Date().toISOString(),
        mapping_version: MAPPING_VERSION,
        defcon_level: indicatorData.defcon_level,
        event_count: events.length,
      },
    });
  } catch (error) {
    console.error('[Visual API] State error:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to generate Visual State Vector',
        message: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
