// Central export for all types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08

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
export * from './competitor-matching';
export * from './integration';
export * from './pricing';
export * from './user';
export * from './payment';
export * from './trust-scoring';
export * from './retrospective-audit';

// AP-013: Added missing barrel exports for intelligence, outcome, trend-analysis.
// Without these, types from these files were not available via the central barrel
// and had to be imported directly from the file — breaking the single-import pattern.
export * from './intelligence';
export * from './outcome';
export * from './trend-analysis';

// Re-export generated types for direct access if needed
// Usage: import type { components } from '@/types/api-generated';
export type { components, paths, operations } from './api-generated';


