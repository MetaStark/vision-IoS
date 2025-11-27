/**
 * Market Data Client Component (Sprint 1.3)
 * Main interactive client component
 * Manages state: asset, resolution, time range, indicators
 * MBB-grade: State management + data flow
 */

'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { CandlestickChart } from '@/components/charts/CandlestickChart'
import { LineChart } from '@/components/charts/LineChart'
import { AssetSelector, type Asset } from '@/components/controls/AssetSelector'
import { ResolutionSelector, type Resolution } from '@/components/controls/ResolutionSelector'
import {
  TimeRangeSelector,
  getDefaultTimeRange,
  getDateRange,
} from '@/components/controls/TimeRangeSelector'
import {
  IndicatorSelector,
  type IndicatorType,
  indicatorsToLineSeries,
} from '@/components/controls/IndicatorSelector'
import { MarketSummaryStats, type MarketSummaryData } from '@/components/MarketSummaryStats'
import { Skeleton } from '@/components/ui/Skeleton'
import { addIndicators } from '@/lib/utils/indicators'

interface OHLCVData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/**
 * Market Data Client Component
 * Fully interactive charting interface
 */
export function MarketDataClient() {
  // State management
  const [asset, setAsset] = useState<Asset>('BTC-USD')
  const [resolution, setResolution] = useState<Resolution>('1d')
  const [timeRange, setTimeRange] = useState<string>(() => getDefaultTimeRange('1d'))
  const [indicators, setIndicators] = useState<IndicatorType[]>([])
  const [chartData, setChartData] = useState<OHLCVData[]>([])
  const [loading, setLoading] = useState(true)

  // Fetch data when filters change
  useEffect(() => {
    async function fetchData() {
      setLoading(true)

      const { startDate, endDate } = getDateRange(timeRange)

      try {
        const response = await fetch(
          `/api/market/price-series?` +
            new URLSearchParams({
              ticker: asset,
              resolution,
              startDate: startDate.toISOString(),
              endDate: endDate.toISOString(),
            })
        )

        if (!response.ok) {
          throw new Error('Failed to fetch price data')
        }

        const data = await response.json()
        setChartData(data)
      } catch (error) {
        console.error('Error fetching market data:', error)
        setChartData([])
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [asset, resolution, timeRange])

  // Handle resolution change (update time range to default for new resolution)
  const handleResolutionChange = (newResolution: Resolution) => {
    setResolution(newResolution)
    setTimeRange(getDefaultTimeRange(newResolution))
  }

  // Calculate enriched data with indicators
  const enrichedData = chartData.length > 0 ? addIndicators(chartData, indicators) : []

  // Calculate summary stats
  const summaryData: MarketSummaryData | null =
    chartData.length > 0
      ? {
          asset,
          resolution: resolution.toUpperCase(),
          period: timeRange.toUpperCase(),
          latest: {
            date: chartData[chartData.length - 1].date,
            open: chartData[chartData.length - 1].open,
            high: chartData[chartData.length - 1].high,
            low: chartData[chartData.length - 1].low,
            close: chartData[chartData.length - 1].close,
            volume: chartData[chartData.length - 1].volume,
          },
          periodStats: {
            high: Math.max(...chartData.map((d) => d.high)),
            low: Math.min(...chartData.map((d) => d.low)),
            avgVolume:
              chartData.reduce((sum, d) => sum + d.volume, 0) / chartData.length,
            change: chartData[chartData.length - 1].close - chartData[0].close,
            changePercent:
              ((chartData[chartData.length - 1].close - chartData[0].close) /
                chartData[0].close) *
              100,
          },
          source: `fhq_data.price_series (listing_id, resolution=${resolution})`,
        }
      : null

  // Get indicator line series configs for overlay
  const overlayIndicators = indicatorsToLineSeries(indicators, 'overlay')
  const subplotIndicators = indicatorsToLineSeries(indicators, 'subplot')

  return (
    <div className="space-y-6">
      {/* Control Panel */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Asset Selector */}
            <AssetSelector selectedAsset={asset} onAssetChange={setAsset} />

            {/* Resolution Selector */}
            <ResolutionSelector
              selectedResolution={resolution}
              onResolutionChange={handleResolutionChange}
            />

            {/* Time Range Selector */}
            <TimeRangeSelector
              selectedRange={timeRange}
              onRangeChange={setTimeRange}
              resolution={resolution}
            />
          </div>

          {/* Indicator Selector - Full width */}
          <div className="mt-4 pt-4 border-t border-slate-200">
            <IndicatorSelector
              selectedIndicators={indicators}
              onIndicatorsChange={setIndicators}
            />
          </div>
        </CardContent>
      </Card>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT: Charts (2/3 width) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Primary Chart: Candlestick with Overlay Indicators */}
          <Card>
            <CardContent className="pt-6">
              {loading ? (
                <Skeleton className="h-96" />
              ) : enrichedData.length > 0 ? (
                <CandlestickChart
                  data={enrichedData}
                  resolution={resolution}
                  title={`${asset} - ${resolution.toUpperCase()}`}
                  showVolume={true}
                  source={`fhq_data.price_series`}
                  height={400}
                />
              ) : (
                <div className="flex items-center justify-center h-96">
                  <p className="text-slate-500">No data available for selected period</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Overlay Indicators Line Chart */}
          {overlayIndicators.length > 0 && enrichedData.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <LineChart
                  data={enrichedData}
                  series={[
                    {
                      dataKey: 'close',
                      name: 'Close Price',
                      color: '#1e293b',
                      strokeWidth: 2,
                    },
                    ...overlayIndicators,
                  ]}
                  resolution={resolution}
                  title="Price + Indicators Overlay"
                  source="fhq_data.price_series + calculated indicators"
                  height={300}
                />
              </CardContent>
            </Card>
          )}

          {/* Subplot Indicators (RSI, MACD) */}
          {subplotIndicators.map((indicator) => {
            if (!enrichedData.length) return null

            return (
              <Card key={indicator.dataKey}>
                <CardContent className="pt-6">
                  <LineChart
                    data={enrichedData}
                    series={[indicator]}
                    resolution={resolution}
                    title={indicator.name}
                    source="Calculated from fhq_data.price_series"
                    height={200}
                    showLegend={false}
                    yAxisFormatter={(value) => value.toFixed(2)}
                  />
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* RIGHT: Summary Stats (1/3 width) */}
        <div className="lg:col-span-1">
          {loading ? (
            <Skeleton className="h-96" />
          ) : summaryData ? (
            <MarketSummaryStats data={summaryData} />
          ) : (
            <Card>
              <CardContent className="pt-6">
                <p className="text-slate-500">No summary data available</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
