/**
 * The Nexus - Floating Omnibar Component
 * CEO inquiry input with mode switching via slash commands
 * Authority: G1 UI Governance Patch - Vision-Chat 2026
 *
 * Features:
 * - Mode switching: /ask, /inject, /query
 * - Glassmorphism design
 * - DEFCON-reactive styling
 */

'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { cn } from '@/lib/utils/cn'
import { Send, Sparkles, Database, Syringe, Loader2 } from 'lucide-react'

export type NexusMode = 'ask' | 'inject' | 'query'

interface NexusProps {
  onSubmit: (message: string, mode: NexusMode) => void
  isLoading?: boolean
  defconLevel?: 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'BLACK'
  disabled?: boolean
}

const MODE_CONFIG = {
  ask: {
    icon: Sparkles,
    placeholder: 'Ask VISION anything about the system...',
    hint: 'Claude-powered inquiry channel',
    color: 'hsl(var(--primary))',
  },
  inject: {
    icon: Syringe,
    placeholder: 'Inject narrative vector (G0 Submission)...',
    hint: 'Human oracle input with decay',
    color: 'hsl(38, 92%, 50%)',
  },
  query: {
    icon: Database,
    placeholder: 'Execute read-only SQL query...',
    hint: 'Direct database access (SELECT only)',
    color: 'hsl(142, 76%, 36%)',
  },
}

const DEFCON_BORDER_COLORS = {
  GREEN: 'rgba(34, 197, 94, 0.3)',
  YELLOW: 'rgba(234, 179, 8, 0.4)',
  ORANGE: 'rgba(249, 115, 22, 0.5)',
  RED: 'rgba(239, 68, 68, 0.6)',
  BLACK: 'rgba(255, 255, 255, 0.2)',
}

export function Nexus({ onSubmit, isLoading = false, defconLevel = 'GREEN', disabled = false }: NexusProps) {
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<NexusMode>('ask')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Parse slash commands
  useEffect(() => {
    if (input.startsWith('/ask ')) {
      setMode('ask')
      setInput(input.slice(5))
    } else if (input.startsWith('/inject ')) {
      setMode('inject')
      setInput(input.slice(8))
    } else if (input.startsWith('/query ')) {
      setMode('query')
      setInput(input.slice(7))
    } else if (input === '/ask' || input === '/inject' || input === '/query') {
      // Just switching mode, clear input
      setMode(input.slice(1) as NexusMode)
      setInput('')
    }
  }, [input])

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (trimmed && !isLoading && !disabled) {
      onSubmit(trimmed, mode)
      setInput('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    // Tab to cycle modes
    if (e.key === 'Tab') {
      e.preventDefault()
      const modes: NexusMode[] = ['ask', 'inject', 'query']
      const currentIndex = modes.indexOf(mode)
      setMode(modes[(currentIndex + 1) % modes.length])
    }
  }

  const currentConfig = MODE_CONFIG[mode]
  const Icon = currentConfig.icon
  const borderColor = DEFCON_BORDER_COLORS[defconLevel]

  return (
    <div className="nexus-container">
      {/* Mode indicator pills */}
      <div className="flex items-center gap-2 mb-3">
        {Object.entries(MODE_CONFIG).map(([key, config]) => {
          const ModeIcon = config.icon
          const isActive = mode === key
          return (
            <button
              key={key}
              onClick={() => setMode(key as NexusMode)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                isActive ? 'opacity-100' : 'opacity-50 hover:opacity-75'
              )}
              style={{
                backgroundColor: isActive ? `${config.color}20` : 'transparent',
                color: config.color,
                border: isActive ? `1px solid ${config.color}40` : '1px solid transparent',
              }}
            >
              <ModeIcon className="w-3.5 h-3.5" />
              <span className="capitalize">{key}</span>
            </button>
          )
        })}
        <span className="text-xs ml-auto" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Tab to cycle | Shift+Enter for newline
        </span>
      </div>

      {/* Main input area */}
      <div
        className="nexus-input-wrapper relative rounded-xl overflow-hidden transition-all"
        style={{
          backgroundColor: 'hsl(var(--card))',
          border: `1px solid ${borderColor}`,
          boxShadow: `0 0 20px ${borderColor}, inset 0 1px 0 rgba(255,255,255,0.05)`,
        }}
      >
        {/* Mode icon */}
        <div
          className="absolute left-4 top-1/2 -translate-y-1/2"
          style={{ color: currentConfig.color }}
        >
          <Icon className="w-5 h-5" />
        </div>

        {/* Textarea */}
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={currentConfig.placeholder}
          disabled={isLoading || disabled}
          rows={1}
          className={cn(
            'w-full bg-transparent text-sm resize-none outline-none',
            'pl-12 pr-14 py-4',
            'placeholder:text-[hsl(var(--muted-foreground))]'
          )}
          style={{
            color: 'hsl(var(--foreground))',
            minHeight: '56px',
            maxHeight: '200px',
          }}
        />

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading || disabled}
          className={cn(
            'absolute right-3 top-1/2 -translate-y-1/2',
            'p-2 rounded-lg transition-all',
            'disabled:opacity-30 disabled:cursor-not-allowed'
          )}
          style={{
            backgroundColor: input.trim() && !isLoading ? `${currentConfig.color}20` : 'transparent',
            color: currentConfig.color,
          }}
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Mode hint */}
      <div className="mt-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
        {currentConfig.hint}
        {mode === 'inject' && (
          <span className="ml-2 px-1.5 py-0.5 rounded" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            Routes to oracle_staging for VEGA review
          </span>
        )}
      </div>
    </div>
  )
}
