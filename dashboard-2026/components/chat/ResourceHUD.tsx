/**
 * Resource HUD Component
 * Token budget, cost tracking, and rate limits per ADR-012
 * Authority: G1 UI Governance Patch - Vision-Chat 2026
 *
 * Features:
 * - Real-time token usage
 * - Session cost tracking
 * - Rate limit indicators
 * - DEFCON-reactive coloring
 */

'use client'

import { cn } from '@/lib/utils/cn'
import { Coins, Zap, Clock, AlertTriangle } from 'lucide-react'

interface ResourceHUDProps {
  tokensUsed: number
  tokenLimit: number
  costUsd: number
  dailyBudgetUsd: number
  requestsThisMinute: number
  rateLimit: number
  defconLevel?: 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'BLACK'
}

export function ResourceHUD({
  tokensUsed,
  tokenLimit,
  costUsd,
  dailyBudgetUsd,
  requestsThisMinute,
  rateLimit,
  defconLevel = 'GREEN',
}: ResourceHUDProps) {
  const tokenPercent = (tokensUsed / tokenLimit) * 100
  const costPercent = (costUsd / dailyBudgetUsd) * 100
  const ratePercent = (requestsThisMinute / rateLimit) * 100

  const getBarColor = (percent: number) => {
    if (percent >= 90) return 'rgb(239, 68, 68)' // red
    if (percent >= 70) return 'rgb(249, 115, 22)' // orange
    if (percent >= 50) return 'rgb(234, 179, 8)' // yellow
    return 'rgb(34, 197, 94)' // green
  }

  const defconColors = {
    GREEN: 'rgba(34, 197, 94, 0.2)',
    YELLOW: 'rgba(234, 179, 8, 0.2)',
    ORANGE: 'rgba(249, 115, 22, 0.2)',
    RED: 'rgba(239, 68, 68, 0.2)',
    BLACK: 'rgba(0, 0, 0, 0.4)',
  }

  return (
    <div
      className="resource-hud rounded-lg p-3"
      style={{
        backgroundColor: defconColors[defconLevel],
        border: '1px solid hsl(var(--border))',
      }}
    >
      <div className="flex items-center justify-between gap-6">
        {/* Token Usage */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <Zap className="w-3.5 h-3.5" />
              <span>Tokens</span>
            </div>
            <span className="text-xs font-mono">
              {formatNumber(tokensUsed)} / {formatNumber(tokenLimit)}
            </span>
          </div>
          <div className="h-1.5 rounded-full" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(tokenPercent, 100)}%`,
                backgroundColor: getBarColor(tokenPercent),
              }}
            />
          </div>
        </div>

        {/* Cost */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <Coins className="w-3.5 h-3.5" />
              <span>Cost</span>
            </div>
            <span className="text-xs font-mono">
              ${costUsd.toFixed(2)} / ${dailyBudgetUsd.toFixed(0)}
            </span>
          </div>
          <div className="h-1.5 rounded-full" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(costPercent, 100)}%`,
                backgroundColor: getBarColor(costPercent),
              }}
            />
          </div>
        </div>

        {/* Rate Limit */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <Clock className="w-3.5 h-3.5" />
              <span>Rate</span>
            </div>
            <span className="text-xs font-mono">
              {requestsThisMinute} / {rateLimit} rpm
            </span>
          </div>
          <div className="h-1.5 rounded-full" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(ratePercent, 100)}%`,
                backgroundColor: getBarColor(ratePercent),
              }}
            />
          </div>
        </div>

        {/* DEFCON Indicator */}
        <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
          <div
            className={cn(
              'w-2.5 h-2.5 rounded-full',
              defconLevel !== 'GREEN' && 'animate-pulse'
            )}
            style={{
              backgroundColor: {
                GREEN: 'rgb(34, 197, 94)',
                YELLOW: 'rgb(234, 179, 8)',
                ORANGE: 'rgb(249, 115, 22)',
                RED: 'rgb(239, 68, 68)',
                BLACK: 'rgb(255, 255, 255)',
              }[defconLevel],
            }}
          />
          <span className="text-xs font-mono font-semibold">
            DEFCON {defconLevel}
          </span>
        </div>

        {/* Warning if any resource is critical */}
        {(tokenPercent >= 90 || costPercent >= 90 || ratePercent >= 90) && (
          <div
            className="flex items-center gap-1.5 text-xs px-2 py-1 rounded"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              color: 'rgb(252, 165, 165)',
            }}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Limit Warning</span>
          </div>
        )}
      </div>
    </div>
  )
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toString()
}
