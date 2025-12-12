// Toast hook for easy toast notifications
import { useToastStore } from '@/lib/stores/toast-store';

interface ToastOptions {
  title: string;
  message?: string;
  duration?: number;
}

export function useToast() {
  const { addToast, removeToast, clearToasts } = useToastStore();

  const toast = {
    success: (options: ToastOptions | string) => {
      const opts = typeof options === 'string' ? { title: options } : options;
      addToast({ type: 'success', ...opts });
    },

    error: (options: ToastOptions | string) => {
      const opts = typeof options === 'string' ? { title: options } : options;
      addToast({ type: 'error', ...opts, duration: opts.duration ?? 7000 });
    },

    warning: (options: ToastOptions | string) => {
      const opts = typeof options === 'string' ? { title: options } : options;
      addToast({ type: 'warning', ...opts });
    },

    info: (options: ToastOptions | string) => {
      const opts = typeof options === 'string' ? { title: options } : options;
      addToast({ type: 'info', ...opts });
    },

    dismiss: removeToast,
    
    clear: clearToasts,
  };

  return toast;
}

// Standalone function for use outside of React components (e.g., in API callbacks)
export const toast = {
  success: (options: ToastOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    useToastStore.getState().addToast({ type: 'success', ...opts });
  },

  error: (options: ToastOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    useToastStore.getState().addToast({ type: 'error', ...opts, duration: opts.duration ?? 7000 });
  },

  warning: (options: ToastOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    useToastStore.getState().addToast({ type: 'warning', ...opts });
  },

  info: (options: ToastOptions | string) => {
    const opts = typeof options === 'string' ? { title: options } : options;
    useToastStore.getState().addToast({ type: 'info', ...opts });
  },

  dismiss: (id: string) => useToastStore.getState().removeToast(id),
  
  clear: () => useToastStore.getState().clearToasts(),
};
