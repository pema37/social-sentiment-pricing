// frontend/components/features/pricing/rule-form/types.ts

import type { RuleType, RuleAction } from '@/types';

export type ScopeType = 'single' | 'multiple' | 'categories' | 'all';

export interface RuleFormData {
  name: string;
  description: string;
  rule_type: RuleType;
  is_active: boolean;
  priority: number;
  scope_type: ScopeType;
  product_id: string;
  applies_to_products: string[];
  applies_to_categories: string[];
  sentiment_threshold: string;
  sentiment_direction: string;
  competitor_id: string;
  price_position: string;
  time_days: string;
  volume_threshold: string;
  viral_threshold_reach: string;
  action: RuleAction;
  action_value: string;
  max_change_percent: string;
  min_price: string;
  max_price: string;
  cooldown_hours: string;
}

export type RuleFormErrors = Partial<Record<keyof RuleFormData, string>>;

export interface RuleFormSectionProps {
  data: RuleFormData;
  errors: RuleFormErrors;
  onChange: (field: keyof RuleFormData, value: string | boolean | number | string[]) => void;
}
