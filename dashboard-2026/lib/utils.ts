import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency
 */
export function formatCurrency(value: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Format a number with compact notation
 */
export function formatCompact(value: number): string {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    compactDisplay: 'short',
  }).format(value);
}

/**
 * Format a percentage
 */
export function formatPercent(value: number, decimals = 2): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format relative time (e.g., "5 minutes ago")
 */
export function formatRelativeTime(date: Date | string): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
}

/**
 * Get status color class based on status type
 */
export function getStatusColor(status: string): string {
  const statusLower = status.toLowerCase();
  if (['pass', 'fresh', 'safe', 'active', 'approved', 'success'].includes(statusLower)) {
    return 'text-trust-green bg-trust-green/10 border-trust-green/20';
  }
  if (['warning', 'stale', 'pending', 'medium'].includes(statusLower)) {
    return 'text-trust-yellow bg-trust-yellow/10 border-trust-yellow/20';
  }
  if (['fail', 'critical', 'error', 'blocked', 'high'].includes(statusLower)) {
    return 'text-trust-red bg-trust-red/10 border-trust-red/20';
  }
  return 'text-trust-blue bg-trust-blue/10 border-trust-blue/20';
}

/**
 * Get agent color class
 */
export function getAgentColor(agent: string): string {
  const agentColors: Record<string, string> = {
    LARS: 'text-agent-lars bg-agent-lars/10 border-agent-lars/20',
    STIG: 'text-agent-stig bg-agent-stig/10 border-agent-stig/20',
    LINE: 'text-agent-line bg-agent-line/10 border-agent-line/20',
    FINN: 'text-agent-finn bg-agent-finn/10 border-agent-finn/20',
    VEGA: 'text-agent-vega bg-agent-vega/10 border-agent-vega/20',
  };
  return agentColors[agent.toUpperCase()] || 'text-gray-400 bg-gray-400/10 border-gray-400/20';
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.slice(0, length) + '...';
}

/**
 * Generate a simple unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
