'use client'
import { useState, ReactNode } from 'react'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { WagmiProvider } from 'wagmi'
import { RainbowKitProvider, darkTheme } from '@rainbow-me/rainbowkit'
import { wagmiConfig } from '@/lib/web3/config'
import { Toaster } from '@/components/ui/Toaster'
import { toast } from 'sonner'
import {
  isAuthError,
  isExpiredError,
  getErrorMessage,
  parseApiError,
} from '@/lib/api/errors'

// @ts-expect-error CSS imports handled by Next.js, not TS
import '@rainbow-me/rainbowkit/styles.css'

interface ProvidersProps {
  children: ReactNode
}

/**
 * Redirect to login on auth failures.
 * Stores current path so login page can redirect back after sign-in.
 */
function handleAuthFailure() {
  // Avoid redirect loops if already on login page
  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    // Redirect to login — middleware will handle preserving the return path
    // via ?redirect= query param on subsequent server-side requests.
    window.location.href = '/login'
  }
}

/**
 * Global error handler for queries and mutations.
 * - Auth errors (401) → redirect to login
 * - Expired tokens → redirect to login
 * - Everything else → toast with human-readable message
 *
 * Mutations get toasted here only if the individual hook didn't handle
 * the error itself (React Query calls global onError after local onError).
 */
function handleGlobalError(error: unknown, isQuery: boolean) {
  if (isAuthError(error) || isExpiredError(error)) {
    handleAuthFailure()
    return
  }

  // For queries, only toast on non-retryable errors to avoid spamming
  // during transient failures that will be retried
  if (isQuery) return

  // Mutations: toast the error (local onError in hooks can still override)
  const message = getErrorMessage(error)
  toast.error(message)
}

/**
 * Retry logic: skip retries on errors that won't resolve by trying again.
 * - 401/403: auth problem, retrying won't help
 * - 404: resource doesn't exist
 * - 422: validation error, same payload will fail again
 * - Everything else: retry up to 2 times
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isAuthError(error) || isExpiredError(error)) return false

  const parsed = parseApiError(error)
  const status = parsed.status

  // Don't retry client errors that won't change
  if (status === 403 || status === 404 || status === 422) return false

  // Retry retryable errors (5xx, network) up to 2 times
  return failureCount < 2
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(() => new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => handleGlobalError(error, true),
    }),
    mutationCache: new MutationCache({
      onError: (error) => handleGlobalError(error, false),
    }),
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        retry: shouldRetry,
      },
      mutations: {
        retry: false, // Mutations never auto-retry
      },
    },
  }))

  return (
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider
          theme={darkTheme({
            accentColor: '#10b981',
            accentColorForeground: 'white',
            borderRadius: 'medium',
            fontStack: 'system',
          })}
          modalSize="compact"
          appInfo={{
            appName: 'ActualPrice',
          }}
        >
          {children}
          <Toaster />
          <ReactQueryDevtools initialIsOpen={false} />
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  )
}

export default Providers

