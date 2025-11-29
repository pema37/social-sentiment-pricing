// Competitors Page
'use client';

import { SectionHeader, Button, Card } from '@/components/ui';
import { Plus } from 'lucide-react';

export default function CompetitorsPage() {
  return (
    <div>
      <SectionHeader
        title="Competitors"
        description="Track and compare competitor pricing"
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Competitor
          </Button>
        }
      />

      <Card>
        <div className="h-64 flex items-center justify-center text-gray-400">
          Competitor tracking coming soon...
        </div>
      </Card>
    </div>
  );
}
