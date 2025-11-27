/**
 * Multi-Asset Freshness Component
 * Display data freshness for BTC, ETH, GSPC with lineage
 * MBB-grade: Layout clarity + lineage exposition
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatDate, formatAge } from '@/lib/utils/data-freshness'
import type { AssetFreshness } from '@/lib/data/market'

interface MultiAssetFreshnessProps {
  freshnessList: AssetFreshness[]
}

export function MultiAssetFreshness({ freshnessList }: MultiAssetFreshnessProps) {
  if (!freshnessList || freshnessList.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Multi-Asset Data Freshness</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {freshnessList.map((asset) => (
            <div
              key={asset.ticker}
              className="p-4 bg-slate-50 rounded-lg border border-slate-200"
            >
              {/* Asset ticker */}
              <div className="flex items-center justify-between mb-3">
                <span className="font-semibold text-slate-900">{asset.ticker}</span>
                <StatusBadge
                  variant={
                    asset.status === 'FRESH'
                      ? 'fresh'
                      : asset.status === 'STALE'
                      ? 'stale'
                      : 'outdated'
                  }
                  icon={
                    asset.status === 'FRESH'
                      ? '✓'
                      : asset.status === 'STALE'
                      ? '⚠'
                      : '✗'
                  }
                >
                  {asset.status}
                </StatusBadge>
              </div>

              {/* Latest date */}
              <div className="space-y-2 text-sm">
                <div>
                  <span className="text-slate-600">Latest Data:</span>
                  <p className="font-mono text-slate-900">
                    {asset.latestDate ? formatDate(asset.latestDate, false) : 'N/A'}
                  </p>
                </div>

                {/* Age */}
                {asset.minutesAgo !== null && (
                  <div>
                    <span className="text-slate-600">Updated:</span>
                    <p className="text-slate-900">{formatAge(asset.minutesAgo)}</p>
                  </div>
                )}
              </div>

              {/* Data lineage */}
              <div className="mt-3 pt-3 border-t border-slate-200">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-slate-500">Source:</span>
                  <code className="text-xs font-mono text-slate-600">
                    fhq_finn.v_{asset.ticker.toLowerCase().replace('-', '_')}_data_freshness
                  </code>
                  <span
                    className="data-lineage-indicator"
                    title={`Source view: fhq_finn.v_${asset.ticker.toLowerCase().replace('-', '_')}_data_freshness`}
                  >
                    i
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-xs text-blue-900 font-medium mb-2">Freshness Thresholds:</p>
          <div className="flex gap-4 text-xs text-blue-800">
            <span><strong>FRESH:</strong> ≤ 2h (daily)</span>
            <span><strong>STALE:</strong> 2-6h (daily)</span>
            <span><strong>OUTDATED:</strong> &gt; 6h (daily)</span>
          </div>
          <p className="text-xs text-blue-700 mt-2">
            Thresholds sourced from <code className="bg-blue-100 px-1 rounded">fhq_meta.dashboard_config</code>
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
