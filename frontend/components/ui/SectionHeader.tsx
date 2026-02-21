// SectionHeader Component
// Used at the top of pages/sections with title and optional action button

import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface SectionHeaderProps {
  title: ReactNode;           // Main heading text (can include components)
  description?: string;       // Optional subtitle/description
  action?: ReactNode;         // Optional action button on the right
  className?: string;
}

export function SectionHeader({ 
  title, 
  description, 
  action, 
  className 
}: SectionHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-6', className)}>
      {/* Left side - Title and description */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-gray-500">
            {description}
          </p>
        )}
      </div>
      
      {/* Right side - Action button */}
      {action && (
        <div>{action}</div>
      )}
    </div>
  );
}
