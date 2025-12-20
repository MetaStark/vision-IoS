'use client'

/**
 * ModuleErrorBoundary
 * ====================
 * CD-EXEC-PERMANENT-UPTIME: Module failures must not crash dashboard
 *
 * Wraps individual dashboard modules to isolate failures.
 * If a module crashes, it shows a graceful degradation message
 * instead of taking down the entire page.
 */

import React, { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  moduleName: string
  onError?: (error: Error, moduleName: string) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ModuleErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(`[MODULE-ERROR] ${this.props.moduleName}:`, error.message)
    console.error('Component stack:', errorInfo.componentStack)
    this.props.onError?.(error, this.props.moduleName)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="p-4 rounded-lg border"
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderColor: 'rgba(239, 68, 68, 0.3)',
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="p-2 rounded-lg"
                style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)' }}
              >
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="font-medium text-slate-200">
                  {this.props.moduleName} Unavailable
                </p>
                <p className="text-xs text-slate-400">
                  Module failed to load - dashboard continues operating
                </p>
              </div>
            </div>
            <button
              onClick={this.handleRetry}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors hover:bg-slate-700"
              style={{ color: 'hsl(var(--primary))' }}
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <div
              className="mt-3 p-2 rounded text-xs font-mono overflow-auto max-h-24"
              style={{ backgroundColor: 'rgba(0, 0, 0, 0.3)', color: 'rgb(252, 165, 165)' }}
            >
              {this.state.error.message}
            </div>
          )}
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Server-side module wrapper with error handling
 * Use this to wrap async data-fetching sections
 */
export function ModuleUnavailable({
  moduleName,
  error
}: {
  moduleName: string
  error?: string
}) {
  return (
    <div
      className="p-4 rounded-lg border"
      style={{
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderColor: 'rgba(239, 68, 68, 0.3)',
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="p-2 rounded-lg"
          style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)' }}
        >
          <AlertTriangle className="w-5 h-5 text-red-400" />
        </div>
        <div>
          <p className="font-medium text-slate-200">
            {moduleName} Unavailable
          </p>
          <p className="text-xs text-slate-400">
            {error || 'Data source temporarily unavailable'}
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Loading placeholder for async modules
 */
export function ModuleLoading({ moduleName }: { moduleName: string }) {
  return (
    <div
      className="p-4 rounded-lg border animate-pulse"
      style={{
        backgroundColor: 'rgba(59, 130, 246, 0.05)',
        borderColor: 'rgba(59, 130, 246, 0.2)',
      }}
    >
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-slate-700" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-slate-700 rounded w-1/3" />
          <div className="h-3 bg-slate-700/50 rounded w-1/2" />
        </div>
      </div>
    </div>
  )
}

export default ModuleErrorBoundary
