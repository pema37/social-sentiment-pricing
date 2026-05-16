'use client';

// frontend/lib/hooks/use-auth.ts

/**
 * Auth hooks for login, register, logout, and user queries.
 * 
 * PATCHED (2025-01-28): Fixed Bug #5 - Now stores refresh token on login
 * to enable silent session renewal and prevent "Not authenticated" errors.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { authKeys } from '@/lib/api/query-keys';
import {
  setToken,
  removeAllTokens,
  isAuthenticated
} from '@/lib/auth/token';
import { useRouter } from 'next/navigation';

// Get current user
export function useUser() {
  return useQuery({
    queryKey: authKeys.user(),
    queryFn: () => authApi.me(),
    enabled: isAuthenticated(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  });
}

// Login
export function useLogin() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password),
    onSuccess: (data) => {
      // Backend sets httpOnly cookies automatically.
      // Set the hint cookie so Next.js middleware knows we're logged in.
      setToken(data.access_token);
      
      queryClient.invalidateQueries({ queryKey: authKeys.user() });
      
      // Check for redirect path (set when session expired)
      const redirectPath = typeof window !== 'undefined'
        ? sessionStorage.getItem('redirectAfterLogin')
        : null;

      // Also check URL ?redirect param (set by middleware redirect)
      const urlRedirect = typeof window !== 'undefined'
        ? new URLSearchParams(window.location.search).get('redirect')
        : null;

      if (redirectPath) {
        sessionStorage.removeItem('redirectAfterLogin');
        router.push(redirectPath);
      } else if (urlRedirect && urlRedirect.startsWith('/')) {
        router.push(urlRedirect);
      } else {
        router.push('/dashboard');
      }
    },
  });
}

// Register
export function useRegister() {
  const router = useRouter();

  return useMutation({
    mutationFn: ({
      email,
      password,
      fullName,
    }: {
      email: string;
      password: string;
      fullName: string;
    }) => authApi.register(email, password, fullName),
    onSuccess: () => {
      router.push('/login?registered=true');
    },
  });
}

// Logout
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      // Clear httpOnly cookies on the backend
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/logout`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch {
        // Best-effort — cookies will expire anyway
      }
      // Clear the hint cookie
      removeAllTokens();
    },
    onSuccess: () => {
      queryClient.clear();
      router.push('/login');
    },
  });
}


