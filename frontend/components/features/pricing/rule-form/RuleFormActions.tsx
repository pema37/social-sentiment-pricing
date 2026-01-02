// frontend/components/features/pricing/rule-form/RuleFormActions.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import type { RuleAction } from '@/types';
import type { RuleFormSectionProps } from './types';

const ruleActions: { value: RuleAction; label: string }[] = [
  { value: 'increase_percent', label: 'Increase by percentage' },
  { value: 'decrease_percent', label: 'Decrease by percentage' },
  { value: 'set_absolute', label: 'Set to absolute price' },
  { value: 'match_competitor', label: 'Match competitor price' },
  { value: 'undercut_competitor', label: 'Undercut competitor' },
];

// Actions that don't require a value input
const ACTIONS_WITHOUT_VALUE = ['match_competitor'];

export function RuleFormActions({ data, errors, onChange }: RuleFormSectionProps) {
  const inputClass = (field: keyof typeof errors) => cn(
    'w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
    errors[field] ? 'border-red-300' : 'border-gray-300'
  );

  const requiresValue = !ACTIONS_WITHOUT_VALUE.includes(data.action);

  return (
    <>
      {/* Action */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Action</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Action Type</label>
            <select
              value={data.action}
              onChange={(e) => onChange('action', e.target.value)}
              className={inputClass('action')}
            >
              {ruleActions.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          {/* Only show Action Value for actions that need it */}
          {requiresValue && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Action Value <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={data.action_value}
                onChange={(e) => onChange('action_value', e.target.value)}
                placeholder={data.action.includes('percent') ? 'e.g., 10 (for 10%)' : 'e.g., 29.99'}
                className={inputClass('action_value')}
              />
              {errors.action_value && <p className="mt-1 text-sm text-red-600">{errors.action_value}</p>}
            </div>
          )}

          {/* Show info message when action doesn't need value */}
          {!requiresValue && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-700">
                This action will automatically match the competitor&apos;s price. No value needed.
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* Constraints */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Safety Constraints</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Change (%)</label>
            <input
              type="number"
              value={data.max_change_percent}
              onChange={(e) => onChange('max_change_percent', e.target.value)}
              min={0}
              max={100}
              placeholder="20"
              className={inputClass('max_change_percent')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cooldown (hours)</label>
            <input
              type="number"
              value={data.cooldown_hours}
              onChange={(e) => onChange('cooldown_hours', e.target.value)}
              min={1}
              placeholder="24"
              className={inputClass('cooldown_hours')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min Price</label>
            <input
              type="number"
              value={data.min_price}
              onChange={(e) => onChange('min_price', e.target.value)}
              min={0}
              step={0.01}
              placeholder="0.00"
              className={inputClass('min_price')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Price</label>
            <input
              type="number"
              value={data.max_price}
              onChange={(e) => onChange('max_price', e.target.value)}
              min={0}
              step={0.01}
              placeholder="999.99"
              className={inputClass('max_price')}
            />
          </div>
        </div>
      </Card>
    </>
  );
}

