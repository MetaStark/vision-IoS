/**
 * Research & Backtesting Module (Placeholder)
 * TODO: Implement in Phase 4 Sprint 4.1 (Week 8)
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'

export default function ResearchPage() {
  return (
    <div className="space-y-8 fade-in">
      <div className="flex items-center gap-3">
        <h1 className="text-display">Research & Backtesting</h1>
        <StatusBadge variant="info">Beta</StatusBadge>
      </div>
      <p className="text-slate-600 -mt-6">
        Strategy performance analysis and research library
      </p>

      <Card>
        <CardHeader>
          <CardTitle>🚧 Under Construction - Phase 4 Sprint 4.1 (Week 8)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-slate-700">
              This module will include:
            </p>
            <ul className="list-disc list-inside space-y-2 text-sm text-slate-600">
              <li>Backtest results viewer (strategy_baseline_results, btc_backtest_trades)</li>
              <li>Strategy performance vs buy-and-hold charts</li>
              <li>Feature performance table</li>
              <li>Lessons learned viewer</li>
              <li>Access to btc_analysis_dataset</li>
              <li>Interactive backtest runner (via MCP Docker exec)</li>
            </ul>
            <p className="text-sm text-slate-500 mt-4">
              Target completion: Phase 4 Sprint 4.1 (Week 8)
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
