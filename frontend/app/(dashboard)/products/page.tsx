// Products Page
'use client';

import { SectionHeader, Button, Card } from '@/components/ui';
import { Plus } from 'lucide-react';

export default function ProductsPage() {
  return (
    <div>
      <SectionHeader
        title="Products"
        description="Manage your tracked products"
        action={
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Product
          </Button>
        }
      />

      <Card>
        <div className="h-64 flex items-center justify-center text-gray-400">
          Product list coming soon...
        </div>
      </Card>
    </div>
  );
}

