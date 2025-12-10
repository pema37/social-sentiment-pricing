import { memo, ReactNode } from 'react';
import { Card } from '@/components/ui';
import { cn } from '@/lib/utils';

export const EmptyState = memo(function EmptyState({ icon, title, description, className }: { icon?: ReactNode; title: string; description?: string; className?: string }) {
  return (
    <Card className={cn('p-8', className)}>
      <div className="flex flex-col items-center justify-center h-64 text-gray-500">
        <div className="mb-4 text-gray-400">
          {icon || (
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          )}
        </div>
        <p className="text-lg font-medium text-gray-700">{title}</p>
        {description && <p className="text-sm mt-1 text-center max-w-md">{description}</p>}
      </div>
    </Card>
  );
});
