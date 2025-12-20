'use client'

/**
 * Global Error Handler (Next.js App Router)
 * Catches unhandled errors in the application
 */

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Application error:', error)
  }, [error])

  return (
    <div className="min-h-[400px] flex items-center justify-center p-8">
      <div
        className="max-w-lg w-full p-6 rounded-lg border"
        style={{
          backgroundColor: 'hsl(var(--card))',
          borderColor: 'hsl(0, 84%, 60%, 0.3)',
        }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ backgroundColor: 'hsl(0, 84%, 60%, 0.15)' }}
          >
            <span style={{ color: 'hsl(0, 84%, 60%)' }}>!</span>
          </div>
          <div>
            <h2
              className="text-lg font-semibold"
              style={{ color: 'hsl(var(--foreground))' }}
            >
              Something went wrong
            </h2>
            <p
              className="text-sm"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            >
              An error occurred while loading this page
            </p>
          </div>
        </div>

        {process.env.NODE_ENV === 'development' && (
          <div
            className="mb-4 p-3 rounded text-sm font-mono overflow-auto max-h-32"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(0, 84%, 60%)',
            }}
          >
            {error.message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => reset()}
            className="px-4 py-2 rounded text-sm font-medium transition-colors"
            style={{
              backgroundColor: 'hsl(var(--primary))',
              color: 'hsl(var(--primary-foreground))',
            }}
          >
            Try Again
          </button>
          <button
            onClick={() => window.location.href = '/'}
            className="px-4 py-2 rounded text-sm font-medium transition-colors"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--foreground))',
            }}
          >
            Go Home
          </button>
        </div>

        <p
          className="mt-4 text-xs"
          style={{ color: 'hsl(var(--muted-foreground))' }}
        >
          Error ID: {error.digest || 'N/A'}
        </p>
      </div>
    </div>
  )
}
