'use client'

/**
 * Global Error Handler (Root Layout Errors)
 * Catches errors in the root layout
 */

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0a0a0a',
            color: '#fafafa',
            fontFamily: 'system-ui, sans-serif',
          }}
        >
          <div
            style={{
              maxWidth: '400px',
              padding: '24px',
              borderRadius: '8px',
              border: '1px solid #333',
              backgroundColor: '#141414',
            }}
          >
            <h2 style={{ marginBottom: '12px', fontSize: '18px' }}>
              Application Error
            </h2>
            <p style={{ marginBottom: '16px', color: '#888', fontSize: '14px' }}>
              A critical error occurred. Please try again.
            </p>
            <button
              onClick={() => reset()}
              style={{
                padding: '8px 16px',
                borderRadius: '4px',
                border: 'none',
                backgroundColor: '#3b82f6',
                color: 'white',
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              Try Again
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}
