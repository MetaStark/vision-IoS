/**
 * Message Stream Component
 * Intelligent conversation display with agent badges
 * Authority: G1 UI Governance Patch - Vision-Chat 2026
 *
 * Features:
 * - Block-based layout (not bubbles)
 * - Agent badges with color coding
 * - Evidence drawers for SQL
 * - Markdown rendering
 */

'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils/cn'
import { AgentBadge, AgentId } from './AgentBadge'
import { EvidenceDrawer } from './EvidenceDrawer'
import { ChevronDown, ChevronRight, Clock, Database } from 'lucide-react'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  agent?: AgentId
  timestamp: Date
  sqlExecuted?: string[]
  mode?: 'ask' | 'inject' | 'query'
  metadata?: {
    tokensUsed?: number
    latencyMs?: number
    model?: string
  }
}

interface MessageStreamProps {
  messages: ChatMessage[]
  isLoading?: boolean
}

export function MessageStream({ messages, isLoading }: MessageStreamProps) {
  return (
    <div className="message-stream space-y-4">
      {messages.map((message) => (
        <MessageBlock key={message.id} message={message} />
      ))}

      {isLoading && (
        <div className="flex items-center gap-3 p-4">
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
            VISION is processing...
          </span>
        </div>
      )}
    </div>
  )
}

interface MessageBlockProps {
  message: ChatMessage
}

function MessageBlock({ message }: MessageBlockProps) {
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        'message-block rounded-lg transition-all',
        isUser ? 'ml-8' : 'mr-8'
      )}
      style={{
        backgroundColor: isUser ? 'hsl(var(--secondary))' : 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: 'hsl(var(--border))' }}
      >
        <div className="flex items-center gap-3">
          <AgentBadge agent={isUser ? 'CSEO' : (message.agent || 'VISION')} size="sm" />
          {message.mode && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded uppercase"
              style={{
                backgroundColor: 'hsl(var(--secondary))',
                color: 'hsl(var(--muted-foreground))',
              }}
            >
              {message.mode}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          {message.metadata?.latencyMs && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {message.metadata.latencyMs}ms
            </span>
          )}
          <span>{formatTime(message.timestamp)}</span>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        <div className="prose prose-invert prose-sm max-w-none">
          <MessageContent content={message.content} />
        </div>
      </div>

      {/* Evidence Drawer Toggle (if SQL was executed) */}
      {message.sqlExecuted && message.sqlExecuted.length > 0 && (
        <div
          className="border-t"
          style={{ borderColor: 'hsl(var(--border))' }}
        >
          <button
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            className="w-full flex items-center justify-between px-4 py-2 text-xs transition-colors"
            style={{ color: 'hsl(var(--muted-foreground))' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'hsl(var(--secondary))'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            <div className="flex items-center gap-2">
              <Database className="w-3.5 h-3.5" />
              <span>{message.sqlExecuted.length} SQL {message.sqlExecuted.length === 1 ? 'query' : 'queries'} executed</span>
            </div>
            {evidenceOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>

          {evidenceOpen && (
            <EvidenceDrawer queries={message.sqlExecuted} />
          )}
        </div>
      )}
    </div>
  )
}

function MessageContent({ content }: { content: string }) {
  // Simple markdown-like rendering
  const lines = content.split('\n')
  const elements: JSX.Element[] = []
  let inCodeBlock = false
  let codeContent = ''
  let codeLanguage = ''

  lines.forEach((line, i) => {
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        // End code block
        elements.push(
          <pre
            key={`code-${i}`}
            className="rounded-lg p-4 my-2 overflow-x-auto text-xs"
            style={{ backgroundColor: 'hsl(var(--secondary))' }}
          >
            <code>{codeContent.trim()}</code>
          </pre>
        )
        codeContent = ''
        inCodeBlock = false
      } else {
        // Start code block
        codeLanguage = line.slice(3).trim()
        inCodeBlock = true
      }
    } else if (inCodeBlock) {
      codeContent += line + '\n'
    } else if (line.startsWith('# ')) {
      elements.push(
        <h3 key={i} className="text-lg font-semibold mt-4 mb-2">{line.slice(2)}</h3>
      )
    } else if (line.startsWith('## ')) {
      elements.push(
        <h4 key={i} className="text-base font-semibold mt-3 mb-2">{line.slice(3)}</h4>
      )
    } else if (line.startsWith('### ')) {
      elements.push(
        <h5 key={i} className="text-sm font-semibold mt-2 mb-1">{line.slice(4)}</h5>
      )
    } else if (line.startsWith('- ')) {
      elements.push(
        <li key={i} className="ml-4">{formatInline(line.slice(2))}</li>
      )
    } else if (line.startsWith('**') && line.endsWith('**')) {
      elements.push(
        <p key={i} className="font-semibold">{line.slice(2, -2)}</p>
      )
    } else if (line.startsWith('| ')) {
      // Table row
      const cells = line.split('|').slice(1, -1).map(c => c.trim())
      const isSeparator = cells.every(c => /^-+$/.test(c))
      if (!isSeparator) {
        elements.push(
          <div key={i} className="flex border-b" style={{ borderColor: 'hsl(var(--border))' }}>
            {cells.map((cell, j) => (
              <div key={j} className="flex-1 px-2 py-1 text-xs font-mono">
                {cell}
              </div>
            ))}
          </div>
        )
      }
    } else if (line.trim()) {
      elements.push(
        <p key={i} className="mb-2">{formatInline(line)}</p>
      )
    }
  })

  return <>{elements}</>
}

function formatInline(text: string): React.ReactNode {
  // Handle inline code
  const parts = text.split(/(`[^`]+`)/)
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded text-xs"
          style={{ backgroundColor: 'hsl(var(--secondary))' }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    // Handle bold
    const boldParts = part.split(/(\*\*[^*]+\*\*)/)
    return boldParts.map((bp, j) => {
      if (bp.startsWith('**') && bp.endsWith('**')) {
        return <strong key={`${i}-${j}`}>{bp.slice(2, -2)}</strong>
      }
      return bp
    })
  })
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  })
}
