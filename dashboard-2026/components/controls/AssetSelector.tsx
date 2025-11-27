/**
 * Asset Selector Component (Sprint 1.3)
 * Switch between BTC-USD, ETH-USD, GSPC
 * Bloomberg-minimal button group design
 * MBB-grade: Clear selection state + accessibility
 */

'use client'

import { cn } from '@/lib/utils/cn'

export type Asset = 'BTC-USD' | 'ETH-USD' | 'GSPC'

export interface AssetConfig {
  ticker: Asset
  name: string
  listingId: string
}

export const AVAILABLE_ASSETS: AssetConfig[] = [
  { ticker: 'BTC-USD', name: 'Bitcoin', listingId: 'LST_BTC_XCRYPTO' },
  { ticker: 'ETH-USD', name: 'Ethereum', listingId: 'LST_ETH_XCRYPTO' },
  { ticker: 'GSPC', name: 'S&P 500', listingId: 'LST_GSPC_XNYS' },
]

interface AssetSelectorProps {
  selectedAsset: Asset
  onAssetChange: (asset: Asset) => void
  className?: string
}

/**
 * Asset Selector Component
 * Minimal button group for asset switching
 * Visual hierarchy: Active state clearly distinguished
 */
export function AssetSelector({
  selectedAsset,
  onAssetChange,
  className,
}: AssetSelectorProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-sm text-slate-600 mr-2">Asset:</span>
      <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
        {AVAILABLE_ASSETS.map((asset) => (
          <button
            key={asset.ticker}
            onClick={() => onAssetChange(asset.ticker)}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-md transition-all',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
              selectedAsset === asset.ticker
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
            )}
            aria-pressed={selectedAsset === asset.ticker}
            aria-label={`Select ${asset.name}`}
          >
            {asset.ticker}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Get asset config by ticker
 */
export function getAssetConfig(ticker: Asset): AssetConfig {
  return AVAILABLE_ASSETS.find((a) => a.ticker === ticker) || AVAILABLE_ASSETS[0]
}
