// Auth Layout
// Wraps all auth pages (login, register, forgot-password)
// If inside Shopify embedded context, redirects to dashboard (session tokens handle auth)

import { AuthShell } from '@/components/layout';
import { AuthEmbeddedGate } from './embedded-gate';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthEmbeddedGate>
      <AuthShell>{children}</AuthShell>
    </AuthEmbeddedGate>
  );
}

