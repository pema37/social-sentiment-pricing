'use client';

/**
 * IntegrationsList
 * 
 * Displays a list of connected e-commerce integrations with status and actions.
 */

import { Integration } from '@/types/integration';
import { IntegrationCard } from './IntegrationCard';

interface IntegrationsListProps {
  integrations: Integration[];
}

export function IntegrationsList({ integrations }: IntegrationsListProps) {
  if (integrations.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {integrations.map((integration) => (
        <IntegrationCard key={integration.id} integration={integration} />
      ))}
    </div>
  );
}
