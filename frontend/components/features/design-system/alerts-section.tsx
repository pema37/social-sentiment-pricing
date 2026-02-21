import { colors } from '@/lib/theme';
import { Alert, Card, CardHeader, CardTitle } from '@/components/ui';

export function AlertsSection() {
  return (
    <Card padding="lg" className="space-y-4">
      <CardHeader>
        <CardTitle>Feedback States</CardTitle>
        <p className="text-sm" style={{ color: colors.text.secondary }}>
          Success, warning, error, and info alerts with consistent tone and spacing.
        </p>
      </CardHeader>
      <div className="grid gap-3 md:grid-cols-2">
        <Alert variant="success" title="Sync completed">
          Product catalog finished syncing with Shopify 2 minutes ago.
        </Alert>
        <Alert variant="warning" title="Pricing drift detected">
          Suggested margin dropped below target on 3 monitored products.
        </Alert>
        <Alert variant="error" title="Connection failed">
          Competitor feed timed out. Retry the integration to restore updates.
        </Alert>
        <Alert variant="info" title="New insight">
          Sentiment momentum increased 14% after the latest campaign.
        </Alert>
      </div>
    </Card>
  );
}
