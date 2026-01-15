// frontend/lib/domain/alerts.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type { 
  Alert,
  AlertConfiguration,
  AlertConfigurationCreate,
  AlertConfigurationUpdate,
  AlertType,
  AlertSeverity,
  AlertChannel,
  AlertStatus,
} from '@/types/alert';

// ============================================
// CONSTANTS
// ============================================

export const ALERT_TYPES: { value: AlertType; label: string }[] = [
  { value: 'sentiment_drop', label: 'Sentiment Drop' },
  { value: 'sentiment_spike', label: 'Sentiment Spike' },
  { value: 'volume_surge', label: 'Volume Surge' },
  { value: 'viral_mention', label: 'Viral Mention' },
  { value: 'competitor_price_change', label: 'Competitor Price Change' },
  { value: 'price_recommendation', label: 'Price Recommendation' },
  { value: 'price_applied', label: 'Price Applied' },
  { value: 'trend_detected', label: 'Trend Detected' },
  { value: 'anomaly_detected', label: 'Anomaly Detected' },
];

export const ALERT_SEVERITIES: { value: AlertSeverity; label: string; color: string }[] = [
  { value: 'low', label: 'Low', color: 'gray' },
  { value: 'medium', label: 'Medium', color: 'yellow' },
  { value: 'high', label: 'High', color: 'orange' },
  { value: 'critical', label: 'Critical', color: 'red' },
];

export const ALERT_CHANNELS: { value: AlertChannel; label: string }[] = [
  { value: 'in_app', label: 'In-App' },
  { value: 'email', label: 'Email' },
  { value: 'slack', label: 'Slack' },
  { value: 'webhook', label: 'Webhook' },
];

export const ALERT_STATUSES: { value: AlertStatus; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'sent', label: 'Sent' },
  { value: 'failed', label: 'Failed' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
];

// ============================================
// ZOD SCHEMAS
// ============================================

const alertTypes = [
  'sentiment_drop',
  'sentiment_spike',
  'volume_surge',
  'viral_mention',
  'competitor_price_change',
  'price_recommendation',
  'price_applied',
  'trend_detected',
  'anomaly_detected',
] as const;

const alertChannels = ['email', 'slack', 'webhook', 'in_app'] as const;

/**
 * Alert configuration form schema
 */
export const alertConfigFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string(),
  alert_type: z.enum(alertTypes),
  is_active: z.boolean(),
  product_ids: z.array(z.string()),
  channels: z.array(z.enum(alertChannels)).min(1, 'Select at least one channel'),
  cooldown_minutes: z.string().refine((val) => {
    if (val === '') return true;
    const num = parseInt(val, 10);
    return !isNaN(num) && num >= 1;
  }, { message: 'Must be at least 1 minute' }),
  max_per_day: z.string().refine((val) => {
    if (val === '') return true;
    const num = parseInt(val, 10);
    return !isNaN(num) && num >= 1;
  }, { message: 'Must be at least 1' }),
  // Condition fields (varies by alert_type)
  threshold_value: z.string(),
  threshold_percent: z.string(),
  // Channel settings
  slack_webhook_url: z.string(),
  webhook_url: z.string(),
});

// ============================================
// TYPES
// ============================================

export type AlertConfigFormData = z.input<typeof alertConfigFormSchema>;
export type AlertConfigFormErrors = Partial<Record<keyof AlertConfigFormData, string>>;

// ============================================
// UTILITIES
// ============================================

function parseInteger(value: string | number | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') return undefined;
  if (typeof value === 'number') return isNaN(value) ? undefined : Math.floor(value);
  const num = parseInt(value.toString().trim(), 10);
  return isNaN(num) ? undefined : num;
}

// ============================================
// API → Form
// ============================================

export const DEFAULT_ALERT_CONFIG_FORM: AlertConfigFormData = {
  name: '',
  description: '',
  alert_type: 'sentiment_drop',
  is_active: true,
  product_ids: [],
  channels: ['in_app'],
  cooldown_minutes: '60',
  max_per_day: '10',
  threshold_value: '',
  threshold_percent: '',
  slack_webhook_url: '',
  webhook_url: '',
};

export function alertConfigToFormData(config: Partial<AlertConfiguration>): AlertConfigFormData {
  const conditions = config.conditions ?? {};
  const channelSettings = config.channel_settings ?? {};

  return {
    name: config.name ?? '',
    description: config.description ?? '',
    alert_type: config.alert_type ?? 'sentiment_drop',
    is_active: config.is_active ?? true,
    product_ids: config.product_ids ?? [],
    channels: (config.channels as AlertChannel[]) ?? ['in_app'],
    cooldown_minutes: config.cooldown_minutes?.toString() ?? '60',
    max_per_day: config.max_per_day?.toString() ?? '10',
    threshold_value: (conditions as Record<string, unknown>).threshold_value?.toString() ?? '',
    threshold_percent: (conditions as Record<string, unknown>).threshold_percent?.toString() ?? '',
    slack_webhook_url: (channelSettings as Record<string, unknown>).slack_webhook_url?.toString() ?? '',
    webhook_url: (channelSettings as Record<string, unknown>).webhook_url?.toString() ?? '',
  };
}

// ============================================
// Form → API
// ============================================

export function formDataToCreateAlertConfig(form: AlertConfigFormData): AlertConfigurationCreate {
  const payload: AlertConfigurationCreate = {
    name: form.name.trim(),
    alert_type: form.alert_type,
    is_active: form.is_active,
    channels: form.channels,
    cooldown_minutes: parseInteger(form.cooldown_minutes) ?? 60,
    max_per_day: parseInteger(form.max_per_day) ?? 10,
  };

  if (form.description.trim()) payload.description = form.description.trim();
  if (form.product_ids.length > 0) payload.product_ids = form.product_ids;

  // Build conditions based on alert type
  const conditions: Record<string, unknown> = {};
  if (form.threshold_value.trim()) {
    const val = parseFloat(form.threshold_value);
    if (!isNaN(val)) conditions.threshold_value = val;
  }
  if (form.threshold_percent.trim()) {
    const val = parseFloat(form.threshold_percent);
    if (!isNaN(val)) conditions.threshold_percent = val;
  }
  if (Object.keys(conditions).length > 0) payload.conditions = conditions;

  // Build channel settings
  const channelSettings: Record<string, unknown> = {};
  if (form.channels.includes('slack') && form.slack_webhook_url.trim()) {
    channelSettings.slack_webhook_url = form.slack_webhook_url.trim();
  }
  if (form.channels.includes('webhook') && form.webhook_url.trim()) {
    channelSettings.webhook_url = form.webhook_url.trim();
  }
  if (Object.keys(channelSettings).length > 0) payload.channel_settings = channelSettings;

  return payload;
}

export function formDataToUpdateAlertConfig(form: AlertConfigFormData): AlertConfigurationUpdate {
  const conditions: Record<string, unknown> = {};
  if (form.threshold_value.trim()) {
    const val = parseFloat(form.threshold_value);
    if (!isNaN(val)) conditions.threshold_value = val;
  }
  if (form.threshold_percent.trim()) {
    const val = parseFloat(form.threshold_percent);
    if (!isNaN(val)) conditions.threshold_percent = val;
  }

  const channelSettings: Record<string, unknown> = {};
  if (form.channels.includes('slack') && form.slack_webhook_url.trim()) {
    channelSettings.slack_webhook_url = form.slack_webhook_url.trim();
  }
  if (form.channels.includes('webhook') && form.webhook_url.trim()) {
    channelSettings.webhook_url = form.webhook_url.trim();
  }

  return {
    name: form.name.trim() || null,
    description: form.description.trim() || null,
    is_active: form.is_active,
    product_ids: form.product_ids.length > 0 ? form.product_ids : null,
    channels: form.channels,
    conditions: Object.keys(conditions).length > 0 ? conditions : null,
    channel_settings: Object.keys(channelSettings).length > 0 ? channelSettings : null,
    cooldown_minutes: parseInteger(form.cooldown_minutes) ?? null,
    max_per_day: parseInteger(form.max_per_day) ?? null,
  };
}

// ============================================
// VALIDATION
// ============================================

export function validateAlertConfigForm(form: AlertConfigFormData): AlertConfigFormErrors {
  const result = alertConfigFormSchema.safeParse(form);
  if (result.success) return {};

  const errors: AlertConfigFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof AlertConfigFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

/**
 * Validate and transform for create
 */
export function validateAndCreateAlertConfig(form: AlertConfigFormData): 
  | { success: true; data: AlertConfigurationCreate }
  | { success: false; errors: AlertConfigFormErrors } {
  
  const errors = validateAlertConfigForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToCreateAlertConfig(form) };
}

/**
 * Validate and transform for update
 */
export function validateAndUpdateAlertConfig(form: AlertConfigFormData): 
  | { success: true; data: AlertConfigurationUpdate }
  | { success: false; errors: AlertConfigFormErrors } {
  
  const errors = validateAlertConfigForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToUpdateAlertConfig(form) };
}

// ============================================
// DISPLAY HELPERS
// ============================================

/**
 * Get human-readable alert type label
 */
export function getAlertTypeLabel(type: AlertType): string {
  const found = ALERT_TYPES.find(t => t.value === type);
  return found?.label ?? type;
}

/**
 * Get severity color for badges
 */
export function getSeverityColor(severity: AlertSeverity): 'gray' | 'yellow' | 'orange' | 'red' {
  const colors: Record<AlertSeverity, 'gray' | 'yellow' | 'orange' | 'red'> = {
    low: 'gray',
    medium: 'yellow',
    high: 'orange',
    critical: 'red',
  };
  return colors[severity] ?? 'gray';
}

/**
 * Get status color for badges
 */
export function getAlertStatusColor(status: AlertStatus): 'gray' | 'green' | 'red' | 'blue' | 'yellow' {
  const colors: Record<AlertStatus, 'gray' | 'green' | 'red' | 'blue' | 'yellow'> = {
    pending: 'yellow',
    sent: 'green',
    failed: 'red',
    acknowledged: 'blue',
    resolved: 'gray',
  };
  return colors[status] ?? 'gray';
}

/**
 * Get status label
 */
export function getAlertStatusLabel(status: AlertStatus): string {
  const found = ALERT_STATUSES.find(s => s.value === status);
  return found?.label ?? status;
}

/**
 * Format alert time relative to now
 */
export function formatAlertTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}

/**
 * Check if alert is unread (pending or sent but not acknowledged)
 */
export function isAlertUnread(alert: Alert): boolean {
  return alert.status === 'pending' || alert.status === 'sent';
}



