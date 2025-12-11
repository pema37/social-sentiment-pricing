// Central export for all types

// Base API types
export * from './api';

// Shared/common types
export * from './common';

// Domain types
export * from './product';
export * from './sentiment';
export * from './analytics';
export * from './alert';
export * from './competitor';
export * from './integration';
export * from './pricing';

// Legacy type for backwards compatibility
export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}

// Re-export User from auth
export type { User } from '@/lib/api/auth';
