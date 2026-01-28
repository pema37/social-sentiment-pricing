// frontend/lib/hooks/use-auth.ts

/**
 * Auth hooks for login, register, logout, and user queries.
 * 
 * PATCHED (2025-01-28): Fixed Bug #5 - Now stores refresh token on login
 * to enable silent session renewal and prevent "Not authenticated" errors.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { 
  setToken, 
  setRefreshToken,
  removeAllTokens, 
  getToken 
} from '@/lib/auth/token';
import { useRouter } from 'next/navigation';

// Query keys
export const authKeys = {
  all: ['auth'] as const,
  user: () => [...authKeys.all, 'user'] as const,
};

// Get current user
export function useUser() {
  return useQuery({
    queryKey: authKeys.user(),
    queryFn: () => authApi.me(),
    enabled: !!getToken(),
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
      // Store access token
      setToken(data.access_token);
      
      // BUGFIX: Store refresh token for silent session renewal
      // Without this, users get "Not authenticated" after 30 min
      if (data.refresh_token) {
        setRefreshToken(data.refresh_token);
      }
      
      queryClient.invalidateQueries({ queryKey: authKeys.user() });
      
      // Check for redirect path (set when session expired)
      const redirectPath = typeof window !== 'undefined' 
        ? sessionStorage.getItem('redirectAfterLogin') 
        : null;
      
      if (redirectPath) {
        sessionStorage.removeItem('redirectAfterLogin');
        router.push(redirectPath);
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
      // Clear both access and refresh tokens
      removeAllTokens();
      return Promise.resolve();
    },
    onSuccess: () => {
      queryClient.clear();
      router.push('/login');
    },
  });
}


