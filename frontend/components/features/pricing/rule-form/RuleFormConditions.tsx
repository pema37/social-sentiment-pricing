// frontend/components/features/pricing/rule-form/RuleFormConditions.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { CompetitorSelect } from '@/components/ui/CompetitorSelect';
import { cn } from '@/lib/utils';
import type { RuleType } from '@/types';
import type { RuleFormSectionProps } from './types';

const ruleTypes: { value: RuleType; label: string; description: string }[] = [
  { value: 'sentiment_threshold', label: 'Sentiment Threshold', description: 'Trigger when sentiment crosses threshold' },
  { value: 'competitor_relative', label: 'Competitor Relative', description: 'React to competitor price changes' },
  { value: 'time_based', label: 'Time-Based', description: 'Adjust based on time patterns' },
  { value: 'volume_surge', label: 'Volume Surge', description: 'Respond to demand increases' },
  { value: 'viral_detection', label: 'Viral Detection', description: 'Detect viral social activity' },
];

const sentimentDirections = [
  { value: 'above', label: 'Above threshold' },
  { value: 'below', label: 'Below threshold' },
];

const pricePositions = [
  { value: 'below', label: 'Below competitor' },
  { value: 'match', label: 'Match competitor' },
  { value: 'above', label: 'Above competitor' },
];

export function RuleFormConditions({ data, errors, onChange }: RuleFormSectionProps) {
  const inputClass = (field: keyof typeof errors) => cn(
    'w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
    errors[field] ? 'border-red-300' : 'border-gray-300'
  );

  return (
    <>
      {/* Rule Type Selection */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Rule Type</h2>
        <div className="grid gap-2">
          {ruleTypes.map((type) => (
            <button
              key={type.value}
              type="button"
              onClick={() => onChange('rule_type', type.value)}
              className={cn(
                'p-3 text-left border rounded-lg transition-colors',
                data.rule_type === type.value
                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500'
                  : 'border-gray-200 hover:border-gray-300'
              )}
            >
              <p className="font-medium text-gray-900 text-sm">{type.label}</p>
              <p className="text-xs text-gray-500">{type.description}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Type-Specific Conditions */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Conditions</h2>
        <div className="space-y-4">
          {data.rule_type === 'sentiment_threshold' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sentiment Threshold <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  value={data.sentiment_threshold}
                  onChange={(e) => onChange('sentiment_threshold', e.target.value)}
                  min={-1}
                  max={1}
                  step={0.1}
                  placeholder="0.7"
                  className={inputClass('sentiment_threshold')}
                />
                {errors.sentiment_threshold && <p className="mt-1 text-sm text-red-600">{errors.sentiment_threshold}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Direction</label>
                <select
                  value={data.sentiment_direction}
                  onChange={(e) => onChange('sentiment_direction', e.target.value)}
                  className={inputClass('sentiment_direction')}
                >
                  {sentimentDirections.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {data.rule_type === 'competitor_relative' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Competitor</label>
                <CompetitorSelect
                  value={data.competitor_id}
                  onChange={(value) => onChange('competitor_id', value)}
                  allowAny={true}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Select a specific competitor or leave as &quot;Any&quot; to react to all competitors
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Price Position</label>
                <select
                  value={data.price_position}
                  onChange={(e) => onChange('price_position', e.target.value)}
                  className={inputClass('price_position')}
                >
                  {pricePositions.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {data.rule_type === 'time_based' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Days <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={data.time_days}
                onChange={(e) => onChange('time_days', e.target.value)}
                placeholder="monday, tuesday, friday"
                className={inputClass('time_days')}
              />
              {errors.time_days && <p className="mt-1 text-sm text-red-600">{errors.time_days}</p>}
            </div>
          )}

          {data.rule_type === 'volume_surge' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Volume Threshold (%) <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                value={data.volume_threshold}
                onChange={(e) => onChange('volume_threshold', e.target.value)}
                min={1}
                placeholder="50"
                className={inputClass('volume_threshold')}
              />
              {errors.volume_threshold && <p className="mt-1 text-sm text-red-600">{errors.volume_threshold}</p>}
            </div>
          )}

          {data.rule_type === 'viral_detection' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reach Threshold <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                value={data.viral_threshold_reach}
                onChange={(e) => onChange('viral_threshold_reach', e.target.value)}
                min={1000}
                placeholder="10000"
                className={inputClass('viral_threshold_reach')}
              />
              {errors.viral_threshold_reach && <p className="mt-1 text-sm text-red-600">{errors.viral_threshold_reach}</p>}
            </div>
          )}
        </div>
      </Card>
    </>
  );
}
