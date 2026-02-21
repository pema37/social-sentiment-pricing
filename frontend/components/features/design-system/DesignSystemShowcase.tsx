import { colors } from '@/lib/theme';
import { SectionHeader } from '@/components/ui';
import { AlertsSection } from './alerts-section';
import { DashboardPreviewSection } from './dashboard-preview-section';
import { DataSection } from './data-section';
import { PrimitivesSection } from './primitives-section';

export function DesignSystemShowcase() {
  return (
    <div className="space-y-6 px-6 py-6" style={{ backgroundColor: colors.background.light }}>
      <SectionHeader
        title="Design System"
        description="Reference page for reusable ActualPrice interface components."
      />
      <DashboardPreviewSection />
      <div className="grid gap-6" style={{ color: colors.text.body }}>
        <PrimitivesSection />
        <DataSection />
        <AlertsSection />
      </div>
    </div>
  );
}
