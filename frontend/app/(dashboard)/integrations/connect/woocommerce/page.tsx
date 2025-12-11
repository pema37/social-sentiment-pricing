'use client';

/**
 * WooCommerce Connect Page
 * 
 * Allows users to connect their WooCommerce store using API keys.
 * WooCommerce uses Consumer Key/Secret instead of OAuth.
 * 
 * URL: /integrations/connect/woocommerce
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { useConnectWooCommerce } from '@/lib/hooks/use-integrations';

// ==================== Types ====================

interface FormData {
  store_url: string;
  store_name: string;
  consumer_key: string;
  consumer_secret: string;
}

interface FormErrors {
  store_url?: string;
  consumer_key?: string;
  consumer_secret?: string;
  general?: string;
}

// ==================== Component ====================

export default function WooCommerceConnectPage() {
  const router = useRouter();
  const connectWooCommerce = useConnectWooCommerce();

  const [formData, setFormData] = useState<FormData>({
    store_url: '',
    store_name: '',
    consumer_key: '',
    consumer_secret: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [showSecrets, setShowSecrets] = useState(false);

  /**
   * Validate form fields
   */
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Store URL validation
    const urlTrimmed = formData.store_url.trim().toLowerCase();
    if (!urlTrimmed) {
      newErrors.store_url = 'Please enter your WooCommerce store URL';
    } else if (!isValidUrl(urlTrimmed)) {
      newErrors.store_url = 'Please enter a valid URL (e.g., mystore.com)';
    }

    // Consumer Key validation
    const keyTrimmed = formData.consumer_key.trim();
    if (!keyTrimmed) {
      newErrors.consumer_key = 'Consumer Key is required';
    } else if (!keyTrimmed.startsWith('ck_')) {
      newErrors.consumer_key = 'Consumer Key must start with "ck_"';
    } else if (keyTrimmed.length < 20) {
      newErrors.consumer_key = 'Consumer Key appears too short';
    }

    // Consumer Secret validation
    const secretTrimmed = formData.consumer_secret.trim();
    if (!secretTrimmed) {
      newErrors.consumer_secret = 'Consumer Secret is required';
    } else if (!secretTrimmed.startsWith('cs_')) {
      newErrors.consumer_secret = 'Consumer Secret must start with "cs_"';
    } else if (secretTrimmed.length < 20) {
      newErrors.consumer_secret = 'Consumer Secret appears too short';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Normalize store URL
   */
  const normalizeStoreUrl = (url: string): string => {
    let cleaned = url.trim().toLowerCase();
    
    // Remove protocol
    cleaned = cleaned.replace(/^https?:\/\//, '');
    
    // Remove trailing slash
    cleaned = cleaned.replace(/\/$/, '');
    
    // Remove /wp-json or /wc-api paths if present
    cleaned = cleaned.replace(/\/wp-json.*$/, '');
    cleaned = cleaned.replace(/\/wc-api.*$/, '');
    
    return cleaned;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      await connectWooCommerce.mutateAsync({
        store_url: normalizeStoreUrl(formData.store_url),
        store_name: formData.store_name.trim() || undefined,
        consumer_key: formData.consumer_key.trim(),
        consumer_secret: formData.consumer_secret.trim(),
      });

      // Redirect on success
      router.push('/integrations?connected=true&platform=woocommerce');
    } catch (err) {
      console.error('WooCommerce connect error:', err);
      
      let errorMessage = 'Failed to connect. Please check your credentials.';
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      
      setErrors({ general: errorMessage });
    }
  };

  /**
   * Handle input change
   */
  const handleChange = (field: keyof FormData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    // Clear error for this field
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
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
            src="/logos/woocommerce.svg"
            alt="WooCommerce"
            width={48}
            height={48}
            className="h-12 w-12"
          />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Connect WooCommerce
            </h1>
            <p className="text-sm text-gray-500">
              Link your WooCommerce store with API keys
            </p>
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-6 rounded-md bg-blue-50 p-4">
          <h3 className="text-sm font-medium text-blue-800">
            How to get your API keys:
          </h3>
          <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-blue-700">
            <li>Go to WooCommerce → Settings → Advanced → REST API</li>
            <li>Click &quot;Add key&quot; and enter a description</li>
            <li>Click &quot;Generate API key&quot;</li>
            <li>Copy the Consumer Key and Consumer Secret</li>
          </ol>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {/* General error */}
          {errors.general && (
            <div className="rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-700">{errors.general}</p>
            </div>
          )}

          {/* Store URL */}
          <div>
            <label
              htmlFor="store_url"
              className="block text-sm font-medium text-gray-700"
            >
              Store URL <span className="text-red-500">*</span>
            </label>
            <input
              id="store_url"
              type="text"
              value={formData.store_url}
              onChange={handleChange('store_url')}
              placeholder="mystore.com"
              className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-0 ${
                errors.store_url
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
              }`}
              disabled={connectWooCommerce.isPending}
            />
            {errors.store_url && (
              <p className="mt-1 text-sm text-red-600">{errors.store_url}</p>
            )}
          </div>

          {/* Store Name (optional) */}
          <div>
            <label
              htmlFor="store_name"
              className="block text-sm font-medium text-gray-700"
            >
              Store Name <span className="text-gray-400">(optional)</span>
            </label>
            <input
              id="store_name"
              type="text"
              value={formData.store_name}
              onChange={handleChange('store_name')}
              placeholder="My Awesome Store"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-0"
              disabled={connectWooCommerce.isPending}
            />
            <p className="mt-1 text-xs text-gray-500">
              A friendly name to identify this store
            </p>
          </div>

          {/* Consumer Key */}
          <div>
            <label
              htmlFor="consumer_key"
              className="block text-sm font-medium text-gray-700"
            >
              Consumer Key <span className="text-red-500">*</span>
            </label>
            <input
              id="consumer_key"
              type={showSecrets ? 'text' : 'password'}
              value={formData.consumer_key}
              onChange={handleChange('consumer_key')}
              placeholder="ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className={`mt-1 block w-full rounded-md border px-3 py-2 font-mono text-sm shadow-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-0 ${
                errors.consumer_key
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
              }`}
              disabled={connectWooCommerce.isPending}
            />
            {errors.consumer_key && (
              <p className="mt-1 text-sm text-red-600">{errors.consumer_key}</p>
            )}
          </div>

          {/* Consumer Secret */}
          <div>
            <label
              htmlFor="consumer_secret"
              className="block text-sm font-medium text-gray-700"
            >
              Consumer Secret <span className="text-red-500">*</span>
            </label>
            <input
              id="consumer_secret"
              type={showSecrets ? 'text' : 'password'}
              value={formData.consumer_secret}
              onChange={handleChange('consumer_secret')}
              placeholder="cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className={`mt-1 block w-full rounded-md border px-3 py-2 font-mono text-sm shadow-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-0 ${
                errors.consumer_secret
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
              }`}
              disabled={connectWooCommerce.isPending}
            />
            {errors.consumer_secret && (
              <p className="mt-1 text-sm text-red-600">{errors.consumer_secret}</p>
            )}
          </div>

          {/* Show/hide secrets toggle */}
          <div className="flex items-center">
            <input
              id="show_secrets"
              type="checkbox"
              checked={showSecrets}
              onChange={(e) => setShowSecrets(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label
              htmlFor="show_secrets"
              className="ml-2 text-sm text-gray-600"
            >
              Show API keys
            </label>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={connectWooCommerce.isPending}
            className={`w-full rounded-md px-4 py-2.5 text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
              connectWooCommerce.isPending
                ? 'cursor-not-allowed bg-indigo-400'
                : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {connectWooCommerce.isPending ? (
              <span className="flex items-center justify-center gap-2">
                <LoadingSpinner />
                Connecting...
              </span>
            ) : (
              'Connect Store'
            )}
          </button>
        </form>

        {/* Security note */}
        <p className="mt-4 text-center text-xs text-gray-400">
          Your API keys are encrypted and stored securely.
          We only request read/write access for products and prices.
        </p>
      </div>

      {/* Help section */}
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-500">
          Need help?{' '}
          <a
            href="https://woocommerce.com/document/woocommerce-rest-api/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:text-indigo-500"
          >
            View WooCommerce REST API documentation
          </a>
        </p>
      </div>
    </div>
  );
}

// ==================== Helpers ====================

function isValidUrl(url: string): boolean {
  // Basic URL validation - allows domain names with optional paths
  const pattern = /^[\w.-]+\.[a-z]{2,}(\/.*)?$/i;
  return pattern.test(url);
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
