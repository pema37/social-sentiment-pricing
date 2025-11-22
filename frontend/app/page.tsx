// frontend/app/page.tsx
// frontend/app/page.tsx
import React from "react";
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="max-w-md mx-auto text-center px-4">
        <h1 className="text-2xl font-semibold text-slate-900 mb-3">
          Social Sentiment Pricing
        </h1>
        <p className="text-sm text-slate-500 mb-6">
          Welcome. Go to your dashboard to manage products and pricing.
        </p>

        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center rounded-xl bg-slate-900 text-white text-sm font-medium px-4 py-2 hover:bg-slate-800"
        >
          Go to dashboard
        </Link>
      </div>
    </main>
  );
}
