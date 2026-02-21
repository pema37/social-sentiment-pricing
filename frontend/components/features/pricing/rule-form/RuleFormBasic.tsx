// frontend/components/features/pricing/rule-form/RuleFormBasic.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import type { RuleFormSectionProps } from './types';

export function RuleFormBasic({ data, errors, onChange }: RuleFormSectionProps) {
  return (
    <Card padding="md">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>
      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Rule Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={data.name}
            onChange={(e) => onChange('name', e.target.value)}
            placeholder="e.g., Increase price on positive sentiment"
            className={cn(
              'w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
              errors.name ? 'border-red-300' : 'border-gray-300'
            )}
          />
          {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            value={data.description}
            onChange={(e) => onChange('description', e.target.value)}
            placeholder="Describe what this rule does..."
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Priority & Status */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <input
              type="number"
              value={data.priority}
              onChange={(e) => onChange('priority', parseInt(e.target.value) || 0)}
              min={1}
              max={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <div className="flex gap-2 mt-1">
              <button
                type="button"
                onClick={() => onChange('is_active', true)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                  data.is_active
                    ? 'bg-green-100 text-green-800 ring-2 ring-green-500'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Active
              </button>
              <button
                type="button"
                onClick={() => onChange('is_active', false)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                  !data.is_active
                    ? 'bg-gray-200 text-gray-800 ring-2 ring-gray-500'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                Inactive
              </button>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

