import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: 'standalone',
  devIndicators: false,
  
  // FIXED: Allow images from both HTTP and HTTPS sources
  images: {
    remotePatterns: [
      // Allow HTTPS images from any source
      {
        protocol: 'https',
        hostname: '**',
      },
      // ADDED: Allow HTTP images (for local WooCommerce stores without SSL)
      {
        protocol: 'http',
        hostname: '**',
      },
    ],
    // Fallback for older Next.js versions or specific domains
    // domains: ['bestbuy.com', 'amazon.com', 'walmart.com', 'target.com'],
    
    // ADDED: Disable strict domain checking for external images
    dangerouslyAllowSVG: true,
    contentDispositionType: 'attachment',
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },
  
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            // FIXED: Added Ethereum RPC endpoints to connect-src for wallet balance reading
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https: http:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' http://localhost:* ws://localhost:* https://*.railway.app https://*.sentry.io wss://*.railway.app https://*.walletconnect.org https://*.walletconnect.com https://api.web3modal.org https://pulse.walletconnect.org https://rpc.sepolia.org https://eth.merkle.io https://*.infura.io https://*.alchemy.com https://cloudflare-eth.com https://ethereum.publicnode.com https://sepolia.publicnode.com; frame-ancestors 'none';",
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
        ],
      },
    ];
  },
  
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
};

const sentryWebpackPluginOptions = {
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
};

const config = process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, sentryWebpackPluginOptions)
  : nextConfig;

export default config;



