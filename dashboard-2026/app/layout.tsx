/**
 * Root Layout
 * Global layout with navigation and Trust Banner
 * Sprint 1.2: Real data from database
 * FINN V3.0: CDS / Narrative Shift Risk indicator
 */

import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { TrustBanner } from '@/components/TrustBanner'
import { Navigation } from '@/components/Navigation'
import { getSystemHealth } from '@/lib/data/health'
import { getLatestCDS } from '@/lib/data/serper'
import { ErrorBoundary } from '@/components/ErrorBoundary'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'FHQ Market System Dashboard',
  description: 'Institution-Level Market Intelligence Platform - 2026 Edition',
}

export const revalidate = 120 // Revalidate every 2 minutes

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Fetch system health data for Trust Banner
  // Wrapped in try/catch for graceful degradation
  let systemHealth
  try {
    systemHealth = await getSystemHealth()
  } catch (error) {
    console.error('Failed to fetch system health:', error)
    // Fallback to safe defaults
    systemHealth = {
      gateStatus: 'FAIL' as const,
      gatesPassed: 0,
      gatesTotal: 0,
      alertCount: 0,
      adrCompliant: false,
      adrActiveCount: 0,
      adrTotalCount: 0,
      dataFreshness: 'OUTDATED' as const,
      lastUpdate: new Date(),
    }
  }

  // FINN V3.0: Fetch CDS data for Narrative Shift Risk indicator
  let cdsData = null
  try {
    cdsData = await getLatestCDS('BTC-USD')
  } catch (error) {
    console.error('Failed to fetch CDS data:', error)
    // CDS is optional - continue without it
  }

  return (
    <html lang="en">
      <body className={inter.className}>
        <ErrorBoundary>
          <div className="min-h-screen" style={{ backgroundColor: 'hsl(var(--background))' }}>
            {/* Trust Banner - Real Data + FINN V3.0 CDS */}
            <TrustBanner
              gateStatus={systemHealth.gateStatus}
              gatesPassed={systemHealth.gatesPassed}
              gatesTotal={systemHealth.gatesTotal}
              alertCount={systemHealth.alertCount}
              adrCompliant={systemHealth.adrCompliant}
              dataFreshness={systemHealth.dataFreshness}
              narrativeShiftRisk={cdsData?.riskLevel}
              cdsScore={cdsData?.cdsScore}
            />

            <div className="flex">
              {/* Sidebar Navigation */}
              <Navigation />

              {/* Main Content */}
              <main className="flex-1 p-8">
                <div className="max-w-[1920px] mx-auto">
                  <ErrorBoundary>
                    {children}
                  </ErrorBoundary>
                </div>
              </main>
            </div>
          </div>
        </ErrorBoundary>
      </body>
    </html>
  )
}
