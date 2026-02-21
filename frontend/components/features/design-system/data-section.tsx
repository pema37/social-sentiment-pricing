import { colors } from '@/lib/theme';
import { Badge, Card, CardHeader, CardTitle, Table, TableCell, TableHeadCell, TableWrapper } from '@/components/ui';

const rows = [
  { product: 'Aurora Headphones', sentiment: '+18%', suggestion: '$159.00', status: 'Ready' },
  { product: 'Nebula Smart Lamp', sentiment: '+7%', suggestion: '$69.00', status: 'Review' },
  { product: 'Pulse Fitness Band', sentiment: '-5%', suggestion: '$119.00', status: 'Watch' },
];

export function DataSection() {
  return (
    <Card padding="lg" className="space-y-4">
      <CardHeader>
        <CardTitle>Data Presentation</CardTitle>
        <p className="text-sm" style={{ color: colors.text.secondary }}>
          Pricing decisions displayed in a table with status badges and realistic values.
        </p>
      </CardHeader>
      <TableWrapper>
        <Table>
          <thead>
            <tr>
              <TableHeadCell>Product</TableHeadCell>
              <TableHeadCell>Sentiment</TableHeadCell>
              <TableHeadCell>Suggested Price</TableHeadCell>
              <TableHeadCell>Status</TableHeadCell>
            </tr>
          </thead>
          <tbody style={{ backgroundColor: colors.background.white }}>
            {rows.map((row) => (
              <tr key={row.product}>
                <TableCell className="font-medium" style={{ color: colors.text.title }}>{row.product}</TableCell>
                <TableCell>{row.sentiment}</TableCell>
                <TableCell>{row.suggestion}</TableCell>
                <TableCell>
                  <Badge variant={row.status === 'Ready' ? 'success' : row.status === 'Review' ? 'warning' : 'info'}>
                    {row.status}
                  </Badge>
                </TableCell>
              </tr>
            ))}
          </tbody>
        </Table>
      </TableWrapper>
    </Card>
  );
}
