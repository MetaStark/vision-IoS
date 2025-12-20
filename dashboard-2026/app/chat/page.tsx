/**
 * Vision-Chat 2026 - Glass Cockpit Interface
 * CEO Oracle Channel with full system inquiry capabilities
 *
 * Authority: G1 UI Governance Patch
 * Constitutional Basis: ADR-019, IoS-009
 *
 * Features:
 * - The Nexus (floating omnibar with mode switching)
 * - Intelligent Stream (agent-badged message blocks)
 * - Evidence Drawer (SQL preview with lineage)
 * - G0 Submission Card (narrative vector injection)
 * - Resource HUD (token/cost tracking per ADR-012)
 * - DEFCON-reactive theming
 */

'use client'

import { useState, useEffect, useRef } from 'react'
import { Nexus, NexusMode } from '@/components/chat/Nexus'
import { MessageStream, ChatMessage } from '@/components/chat/MessageStream'
import { ResourceHUD } from '@/components/chat/ResourceHUD'
import { G0SubmissionCard, NarrativeSubmission } from '@/components/chat/G0SubmissionCard'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { MessageSquare, Syringe, BarChart3 } from 'lucide-react'

type DefconLevel = 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'BLACK'

interface SessionStats {
  tokensUsed: number
  tokenLimit: number
  costUsd: number
  dailyBudgetUsd: number
  requestsThisMinute: number
  rateLimit: number
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showG0Card, setShowG0Card] = useState(false)
  const [defconLevel, setDefconLevel] = useState<DefconLevel>('GREEN')
  const [sessionStats, setSessionStats] = useState<SessionStats>({
    tokensUsed: 0,
    tokenLimit: 100000,
    costUsd: 0,
    dailyBudgetUsd: 50,
    requestsThisMinute: 0,
    rateLimit: 60,
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Fetch DEFCON level on mount
  useEffect(() => {
    fetchDefconLevel()
    const interval = setInterval(fetchDefconLevel, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  async function fetchDefconLevel() {
    try {
      const res = await fetch('/api/engine/defcon')
      if (res.ok) {
        const data = await res.json()
        setDefconLevel(data.level || 'GREEN')
      }
    } catch (error) {
      console.error('Failed to fetch DEFCON level:', error)
    }
  }

  async function handleNexusSubmit(message: string, mode: NexusMode) {
    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: new Date(),
      mode,
    }
    setMessages((prev) => [...prev, userMessage])

    if (mode === 'inject') {
      setShowG0Card(true)
      return
    }

    setIsLoading(true)
    const startTime = Date.now()

    try {
      if (mode === 'query') {
        // Direct SQL execution
        const res = await fetch('/api/engine/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sql: message }),
        })
        const data = await res.json()

        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.error
            ? `**Query Error:**\n\`\`\`\n${data.error}\n\`\`\``
            : `**Query Results (${data.rows?.length || 0} rows):**\n\n${formatQueryResults(data.rows)}`,
          agent: 'STIG',
          timestamp: new Date(),
          sqlExecuted: data.error ? undefined : [message],
          mode: 'query',
          metadata: {
            latencyMs: Date.now() - startTime,
          },
        }
        setMessages((prev) => [...prev, assistantMessage])
      } else {
        // Claude-powered inquiry
        const history = messages
          .filter((m) => m.mode === 'ask' || m.mode === undefined)
          .map((m) => ({
            role: m.role,
            content: m.content,
          }))

        const res = await fetch('/api/vision-chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, history }),
        })
        const data = await res.json()

        if (data.success) {
          const assistantMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: data.response,
            agent: 'VISION',
            timestamp: new Date(),
            sqlExecuted: data.sql_executed,
            mode: 'ask',
            metadata: {
              latencyMs: Date.now() - startTime,
            },
          }
          setMessages((prev) => [...prev, assistantMessage])

          // Update session stats (approximate)
          setSessionStats((prev) => ({
            ...prev,
            tokensUsed: prev.tokensUsed + Math.ceil(message.length / 4) + Math.ceil((data.response?.length || 0) / 4),
            costUsd: prev.costUsd + 0.01, // Approximate per request
            requestsThisMinute: prev.requestsThisMinute + 1,
          }))
        } else {
          const errorMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `**Error:** ${data.error || 'Unknown error occurred'}`,
            agent: 'VISION',
            timestamp: new Date(),
            mode: 'ask',
          }
          setMessages((prev) => [...prev, errorMessage])
        }
      }
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `**Connection Error:** Failed to reach the API. ${error instanceof Error ? error.message : ''}`,
        agent: 'VISION',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  async function handleG0Submit(submission: NarrativeSubmission) {
    try {
      const res = await fetch('/api/oracle/staging', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submission),
      })
      const data = await res.json()

      if (data.success) {
        const confirmMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `**G0 Submission Accepted**\n\nNarrative vector submitted to \`oracle_staging\` for VEGA review.\n\n- **Domain:** ${submission.domain}\n- **Probability:** ${(submission.probability * 100).toFixed(0)}%\n- **Confidence:** ${(submission.confidence * 100).toFixed(0)}%\n- **Half-Life:** ${submission.halfLifeHours}h\n- **Status:** Pending VEGA G1 approval`,
          agent: 'VEGA',
          timestamp: new Date(),
          mode: 'inject',
        }
        setMessages((prev) => [...prev, confirmMessage])
        setShowG0Card(false)
      }
    } catch (error) {
      console.error('G0 submission failed:', error)
    }
  }

  return (
    <div className="chat-page flex flex-col h-[calc(100vh-180px)]">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-display flex items-center gap-3">
            <MessageSquare className="w-8 h-8" style={{ color: 'hsl(var(--primary))' }} />
            Vision-Chat
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
            CEO Oracle Channel — Full System Inquiry
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowG0Card(!showG0Card)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all"
            style={{
              backgroundColor: showG0Card ? 'hsl(38, 92%, 50%)' : 'hsl(var(--secondary))',
              color: showG0Card ? 'black' : 'hsl(var(--foreground))',
            }}
          >
            <Syringe className="w-4 h-4" />
            G0 Submission
          </button>
        </div>
      </div>

      {/* Resource HUD */}
      <div className="mb-4">
        <ResourceHUD
          tokensUsed={sessionStats.tokensUsed}
          tokenLimit={sessionStats.tokenLimit}
          costUsd={sessionStats.costUsd}
          dailyBudgetUsd={sessionStats.dailyBudgetUsd}
          requestsThisMinute={sessionStats.requestsThisMinute}
          rateLimit={sessionStats.rateLimit}
          defconLevel={defconLevel}
        />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex gap-6 min-h-0">
        {/* Message Stream */}
        <div
          className="flex-1 overflow-y-auto rounded-lg p-4"
          style={{
            backgroundColor: 'hsl(var(--secondary) / 0.3)',
            border: '1px solid hsl(var(--border))',
          }}
        >
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <MessageSquare className="w-16 h-16 mb-4" style={{ color: 'hsl(var(--muted-foreground) / 0.3)' }} />
              <h3 className="text-lg font-semibold mb-2">Welcome to Vision-Chat</h3>
              <p className="text-sm max-w-md" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Your CEO Oracle Channel to the FjordHQ Market System.
                Ask anything about system state, signals, governance, or data.
              </p>
              <div className="mt-6 grid grid-cols-3 gap-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <span className="font-mono text-primary">/ask</span>
                  <p className="mt-1">Claude inquiry</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <span className="font-mono" style={{ color: 'hsl(38, 92%, 50%)' }}>/inject</span>
                  <p className="mt-1">G0 submission</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <span className="font-mono" style={{ color: 'hsl(142, 76%, 36%)' }}>/query</span>
                  <p className="mt-1">Direct SQL</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              <MessageStream messages={messages} isLoading={isLoading} />
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* G0 Submission Card (Sidebar) */}
        {showG0Card && (
          <div className="w-96 shrink-0">
            <G0SubmissionCard onSubmit={handleG0Submit} />
          </div>
        )}
      </div>

      {/* The Nexus (Input) */}
      <div className="mt-4">
        <Nexus
          onSubmit={handleNexusSubmit}
          isLoading={isLoading}
          defconLevel={defconLevel}
        />
      </div>
    </div>
  )
}

function formatQueryResults(rows: any[] | undefined): string {
  if (!rows || rows.length === 0) {
    return '*No results*'
  }

  const keys = Object.keys(rows[0])
  const header = `| ${keys.join(' | ')} |`
  const separator = `| ${keys.map(() => '---').join(' | ')} |`
  const dataRows = rows
    .slice(0, 50)
    .map((row) => `| ${keys.map((k) => String(row[k] ?? '')).join(' | ')} |`)
    .join('\n')

  let result = `${header}\n${separator}\n${dataRows}`
  if (rows.length > 50) {
    result += `\n\n*Showing first 50 of ${rows.length} rows*`
  }

  return result
}
