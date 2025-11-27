/**
 * Root Layout for Vision-IoS Dashboard
 * Implements ADR-005 Human Interaction Layer
 */

import type { Metadata } from 'next';
import './globals.css';
import { Navigation } from '@/components/Navigation';
import { TrustBanner, TrustBannerSkeleton } from '@/components/TrustBanner';
import { getSystemHealth } from '@/lib/data';
import { Suspense } from 'react';

export const metadata: Metadata = {
  title: 'Vision-IoS Dashboard 2026',
  description: 'The only authorized human interface to FjordHQ (ADR-005)',
};

async function TrustBannerWrapper() {
  try {
    const systemHealth = await getSystemHealth();
    return <TrustBanner systemHealth={systemHealth} />;
  } catch (error) {
    console.error('Failed to load system health:', error);
    return <TrustBannerSkeleton />;
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-fjord-900 text-white">
        {/* Navigation */}
        <Navigation />

        {/* Trust Banner */}
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Suspense fallback={<TrustBannerSkeleton />}>
            <TrustBannerWrapper />
          </Suspense>
        </div>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 pb-8">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t border-fjord-700 mt-8 py-4">
          <div className="max-w-7xl mx-auto px-4 flex items-center justify-between text-xs text-gray-500">
            <div className="flex items-center gap-4">
              <span>Vision-IoS Dashboard 2026</span>
              <span>|</span>
              <span>ADR-005 Human Interaction Layer</span>
            </div>
            <div className="flex items-center gap-4">
              <span>CEO-Only Access</span>
              <span>|</span>
              <span>VEGA Governed</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
