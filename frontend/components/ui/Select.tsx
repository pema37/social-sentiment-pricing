import { colors } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { SelectHTMLAttributes } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({ className, label, id, children, ...props }: SelectProps) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1 block text-sm font-medium" style={{ color: colors.text.body }}>
          {label}
        </label>
      )}
      <select
        id={id}
        className={cn('h-11 w-full rounded-lg border px-3 text-sm focus:outline-none focus:ring-2', className)}
        style={{
          borderColor: colors.border.input,
          backgroundColor: colors.background.white,
          color: colors.text.title,
          ['--tw-ring-color' as string]: colors.primary.ring,
        }}
        {...props}
      >
        {children}
      </select>
    </div>
  );
}
