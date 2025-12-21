/**
 * ACI Triangle Dedicated Page
 * CEO Directive CEO-ACI-TRIANGLE-2025-12-21
 *
 * Standalone view for ACI Constraint Triangle telemetry
 */

import { ACITrianglePanel } from '@/components/dashboard/ACITrianglePanel'

export default function ACITrianglePage() {
  return (
    <main className="min-h-screen bg-black p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">ACI Constraint Triangle</h1>
            <p className="text-sm text-gray-500">
              Cognitive Governance Shadow Evaluation | Crypto Assets Only
            </p>
          </div>
          <a
            href="/dashboard"
            className="px-4 py-2 text-sm bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 transition-colors"
          >
            Back to Dashboard
          </a>
        </div>

        {/* ACI Triangle Panel */}
        <ACITrianglePanel />

        {/* Documentation */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">ACI Triangle Documentation</h2>

          <div className="grid grid-cols-3 gap-6 text-sm">
            {/* EC-020 */}
            <div className="space-y-2">
              <h3 className="font-medium text-purple-400">EC-020 SitC</h3>
              <p className="text-gray-400">
                <strong>Show-in-the-Chain</strong> ensures reasoning chain integrity.
                Every golden needle must have a valid chain_of_query_hash proving
                the hypothesis followed a structured reasoning process.
              </p>
              <ul className="text-gray-500 space-y-1">
                <li>• Validates chain_of_query_hash exists</li>
                <li>• Checks node completion (≥80%)</li>
                <li>• Detects circular reasoning</li>
              </ul>
            </div>

            {/* EC-021 */}
            <div className="space-y-2">
              <h3 className="font-medium text-green-400">EC-021 InForage</h3>
              <p className="text-gray-400">
                <strong>Information Foraging</strong> enforces API budget discipline.
                Tracks cost per needle and prevents budget overruns during
                autonomous research operations.
              </p>
              <ul className="text-gray-500 space-y-1">
                <li>• Daily budget cap: $50</li>
                <li>• Tracks API calls per needle</li>
                <li>• Monitors budget pressure %</li>
              </ul>
            </div>

            {/* EC-022 */}
            <div className="space-y-2">
              <h3 className="font-medium text-blue-400">EC-022 IKEA</h3>
              <p className="text-gray-400">
                <strong>Integrity Knowledge Evidence Audit</strong> is the
                hallucination firewall. Detects fabricated data, stale references,
                and unverifiable claims in hypotheses.
              </p>
              <ul className="text-gray-500 space-y-1">
                <li>• Fabrication detection</li>
                <li>• Stale data flagging (>24h)</li>
                <li>• Verifiability scoring</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-800">
            <p className="text-xs text-gray-600">
              Mode: SHADOW (evaluate and log, do not block) |
              CEO Directive: CEO-ACI-TRIANGLE-2025-12-21 |
              Run evaluation: <code className="bg-gray-800 px-1 rounded">python aci_triangle_shadow.py --evaluate</code>
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
