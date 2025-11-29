// frontend/components/layout/AuthShell.tsx
import React from "react";

type AuthShellProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
};

export function AuthShell({ title, description, children }: AuthShellProps) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white shadow-sm rounded-2xl border border-slate-200 px-6 py-8 md:px-8">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
            {description && (
              <p className="mt-2 text-sm text-slate-500">{description}</p>
            )}
          </div>

          {children}
        </div>

        <p className="mt-4 text-center text-xs text-slate-400">
          Social Sentiment Pricing · v0.1
        </p>
      </div>
    </div>
  );
}
