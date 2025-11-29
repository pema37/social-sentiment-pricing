import React from "react";

type SectionHeaderProps = {
  title: string;
  description?: string;
  right?: React.ReactNode; // ex: button, link, dropdown
};

export function SectionHeader({ title, description, right }: SectionHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {description && (
          <p className="text-sm text-slate-500 mt-1">{description}</p>
        )}
      </div>

      {right && <div>{right}</div>}
    </div>
  );
}

