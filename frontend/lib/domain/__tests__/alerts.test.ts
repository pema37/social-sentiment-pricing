import { describe, it, expect } from 'vitest';
import {
  alertConfigToFormData,
  formDataToCreateAlertConfig,
  formDataToUpdateAlertConfig,
  validateAlertConfigForm,
  validateAndCreateAlertConfig,
  getAlertTypeLabel,
  getSeverityColor,
  getAlertStatusColor,
  getAlertStatusLabel,
  formatAlertTime,
  isAlertUnread,
  DEFAULT_ALERT_CONFIG_FORM,
  ALERT_TYPES,
  ALERT_CHANNELS,
  type AlertConfigFormData,
} from '../alerts';
import type { AlertChannel } from '@/types/alert';

describe('validateAlertConfigForm', () => {
  it('requires name', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: '' };
    const errors = validateAlertConfigForm(form);
    expect(errors.name).toBeDefined();
  });

  it('requires at least one channel', () => {
    const form: AlertConfigFormData = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', channels: [] };
    const errors = validateAlertConfigForm(form);
    expect(errors.channels).toBeDefined();
  });

  it('passes with valid data', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Critical Alerts',
      channels: ['email', 'in_app'],
    };
    const errors = validateAlertConfigForm(form);
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it('validates cooldown_minutes minimum', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', cooldown_minutes: '0' };
    const errors = validateAlertConfigForm(form);
    expect(errors.cooldown_minutes).toBeDefined();
  });

  it('accepts valid cooldown_minutes', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', cooldown_minutes: '30' };
    const errors = validateAlertConfigForm(form);
    expect(errors.cooldown_minutes).toBeUndefined();
  });

  it('allows empty cooldown_minutes', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', cooldown_minutes: '' };
    const errors = validateAlertConfigForm(form);
    expect(errors.cooldown_minutes).toBeUndefined();
  });

  it('validates max_per_day minimum', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', max_per_day: '0' };
    const errors = validateAlertConfigForm(form);
    expect(errors.max_per_day).toBeDefined();
  });

  it('accepts valid max_per_day', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', max_per_day: '5' };
    const errors = validateAlertConfigForm(form);
    expect(errors.max_per_day).toBeUndefined();
  });
});

describe('formDataToCreateAlertConfig', () => {
  it('includes required fields', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Critical Alerts',
      alert_type: 'sentiment_drop',
      channels: ['email'],
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.name).toBe('Critical Alerts');
    expect(request.alert_type).toBe('sentiment_drop');
    expect(request.channels).toEqual(['email']);
  });

  it('parses cooldown_minutes as integer', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', cooldown_minutes: '45' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.cooldown_minutes).toBe(45);
  });

  it('parses max_per_day as integer', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', max_per_day: '20' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.max_per_day).toBe(20);
  });

  it('defaults cooldown_minutes to 60', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', cooldown_minutes: '' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.cooldown_minutes).toBe(60);
  });

  it('defaults max_per_day to 10', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', max_per_day: '' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.max_per_day).toBe(10);
  });

  it('omits empty description', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', description: '' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.description).toBeUndefined();
  });

  it('includes description when provided', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', description: 'Important alerts' };
    const request = formDataToCreateAlertConfig(form);
    expect(request.description).toBe('Important alerts');
  });

  it('includes product_ids when provided', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', product_ids: ['p1', 'p2'] };
    const request = formDataToCreateAlertConfig(form);
    expect(request.product_ids).toEqual(['p1', 'p2']);
  });

  it('omits empty product_ids', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', product_ids: [] };
    const request = formDataToCreateAlertConfig(form);
    expect(request.product_ids).toBeUndefined();
  });

  it('builds conditions from threshold fields', () => {
    const form = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      threshold_value: '0.5',
      threshold_percent: '10',
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.conditions).toEqual({
      threshold_value: 0.5,
      threshold_percent: 10,
    });
  });

  it('omits conditions when thresholds empty', () => {
    const form = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      threshold_value: '',
      threshold_percent: '',
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.conditions).toBeUndefined();
  });

  it('builds channel_settings for slack', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      channels: ['slack'],
      slack_webhook_url: 'https://hooks.slack.com/xxx',
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.channel_settings).toEqual({
      slack_webhook_url: 'https://hooks.slack.com/xxx',
    });
  });

  it('builds channel_settings for webhook', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      channels: ['webhook'],
      webhook_url: 'https://example.com/webhook',
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.channel_settings).toEqual({
      webhook_url: 'https://example.com/webhook',
    });
  });

  it('ignores slack_webhook_url if slack not in channels', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      channels: ['email'],
      slack_webhook_url: 'https://hooks.slack.com/xxx',
    };
    const request = formDataToCreateAlertConfig(form);
    expect(request.channel_settings).toBeUndefined();
  });
});

describe('formDataToUpdateAlertConfig', () => {
  it('returns null for empty name', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: '' };
    const request = formDataToUpdateAlertConfig(form);
    expect(request.name).toBeNull();
  });

  it('returns null for empty description', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', description: '' };
    const request = formDataToUpdateAlertConfig(form);
    expect(request.description).toBeNull();
  });

  it('returns null for empty product_ids', () => {
    const form = { ...DEFAULT_ALERT_CONFIG_FORM, name: 'Test', product_ids: [] };
    const request = formDataToUpdateAlertConfig(form);
    expect(request.product_ids).toBeNull();
  });

  it('returns null for empty conditions', () => {
    const form = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test',
      threshold_value: '',
      threshold_percent: '',
    };
    const request = formDataToUpdateAlertConfig(form);
    expect(request.conditions).toBeNull();
  });
});

describe('alertConfigToFormData', () => {
  it('handles empty/partial config', () => {
    const form = alertConfigToFormData({});
    expect(form.name).toBe('');
    expect(form.alert_type).toBe('sentiment_drop');
    expect(form.is_active).toBe(true);
    expect(form.channels).toEqual(['in_app']);
    expect(form.cooldown_minutes).toBe('60');
    expect(form.max_per_day).toBe('10');
  });

  it('maps all fields correctly', () => {
    const config = {
      name: 'Critical Alerts',
      description: 'Important notifications',
      alert_type: 'viral_mention' as const,
      is_active: false,
      product_ids: ['p1', 'p2'],
      channels: ['email', 'slack'] as AlertChannel[],
      cooldown_minutes: 30,
      max_per_day: 5,
      conditions: { threshold_value: 0.8, threshold_percent: 15 },
      channel_settings: { slack_webhook_url: 'https://hooks.slack.com/xxx' },
    };
    const form = alertConfigToFormData(config);
    expect(form.name).toBe('Critical Alerts');
    expect(form.description).toBe('Important notifications');
    expect(form.alert_type).toBe('viral_mention');
    expect(form.is_active).toBe(false);
    expect(form.product_ids).toEqual(['p1', 'p2']);
    expect(form.channels).toEqual(['email', 'slack']);
    expect(form.cooldown_minutes).toBe('30');
    expect(form.max_per_day).toBe('5');
    expect(form.threshold_value).toBe('0.8');
    expect(form.threshold_percent).toBe('15');
    expect(form.slack_webhook_url).toBe('https://hooks.slack.com/xxx');
  });
});

describe('validateAndCreateAlertConfig', () => {
  it('returns success with valid data', () => {
    const form: AlertConfigFormData = {
      ...DEFAULT_ALERT_CONFIG_FORM,
      name: 'Test Alert',
      channels: ['email'],
    };
    const result = validateAndCreateAlertConfig(form);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('Test Alert');
    }
  });

  it('returns errors with invalid data', () => {
    const form: AlertConfigFormData = { ...DEFAULT_ALERT_CONFIG_FORM, name: '', channels: [] };
    const result = validateAndCreateAlertConfig(form);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.name).toBeDefined();
      expect(result.errors.channels).toBeDefined();
    }
  });
});

describe('display helpers', () => {
  describe('getAlertTypeLabel', () => {
    it('returns label for known types', () => {
      expect(getAlertTypeLabel('sentiment_drop')).toBe('Sentiment Drop');
      expect(getAlertTypeLabel('viral_mention')).toBe('Viral Mention');
      expect(getAlertTypeLabel('price_applied')).toBe('Price Applied');
    });

    it('returns type as-is for unknown types', () => {
      expect(getAlertTypeLabel('unknown_type' as never)).toBe('unknown_type');
    });
  });

  describe('getSeverityColor', () => {
    it('returns correct colors', () => {
      expect(getSeverityColor('low')).toBe('gray');
      expect(getSeverityColor('medium')).toBe('yellow');
      expect(getSeverityColor('high')).toBe('orange');
      expect(getSeverityColor('critical')).toBe('red');
    });

    it('defaults to gray for unknown', () => {
      expect(getSeverityColor('unknown' as never)).toBe('gray');
    });
  });

  describe('getAlertStatusColor', () => {
    it('returns correct colors', () => {
      expect(getAlertStatusColor('pending')).toBe('yellow');
      expect(getAlertStatusColor('sent')).toBe('green');
      expect(getAlertStatusColor('failed')).toBe('red');
      expect(getAlertStatusColor('acknowledged')).toBe('blue');
      expect(getAlertStatusColor('resolved')).toBe('gray');
    });
  });

  describe('getAlertStatusLabel', () => {
    it('returns correct labels', () => {
      expect(getAlertStatusLabel('pending')).toBe('Pending');
      expect(getAlertStatusLabel('sent')).toBe('Sent');
      expect(getAlertStatusLabel('acknowledged')).toBe('Acknowledged');
    });

    it('returns status as-is for unknown', () => {
      expect(getAlertStatusLabel('unknown' as never)).toBe('unknown');
    });
  });

  describe('formatAlertTime', () => {
    it('formats recent times as "Just now"', () => {
      const now = new Date().toISOString();
      expect(formatAlertTime(now)).toBe('Just now');
    });

    it('formats minutes ago', () => {
      const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
      expect(formatAlertTime(fiveMinAgo)).toBe('5m ago');
    });

    it('formats hours ago', () => {
      const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
      expect(formatAlertTime(threeHoursAgo)).toBe('3h ago');
    });

    it('formats days ago', () => {
      const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
      expect(formatAlertTime(twoDaysAgo)).toBe('2d ago');
    });
  });

  describe('isAlertUnread', () => {
    it('returns true for pending', () => {
      expect(isAlertUnread({ status: 'pending' } as never)).toBe(true);
    });

    it('returns true for sent', () => {
      expect(isAlertUnread({ status: 'sent' } as never)).toBe(true);
    });

    it('returns false for acknowledged', () => {
      expect(isAlertUnread({ status: 'acknowledged' } as never)).toBe(false);
    });

    it('returns false for resolved', () => {
      expect(isAlertUnread({ status: 'resolved' } as never)).toBe(false);
    });
  });
});

describe('constants', () => {
  it('ALERT_TYPES has all types', () => {
    expect(ALERT_TYPES.length).toBeGreaterThan(0);
    expect(ALERT_TYPES.find(t => t.value === 'sentiment_drop')).toBeDefined();
    expect(ALERT_TYPES.find(t => t.value === 'viral_mention')).toBeDefined();
  });

  it('ALERT_CHANNELS has all channels', () => {
    expect(ALERT_CHANNELS.length).toBe(4);
    expect(ALERT_CHANNELS.find(c => c.value === 'email')).toBeDefined();
    expect(ALERT_CHANNELS.find(c => c.value === 'slack')).toBeDefined();
    expect(ALERT_CHANNELS.find(c => c.value === 'webhook')).toBeDefined();
    expect(ALERT_CHANNELS.find(c => c.value === 'in_app')).toBeDefined();
  });
});


