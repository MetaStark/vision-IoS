import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Optimize for production
  compress: true,

  // Image optimization (if needed in future)
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
  },

  // Environment variables accessible on client
  env: {
    NEXT_PUBLIC_APP_NAME: 'FHQ Market System Dashboard',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
  },

  // Experimental features
  experimental: {
    // Enable Server Actions for future write operations
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },
}

export default nextConfig
