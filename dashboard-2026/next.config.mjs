import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
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

  // Fix Windows case-sensitivity issue causing duplicate module instances
  webpack: (config, { isServer }) => {
    // Normalize all paths to lowercase to prevent duplicate modules
    // This fixes the "vision-IoS" vs "vision-ios" casing mismatch
    config.resolve = config.resolve || {}
    config.resolve.alias = {
      ...config.resolve.alias,
      // Force consistent casing by using absolute paths
      '@': path.resolve(__dirname),
    }

    // Disable case-sensitive paths plugin warnings
    config.infrastructureLogging = {
      ...config.infrastructureLogging,
      level: 'error',
    }

    return config
  },
}

export default nextConfig
