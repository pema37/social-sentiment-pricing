// components/ui/ai-badge.tsx
import { Sparkles } from 'lucide-react';

interface AIBadgeProps {
  size?: 'sm' | 'md';
}

export function AIBadge({ size = 'sm' }: AIBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1 px-2 py-0.5 
        bg-gradient-to-r from-purple-100 to-blue-100
        text-purple-700 rounded-full font-medium
        ${size === 'sm' ? 'text-xs' : 'text-sm'}
      `}
    >
      <Sparkles className={size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />
      AI Powered
    </span>
  );
}
