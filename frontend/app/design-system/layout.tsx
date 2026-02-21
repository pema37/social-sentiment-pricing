import type { Metadata } from 'next';
import { colors } from '@/lib/theme';

export const metadata: Metadata = {
  title: 'ActualPrice - Design System',
  description: 'Showcase of ActualPrice UI components, layout patterns, and feedback states.',
  keywords: ['ActualPrice', 'design system', 'UI components', 'showcase', 'Next.js'],
  openGraph: {
    title: 'ActualPrice Design System',
    description: 'Reusable UI patterns and components used across ActualPrice.',
    type: 'website',
  },
};

export default function DesignSystemLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen" style={{ backgroundColor: colors.background.light }}>{children}</div>;
}
