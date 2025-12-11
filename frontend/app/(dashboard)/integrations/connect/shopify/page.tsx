'use client';

/**
 * Shopify Connect Page
 * 
 * Allows users to enter their Shopify store URL to initiate OAuth.
 * Validates the store URL format and redirects to Shopify authorization.
 * 
 * URL: /integrations/connect/shopify
 */

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useInitOAuth } from '@/lib/hooks/use-integrations';

// ==================== Types ====================

interface FormErrors {
  store_url?: string;
  general?: string;
}

// ==================== Component ====================

export default function ShopifyConnectPage() {

  const initOAuth = useInitOAuth();
  
  const [storeUrl, setStoreUrl] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});

  /**
   * Validate store URL format
   * Accepts: mystore.myshopify.com or mystore
   */
  const validateStoreUrl = (url: string): string | null => {
    const trimmed = url.trim().toLowerCase();
    
    if (!trimmed) {
      return 'Please enter your Shopify store URL';
    }

    // Remove protocol if present
    const cleaned = storeUrl.trim().toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/\.myshopify\.com.*$/, '');

    // Check for valid Shopify domain patterns
    const shopifyPattern = /^[\w-]+\.myshopify\.com$/;
    const simplePattern = /^[\w-]+$/;

    if (!shopifyPattern.test(cleaned) && !simplePattern.test(cleaned)) {
      return 'Please enter a valid Shopify store URL (e.g., mystore.myshopify.com)';
    }

    return null;
  };

  /**
   * Normalize store URL to consistent format
   */
  const normalizeStoreUrl = (url: string): string => {
    let cleaned = url.trim().toLowerCase()
      .replace(/^https?:\/\//, '')
      .replace(/\/$/, '');

    // Add .myshopify.com if not present
    if (!cleaned.includes('.myshopify.com')) {
      cleaned = `${cleaned}.myshopify.com`;
    }

    return cleaned;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    // Validate
    const validationError = validateStoreUrl(storeUrl);
    if (validationError) {
      setErrors({ store_url: validationError });
      return;
    }

    // Normalize URL
    const normalizedUrl = normalizeStoreUrl(storeUrl);

    // Initiate OAuth
    try {
      await initOAuth.mutateAsync({
        platform: 'shopify',
        store_url: normalizedUrl,
      });
      // useInitOAuth handles the redirect to Shopify
    } catch (err) {
      console.error('OAuth init error:', err);
      
      let errorMessage = 'Failed to connect. Please try again.';
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      
      setErrors({ general: errorMessage });
    }
  };

  /**
   * Handle input change with live validation clearing
   */
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStoreUrl(e.target.value);
    if (errors.store_url) {
      setErrors((prev) => ({ ...prev, store_url: undefined }));
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      {/* Back link */}
      <Link
        href="/integrations"
        className="mb-6 inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
      >
        <BackArrowIcon />
        <span className="ml-1">Back to Integrations</span>
      </Link>

      {/* Main card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Image
            src="/logos/shopify.svg"
            alt="Shopify"
            width={48}
            height={48}
            className="h-12 w-12"
          />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Connect Shopify
            </h1>
            <p className="text-sm text-gray-500">
              Link your Shopify store to sync products
            </p>
          </div>
        </div>

        {/* Features list */}
        <div className="mt-6 rounded-md bg-gray-50 p-4">
          <h3 className="text-sm font-medium text-gray-700">
            What {"you'"}ll get:
          </h3>
          <ul className="mt-2 space-y-2 text-sm text-gray-600">
            <li className="flex items-start gap-2">
              <CheckIcon />
              <span>Automatic product sync from your store</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckIcon />
              <span>Real-time updates via webhooks</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckIcon />
              <span>Push price changes directly to Shopify</span>
            </li>
          </ul>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {/* General error */}
          {errors.general && (
            <div className="rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-700">{errors.general}</p>
            </div>
          )}

          {/* Store URL input */}
          <div>
            <label
              htmlFor="store_url"
              className="block text-sm font-medium text-gray-700"
            >
              Store URL
            </label>
            <div className="mt-1">
              <input
                id="store_url"
                type="text"
                value={storeUrl}
                onChange={handleInputChange}
                placeholder="mystore.myshopify.com"
                className={`
                  block w-full rounded-md border px-3 py-2 shadow-sm
                  placeholder:text-gray-400
                  focus:outline-none focus:ring-2 focus:ring-offset-0
                  ${
                    errors.store_url
                      ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                      : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                  }
                `}
                disabled={initOAuth.isPending}
              />
            </div>
            {errors.store_url && (
              <p className="mt-1 text-sm text-red-600">{errors.store_url}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              Enter your store name (e.g., mystore) or full URL
            </p>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={initOAuth.isPending || !storeUrl.trim()}
            className={`
              w-full rounded-md px-4 py-2.5 text-sm font-medium text-white
              focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2
              ${
                initOAuth.isPending || !storeUrl.trim()
                  ? 'cursor-not-allowed bg-indigo-400'
                  : 'bg-indigo-600 hover:bg-indigo-700'
              }
            `}
          >
            {initOAuth.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <LoadingSpinner />
                Connecting...
              </span>
            ) : (
              'Connect to Shopify'
            )}
          </button>
        </form>

        {/* Security note */}
        <p className="mt-4 text-center text-xs text-gray-400">
          {"You'"}ll be redirected to Shopify to authorize access.
          We only request the permissions needed to sync products and prices.
        </p>
      </div>

      {/* Help section */}
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-500">
          Need help?{' '}
          <a
            href="https://help.shopify.com/en/manual/apps"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:text-indigo-500"
          >
            Learn about Shopify app permissions
          </a>
        </p>
      </div>
    </div>
  );
}

// ==================== Sub-components ====================

function BackArrowIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10 19l-7-7m0 0l7-7m-7 7h18"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      className="mt-0.5 h-4 w-4 shrink-0 text-green-500"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}
