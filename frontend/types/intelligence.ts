// frontend/types/intelligence.ts
// Re-exports from Generated namespace for clean imports.
// Source of truth: api-generated.ts (via openapi-typescript)

import type { components } from './api-generated';

// ── Intelligence Environment Types ──

export type ExperimentArmStatus = components['schemas']['ExperimentArmStatus'];
export type ExperimentStatus = components['schemas']['ExperimentStatus'];
export type CalibrationReport = components['schemas']['CalibrationReport'];
export type DriftAlert = components['schemas']['DriftAlert'];
export type CategoryPerformance = components['schemas']['CategoryPerformance'];
export type IEHealthStatus = components['schemas']['IEHealthStatus'];
export type IEDashboard = components['schemas']['IEDashboard'];

// ── Derived types (hand-typed since OpenAPI loses the detail) ──

/** Typed version of CalibrationReport.confidence_bands entries */
export interface CalibrationBand {
  band: string;
  predicted: number;
  actual: number;
  count: number;
}

/** Narrow severity to known values */
export type DriftSeverity = 'info' | 'warning' | 'critical';

/** Narrow drift_type to known values */
export type DriftType =
  | 'correlation_drop'
  | 'distribution_shift'
  | 'acceptance_change'
  | 'lift_decline';


  