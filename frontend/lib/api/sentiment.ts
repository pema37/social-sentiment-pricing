// Sentiment API
import { api } from './client';
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  PaginatedMentions,
  SocialMention,
} from '@/types';

export const sentimentApi = {
  // Analyze text for sentiment
  analyze: (data: AnalyzeRequest) =>
    api.post<AnalyzeResponse>('/api/v1/sentiment/analyze', data),

  // Get sentiment results for a product
  getByProduct: (productId: string) =>
    api.get<AnalyzeResponse[]>(`/api/v1/sentiment/product/${productId}`),

  // Get social mentions for a product
  getMentions: (productId: string, params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedMentions>(`/api/v1/sentiment/mentions/${productId}`, params),

  // Get a single mention
  getMention: (mentionId: string) =>
    api.get<SocialMention>(`/api/v1/sentiment/mentions/detail/${mentionId}`),

  // Manually add a mention
  addMention: (data: {
    product_id: string;
    content: string;
    source: string;
    author?: string;
    url?: string;
  }) =>
    api.post<SocialMention>('/api/v1/sentiment/mentions', data),
};
