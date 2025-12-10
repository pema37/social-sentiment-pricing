// Auth hooks
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { setToken, removeToken, getToken } from '@/lib/auth/token';
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
      setToken(data.access_token);
      queryClient.invalidateQueries({ queryKey: authKeys.user() });
      router.push('/dashboard');
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
      removeToken();
      return Promise.resolve();
    },
    onSuccess: () => {
      queryClient.clear();
      router.push('/login');
    },
  });
}
