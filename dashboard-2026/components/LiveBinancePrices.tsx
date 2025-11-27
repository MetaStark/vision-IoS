'use client'

/**
 * Live Binance Market Prices - Client-side WebSocket Component
 * Connects directly to Binance WebSocket API (no backend needed)
 * Real-time display only - NO database writes
 */

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Zap } from 'lucide-react'

interface LivePrice {
  asset: string
  price: number
  bid: number | null
  ask: number | null
  volume: number
  lastUpdate: Date
  status: 'LIVE' | 'STALE' | 'DISCONNECTED'
}

const BINANCE_WS_URL = 'wss://stream.binance.com:9443/stream'

// Symbols to track
const SYMBOLS = [
  { symbol: 'btcusdt', display: 'BTC-USD' },
  { symbol: 'ethusdt', display: 'ETH-USD' },
  { symbol: 'solusdt', display: 'SOL-USD' },
]

export function LiveBinancePrices() {
  const [prices, setPrices] = useState<Record<string, LivePrice>>({})
  const [connected, setConnected] = useState(false)
  const [tickCount, setTickCount] = useState(0)

  useEffect(() => {
    // Build WebSocket subscription message
    const streams = SYMBOLS.map(s => `${s.symbol}@ticker`).join('/')
    const wsUrl = `${BINANCE_WS_URL}?streams=${streams}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('🟢 Connected to Binance WebSocket')
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.stream && data.data) {
          const ticker = data.data
          const symbol = data.stream.split('@')[0]

          // Find display name
          const symbolConfig = SYMBOLS.find(s => s.symbol === symbol)
          if (!symbolConfig) return

          const now = new Date()

          setPrices(prev => ({
            ...prev,
            [symbolConfig.display]: {
              asset: symbolConfig.display,
              price: parseFloat(ticker.c), // Current price
              bid: parseFloat(ticker.b),   // Best bid
              ask: parseFloat(ticker.a),   // Best ask
              volume: parseFloat(ticker.v), // 24h volume
              lastUpdate: now,
              status: 'LIVE',
            }
          }))

          setTickCount(prev => prev + 1)
        }
      } catch (error) {
        console.error('WebSocket parse error:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      console.log('🔴 Disconnected from Binance WebSocket')
      setConnected(false)

      // Mark all prices as disconnected
      setPrices(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(key => {
          updated[key].status = 'DISCONNECTED'
        })
        return updated
      })
    }

    // Cleanup on unmount
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [])

  // Update status based on last update time
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date()
      setPrices(prev => {
        const updated = { ...prev }
        Object.keys(updated).forEach(key => {
          const ageSeconds = (now.getTime() - updated[key].lastUpdate.getTime()) / 1000

          if (ageSeconds < 5) {
            updated[key].status = 'LIVE'
          } else if (ageSeconds < 30) {
            updated[key].status = 'STALE'
          } else {
            updated[key].status = 'DISCONNECTED'
          }
        })
        return updated
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  const formatAge = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    return `${Math.floor(seconds / 3600)}h ago`
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle>Live Market Prices</CardTitle>
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md border ${
              connected
                ? 'bg-green-500/20 border-green-500/30'
                : 'bg-red-500/20 border-red-500/30'
            }`}>
              <Zap className={`w-3.5 h-3.5 ${connected ? 'text-green-400' : 'text-red-400'}`} />
              <span className={`text-xs font-semibold ${connected ? 'text-green-400' : 'text-red-400'}`}>
                {connected ? 'LIVE' : 'OFFLINE'}
              </span>
            </div>
          </div>
          <span
            className="data-lineage-indicator"
            title="Source: Binance Public WebSocket API (Direct Connection)"
          >
            i
          </span>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          {tickCount} ticks received • Direct WebSocket connection (no database)
        </p>
      </CardHeader>
      <CardContent>
        {Object.keys(prices).length > 0 ? (
          <div className="space-y-4">
            {SYMBOLS.map(({ display }) => {
              const price = prices[display]
              if (!price) return null

              return (
                <div
                  key={display}
                  className="p-4 bg-slate-50 rounded-lg border border-slate-200"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">
                        {price.asset}
                      </h3>
                      <p className="text-xs text-slate-500 uppercase">
                        Binance Spot
                      </p>
                    </div>
                    <StatusBadge
                      variant={
                        price.status === 'LIVE'
                          ? 'fresh'
                          : price.status === 'STALE'
                          ? 'stale'
                          : 'outdated'
                      }
                    >
                      {price.status}
                    </StatusBadge>
                  </div>

                  <div className="space-y-2">
                    {/* Price */}
                    <div className="flex items-baseline justify-between">
                      <span className="text-sm text-slate-600">Price</span>
                      <span className="text-2xl font-mono font-bold text-slate-900">
                        ${formatNumber(price.price, 2)}
                      </span>
                    </div>

                    {/* Bid/Ask Spread */}
                    {price.bid && price.ask && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">Bid/Ask</span>
                        <span className="font-mono text-slate-700">
                          ${formatNumber(price.bid, 2)} / ${formatNumber(price.ask, 2)}
                        </span>
                      </div>
                    )}

                    {/* Volume */}
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Volume (24h)</span>
                      <span className="font-mono text-slate-700">
                        {formatNumber(price.volume, 0)}
                      </span>
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-200">
                      <span>Updated {formatAge(price.lastUpdate)}</span>
                      <span>Real-time WebSocket</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-slate-500 mb-2">
              {connected ? 'Waiting for data...' : 'Connecting to Binance...'}
            </p>
            <p className="text-xs text-slate-400">
              Live WebSocket stream • No backend required
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
