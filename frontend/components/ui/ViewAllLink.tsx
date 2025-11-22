import Link from "next/link";
import React from "react";

export function ViewAllLink({ href }: { href: string }) {
  return (
    <Link
      href={href}
      className="text-sm font-medium text-slate-900 hover:underline"
    >
      View all →
    </Link>
  );
}
