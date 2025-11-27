import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  lineage?: string[];
  action?: ReactNode;
}

export function Card({ children, className, title, subtitle, lineage, action }: CardProps) {
  return (
    <div className={cn(
      'bg-fjord-800 border border-fjord-700 rounded-lg overflow-hidden',
      className
    )}>
      {(title || action) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-fjord-700">
          <div>
            {title && <h3 className="font-medium text-white">{title}</h3>}
            {subtitle && <p className="text-sm text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-2">
            {lineage && lineage.length > 0 && (
              <DataLineageIndicator sources={lineage} />
            )}
            {action}
          </div>
        </div>
      )}
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}

interface DataLineageIndicatorProps {
  sources: string[];
}

export function DataLineageIndicator({ sources }: DataLineageIndicatorProps) {
  return (
    <div className="group relative">
      <button className="p-1.5 rounded hover:bg-fjord-700 text-gray-400 hover:text-white transition-colors">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>
      <div className="absolute right-0 top-full mt-1 w-64 p-3 bg-fjord-900 border border-fjord-600 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
        <p className="text-xs font-medium text-gray-400 mb-2">Data Lineage</p>
        <ul className="space-y-1">
          {sources.map((source, i) => (
            <li key={i} className="text-xs text-gray-300 font-mono">
              {source}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
