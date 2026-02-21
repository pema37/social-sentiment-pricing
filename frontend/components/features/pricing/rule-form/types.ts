// frontend/components/features/pricing/rule-form/types.ts
// Re-export from domain layer for backwards compatibility

export type { 
  RuleFormData, 
  RuleFormErrors,
  ScopeType,
} from '@/lib/domain/pricing';

export interface RuleFormSectionProps {
  data: import('@/lib/domain/pricing').RuleFormData;
  errors: import('@/lib/domain/pricing').RuleFormErrors;
  onChange: (field: keyof import('@/lib/domain/pricing').RuleFormData, value: string | boolean | number | string[]) => void;
}


