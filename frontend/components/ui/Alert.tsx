import { cn } from '@/lib/utils';
import { colors } from '@/lib/theme';
import { ReactNode } from 'react';

type AlertVariant = 'success' | 'warning' | 'error' | 'info';

interface AlertProps {
  title: string;
  children: ReactNode;
  variant?: AlertVariant;
}

const variantStyles: Record<AlertVariant, React.CSSProperties> = {
  success: { borderColor: colors.success.border, backgroundColor: colors.success.light, color: colors.success.default },
  warning: { borderColor: colors.warning.border, backgroundColor: colors.warning.light, color: colors.warning.default },
  error: { borderColor: colors.error.border, backgroundColor: colors.error.light, color: colors.error.default },
  info: { borderColor: colors.info.border, backgroundColor: colors.info.light, color: colors.info.default },
};

export function Alert({ title, children, variant = 'info' }: AlertProps) {
  return (
    <div className={cn('rounded-lg border p-4')} style={variantStyles[variant]} role="alert">
      <h4 className="text-sm font-semibold">{title}</h4>
      <p className="mt-1 text-sm">{children}</p>
    </div>
  );
}
