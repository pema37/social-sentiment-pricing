import Link from 'next/link';
import { BarChart3, Bell, LayoutDashboard, Settings } from 'lucide-react';
import { colors } from '@/lib/theme';
import { Card, CardHeader, CardTitle } from '@/components/ui';

const nav = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  { label: 'Alerts', href: '/alerts', icon: Bell },
  { label: 'Settings', href: '/settings', icon: Settings },
];

export function DashboardPreviewSection() {
  return (
    <Card padding="lg" className="space-y-4">
      <CardHeader>
        <CardTitle>Dashboard Layout Pattern</CardTitle>
        <p className="text-sm" style={{ color: colors.text.secondary }}>
          Sidebar navigation and content area using the same visual language as the app.
        </p>
      </CardHeader>
      <Card padding="none" className="overflow-hidden">
        <div className="grid min-h-72 md:grid-cols-[220px_1fr]">
          <aside className="p-4" style={{ backgroundColor: colors.background.dark, color: colors.text.onDark }}>
            <p className="mb-4 text-xs font-semibold uppercase tracking-widest" style={{ color: colors.text.secondary }}>
              Navigation
            </p>
            <nav className="space-y-1">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-opacity hover:opacity-80"
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <section className="space-y-4 p-6" style={{ backgroundColor: colors.background.light }}>
            <CardTitle>Dashboard Layout Preview</CardTitle>
            <div className="grid gap-3 md:grid-cols-3">
              <Card className="p-4"><p className="text-sm" style={{ color: colors.text.secondary }}>Revenue uplift</p><p className="text-2xl font-semibold">+12.8%</p></Card>
              <Card className="p-4"><p className="text-sm" style={{ color: colors.text.secondary }}>Active alerts</p><p className="text-2xl font-semibold">07</p></Card>
              <Card className="p-4"><p className="text-sm" style={{ color: colors.text.secondary }}>Rules applied</p><p className="text-2xl font-semibold">43</p></Card>
            </div>
          </section>
        </div>
      </Card>
    </Card>
  );
}
