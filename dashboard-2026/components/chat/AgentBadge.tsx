/**
 * Agent Badge Component
 * Visual identifier for agent responses per G1 UI Governance Patch
 * Authority: ADR-019, IoS-009
 */

'use client'

import { cn } from '@/lib/utils/cn'

export type AgentId = 'LARS' | 'STIG' | 'VEGA' | 'FINN' | 'LINE' | 'CSEO' | 'VISION'

interface AgentConfig {
  name: string
  title: string
  color: string
  bgColor: string
  borderColor: string
}

const AGENT_CONFIGS: Record<AgentId, AgentConfig> = {
  LARS: {
    name: 'LARS',
    title: 'Logic, Analytics & Research Strategy',
    color: 'rgb(96, 165, 250)',      // blue-400
    bgColor: 'rgba(59, 130, 246, 0.15)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
  },
  STIG: {
    name: 'STIG',
    title: 'System for Technical Implementation & Governance',
    color: 'rgb(52, 211, 153)',      // emerald-400
    bgColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  VEGA: {
    name: 'VEGA',
    title: 'Verification & Governance Authority',
    color: 'rgb(167, 139, 250)',     // violet-400
    bgColor: 'rgba(139, 92, 246, 0.15)',
    borderColor: 'rgba(139, 92, 246, 0.3)',
  },
  FINN: {
    name: 'FINN',
    title: 'Financial Investments Neural Network',
    color: 'rgb(251, 191, 36)',      // amber-400
    bgColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  LINE: {
    name: 'LINE',
    title: 'Local Infrastructure, Network & Execution',
    color: 'rgb(248, 113, 113)',     // red-400
    bgColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  CSEO: {
    name: 'CEO',
    title: 'Chief Executive Officer',
    color: 'rgb(255, 255, 255)',     // white
    bgColor: 'rgba(255, 255, 255, 0.1)',
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  VISION: {
    name: 'VISION',
    title: 'VisionChat - CEO Inquiry Channel',
    color: 'rgb(14, 165, 233)',      // sky-500
    bgColor: 'rgba(14, 165, 233, 0.15)',
    borderColor: 'rgba(14, 165, 233, 0.3)',
  },
}

interface AgentBadgeProps {
  agent: AgentId
  size?: 'sm' | 'md' | 'lg'
  showTitle?: boolean
  className?: string
}

export function AgentBadge({ agent, size = 'md', showTitle = false, className }: AgentBadgeProps) {
  const config = AGENT_CONFIGS[agent]

  const sizeClasses = {
    sm: 'text-[10px] px-1.5 py-0.5',
    md: 'text-xs px-2 py-1',
    lg: 'text-sm px-3 py-1.5',
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span
        className={cn(
          'font-mono font-bold rounded',
          sizeClasses[size]
        )}
        style={{
          color: config.color,
          backgroundColor: config.bgColor,
          border: `1px solid ${config.borderColor}`,
        }}
        title={config.title}
      >
        {config.name}
      </span>
      {showTitle && (
        <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          {config.title}
        </span>
      )}
    </div>
  )
}

export function getAgentConfig(agent: AgentId): AgentConfig {
  return AGENT_CONFIGS[agent]
}
