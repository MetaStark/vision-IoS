/**
 * Market Data Page - Vision-IoS Dashboard
 * Price charts and indicators (IoS-001 Market Pulse)
 *
 * Data Lineage:
 * - fhq_data.price_series
 * - fhq_data.tickers
 * - fhq_validation.data_freshness
 */

import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getTickers, getPriceData, getDataFreshness, getLatestPrice } from '@/lib/data';
import { formatCurrency, formatRelativeTime, cn } from '@/lib/utils';
import { Suspense } from 'react';

export const dynamic = 'force-dynamic';

async function AssetOverview() {
  const tickers = await getTickers();
  const prices = await Promise.all(
    tickers.slice(0, 5).map(async (t) => {
      const price = await getLatestPrice(t.ticker);
      const freshness = await getDataFreshness(t.ticker);
      return {
        ...t,
        price,
        freshness: freshness[0],
      };
    })
  );

  return (
    <Card
      title="Asset Overview"
      subtitle="Live prices and freshness"
      lineage={['fhq_data.price_series', 'fhq_data.tickers', 'fhq_validation.data_freshness']}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Class</th>
              <th>Price</th>
              <th>Change</th>
              <th>Data Status</th>
            </tr>
          </thead>
          <tbody>
            {prices.map((asset) => {
              const priceChange = asset.price
                ? ((asset.price.close - asset.price.open) / asset.price.open)
                : 0;
              const isPositive = priceChange >= 0;

              return (
                <tr key={asset.ticker}>
                  <td>
                    <div>
                      <span className="font-medium text-white">{asset.ticker}</span>
                      <span className="text-xs text-gray-500 ml-2">{asset.name}</span>
                    </div>
                  </td>
                  <td>
                    <span className="text-xs text-gray-400 uppercase">{asset.assetClass}</span>
                  </td>
                  <td>
                    <span className="font-mono text-white">
                      {asset.price ? formatCurrency(asset.price.close) : '-'}
                    </span>
                  </td>
                  <td>
                    <span className={cn(
                      'font-medium',
                      isPositive ? 'text-trust-green' : 'text-trust-red'
                    )}>
                      {isPositive ? '+' : ''}{(priceChange * 100).toFixed(2)}%
                    </span>
                  </td>
                  <td>
                    <StatusBadge
                      status={asset.freshness?.status || 'UNKNOWN'}
                      size="sm"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

async function PriceChart({ ticker = 'BTC-USD' }: { ticker?: string }) {
  const priceData = await getPriceData(ticker, '1d', 30);

  if (priceData.length === 0) {
    return (
      <Card title={`${ticker} Price Chart`}>
        <p className="text-gray-400">No price data available</p>
      </Card>
    );
  }

  // Reverse to get chronological order
  const chartData = [...priceData].reverse();
  const minPrice = Math.min(...chartData.map(p => p.low));
  const maxPrice = Math.max(...chartData.map(p => p.high));
  const priceRange = maxPrice - minPrice;

  // Simple SVG chart
  const width = 600;
  const height = 200;
  const padding = 40;

  const getX = (index: number) => padding + (index / (chartData.length - 1)) * (width - 2 * padding);
  const getY = (price: number) => height - padding - ((price - minPrice) / priceRange) * (height - 2 * padding);

  const linePath = chartData
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.close)}`)
    .join(' ');

  return (
    <Card
      title={`${ticker} Price Chart`}
      subtitle="Last 30 days"
      lineage={['fhq_data.price_series']}
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding + ratio * (height - 2 * padding);
          const price = maxPrice - ratio * priceRange;
          return (
            <g key={ratio}>
              <line
                x1={padding}
                y1={y}
                x2={width - padding}
                y2={y}
                stroke="#374151"
                strokeDasharray="4,4"
              />
              <text
                x={padding - 8}
                y={y + 4}
                textAnchor="end"
                className="text-xs fill-gray-500"
              >
                {formatCurrency(price).replace('$', '')}
              </text>
            </g>
          );
        })}

        {/* Price line */}
        <path
          d={linePath}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
        />

        {/* Area fill */}
        <path
          d={`${linePath} L ${getX(chartData.length - 1)} ${height - padding} L ${getX(0)} ${height - padding} Z`}
          fill="url(#gradient)"
          opacity={0.2}
        />

        {/* Gradient definition */}
        <defs>
          <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* Data points */}
        {chartData.map((p, i) => (
          <circle
            key={i}
            cx={getX(i)}
            cy={getY(p.close)}
            r={3}
            fill="#3b82f6"
            className="opacity-0 hover:opacity-100 transition-opacity"
          />
        ))}
      </svg>

      {/* Price summary */}
      <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-fjord-700">
        <div>
          <span className="text-xs text-gray-400">Current</span>
          <p className="text-lg font-semibold text-white">
            {formatCurrency(chartData[chartData.length - 1]?.close || 0)}
          </p>
        </div>
        <div>
          <span className="text-xs text-gray-400">High (30d)</span>
          <p className="text-lg font-semibold text-trust-green">
            {formatCurrency(maxPrice)}
          </p>
        </div>
        <div>
          <span className="text-xs text-gray-400">Low (30d)</span>
          <p className="text-lg font-semibold text-trust-red">
            {formatCurrency(minPrice)}
          </p>
        </div>
        <div>
          <span className="text-xs text-gray-400">Range</span>
          <p className="text-lg font-semibold text-white">
            {formatCurrency(priceRange)}
          </p>
        </div>
      </div>
    </Card>
  );
}

async function DataFreshnessTable() {
  const freshness = await getDataFreshness();

  return (
    <Card
      title="Data Freshness"
      subtitle="All assets and resolutions"
      lineage={['fhq_validation.data_freshness']}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Resolution</th>
              <th>Last Update</th>
              <th>Freshness</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {freshness.map((f) => (
              <tr key={`${f.ticker}-${f.resolution}`}>
                <td className="font-medium text-white">{f.ticker}</td>
                <td className="font-mono text-gray-400">{f.resolution}</td>
                <td className="text-gray-400">
                  {f.lastDataPoint ? formatRelativeTime(f.lastDataPoint) : '-'}
                </td>
                <td className="text-gray-400">{f.freshnessMinutes}m</td>
                <td>
                  <StatusBadge status={f.status} size="sm" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function MarketDataPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Market Data</h1>
        <p className="text-gray-400 mt-1">
          IoS-001 Market Pulse - Price charts, indicators, and data freshness
        </p>
      </div>

      {/* Asset Overview */}
      <Suspense fallback={<SkeletonCard />}>
        <AssetOverview />
      </Suspense>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Suspense fallback={<SkeletonCard />}>
          <PriceChart ticker="BTC-USD" />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <DataFreshnessTable />
        </Suspense>
      </div>
    </div>
  );
}
