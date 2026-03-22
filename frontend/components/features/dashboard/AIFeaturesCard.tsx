// components/features/dashboard/AIFeaturesCard.tsx
'use client';

import Link from 'next/link';
import { 
  Brain, 
  Sparkles, 
  TrendingUp, 
  AlertTriangle, 
  Target,
  BarChart3,
  ArrowRight
} from 'lucide-react';
import { Card, CardTitle } from '@/components/ui';

interface AIFeature {
  name: string;
  description: string;
  icon: typeof Brain;
  href: string;
  color: string;
  bgColor: string;
}

const aiFeatures: AIFeature[] = [
  {
    name: 'AI Sentiment',
    description: 'AI-powered analysis',
    icon: Brain,
    href: '/sentiment',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  {
    name: 'AI Descriptions',
    description: 'SEO-optimized copy',
    icon: Sparkles,
    href: '/products',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  {
    name: 'AI Pricing',
    description: 'Smart explanations',
    icon: TrendingUp,
    href: '/pricing',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  {
    name: 'AI Competitor',
    description: 'Strategy detection',
    icon: Target,
    href: '/competitors',
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  {
    name: 'Crisis Detection',
    description: 'Sentiment alerts',
    icon: AlertTriangle,
    href: '/alerts',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
  },
  {
    name: 'Market Trends',
    description: 'Trending products',
    icon: BarChart3,
    href: '/trends',
    color: 'text-teal-600',
    bgColor: 'bg-teal-50',
  },
];

export function AIFeaturesCard() {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-linear-to-br from-purple-500 to-blue-500 rounded-lg">
            <Brain className="h-4 w-4 text-white" />
          </div>
          <CardTitle>AI Features</CardTitle>
          <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded-full">
            Gemini 2.0
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {aiFeatures.map((feature) => {
          const Icon = feature.icon;
          return (
            <Link
              key={feature.name}
              href={feature.href}
              className="group p-3 rounded-lg border border-gray-200 hover:border-purple-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-start gap-2">
                <div className={`p-1.5 rounded-md ${feature.bgColor}`}>
                  <Icon className={`h-4 w-4 ${feature.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {feature.name}
                  </p>
                  <p className="text-xs text-gray-500 truncate">
                    {feature.description}
                  </p>
                </div>
              </div>
              <div className="mt-2 flex items-center text-xs text-purple-600 opacity-0 group-hover:opacity-100 transition-opacity">
                <span>Open</span>
                <ArrowRight className="h-3 w-3 ml-1" />
              </div>
            </Link>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-500 text-center">
          Powered by Google Gemini 2.0 Flash • All features work with or without AI
        </p>
      </div>
    </Card>
  );
}

export default AIFeaturesCard;

