// API Keys Page
'use client';

import { SectionHeader, Button, Card } from '@/components/ui';
import { Plus } from 'lucide-react';

export default function ApiKeysPage() {
  return (
    <div>
      <SectionHeader
        title="API Keys"
        description="Manage your API keys for integrations"
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Generate Key
          </Button>
        }
      />

      <Card>
        <div className="h-64 flex items-center justify-center text-gray-400">
          API key management coming soon...
        </div>
      </Card>
    </div>
  );
}
