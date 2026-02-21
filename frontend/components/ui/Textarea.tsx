import { colors } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { TextareaHTMLAttributes, forwardRef } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, id, ...props }, ref) => (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1 block text-sm font-medium" style={{ color: colors.text.body }}>
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={id}
        className={cn('min-h-24 w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2', className)}
        style={{
          borderColor: colors.border.input,
          backgroundColor: colors.background.white,
          color: colors.text.title,
          ['--tw-ring-color' as string]: colors.primary.ring,
        }}
        {...props}
      />
    </div>
  )
);

Textarea.displayName = 'Textarea';
