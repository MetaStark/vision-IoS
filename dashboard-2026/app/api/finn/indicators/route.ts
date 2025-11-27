/**
 * FINN API Route: Indicators Matrix
 * Returns all 18 technical indicators with metadata and current values
 *
 * Authority: ADR-042 (FINN Intelligence), Phase H (Integrity)
 * Data Source: fhq_meta.indicator_definitions + fhq_indicators.*
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface IndicatorMatrixItem {
  indicator_id: string
  name_display: string
  name_subtitle: string | null
  category: string
  ace_family: string | null

  // Current value
  current_value: number | null
  status: 'OVERSOLD' | 'OVERBOUGHT' | 'BULLISH' | 'BEARISH' | 'NEUTRAL' | null

  // Trend (5-day)
  trend_direction: 'UP' | 'DOWN' | 'FLAT' | null
  trend_change_pct: number | null

  // Thresholds
  bullish_threshold: number | null
  bearish_threshold: number | null

  // ACE integration
  meta_allocation_relevance: 'HIGH' | 'MEDIUM' | 'LOW' | null

  // UI metadata
  display_priority: number
  category_color: string
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const listingId = searchParams.get('listing_id') || 'LST_BTC_XCRYPTO'
    const signalDate = searchParams.get('signal_date') // Optional, defaults to latest

    // Query all 18 indicators with current values
    const query = `
      WITH latest_date AS (
        SELECT MAX(signal_date) AS max_date
        FROM fhq_indicators.price_data
        WHERE listing_id = $1
          ${signalDate ? 'AND signal_date <= $2' : ''}
      ),
      current_indicators AS (
        -- RSI
        SELECT
          'RSI_14' AS indicator_id,
          rsi_14 AS current_value,
          signal_date
        FROM fhq_indicators.momentum
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- MACD
        SELECT 'MACD_LINE', macd_line, signal_date
        FROM fhq_indicators.momentum
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'MACD_SIGNAL', macd_signal, signal_date
        FROM fhq_indicators.momentum
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- Stochastic
        SELECT 'STOCH_K', stoch_k, signal_date
        FROM fhq_indicators.momentum
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'STOCH_D', stoch_d, signal_date
        FROM fhq_indicators.momentum
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- EMAs
        SELECT 'EMA_12', ema_12, signal_date
        FROM fhq_indicators.trend
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'EMA_26', ema_26, signal_date
        FROM fhq_indicators.trend
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- SMAs
        SELECT 'SMA_50', sma_50, signal_date
        FROM fhq_indicators.trend
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'SMA_200', sma_200, signal_date
        FROM fhq_indicators.trend
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- Bollinger Bands
        SELECT 'BB_UPPER', bb_upper, signal_date
        FROM fhq_indicators.volatility
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'BB_MIDDLE', bb_middle, signal_date
        FROM fhq_indicators.volatility
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'BB_LOWER', bb_lower, signal_date
        FROM fhq_indicators.volatility
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- ATR
        SELECT 'ATR_14', atr_14, signal_date
        FROM fhq_indicators.volatility
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- OBV
        SELECT 'OBV', obv, signal_date
        FROM fhq_indicators.volume
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        -- Price data
        SELECT 'PRICE_CLOSE', price_close, signal_date
        FROM fhq_indicators.price_data
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'PRICE_HIGH', price_high, signal_date
        FROM fhq_indicators.price_data
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'PRICE_LOW', price_low, signal_date
        FROM fhq_indicators.price_data
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)

        UNION ALL

        SELECT 'VOLUME', volume, signal_date
        FROM fhq_indicators.price_data
        WHERE listing_id = $1 AND signal_date = (SELECT max_date FROM latest_date)
      ),
      historical_indicators AS (
        -- Get 5-day history for trend calculation (simplified - same structure)
        SELECT
          indicator_id,
          AVG(current_value) AS avg_5day
        FROM (
          -- RSI historical
          SELECT 'RSI_14' AS indicator_id, rsi_14 AS current_value
          FROM fhq_indicators.momentum
          WHERE listing_id = $1
            AND signal_date BETWEEN (SELECT max_date FROM latest_date) - INTERVAL '5 days'
                                 AND (SELECT max_date FROM latest_date) - INTERVAL '1 day'
          -- ... (would repeat for all indicators, simplified for now)
        ) hist
        GROUP BY indicator_id
      )
      SELECT
        def.indicator_id,
        def.name_display,
        def.name_subtitle,
        def.category,
        def.ace_family,
        def.bullish_threshold,
        def.bearish_threshold,
        def.meta_allocation_relevance,
        def.display_priority,

        curr.current_value,

        -- Status determination
        CASE
          WHEN def.indicator_id = 'RSI_14' THEN
            CASE
              WHEN curr.current_value < 30 THEN 'OVERSOLD'
              WHEN curr.current_value > 70 THEN 'OVERBOUGHT'
              ELSE 'NEUTRAL'
            END
          WHEN def.indicator_id IN ('MACD_LINE', 'MACD_SIGNAL') THEN
            CASE
              WHEN curr.current_value > 0 THEN 'BULLISH'
              WHEN curr.current_value < 0 THEN 'BEARISH'
              ELSE 'NEUTRAL'
            END
          WHEN def.indicator_id IN ('STOCH_K', 'STOCH_D') THEN
            CASE
              WHEN curr.current_value < 20 THEN 'OVERSOLD'
              WHEN curr.current_value > 80 THEN 'OVERBOUGHT'
              ELSE 'NEUTRAL'
            END
          ELSE 'NEUTRAL'
        END AS status,

        -- Trend (simplified - compare current to 5-day avg)
        CASE
          WHEN curr.current_value > hist.avg_5day * 1.02 THEN 'UP'
          WHEN curr.current_value < hist.avg_5day * 0.98 THEN 'DOWN'
          ELSE 'FLAT'
        END AS trend_direction,

        ROUND(
          ((curr.current_value - hist.avg_5day) / NULLIF(hist.avg_5day, 0) * 100)::NUMERIC,
          2
        ) AS trend_change_pct,

        -- Category color
        CASE def.category
          WHEN 'MOMENTUM' THEN 'blue'
          WHEN 'TREND' THEN 'green'
          WHEN 'VOLATILITY' THEN 'yellow'
          WHEN 'VOLUME' THEN 'purple'
          WHEN 'PRICE' THEN 'gray'
          ELSE 'gray'
        END AS category_color

      FROM fhq_meta.indicator_definitions def
      LEFT JOIN current_indicators curr ON def.indicator_id = curr.indicator_id
      LEFT JOIN historical_indicators hist ON def.indicator_id = hist.indicator_id
      WHERE def.is_active = TRUE
      ORDER BY def.display_priority, def.category, def.indicator_id
    `

    const params = signalDate ? [listingId, signalDate] : [listingId]
    const results = await queryMany<IndicatorMatrixItem>(query, params)

    if (results.length === 0) {
      return NextResponse.json(
        {
          error: 'No indicators found',
          listing_id: listingId
        },
        { status: 404 }
      )
    }

    // Group by category
    const byCategory = results.reduce((acc, ind) => {
      const cat = ind.category
      if (!acc[cat]) acc[cat] = []
      acc[cat].push(ind)
      return acc
    }, {} as Record<string, IndicatorMatrixItem[]>)

    return NextResponse.json({
      indicators: results,
      by_category: byCategory,
      total_count: results.length,
      categories: Object.keys(byCategory)
    })

  } catch (error) {
    console.error('[FINN API] Indicators error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch indicators',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
