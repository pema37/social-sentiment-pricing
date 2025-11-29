// Sentiment Page
'use client';

import { SectionHeader, Card } from '@/components/ui';

export default function SentimentPage() {
  return (
    <div>
      <SectionHeader
        title="Sentiment"
        description="View social media sentiment analysis"
      />

      <Card>
        <div className="h-64 flex items-center justify-center text-gray-400">
          Sentiment feed coming soon...
        </div>
      </Card>
    </div>
  );
}
