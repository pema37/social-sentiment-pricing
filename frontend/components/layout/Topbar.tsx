// frontend/components/layout/Topbar.tsx
import React from "react";

type TopbarProps = {
  title?: string;
};

export function Topbar({ title }: TopbarProps) {
  return (
    <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-4 md:px-8">
      <div className="font-semibold text-sm md:text-base text-slate-900">
        {title ?? "Dashboard"}
      </div>

      <div className="flex items-center gap-3 text-xs md:text-sm text-slate-500">
        {/* TODO: replace with real user menu */}
        <span>Logged in</span>
      </div>
    </header>
  );
}
