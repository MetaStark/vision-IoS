/**
 * Visual State Vector API
 * ADR-022/023/024: Cinematic Engine - Dumb Glass Frontend
 *
 * Authority: STIG (CTO) per EC-003
 * Classification: READ-ONLY
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface VisualStateVector {
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

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const assetId = searchParams.get('asset_id') || 'BTC-USD'

    // Get latest VSV from database using the function
    const vsv = await queryOne<VisualStateVector>(
      `SELECT * FROM vision_cinematic.get_latest_vsv($1)`,
      [assetId]
    )

    // Get DEFCON visual rules for current level
    const defconLevel = vsv?.defcon?.level || 'GREEN'
    const defconRules = await queryOne<DEFCONRules>(
      `SELECT * FROM vision_cinematic.defcon_visual_rules WHERE defcon_level = $1`,
      [defconLevel]
    )

    // Get recent cinematic events
    const events = await queryMany(
      `SELECT event_id, asset_id, event_type, event_timestamp, event_intensity,
              event_duration_ms, camera_animation, particle_burst, flash_color
       FROM vision_cinematic.cinematic_events
       WHERE asset_id = $1
         AND event_timestamp > NOW() - INTERVAL '1 hour'
         AND acknowledged = FALSE
       ORDER BY event_timestamp DESC
       LIMIT 5`,
      [assetId]
    )

    // Get available assets with VSV data
    const availableAssets = await queryMany<{ asset_id: string; latest_timestamp: string }>(
      `SELECT DISTINCT asset_id, MAX(timestamp) as latest_timestamp
       FROM vision_cinematic.visual_state_vectors
       GROUP BY asset_id
       ORDER BY asset_id`
    )

    // If no VSV exists, compute one
    if (!vsv) {
      try {
        await queryOne(
          `SELECT vision_cinematic.compute_vsv($1, NOW())`,
          [assetId]
        )
        // Fetch the newly computed VSV
        const newVsv = await queryOne<VisualStateVector>(
          `SELECT * FROM vision_cinematic.get_latest_vsv($1)`,
          [assetId]
        )

        return NextResponse.json({
          vsv: newVsv,
          defcon_rules: defconRules,
          events: events,
          available_assets: availableAssets,
          computed_fresh: true
        }, {
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
          },
        })
      } catch (computeError) {
        // Return default VSV if computation fails
        return NextResponse.json({
          vsv: getDefaultVSV(assetId),
          defcon_rules: defconRules,
          events: [],
          available_assets: availableAssets,
          fallback: true,
          error: 'VSV computation failed, using defaults'
        }, {
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
          },
        })
      }
    }

    return NextResponse.json({
      vsv: vsv,
      defcon_rules: defconRules,
      events: events,
      available_assets: availableAssets
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30',
      },
    })

  } catch (error) {
    console.error('[API] Cinematic state error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch visual state',
        message: error instanceof Error ? error.message : 'Unknown error',
        vsv: getDefaultVSV('BTC-USD'),
        fallback: true
      },
      { status: 500 }
    )
  }
}

function getDefaultVSV(assetId: string): VisualStateVector {
  return {
    vsv_id: 'default',
    asset_id: assetId,
    vsv_timestamp: new Date().toISOString(),
    trend: {
      flowSpeed: 0.5,
      flowDirection: 0.0,
      intensity: 0.5,
      colorHue: 0.6
    },
    momentum: {
      amplitude: 0.5,
      frequency: 1.0,
      phase: 0.0,
      colorSaturation: 0.7
    },
    volatility: {
      density: 0.3,
      turbulence: 0.5,
      colorLightness: 0.5
    },
    volume: {
      particleCount: 1000,
      particleSpeed: 0.5,
      glowIntensity: 0.5
    },
    camera: {
      shakeIntensity: 0.0,
      zoomLevel: 1.0
    },
    post_processing: {
      bloomIntensity: 0.3,
      vignetteIntensity: 0.2,
      filmGrain: 0.05
    },
    regime: {
      label: null,
      confidence: null
    },
    defcon: {
      level: 'GREEN',
      degradationFactor: 1.0
    },
    metadata: {
      computedAt: new Date().toISOString(),
      computedBy: 'DEFAULT',
      mappingVersion: 'v1.0.0',
      sourceHash: 'default'
    }
  }
}
