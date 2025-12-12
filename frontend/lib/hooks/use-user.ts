// User profile hooks
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth-store';
import { toast } from '@/lib/hooks/use-toast';
import type { UpdateProfileRequest, ChangePasswordRequest } from '@/types';

// Update user profile
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { checkAuth } = useAuthStore();

  return useMutation({
    mutationFn: (data: UpdateProfileRequest) => authApi.updateProfile(data),
    onSuccess: () => {
      // Refresh user data in auth store
      checkAuth();
      queryClient.invalidateQueries({ queryKey: ['user'] });
      toast.success({ title: 'Profile updated', message: 'Your profile has been saved' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update profile', message: error.message });
    },
  });
}

// Change password
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => authApi.changePassword(data),
    onSuccess: () => {
      toast.success({ title: 'Password changed', message: 'Your password has been updated' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to change password', message: error.message });
    },
  });
}
