'use client';

import { useMemo } from 'react';
import type { SocialMention } from '@/types';

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
  'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
  'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
  'must', 'shall', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
  'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
  'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
  'no', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'as',
  'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up',
  'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
  'there', 'any', 'if', 'because', 'until', 'while', 'its', 'my', 'your', 'his',
  'her', 'their', 'our', 'me', 'him', 'them', 'us', 'get', 'got', 'like', 'just',
  'also', 'now', 'even', 'well', 'way', 'many', 'much', 'new', 'one', 'two', 'first',
  'really', 'great', 'good', 'best', 'love', 'thing', 'things', 'dont', 'want',
]);

function extractKeywords(mentions: SocialMention[], limit = 12): { word: string; count: number }[] {
  const wordCounts: Record<string, number> = {};

  mentions.forEach((mention) => {
    const words = mention.content
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .split(/\s+/)
      .filter((word) => word.length > 2 && !STOP_WORDS.has(word));

    words.forEach((word) => {
      wordCounts[word] = (wordCounts[word] || 0) + 1;
    });
  });

  return Object.entries(wordCounts)
    .map(([word, count]) => ({ word, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

interface TopKeywordsProps {
  mentions: SocialMention[];
  limit?: number;
}

export function TopKeywords({ mentions, limit = 12 }: TopKeywordsProps) {
  const keywords = useMemo(() => extractKeywords(mentions, limit), [mentions, limit]);

  if (keywords.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-gray-400 text-sm">
        No keywords available
      </div>
    );
  }

  const maxCount = keywords[0]?.count || 1;

  return (
    <div className="flex flex-wrap gap-2">
      {keywords.map(({ word, count }) => {
        const intensity = Math.max(0.4, count / maxCount);
        return (
          <span
            key={word}
            className="px-3 py-1.5 bg-blue-100 text-blue-800 rounded-full text-sm font-medium transition-transform hover:scale-105"
            style={{ opacity: 0.5 + intensity * 0.5 }}
          >
            {word}
            <span className="ml-1.5 text-blue-600 text-xs">({count})</span>
          </span>
        );
      })}
    </div>
  );
}
