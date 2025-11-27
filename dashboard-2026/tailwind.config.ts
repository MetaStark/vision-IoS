import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Institution-grade color palette (MBB-inspired)
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6', // Main brand blue
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // Status colors
        status: {
          fresh: '#10b981',    // Green
          stale: '#f59e0b',    // Orange
          outdated: '#ef4444', // Red
          pass: '#22c55e',     // Success green
          fail: '#dc2626',     // Fail red
          warning: '#eab308',  // Warning yellow
          info: '#3b82f6',     // Info blue
        },
        // FINN Quality tiers
        finn: {
          platinum: '#9333ea',
          gold: '#eab308',
          silver: '#6b7280',
          bronze: '#cd7f32',
          failing: '#dc2626',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'Fira Code',
          'monospace',
        ],
      },
      fontSize: {
        // Typography scale for institutional clarity
        'display': ['2.5rem', { lineHeight: '3rem', fontWeight: '700' }],
        'heading-1': ['2rem', { lineHeight: '2.5rem', fontWeight: '600' }],
        'heading-2': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        'heading-3': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '500' }],
        'body': ['1rem', { lineHeight: '1.5rem', fontWeight: '400' }],
        'caption': ['0.875rem', { lineHeight: '1.25rem', fontWeight: '400' }],
        'label': ['0.75rem', { lineHeight: '1rem', fontWeight: '500' }],
      },
      spacing: {
        // Consistent spacing scale
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      borderRadius: {
        'card': '0.5rem',
        'panel': '0.75rem',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'panel': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      },
    },
  },
  plugins: [],
}

export default config
