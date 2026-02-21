import { colors } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { HTMLAttributes, TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react';

export function TableWrapper({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('overflow-x-auto rounded-lg border', className)}
      style={{ borderColor: colors.border.default, backgroundColor: colors.background.white }}
      {...props}
    />
  );
}

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn('min-w-full text-sm', className)} {...props} />;
}

export function TableHeadCell({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn('border-b px-4 py-3 text-left font-semibold', className)}
      style={{
        borderColor: colors.border.default,
        backgroundColor: colors.neutral.light,
        color: colors.text.body,
      }}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn('border-b px-4 py-3', className)} style={{ borderColor: colors.border.default, color: colors.text.body }} {...props} />
  );
}
