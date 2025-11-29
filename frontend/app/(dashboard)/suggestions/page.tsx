// Price Suggestions Page
'use client';

import { SectionHeader, Card } from '@/components/ui';

export default function SuggestionsPage() {
  return (
    <div>
      <SectionHeader
        title="Price Suggestions"
        description="Review AI-generated pricing recommendations"
      />

      <Card>
        <div className="h-64 flex items-center justify-center text-gray-400">
          Price suggestions coming soon...
        </div>
      </Card>
    </div>
  );
}
