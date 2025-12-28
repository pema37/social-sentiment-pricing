// Root Layout
// Wraps the entire app with providers and global styles

import type { Metadata } from 'next';
import { Providers } from './providers';
import { Toaster } from '@/components/ui/Toaster';
import './globals.css';

// SEO metadata
export const metadata: Metadata = {
  title: 'ActualPrice',
  description: 'AI-powered pricing optimization for e-commerce',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
