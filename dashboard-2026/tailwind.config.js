/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // FjordHQ Brand Colors
        fjord: {
          900: '#0a0f1c',
          800: '#111827',
          700: '#1f2937',
          600: '#374151',
          500: '#6b7280',
        },
        // Trust indicator colors
        trust: {
          green: '#10b981',
          yellow: '#f59e0b',
          red: '#ef4444',
          blue: '#3b82f6',
        },
        // Agent colors
        agent: {
          lars: '#8b5cf6',   // Purple - Strategy
          stig: '#06b6d4',   // Cyan - Technical
          line: '#22c55e',   // Green - Data
          finn: '#f97316',   // Orange - Intelligence
          vega: '#ec4899',   // Pink - Governance
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
    },
  },
  plugins: [],
};
