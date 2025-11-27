/**
 * FINN Intelligence Module (Placeholder)
 * TODO: Implement full FINN module in Phase 2 Sprint 2.2
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'

export default function FINNPage() {
  return (
    <div className="space-y-8 fade-in">
      <div>
        <h1 className="text-display">FINN Intelligence</h1>
        <p className="text-slate-600 mt-2">
          AI-powered market analysis and regime detection
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>🚧 Under Construction - Phase 2 Sprint 2.2</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-slate-700">
              This module will include:
            </p>
            <ul className="list-disc list-inside space-y-2 text-sm text-slate-600">
              <li><strong>Today's Briefing</strong>: Summary, key bullets, attached signals</li>
              <li><strong>Regime & Market State</strong>: Current BTC regime, historical timeline, distribution vs baseline</li>
              <li><strong>Derivatives & Fragility</strong>: Gamma exposure, fragility metrics, funding rates</li>
              <li><strong>FINN Quality & Confidence</strong>: Quality tier gauge, trend charts, usage metrics</li>
              <li>Contract validation warnings</li>
            </ul>
            <p className="text-sm text-slate-500 mt-4">
              Target completion: Sprint 2.2 (Week 5)
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
