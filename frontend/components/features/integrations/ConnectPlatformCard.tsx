'use client';

/**
 * ConnectPlatformCard
 * 
 * Card for initiating connection to a new e-commerce platform.
 * Handles both OAuth (Shopify) and API key (WooCommerce) flows.
 */

import { useState } from 'react';
import Image from 'next/image';
import { EcommercePlatform, PlatformConfig } from '@/types/integration';
import { useInitOAuth } from '@/lib/hooks/use-integrations';
import { Button } from '@/components/ui';
import { WooCommerceConnectModal } from './WooCommerceConnectModal';

interface ConnectPlatformCardProps {
  platform: EcommercePlatform;
  config: PlatformConfig;
}

export function ConnectPlatformCard({ platform, config }: ConnectPlatformCardProps) {
  const [showStoreInput, setShowStoreInput] = useState(false);
  const [storeUrl, setStoreUrl] = useState('');
  const [showWooModal, setShowWooModal] = useState(false);
  
  const initOAuth = useInitOAuth();

  const handleConnect = () => {
    if (config.authType === 'api_key') {
      setShowWooModal(true);
    } else {
      setShowStoreInput(true);
    }
  };

  const handleOAuthSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!storeUrl.trim()) return;

    initOAuth.mutate({
      platform,
      store_url: storeUrl.trim(),
    });
  };

  return (
    <>
      <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
        <div className="flex items-center gap-3">
          <Image
            src={config.logo}
            alt={config.name}
            width={40}
            height={40}
            className="h-10 w-10 object-contain"
          />
          <div>
            <h3 className="font-medium text-gray-900">{config.name}</h3>
            <p className="text-sm text-gray-500">{config.description}</p>
          </div>
        </div>

        {!showStoreInput ? (
          <Button
            variant="primary"
            size="sm"
            className="mt-4 w-full"
            onClick={handleConnect}
          >
            Connect {config.name}
          </Button>
        ) : (
          <form onSubmit={handleOAuthSubmit} className="mt-4 space-y-3">
            <div>
              <label htmlFor={`store-url-${platform}`} className="sr-only">
                Store URL
              </label>
              <input
                id={`store-url-${platform}`}
                type="text"
                placeholder="yourstore.myshopify.com"
                value={storeUrl}
                onChange={(e) => setStoreUrl(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                autoFocus
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                className="flex-1"
                disabled={!storeUrl.trim() || initOAuth.isPending}
              >
                {initOAuth.isPending ? 'Connecting...' : 'Continue'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowStoreInput(false);
                  setStoreUrl('');
                }}
              >
                Cancel
              </Button>
            </div>
            {initOAuth.isError && (
              <p className="text-xs text-red-600">
                {initOAuth.error?.message || 'Failed to start connection'}
              </p>
            )}
          </form>
        )}

        <a
          href={config.docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-xs text-gray-500 hover:text-gray-700"
        >
          View setup guide →
        </a>
      </article>

      {/* WooCommerce modal */}
      {showWooModal && (
        <WooCommerceConnectModal onClose={() => setShowWooModal(false)} />
      )}
    </>
  );
}