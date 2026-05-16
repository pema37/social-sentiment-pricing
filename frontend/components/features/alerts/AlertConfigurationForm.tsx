'use client';

// frontend/components/features/alerts/AlertConfigurationForm.tsx
// Enhanced alert configuration form with threshold, product selection, and channel URL fields
import { useState, useCallback, useMemo } from 'react';
import { X, Info, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import type { AlertConfiguration } from '@/types/alert';

// Domain layer
import {
  alertConfigToFormData,
  validateAndCreateAlertConfig,
  validateAndUpdateAlertConfig,
  DEFAULT_ALERT_CONFIG_FORM,
  ALERT_TYPES,
  ALERT_CHANNELS,
  type AlertConfigFormData,
  type AlertConfigFormErrors,
} from '@/lib/domain/alerts';
import type { AlertChannel, AlertType } from '@/types/alert';

// Hooks
import { useProducts } from '@/lib/hooks/use-products';

interface AlertConfigurationFormProps {
  configuration?: AlertConfiguration | null;
  onSubmit: (data: ReturnType<typeof validateAndCreateAlertConfig> extends { success: true; data: infer D } ? D : never) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

// Alert types that support threshold configuration
const THRESHOLD_ALERT_TYPES: AlertType[] = [
  'sentiment_drop',
  'sentiment_spike',
  'volume_surge',
  'viral_mention',
  'competitor_price_change',
];

export function AlertConfigurationForm({
  configuration,
  onSubmit,
  onCancel,
  isSubmitting,
}: AlertConfigurationFormProps) {
  const [formData, setFormData] = useState<AlertConfigFormData>(() =>
    configuration ? alertConfigToFormData(configuration) : DEFAULT_ALERT_CONFIG_FORM
  );
  const [errors, setErrors] = useState<AlertConfigFormErrors>({});

  // Fetch products for the selector
  const { data: productsData, isLoading: productsLoading } = useProducts({ page_size: 100 });
  const products = productsData?.items ?? [];

  const isEditing = !!configuration;

  // Check if current alert type supports thresholds
  const showThresholdFields = useMemo(() => 
    THRESHOLD_ALERT_TYPES.includes(formData.alert_type),
    [formData.alert_type]
  );

  // Check if Slack or Webhook channels are selected
  const showSlackUrl = formData.channels.includes('slack');
  const showWebhookUrl = formData.channels.includes('webhook');

  const handleChange = useCallback((field: keyof AlertConfigFormData, value: string | boolean | string[]) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  }, [errors]);

  const handleChannelToggle = useCallback((channel: AlertChannel) => {
    setFormData(prev => {
      const newChannels = prev.channels.includes(channel)
        ? prev.channels.filter(c => c !== channel)
        : [...prev.channels, channel];
      
      // Clear URL fields if channel is removed
      const updates: Partial<AlertConfigFormData> = { channels: newChannels };
      if (channel === 'slack' && prev.channels.includes('slack')) {
        updates.slack_webhook_url = '';
      }
      if (channel === 'webhook' && prev.channels.includes('webhook')) {
        updates.webhook_url = '';
      }
      
      return { ...prev, ...updates };
    });
    if (errors.channels) setErrors(prev => ({ ...prev, channels: undefined }));
  }, [errors]);

  const handleProductToggle = useCallback((productId: string) => {
    setFormData(prev => ({
      ...prev,
      product_ids: prev.product_ids.includes(productId)
        ? prev.product_ids.filter(id => id !== productId)
        : [...prev.product_ids, productId],
    }));
    if (errors.product_ids) setErrors(prev => ({ ...prev, product_ids: undefined }));
  }, [errors]);

  const handleApplyToAllToggle = useCallback((applyToAll: boolean) => {
    setFormData(prev => ({
      ...prev,
      product_ids: applyToAll ? [] : prev.product_ids,
    }));
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Additional validation for channel URLs
    const additionalErrors: AlertConfigFormErrors = {};
    if (formData.channels.includes('slack') && !formData.slack_webhook_url.trim()) {
      additionalErrors.slack_webhook_url = 'Slack webhook URL is required';
    }
    if (formData.channels.includes('webhook') && !formData.webhook_url.trim()) {
      additionalErrors.webhook_url = 'Webhook URL is required';
    }

    const result = isEditing
      ? validateAndUpdateAlertConfig(formData)
      : validateAndCreateAlertConfig(formData);

    // Handle validation failure
    if (!result.success) {
      setErrors({ ...result.errors, ...additionalErrors });
      toast.error('Please fix the errors');
      return;
    }

    // Handle additional errors even if schema validation passed
    if (Object.keys(additionalErrors).length > 0) {
      setErrors(additionalErrors);
      toast.error('Please fix the errors');
      return;
    }

    onSubmit(result.data as Parameters<typeof onSubmit>[0]);
  };

  // Get description for current alert type
  const alertTypeDescription = useMemo(() => {
    const descriptions: Record<AlertType, string> = {
      sentiment_drop: 'Triggers when sentiment score falls below your threshold',
      sentiment_spike: 'Triggers when sentiment score rises above your threshold',
      volume_surge: 'Triggers when mention volume spikes above normal',
      viral_mention: 'Triggers when a post reaches viral levels of engagement',
      competitor_price_change: 'Triggers when competitor prices change significantly',
      price_recommendation: 'Triggers when new price recommendations are generated',
      price_applied: 'Triggers when price changes are applied to your store',
      trend_detected: 'Triggers when market trends are detected',
      anomaly_detected: 'Triggers when unusual patterns are found',
    };
    return descriptions[formData.alert_type];
  }, [formData.alert_type]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Edit Alert Configuration' : 'New Alert Configuration'}
          </h2>
          <button onClick={onCancel} className="p-1 text-gray-400 hover:text-gray-600 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="e.g., Critical Sentiment Alerts"
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.name ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Optional description..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Alert Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Alert Type *</label>
            <select
              value={formData.alert_type}
              onChange={(e) => handleChange('alert_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {ALERT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
              <Info className="w-3 h-3" />
              {alertTypeDescription}
            </p>
          </div>

          {/* ═══════════════════════════════════════════════════════════════════
              THRESHOLD FIELDS (conditional based on alert type)
              ═══════════════════════════════════════════════════════════════════ */}
          {showThresholdFields && (
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 space-y-4">
              <h3 className="text-sm font-medium text-blue-900 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Threshold Settings
              </h3>
              
              <div className="grid grid-cols-2 gap-4">
                {/* Threshold Value */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Threshold Value
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="-1"
                    max="1"
                    value={formData.threshold_value}
                    onChange={(e) => handleChange('threshold_value', e.target.value)}
                    placeholder="e.g., 0.3 or -0.5"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.threshold_value ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {formData.alert_type === 'sentiment_drop' 
                      ? 'Alert when sentiment drops below this value (-1 to 1)'
                      : formData.alert_type === 'sentiment_spike'
                      ? 'Alert when sentiment rises above this value (-1 to 1)'
                      : 'Absolute threshold value'}
                  </p>
                  {errors.threshold_value && <p className="text-red-500 text-xs mt-1">{errors.threshold_value}</p>}
                </div>

                {/* Threshold Percent */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Change Threshold (%)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="100"
                    value={formData.threshold_percent}
                    onChange={(e) => handleChange('threshold_percent', e.target.value)}
                    placeholder="e.g., 15"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.threshold_percent ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Alert when value changes by more than this percentage
                  </p>
                  {errors.threshold_percent && <p className="text-red-500 text-xs mt-1">{errors.threshold_percent}</p>}
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════════
              PRODUCT SELECTION
              ═══════════════════════════════════════════════════════════════════ */}
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
            <h3 className="text-sm font-medium text-gray-900">Apply to Products</h3>
            
            {/* All Products Toggle */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="product_scope"
                checked={formData.product_ids.length === 0}
                onChange={() => handleApplyToAllToggle(true)}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">All products</span>
            </label>
            
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="product_scope"
                checked={formData.product_ids.length > 0}
                onChange={() => handleApplyToAllToggle(false)}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Selected products only</span>
            </label>

            {/* Product List (shown when "Selected products" is chosen) */}
            {formData.product_ids.length > 0 || products.length > 0 ? (
              <div className="mt-3 max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                {productsLoading ? (
                  <div className="p-4 text-center text-gray-500 text-sm">Loading products...</div>
                ) : products.length === 0 ? (
                  <div className="p-4 text-center text-gray-500 text-sm">No products found</div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {products.map((product) => (
                      <label
                        key={product.id}
                        className="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={formData.product_ids.includes(product.id)}
                          onChange={() => handleProductToggle(product.id)}
                          disabled={formData.product_ids.length === 0}
                          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 disabled:opacity-50"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">{product.name}</p>
                          {product.sku && (
                            <p className="text-xs text-gray-500">SKU: {product.sku}</p>
                          )}
                        </div>
                        <span className="text-sm text-gray-500">${product.current_price}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
            
            {formData.product_ids.length > 0 && (
              <p className="text-xs text-blue-600">
                {formData.product_ids.length} product{formData.product_ids.length !== 1 ? 's' : ''} selected
              </p>
            )}
            {errors.product_ids && <p className="text-red-500 text-xs">{errors.product_ids}</p>}
          </div>

          {/* ═══════════════════════════════════════════════════════════════════
              NOTIFICATION CHANNELS
              ═══════════════════════════════════════════════════════════════════ */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Notification Channels *</label>
            <div className="space-y-2">
              {ALERT_CHANNELS.map((channel) => (
                <label
                  key={channel.value}
                  className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={formData.channels.includes(channel.value)}
                    onChange={() => handleChannelToggle(channel.value)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{channel.label}</span>
                </label>
              ))}
            </div>
            {errors.channels && <p className="text-red-500 text-xs mt-1">{errors.channels}</p>}
          </div>

          {/* ═══════════════════════════════════════════════════════════════════
              CHANNEL URL FIELDS (conditional)
              ═══════════════════════════════════════════════════════════════════ */}
          {(showSlackUrl || showWebhookUrl) && (
            <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200 space-y-4">
              <h3 className="text-sm font-medium text-yellow-900">Channel Configuration</h3>
              
              {/* Slack Webhook URL */}
              {showSlackUrl && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Slack Webhook URL *
                  </label>
                  <input
                    type="url"
                    value={formData.slack_webhook_url}
                    onChange={(e) => handleChange('slack_webhook_url', e.target.value)}
                    placeholder="https://hooks.slack.com/services/..."
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.slack_webhook_url ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Create an incoming webhook in your Slack workspace settings
                  </p>
                  {errors.slack_webhook_url && (
                    <p className="text-red-500 text-xs mt-1">{errors.slack_webhook_url}</p>
                  )}
                </div>
              )}

              {/* Webhook URL */}
              {showWebhookUrl && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Webhook URL *
                  </label>
                  <input
                    type="url"
                    value={formData.webhook_url}
                    onChange={(e) => handleChange('webhook_url', e.target.value)}
                    placeholder="https://your-server.com/webhook"
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors.webhook_url ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    We&apos;ll POST alert data to this URL when triggered
                  </p>
                  {errors.webhook_url && (
                    <p className="text-red-500 text-xs mt-1">{errors.webhook_url}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Rate Limiting */}
          <div className="grid grid-cols-2 gap-4">
            {/* Cooldown */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Cooldown (minutes)</label>
              <input
                type="number"
                value={formData.cooldown_minutes}
                onChange={(e) => handleChange('cooldown_minutes', e.target.value)}
                min={1}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Min time between alerts</p>
            </div>

            {/* Max per day */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Per Day</label>
              <input
                type="number"
                value={formData.max_per_day}
                onChange={(e) => handleChange('max_per_day', e.target.value)}
                min={1}
                placeholder="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Daily alert limit</p>
            </div>
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Enable this configuration</span>
            <button
              type="button"
              onClick={() => handleChange('is_active', !formData.is_active)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.is_active ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.is_active ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Saving...' : isEditing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}



