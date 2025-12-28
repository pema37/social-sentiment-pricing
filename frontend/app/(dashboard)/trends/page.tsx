'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, Sparkles, RefreshCw, Filter } from 'lucide-react';
import { AIBadge } from '@/components/ui/ai-badge';

interface TrendingProduct {
  rank: number;
  name: string;
  category: string;
  price_range: string;
  trend_score: number;
  sentiment: string;
  source: string;
  reason: string;
}

interface Category {
  id: string;
  name: string;
  icon: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function TrendsPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Fetch categories
  const { data: categoriesData } = useQuery({
    queryKey: ['trend-categories'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/market-trends/categories`);
      return res.json();
    }
  });

  // Fetch trends
  const { 
    data: trendsData, 
    isLoading, 
    refetch,
    isFetching 
  } = useQuery({
    queryKey: ['market-trends', selectedCategory],
    queryFn: async () => {
      const url = selectedCategory 
        ? `${API_URL}/api/v1/market-trends/trends?category=${selectedCategory}&limit=10`
        : `${API_URL}/api/v1/market-trends/trends?limit=10`;
      const res = await fetch(url);
      return res.json();
    }
  });

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'text-green-600 bg-green-50';
      case 'negative': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getTrendScoreColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    return 'bg-gray-400';
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#111827] flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-purple-600" />
            Market Trends
            <AIBadge />
          </h1>
          <p className="text-[#6B7280] mt-1">
            AI-analyzed trending products across e-commerce platforms
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 bg-[#1F2937] text-white rounded-lg hover:bg-[#374151] disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Category Filters */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="h-4 w-4 text-[#6B7280]" />
          <span className="text-sm text-[#6B7280]">Filter by category:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-3 py-2 rounded-full text-sm transition-all ${
              !selectedCategory
                ? 'bg-[#1F2937] text-white'
                : 'bg-[#F3F4F6] hover:bg-[#E5E7EB] text-[#374151]'
            }`}
          >
            🔥 All Trending
          </button>
          {categoriesData?.categories?.map((cat: Category) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-2 rounded-full text-sm transition-all ${
                selectedCategory === cat.id
                  ? 'bg-[#1F2937] text-white'
                  : 'bg-[#F3F4F6] hover:bg-[#E5E7EB] text-[#374151]'
              }`}
            >
              {cat.icon} {cat.name}
            </button>
          ))}
        </div>
      </div>

      {/* AI Summary */}
      {trendsData?.ai_summary && (
        <div className="mb-6 p-4 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-100 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-4 w-4 text-purple-600" />
            <span className="text-sm font-medium text-purple-700">AI Market Summary</span>
          </div>
          <p className="text-[#374151]">{trendsData.ai_summary}</p>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-3 text-purple-600">
            <Sparkles className="h-5 w-5 animate-pulse" />
            <span>AI is analyzing market trends...</span>
          </div>
        </div>
      )}

      {/* Trends Grid */}
      {!isLoading && trendsData?.trends && (
        <div className="grid gap-4">
          {trendsData.trends.map((trend: TrendingProduct) => (
            <div
              key={trend.rank}
              className="p-4 bg-white border border-[#E5E7EB] rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="flex items-start gap-4">
                {/* Rank Badge */}
                <div className="shrink-0 w-10 h-10 bg-[#1F2937] text-white rounded-full flex items-center justify-center font-bold">
                  #{trend.rank}
                </div>

                {/* Product Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-[#111827] truncate">
                      {trend.name}
                    </h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getSentimentColor(trend.sentiment)}`}>
                      {trend.sentiment}
                    </span>
                  </div>
                  
                  <p className="text-sm text-[#6B7280] mb-2">{trend.reason}</p>
                  
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="text-[#374151] font-medium">{trend.price_range}</span>
                    <span className="text-[#6B7280]">•</span>
                    <span className="text-[#6B7280]">Source: {trend.source}</span>
                    <span className="text-[#6B7280]">•</span>
                    <span className="text-[#6B7280] capitalize">{trend.category.replace('_', ' ')}</span>
                  </div>
                </div>

                {/* Trend Score */}
                <div className="shrink-0 text-right">
                  <div className="text-2xl font-bold text-[#111827]">{trend.trend_score}</div>
                  <div className="text-xs text-[#6B7280]">Trend Score</div>
                  <div className="mt-1 w-16 h-2 bg-[#E5E7EB] rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${getTrendScoreColor(trend.trend_score)} rounded-full`}
                      style={{ width: `${trend.trend_score}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && (!trendsData?.trends || trendsData.trends.length === 0) && (
        <div className="flex flex-col items-center justify-center h-64 text-[#6B7280]">
          <TrendingUp className="h-12 w-12 mb-4 opacity-50" />
          <p>No trending products found</p>
          <button
            onClick={() => refetch()}
            className="mt-4 text-purple-600 hover:underline"
          >
            Try refreshing
          </button>
        </div>
      )}

      {/* Generated At */}
      {trendsData?.generated_at && (
        <p className="mt-6 text-center text-xs text-[#9CA3AF]">
          Generated at {new Date(trendsData.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
