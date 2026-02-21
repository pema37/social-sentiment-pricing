import Link from 'next/link';
import { colors } from '@/lib/theme';
import { Badge, Button, Card, CardHeader, CardTitle, Input, Select, Textarea } from '@/components/ui';

export function PrimitivesSection() {
  return (
    <Card padding="lg" className="space-y-4">
      <CardHeader>
        <CardTitle>Core Inputs And Actions</CardTitle>
        <p className="text-sm" style={{ color: colors.text.secondary }}>
          Buttons, badges, and form controls in one consistent interaction style.
        </p>
      </CardHeader>
      <div className="space-y-6">
        <div className="flex flex-wrap gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="danger">Destructive</Button>
          <Button variant="ghost" style={{ borderColor: colors.border.input, borderWidth: 1 }}>Outline</Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge>Default</Badge>
          <Badge variant="success">Stable</Badge>
          <Badge variant="warning">Attention</Badge>
          <Badge variant="danger">Critical</Badge>
          <Badge variant="info">Live</Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Input id="ds-name" label="Product name" placeholder="Aurora Headphones" />
          <Select id="ds-channel" label="Sales channel" defaultValue="shopify">
            <option value="shopify">Shopify</option>
            <option value="woocommerce">WooCommerce</option>
            <option value="marketplace">Marketplace</option>
          </Select>
          <div className="md:col-span-2">
            <Textarea
              id="ds-summary"
              label="Pricing note"
              placeholder="Summarize the social signals behind this recommendation."
            />
          </div>
        </div>

        <Link href="/dashboard" className="text-sm font-medium" style={{ color: colors.primary.default }}>
          Back to dashboard
        </Link>
      </div>
    </Card>
  );
}
