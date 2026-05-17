// Sentiment API
import { api } from './client';
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  PaginatedMentions,
  AIStatusResponse,
} from '@/types';

export const sentimentApi = {
  // Analyze text for sentiment (without saving)
  analyzeOnly: (data: { text: string; source?: string; use_ai?: boolean }) => {
    const params = data.use_ai ? '?use_ai=true' : '';
    return api.post<AnalyzeResponse>(`/api/v1/sentiment/analyze${params}`, {
      text: data.text,
      source: data.source,
    });
  },

  // Analyze text AND save to database for a product
  analyze: (data: AnalyzeRequest) => {
    const { product_id, content, source, author, url, use_ai } = data;
    const params = use_ai ? '?use_ai=true' : '';
    return api.post<AnalyzeResponse>(`/api/v1/sentiment/analyze/${product_id}${params}`, {
      text: content,  // Backend expects 'text', frontend sends 'content'
      source: source || 'manual',
      author,
      url,
    });
  },

  // Get sentiment results for a product
  getByProduct: (productId: string) =>
    api.get<AnalyzeResponse[]>(`/api/v1/sentiment/product/${productId}`),

  // Get social mentions for a product
  getMentions: (productId: string, params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedMentions>(`/api/v1/sentiment/mentions/${productId}`, params),

  // Check AI status
  getAIStatus: () =>
    api.get<AIStatusResponse>('/api/v1/sentiment/ai-status'),
};


