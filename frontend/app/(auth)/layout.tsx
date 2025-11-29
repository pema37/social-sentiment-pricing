// Auth Layout
// Wraps all auth pages (login, register, forgot-password)

import { AuthShell } from '@/components/layout';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthShell>{children}</AuthShell>;
}
