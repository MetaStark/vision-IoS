/**
 * Evidence Drawer Component
 * SQL preview with lineage headers
 * Authority: G1 UI Governance Patch - Vision-Chat 2026
 *
 * Features:
 * - SQL syntax highlighting (basic)
 * - Lineage header showing source tables
 * - Copy to clipboard
 */

'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils/cn'
import { Copy, Check, Table, ArrowRight } from 'lucide-react'

interface EvidenceDrawerProps {
  queries: string[]
}

export function EvidenceDrawer({ queries }: EvidenceDrawerProps) {
  return (
    <div className="evidence-drawer p-4 space-y-4" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
      {queries.map((query, i) => (
        <QueryBlock key={i} query={query} index={i} />
      ))}
    </div>
  )
}

interface QueryBlockProps {
  query: string
  index: number
}

function QueryBlock({ query, index }: QueryBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(query)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Extract table references from query
  const tables = extractTables(query)

  return (
    <div className="query-block rounded-lg overflow-hidden" style={{ border: '1px solid hsl(var(--border))' }}>
      {/* Lineage Header */}
      {tables.length > 0 && (
        <div
          className="lineage-header flex items-center gap-2 px-3 py-2 text-xs"
          style={{
            backgroundColor: 'hsl(var(--card))',
            borderBottom: '1px solid hsl(var(--border))',
          }}
        >
          <Table className="w-3.5 h-3.5" style={{ color: 'hsl(var(--primary))' }} />
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>Source:</span>
          <div className="flex items-center gap-1">
            {tables.map((table, i) => (
              <span key={i} className="flex items-center gap-1">
                <code
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono"
                  style={{ backgroundColor: 'hsl(var(--secondary))', color: 'hsl(var(--primary))' }}
                >
                  {table}
                </code>
                {i < tables.length - 1 && (
                  <span style={{ color: 'hsl(var(--muted-foreground))' }}>+</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Query Content */}
      <div className="relative">
        <pre
          className="p-4 overflow-x-auto text-xs font-mono"
          style={{ backgroundColor: 'hsl(220, 13%, 10%)' }}
        >
          <code>
            <HighlightedSQL sql={query} />
          </code>
        </pre>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 p-1.5 rounded transition-all"
          style={{
            backgroundColor: 'hsl(var(--secondary))',
            color: copied ? 'hsl(142, 76%, 36%)' : 'hsl(var(--muted-foreground))',
          }}
        >
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>

      {/* Query Index */}
      <div
        className="px-3 py-1.5 text-[10px] flex items-center justify-between"
        style={{
          backgroundColor: 'hsl(var(--card))',
          borderTop: '1px solid hsl(var(--border))',
          color: 'hsl(var(--muted-foreground))',
        }}
      >
        <span>Query #{index + 1}</span>
        <span className="font-mono">{query.length} chars</span>
      </div>
    </div>
  )
}

function HighlightedSQL({ sql }: { sql: string }) {
  // Basic SQL syntax highlighting
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER BY', 'GROUP BY',
    'HAVING', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN',
    'ON', 'AS', 'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN',
    'LIMIT', 'OFFSET', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'COALESCE', 'CAST', 'EXTRACT',
    'WITH', 'UNION', 'ALL', 'EXISTS', 'TRUE', 'FALSE', 'DESC', 'ASC',
  ]

  const keywordPattern = new RegExp(`\\b(${keywords.join('|')})\\b`, 'gi')

  const parts = sql.split(keywordPattern)

  return (
    <>
      {parts.map((part, i) => {
        const isKeyword = keywords.some(k => k.toLowerCase() === part.toLowerCase())
        if (isKeyword) {
          return (
            <span key={i} style={{ color: 'rgb(198, 120, 221)' }}>
              {part.toUpperCase()}
            </span>
          )
        }
        // Check for strings
        if (part.includes("'")) {
          const stringParts = part.split(/(\'[^\']*\')/)
          return stringParts.map((sp, j) => {
            if (sp.startsWith("'") && sp.endsWith("'")) {
              return <span key={`${i}-${j}`} style={{ color: 'rgb(152, 195, 121)' }}>{sp}</span>
            }
            // Check for numbers
            const numParts = sp.split(/(\b\d+\.?\d*\b)/)
            return numParts.map((np, k) => {
              if (/^\d+\.?\d*$/.test(np)) {
                return <span key={`${i}-${j}-${k}`} style={{ color: 'rgb(209, 154, 102)' }}>{np}</span>
              }
              return <span key={`${i}-${j}-${k}`} style={{ color: 'rgb(171, 178, 191)' }}>{np}</span>
            })
          })
        }
        // Default text
        return <span key={i} style={{ color: 'rgb(171, 178, 191)' }}>{part}</span>
      })}
    </>
  )
}

function extractTables(sql: string): string[] {
  const tables: string[] = []

  // Match FROM and JOIN clauses
  const fromMatch = sql.match(/FROM\s+([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)/gi)
  const joinMatch = sql.match(/JOIN\s+([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)/gi)

  if (fromMatch) {
    fromMatch.forEach(m => {
      const table = m.replace(/FROM\s+/i, '').trim()
      if (!tables.includes(table)) tables.push(table)
    })
  }

  if (joinMatch) {
    joinMatch.forEach(m => {
      const table = m.replace(/JOIN\s+/i, '').trim()
      if (!tables.includes(table)) tables.push(table)
    })
  }

  return tables
}
