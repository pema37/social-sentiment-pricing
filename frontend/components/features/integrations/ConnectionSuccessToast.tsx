'use client';

/**
 * ConnectionSuccessToast
 * 
 * Toast notification displayed after OAuth callback.
 * Auto-dismisses after 5 seconds.
 */

import { useEffect } from 'react';

interface ConnectionSuccessToastProps {
  type: 'success' | 'error';
  message: string;
  onDismiss: () => void;
}

export function ConnectionSuccessToast({
  type,
  message,
  onDismiss,
}: ConnectionSuccessToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 5000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const styles = {
    success: {
      container: 'bg-green-50 border-green-200',
      icon: '✓',
      iconBg: 'bg-green-100 text-green-600',
      text: 'text-green-800',
    },
    error: {
      container: 'bg-red-50 border-red-200',
      icon: '✕',
      iconBg: 'bg-red-100 text-red-600',
      text: 'text-red-800',
    },
  };

  const style = styles[type];

  return (
    <div
      role="alert"
      className={`flex items-center gap-3 rounded-lg border p-4 ${style.container}`}
    >
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${style.iconBg}`}
      >
        {style.icon}
      </span>
      <p className={`flex-1 text-sm font-medium ${style.text}`}>{message}</p>
      <button
        onClick={onDismiss}
        className={`text-sm ${style.text} hover:opacity-70`}
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
