'use client';

/**
 * IntegrationsEmptyState
 * 
 * Displayed when user has no integrations connected.
 */

export function IntegrationsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 px-6 py-12 text-center">
      <div className="text-4xl">🔌</div>
      <h3 className="mt-4 text-lg font-medium text-gray-900">
        No integrations yet
      </h3>
      <p className="mt-2 max-w-sm text-sm text-gray-500">
        Connect your e-commerce store to start syncing products and automatically
        update prices based on sentiment analysis.
      </p>
    </div>
  );
}
