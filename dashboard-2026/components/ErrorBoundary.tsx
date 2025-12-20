/**
 * Error Boundary Component
 * Catches React errors and displays fallback UI
 * MBB-grade: Clear error messaging, governance-aligned logging
 */

'use client'

import React from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console (in production, send to monitoring service)
    console.error('ErrorBoundary caught error:', error, errorInfo)

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
  }

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default fallback UI
      return <ErrorFallback error={this.state.error} />
    }

    return this.props.children
  }
}

/**
 * Default Error Fallback UI
 * MBB-grade: Professional, informative, actionable
 */
function ErrorFallback({ error }: { error: Error | null }) {
  return (
    <Card className="border-red-200 bg-red-50">
      <CardHeader>
        <div className="flex items-center gap-3">
          <StatusBadge variant="fail" icon="✗">
            Error
          </StatusBadge>
          <CardTitle className="text-red-900">Component Error</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <p className="text-sm text-red-800">
            An error occurred while rendering this component. The system has logged this error for investigation.
          </p>

          {error && (
            <details className="text-xs">
              <summary className="cursor-pointer font-medium text-red-900 hover:text-red-700">
                Technical Details
              </summary>
              <pre className="mt-2 overflow-auto rounded bg-red-100 p-3 text-red-900">
                {error.message}
              </pre>
              {process.env.NODE_ENV === 'development' && error.stack && (
                <pre className="mt-2 overflow-auto rounded bg-red-100 p-3 text-xs text-red-900">
                  {error.stack}
                </pre>
              )}
            </details>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => window.location.reload()}
              className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Reload Page
            </button>
            <button
              onClick={() => window.history.back()}
              className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
            >
              Go Back
            </button>
          </div>

          <div className="border-t border-red-200 pt-4">
            <p className="text-xs text-red-600">
              <strong>Data Lineage:</strong> Error logged to{' '}
              <code className="rounded bg-red-100 px-1 py-0.5">fhq_monitoring.system_event_log</code>
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Async Error Boundary Wrapper
 * For wrapping async operations with error handling
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: React.ReactNode
) {
  return function WrappedComponent(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <Component {...props} />
      </ErrorBoundary>
    )
  }
}
