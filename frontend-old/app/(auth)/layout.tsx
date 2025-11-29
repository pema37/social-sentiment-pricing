// frontend/app/(auth)/layout.tsx
import React from "react";
import { AuthShell } from "@/components/layout/AuthShell";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthShell
      title="Welcome to SSP"
      description="Log in or create an account to manage your pricing."
    >
      {children}
    </AuthShell>
  );
}
