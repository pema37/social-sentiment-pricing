'use client';

/**
 * WooCommerceConnectModal
 * 
 * Modal for connecting WooCommerce store with API keys.
 * Guides user through generating and entering consumer key/secret.
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { useConnectWooCommerce } from '@/lib/hooks/use-integrations';
import { Button } from '@/components/ui';

// Domain layer
import {
  validateAndConnectWooCommerce,
  DEFAULT_WOOCOMMERCE_FORM,
  type WooCommerceConnectFormData,
  type WooCommerceConnectFormErrors,
} from '@/lib/domain/integrations';


interface WooCommerceConnectModalProps {
  onClose: () => void;
}

export function WooCommerceConnectModal({ onClose }: WooCommerceConnectModalProps) {
  const [formData, setFormData] = useState<WooCommerceConnectFormData>(DEFAULT_WOOCOMMERCE_FORM);
  const [errors, setErrors] = useState<WooCommerceConnectFormErrors>({});

  const connectWoo = useConnectWooCommerce();

  const handleChange = useCallback((field: keyof WooCommerceConnectFormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  }, [errors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const result = validateAndConnectWooCommerce(formData);

    if (!result.success) {
      setErrors(result.errors);
      toast.error('Please fix the errors');
      return;
    }

    connectWoo.mutate(result.data, {
      onSuccess: () => {
        toast.success('WooCommerce connected!');
        onClose();
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="woo-modal-title"
    >
      <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 id="woo-modal-title" className="text-lg font-semibold text-gray-900">
            Connect WooCommerce
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Enter your store URL and REST API credentials.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-4">
          <div className="space-y-4">
            {/* Store URL */}
            <div>
              <label htmlFor="woo-store-url" className="block text-sm font-medium text-gray-700">
                Store URL
              </label>
              <input
                id="woo-store-url"
                type="text"
                placeholder="yourstore.com"
                value={formData.store_url}
                onChange={(e) => handleChange('store_url', e.target.value)}
                className={`mt-1 w-full rounded-md border px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-1 ${
                  errors.store_url
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                }`}
              />
              {errors.store_url && (
                <p className="mt-1 text-xs text-red-600">{errors.store_url}</p>
              )}
            </div>

            {/* Store Name (optional) */}
            <div>
              <label htmlFor="woo-store-name" className="block text-sm font-medium text-gray-700">
                Store Name <span className="text-gray-400">(optional)</span>
              </label>
              <input
                id="woo-store-name"
                type="text"
                placeholder="My Store"
                value={formData.store_name}
                onChange={(e) => handleChange('store_name', e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Consumer Key */}
            <div>
              <label htmlFor="woo-consumer-key" className="block text-sm font-medium text-gray-700">
                Consumer Key
              </label>
              <input
                id="woo-consumer-key"
                type="text"
                placeholder="ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={formData.consumer_key}
                onChange={(e) => handleChange('consumer_key', e.target.value)}
                className={`mt-1 w-full rounded-md border px-3 py-2 font-mono text-sm placeholder-gray-400 focus:outline-none focus:ring-1 ${
                  errors.consumer_key
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                }`}
              />
              {errors.consumer_key && (
                <p className="mt-1 text-xs text-red-600">{errors.consumer_key}</p>
              )}
            </div>

            {/* Consumer Secret */}
            <div>
              <label htmlFor="woo-consumer-secret" className="block text-sm font-medium text-gray-700">
                Consumer Secret
              </label>
              <input
                id="woo-consumer-secret"
                type="password"
                placeholder="cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={formData.consumer_secret}
                onChange={(e) => handleChange('consumer_secret', e.target.value)}
                className={`mt-1 w-full rounded-md border px-3 py-2 font-mono text-sm placeholder-gray-400 focus:outline-none focus:ring-1 ${
                  errors.consumer_secret
                    ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                    : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                }`}
              />
              {errors.consumer_secret && (
                <p className="mt-1 text-xs text-red-600">{errors.consumer_secret}</p>
              )}
            </div>
          </div>

          {/* Help text */}
          <div className="mt-4 rounded-md bg-gray-50 p-3">
            <p className="text-xs text-gray-600">
              Generate API keys in your WooCommerce admin:{' '}
              <span className="font-medium">
                Settings → Advanced → REST API → Add Key
              </span>
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Set permissions to <span className="font-medium">Read/Write</span>.
            </p>
          </div>

          {/* API Error */}
          {connectWoo.isError && (
            <div className="mt-4 rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-700">
                {connectWoo.error?.message || 'Failed to connect. Please check your credentials.'}
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="mt-6 flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={connectWoo.isPending}>
              {connectWoo.isPending ? 'Connecting...' : 'Connect Store'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}



