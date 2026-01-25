/**
 * Mechanism Panel - CEO-DIR-2026-057
 * "How Did We Learn It?" - One-line causality for each learning item
 *
 * Shows Signal -> Reasoning -> Test -> Outcome chain
 * Makes Serper + LLM usage visible and justified
 */

'use client'

import { ArrowRight, Search, Brain, FlaskConical, CheckCircle } from 'lucide-react'

export interface LearningMechanism {
  id: string
  signal: string
  signalSource: 'serper' | 'llm' | 'database' | 'market_data'
  reasoning: string
  test: string
  outcome: string
  outcomeStatus: 'success' | 'partial' | 'pending'
}

interface MechanismPanelProps {
  mechanisms: LearningMechanism[]
}

const SOURCE_ICONS = {
  serper: Search,
  llm: Brain,
  database: FlaskConical,
  market_data: FlaskConical,
}

const SOURCE_LABELS = {
  serper: 'Serper',
  llm: 'LLM',
  database: 'Database',
  market_data: 'Market',
}

const SOURCE_COLORS = {
  serper: 'text-purple-400',
  llm: 'text-blue-400',
  database: 'text-green-400',
  market_data: 'text-yellow-400',
}

const OUTCOME_COLORS = {
  success: 'text-green-400',
  partial: 'text-yellow-400',
  pending: 'text-gray-400',
}

export function MechanismPanel({ mechanisms }: MechanismPanelProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">
            How Did We Learn It?
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Causality Chain | Signal → Reasoning → Test → Outcome
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Search className="h-3 w-3 text-purple-400" /> Serper
          </span>
          <span className="flex items-center gap-1">
            <Brain className="h-3 w-3 text-blue-400" /> LLM
          </span>
        </div>
      </div>

      {/* Mechanism List */}
      <div className="space-y-4">
        {mechanisms.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Brain className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No learning mechanisms recorded today</p>
          </div>
        ) : (
          mechanisms.map((mech) => {
            const SourceIcon = SOURCE_ICONS[mech.signalSource]
            const sourceColor = SOURCE_COLORS[mech.signalSource]
            const outcomeColor = OUTCOME_COLORS[mech.outcomeStatus]

            return (
              <div
                key={mech.id}
                className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4"
              >
                {/* Chain visualization */}
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Signal */}
                  <div className="flex items-center gap-1.5 bg-gray-900 px-3 py-1.5 rounded">
                    <SourceIcon className={`h-4 w-4 ${sourceColor}`} />
                    <span className="text-xs text-gray-300 max-w-[200px] truncate">
                      {mech.signal}
                    </span>
                  </div>

                  <ArrowRight className="h-4 w-4 text-gray-600 flex-shrink-0" />

                  {/* Reasoning */}
                  <div className="flex items-center gap-1.5 bg-gray-900 px-3 py-1.5 rounded">
                    <Brain className="h-4 w-4 text-blue-400" />
                    <span className="text-xs text-gray-300 max-w-[200px] truncate">
                      {mech.reasoning}
                    </span>
                  </div>

                  <ArrowRight className="h-4 w-4 text-gray-600 flex-shrink-0" />

                  {/* Test */}
                  <div className="flex items-center gap-1.5 bg-gray-900 px-3 py-1.5 rounded">
                    <FlaskConical className="h-4 w-4 text-yellow-400" />
                    <span className="text-xs text-gray-300 max-w-[150px] truncate">
                      {mech.test}
                    </span>
                  </div>

                  <ArrowRight className="h-4 w-4 text-gray-600 flex-shrink-0" />

                  {/* Outcome */}
                  <div className="flex items-center gap-1.5 bg-gray-900 px-3 py-1.5 rounded">
                    <CheckCircle className={`h-4 w-4 ${outcomeColor}`} />
                    <span className={`text-xs font-medium ${outcomeColor}`}>
                      {mech.outcome}
                    </span>
                  </div>
                </div>

                {/* Source badge */}
                <div className="mt-2 flex items-center gap-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full bg-gray-900 ${sourceColor}`}>
                    {SOURCE_LABELS[mech.signalSource]}
                  </span>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-800">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>{mechanisms.length} mechanisms traced</span>
          <span>Source: fhq_governance.learning_mechanism_log</span>
        </div>
      </div>
    </div>
  )
}
