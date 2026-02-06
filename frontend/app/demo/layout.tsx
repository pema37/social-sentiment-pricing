import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'ActualPrice Demo - AI-Powered Dynamic Pricing | Gemini API Developer Competition',
  description: 'Experience ActualPrice: AI that watches social sentiment, tracks competitors, and optimizes your e-commerce prices in real-time. Built with Google Gemini.',
  keywords: ['AI pricing', 'dynamic pricing', 'e-commerce', 'sentiment analysis', 'Google Gemini', 'ActualPrice'],
  openGraph: {
    title: 'ActualPrice - AI-Powered Dynamic Pricing',
    description: 'AI-powered dynamic pricing that watches social sentiment and automatically adjusts prices.',
    type: 'website',
  },
};

export default function DemoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // No authentication wrapper - demos are public
  return (
    <div className="min-h-screen">
      {children}
    </div>
  );
}

