'use client';

/**
 * Retail Observer Cinematic Page
 * ADR-024: Retail Observer Cinematic Engine
 *
 * 2026 AAA-quality visual market data visualization
 * Every frame is data-driven and auditable.
 */

import React, { useState } from 'react';
import { StateProvider, CinematicCanvas, useVisualState, useVerification } from '@/engine';

// =============================================================================
// HASH VERIFICATION PANEL (ADR-022: Dumb Glass Compliance)
// =============================================================================

function HashVerificationPanel() {
  const { vsv, loading } = useVisualState();
  const { isVerified, stateHash } = useVerification();
  const [expanded, setExpanded] = useState(false);

  if (loading || !vsv) return null;

  return (
    <div className="absolute bottom-4 left-4 z-10">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`
          px-4 py-2 rounded-lg backdrop-blur-md
          ${isVerified ? 'bg-green-900/50 border border-green-500/50' : 'bg-red-900/50 border border-red-500/50'}
          text-white text-sm font-mono
          transition-all hover:scale-105
        `}
      >
        {isVerified ? '✓' : '!'} Verified State
      </button>

      {expanded && (
        <div className="mt-2 p-4 rounded-lg bg-black/80 backdrop-blur-md border border-gray-700 max-w-md">
          <h3 className="text-white font-bold mb-2">State Verification</h3>

          <div className="space-y-2 text-xs font-mono">
            <div>
              <span className="text-gray-400">Hash:</span>
              <span className="text-green-400 ml-2 break-all">
                {stateHash?.substring(0, 32)}...
              </span>
            </div>

            <div>
              <span className="text-gray-400">Signed by:</span>
              <span className="text-cyan-400 ml-2">{vsv.signer_id}</span>
            </div>

            <div>
              <span className="text-gray-400">Mapping:</span>
              <span className="text-yellow-400 ml-2">{vsv.mapping_version}</span>
            </div>

            <div>
              <span className="text-gray-400">Timestamp:</span>
              <span className="text-white ml-2">{new Date(vsv.timestamp).toLocaleString()}</span>
            </div>

            <div>
              <span className="text-gray-400">DEFCON:</span>
              <span className={`ml-2 ${
                vsv.defcon_level === 'GREEN' ? 'text-green-400' :
                vsv.defcon_level === 'YELLOW' ? 'text-yellow-400' :
                vsv.defcon_level === 'ORANGE' ? 'text-orange-400' :
                vsv.defcon_level === 'RED' ? 'text-red-400' :
                'text-gray-400'
              }`}>
                {vsv.defcon_level}
              </span>
            </div>
          </div>

          <p className="text-gray-500 text-xs mt-4">
            Data from canonical IoS-002/003 - Not investment advice
          </p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// STATUS BADGES
// =============================================================================

function StatusBadges() {
  const { vsv, regime, defcon, events } = useVisualState();

  if (!vsv) return null;

  const regimeColors: Record<string, string> = {
    BULL: 'bg-green-500',
    BEAR: 'bg-red-500',
    RANGE: 'bg-blue-500',
    TRANSITION: 'bg-yellow-500',
    UNKNOWN: 'bg-gray-500',
  };

  const defconColors: Record<string, string> = {
    GREEN: 'bg-green-600',
    YELLOW: 'bg-yellow-500',
    ORANGE: 'bg-orange-500',
    RED: 'bg-red-600',
    BLACK: 'bg-gray-900',
  };

  return (
    <div className="absolute top-4 left-4 z-10 space-y-2">
      {/* Regime Badge */}
      <div className={`px-4 py-2 rounded-lg ${regimeColors[regime]} text-white font-bold shadow-lg`}>
        REGIME: {regime}
      </div>

      {/* DEFCON Badge */}
      <div className={`px-4 py-2 rounded-lg ${defconColors[defcon]} text-white font-bold shadow-lg`}>
        DEFCON: {defcon}
      </div>

      {/* Active Events */}
      {events.length > 0 && (
        <div className="px-4 py-2 rounded-lg bg-purple-600 text-white font-bold shadow-lg animate-pulse">
          {events.length} Active Event{events.length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// STREAM LABELS
// =============================================================================

function StreamLabels() {
  const { visuals } = useVisualState();

  const streams = [
    { label: visuals.trend_label, color: visuals.trend_color, top: '15%' },
    { label: visuals.momentum_label, color: visuals.momentum_color, top: '35%' },
    { label: visuals.volatility_label, color: visuals.volatility_color, top: '55%' },
    { label: visuals.volume_label, color: visuals.volume_color, top: '75%' },
  ];

  return (
    <div className="absolute right-4 top-0 h-full z-10 flex flex-col justify-center space-y-8">
      {streams.map((stream, i) => (
        <div
          key={i}
          className="px-3 py-1 rounded bg-black/50 backdrop-blur-sm border-l-4"
          style={{ borderLeftColor: stream.color }}
        >
          <span className="text-white text-xs font-mono">{stream.label}</span>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// ASSET SELECTOR
// =============================================================================

function AssetSelector({ assetId, onSelect }: { assetId: string; onSelect: (id: string) => void }) {
  const assets = ['BTC-USD', 'ETH-USD', 'SOL-USD'];

  return (
    <div className="absolute top-4 right-4 z-10">
      <select
        value={assetId}
        onChange={(e) => onSelect(e.target.value)}
        className="px-4 py-2 rounded-lg bg-black/70 backdrop-blur-md border border-gray-600 text-white font-mono"
      >
        {assets.map((asset) => (
          <option key={asset} value={asset}>
            {asset}
          </option>
        ))}
      </select>
    </div>
  );
}

// =============================================================================
// CINEMATIC CONTENT (inside provider)
// =============================================================================

function CinematicContent() {
  return (
    <>
      <CinematicCanvas className="w-full h-full" />
      <StatusBadges />
      <StreamLabels />
      <HashVerificationPanel />
    </>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function CinematicPage() {
  const [assetId, setAssetId] = useState('BTC-USD');

  return (
    <div className="w-screen h-screen bg-black overflow-hidden relative">
      <StateProvider initialAssetId={assetId} refreshInterval={5000}>
        <CinematicContent />
        <AssetSelector assetId={assetId} onSelect={setAssetId} />
      </StateProvider>

      {/* FjordHQ Branding */}
      <div className="absolute bottom-4 right-4 z-10 text-white/30 text-xs font-mono">
        FjordHQ Market Intelligence
        <br />
        ADR-024 Retail Observer Cinematic Engine
      </div>
    </div>
  );
}
