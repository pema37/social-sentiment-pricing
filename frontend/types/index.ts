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
export * from './user';

// Legacy type for backwards compatibility
export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}
