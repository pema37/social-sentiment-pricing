import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'SSP Demo - AI-Powered Dynamic Pricing | Gemini 3 Hackathon',
  description: 'Experience Social Sentiment Pricing: AI that watches social media, tracks competitors, and optimizes your e-commerce prices in real-time. Built with Google Gemini 3.',
  keywords: ['AI pricing', 'dynamic pricing', 'e-commerce', 'sentiment analysis', 'Gemini 3', 'hackathon'],
  openGraph: {
    title: 'Social Sentiment Pricing - Gemini 3 Hackathon',
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


