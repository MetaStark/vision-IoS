/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable experimental features for better-sqlite3 compatibility
  experimental: {
    serverComponentsExternalPackages: ['better-sqlite3'],
  },
  // Webpack configuration for better-sqlite3
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals.push('better-sqlite3');
    }
    return config;
  },
};

module.exports = nextConfig;
