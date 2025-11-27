/**
 * Agent Chat Component (IoS-006 Research Workspace)
 * CEO can interact with agents: LARS, FINN, STIG, LINE, VEGA
 *
 * ADR-005 Section 7 Constraints:
 * - Every message bound to target agent
 * - Logged with CEO identity, agent, timestamp, task type
 * - Messages routed via Orchestrator (not direct LLM calls)
 * - Subject to VEGA economic safety (ADR-012)
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { cn, getAgentColor, formatRelativeTime, generateId } from '@/lib/utils';
import { StatusBadge } from './ui/StatusBadge';

interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  capabilities: string[];
}

const AGENTS: Agent[] = [
  {
    id: 'LARS',
    name: 'LARS',
    role: 'Chief Strategy & Alpha Officer',
    description: 'Strategic analysis and scenario framing',
    capabilities: ['Strategy analysis', 'Scenario planning', 'Capital calibration', 'Risk assessment'],
  },
  {
    id: 'FINN',
    name: 'FINN',
    role: 'Financial Intelligence & Narrative Navigator',
    description: 'Research, intelligence synthesis, CDS and narrative coherence',
    capabilities: ['Market research', 'CDS analysis', 'Narrative synthesis', 'Event intelligence'],
  },
  {
    id: 'STIG',
    name: 'STIG',
    role: 'Schema, Technical & Infrastructure Guardian',
    description: 'Technical feasibility and schema/governance checks',
    capabilities: ['Technical validation', 'Schema review', 'Infrastructure checks', 'DDL rules'],
  },
  {
    id: 'LINE',
    name: 'LINE',
    role: 'Lineage & Ingestion Engine',
    description: 'SRE/state-of-pipelines, ingestion health, drift',
    capabilities: ['Data ingestion', 'Pipeline status', 'Freshness monitoring', 'Drift detection'],
  },
  {
    id: 'VEGA',
    name: 'VEGA',
    role: 'Governance Engine',
    description: 'Governance, risk classification, compliance explanations',
    capabilities: ['Governance checks', 'Risk classification', 'ADR compliance', 'Economic safety'],
  },
];

interface Message {
  id: string;
  chatId: string;
  role: 'CEO' | 'LARS' | 'FINN' | 'STIG' | 'LINE' | 'VEGA';
  content: string;
  taskType?: 'research' | 'analysis' | 'operational' | 'governance';
  linkedTaskId?: string;
  createdAt: string;
}

interface AgentChatProps {
  initialAgent?: string;
  onTaskCreated?: (task: any) => void;
}

export function AgentChat({ initialAgent = 'LARS', onTaskCreated }: AgentChatProps) {
  const [selectedAgent, setSelectedAgent] = useState<Agent>(
    AGENTS.find(a => a.id === initialAgent) || AGENTS[0]
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [taskType, setTaskType] = useState<Message['taskType']>('research');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatId = useRef(generateId());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: generateId(),
      chatId: chatId.current,
      role: 'CEO',
      content: input.trim(),
      taskType,
      createdAt: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Create orchestrator task
      const taskId = generateId();
      const task = {
        taskId,
        taskType,
        targetAgent: selectedAgent.id,
        action: 'chat_response',
        parameters: JSON.stringify({
          message: userMessage.content,
          chatId: chatId.current,
          messageId: userMessage.id,
        }),
        requestedBy: 'CEO',
        status: 'PENDING',
        createdAt: new Date().toISOString(),
      };

      // Call API to save message and create task
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          task,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();

      // Add agent response
      const agentMessage: Message = {
        id: generateId(),
        chatId: chatId.current,
        role: selectedAgent.id as Message['role'],
        content: data.response || getDefaultResponse(selectedAgent.id, userMessage.content, taskType),
        taskType,
        linkedTaskId: taskId,
        createdAt: new Date().toISOString(),
      };

      setMessages(prev => [...prev, agentMessage]);
      onTaskCreated?.(task);

    } catch (error) {
      console.error('Chat error:', error);
      // Add error response
      const errorMessage: Message = {
        id: generateId(),
        chatId: chatId.current,
        role: selectedAgent.id as Message['role'],
        content: `[System: Unable to process request. Error logged for review.]`,
        createdAt: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAgentChange = (agent: Agent) => {
    setSelectedAgent(agent);
    // Start new chat session when changing agent
    chatId.current = generateId();
    setMessages([]);
  };

  return (
    <div className="flex h-[600px] bg-fjord-800 border border-fjord-700 rounded-lg overflow-hidden">
      {/* Agent Sidebar */}
      <div className="w-64 border-r border-fjord-700 flex flex-col">
        <div className="p-4 border-b border-fjord-700">
          <h3 className="font-medium text-white">Agents</h3>
          <p className="text-xs text-gray-500 mt-1">IoS-006 Research Workspace</p>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              onClick={() => handleAgentChange(agent)}
              className={cn(
                'w-full text-left p-3 rounded-lg transition-all',
                selectedAgent.id === agent.id
                  ? 'bg-fjord-700 border border-fjord-600'
                  : 'hover:bg-fjord-700/50'
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <StatusBadge status={agent.id} size="sm" variant="agent" />
                <span className="font-medium text-white">{agent.name}</span>
              </div>
              <p className="text-xs text-gray-400 line-clamp-2">{agent.description}</p>
            </button>
          ))}
        </div>

        {/* Task Type Selector */}
        <div className="p-3 border-t border-fjord-700">
          <label className="text-xs text-gray-400 block mb-2">Task Type</label>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value as Message['taskType'])}
            className="w-full bg-fjord-700 border border-fjord-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-trust-blue"
          >
            <option value="research">Research</option>
            <option value="analysis">Analysis</option>
            <option value="operational">Operational</option>
            <option value="governance">Governance</option>
          </select>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Agent Header */}
        <div className="p-4 border-b border-fjord-700 bg-fjord-800/50">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <StatusBadge status={selectedAgent.id} size="md" variant="agent" />
                <h3 className="font-medium text-white">{selectedAgent.name}</h3>
              </div>
              <p className="text-sm text-gray-400 mt-1">{selectedAgent.role}</p>
            </div>
            <div className="text-right text-xs text-gray-500">
              <p>Chat ID: {chatId.current.slice(0, 8)}...</p>
              <p>Routed via Orchestrator</p>
            </div>
          </div>

          {/* Capabilities */}
          <div className="flex flex-wrap gap-1 mt-3">
            {selectedAgent.capabilities.map((cap) => (
              <span
                key={cap}
                className="px-2 py-0.5 bg-fjord-700 rounded text-xs text-gray-400"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className={cn(
                'w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center',
                getAgentColor(selectedAgent.id).replace('text-', 'bg-').replace('/10', '/20')
              )}>
                <span className="text-2xl font-bold">{selectedAgent.id[0]}</span>
              </div>
              <h4 className="text-white font-medium mb-2">Start a conversation with {selectedAgent.name}</h4>
              <p className="text-sm text-gray-400 max-w-md mx-auto">
                {selectedAgent.description}. All messages are logged and routed through the Orchestrator per ADR-005.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'flex',
                  message.role === 'CEO' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[80%] rounded-lg p-3',
                    message.role === 'CEO'
                      ? 'bg-trust-blue/20 border border-trust-blue/30'
                      : 'bg-fjord-700 border border-fjord-600'
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <StatusBadge
                      status={message.role}
                      size="sm"
                      variant={message.role === 'CEO' ? 'status' : 'agent'}
                    />
                    <span className="text-xs text-gray-500">
                      {formatRelativeTime(message.createdAt)}
                    </span>
                    {message.taskType && (
                      <span className="text-xs text-gray-600 px-1.5 py-0.5 bg-fjord-800 rounded">
                        {message.taskType}
                      </span>
                    )}
                  </div>
                  <p className="text-white text-sm whitespace-pre-wrap">{message.content}</p>
                  {message.linkedTaskId && (
                    <p className="text-xs text-gray-500 mt-2">
                      Task: {message.linkedTaskId.slice(0, 8)}...
                    </p>
                  )}
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-fjord-700 border border-fjord-600 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedAgent.id} size="sm" variant="agent" />
                  <span className="text-sm text-gray-400">Thinking...</span>
                </div>
                <div className="flex gap-1 mt-2">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-fjord-700">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder={`Ask ${selectedAgent.name}...`}
              className="flex-1 bg-fjord-700 border border-fjord-600 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-trust-blue"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className={cn(
                'px-4 py-2 rounded-lg font-medium transition-colors',
                input.trim() && !isLoading
                  ? 'bg-trust-blue text-white hover:bg-trust-blue/80'
                  : 'bg-fjord-700 text-gray-500 cursor-not-allowed'
              )}
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Messages logged per ADR-002 | VEGA economic safety active (ADR-012)
          </p>
        </div>
      </div>
    </div>
  );
}

// Default responses when API is not connected
function getDefaultResponse(agentId: string, message: string, taskType?: string): string {
  const responses: Record<string, string> = {
    LARS: `[LARS Analysis]\n\nI've received your ${taskType || 'research'} request. Based on the current market context and governance state:\n\n1. Request logged to Orchestrator\n2. Task queued for processing\n3. Economic safety constraints verified (ADR-012)\n\nNote: Full agent integration pending. This is a placeholder response demonstrating the ADR-005 chat workflow.`,
    FINN: `[FINN Intelligence]\n\nYour inquiry has been registered. Current CDS metrics and narrative analysis:\n\n- Request type: ${taskType || 'research'}\n- Routing: Orchestrator → FINN\n- Compliance: ADR-005, ADR-012\n\nNote: Real-time FINN integration pending. Response demonstrates IoS-006 chat structure.`,
    STIG: `[STIG Technical Review]\n\nTechnical validation request received:\n\n- Schema compliance: Pending verification\n- DDL rules: Active\n- Gate status: G0-G4 operational\n\nNote: Full STIG integration pending. This demonstrates ADR-005 compliant messaging.`,
    LINE: `[LINE Ingestion Status]\n\nPipeline status inquiry logged:\n\n- Data freshness: Monitored\n- Ingestion health: Active\n- Drift detection: Enabled\n\nNote: LINE agent integration pending. Chat workflow per ADR-005 Section 7.`,
    VEGA: `[VEGA Governance Response]\n\nGovernance inquiry received and logged:\n\n- ADR compliance: Verified\n- Economic safety: Active (ADR-012)\n- Risk classification: Pending\n\nAll actions subject to CEO approval per ADR-005 Section 5.1. Full VEGA integration pending.`,
  };

  return responses[agentId] || '[System] Agent response pending.';
}
