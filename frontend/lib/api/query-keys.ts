// Centralized React Query key registry
// All hooks should import keys from here - never define keys inline

export const authKeys = {
  all: ['auth'] as const,
  user: () => [...authKeys.all, 'user'] as const,
  session: () => [...authKeys.all, 'session'] as const,
};

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (params?: { page?: number; page_size?: number; search?: string }) =>
    [...productKeys.lists(), params] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
  priceHistory: (id: string, params?: { days?: number; limit?: number }) =>
    [...productKeys.all, 'price-history', id, params] as const,
  priceSuggestion: (id: string) => [...productKeys.all, 'suggestion', id] as const,
  // Product sync status keys
  syncStatus: () => [...productKeys.all, 'sync-status'] as const,
  syncStatusDetail: (id: string) => [...productKeys.syncStatus(), id] as const,
};

export const pricingKeys = {
  all: ['pricing'] as const,
  
  // Rules
  rules: () => [...pricingKeys.all, 'rules'] as const,
  rulesList: (params?: { page?: number; page_size?: number; rule_type?: string; is_active?: boolean }) =>
    [...pricingKeys.rules(), 'list', params] as const,
  ruleDetail: (id: string) => [...pricingKeys.rules(), 'detail', id] as const,

  // Recommendations
  recommendations: () => [...pricingKeys.all, 'recommendations'] as const,
  recommendationsList: (params?: { page?: number; page_size?: number; status?: string; product_id?: string }) =>
    [...pricingKeys.recommendations(), 'list', params] as const,
  recommendationDetail: (id: string) => [...pricingKeys.recommendations(), 'detail', id] as const,
  recommendationStats: () => [...pricingKeys.recommendations(), 'stats'] as const,

  // Settings
  settings: () => [...pricingKeys.all, 'settings'] as const,
};

export const competitorKeys = {
  all: ['competitors'] as const,
  lists: () => [...competitorKeys.all, 'list'] as const,
  list: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    [...competitorKeys.lists(), params] as const,
  details: () => [...competitorKeys.all, 'detail'] as const,
  detail: (id: string) => [...competitorKeys.details(), id] as const,
  // Products - works with or without competitorId
  products: (competitorId?: string) => 
    competitorId 
      ? [...competitorKeys.detail(competitorId), 'products'] as const
      : [...competitorKeys.all, 'products'] as const,
  analysis: (productId: string) => [...competitorKeys.all, 'comparison', productId] as const,
  // Competitor matching keys
  matching: () => [...competitorKeys.all, 'matching'] as const,
  matchingProviders: () => [...competitorKeys.matching(), 'providers'] as const,
  matchingSearch: (query: string) => [...competitorKeys.matching(), 'search', query] as const,
  matchingProduct: (productId: string) => [...competitorKeys.matching(), 'product', productId] as const,
};

export const integrationKeys = {
  all: ['integrations'] as const,
  lists: () => [...integrationKeys.all, 'list'] as const,
  list: (params?: Record<string, unknown>) => [...integrationKeys.lists(), params] as const,
  details: () => [...integrationKeys.all, 'detail'] as const,
  detail: (id: string) => [...integrationKeys.details(), id] as const,
  allSyncStatus: () => [...integrationKeys.all, 'sync-status'] as const,
  syncStatus: (id: string) => [...integrationKeys.all, 'sync-status', id] as const,
  linkedProducts: (id: string) => [...integrationKeys.all, 'links', id] as const,
};

export const alertKeys = {
  all: ['alerts'] as const,
  lists: () => [...alertKeys.all, 'list'] as const,
  list: (params?: Record<string, unknown>) => [...alertKeys.lists(), params] as const,
  details: () => [...alertKeys.all, 'detail'] as const,
  detail: (id: string) => [...alertKeys.details(), id] as const,
  configurations: () => [...alertKeys.all, 'configurations'] as const,
  configurationsList: (params?: Record<string, unknown>) => [...alertKeys.configurations(), 'list', params] as const,
  configurationDetail: (id: string) => [...alertKeys.configurations(), 'detail', id] as const,
  stats: () => [...alertKeys.all, 'stats'] as const,
  unreadCount: () => [...alertKeys.all, 'unread-count'] as const,
};

export const sentimentKeys = {
  all: ['sentiment'] as const,
  overview: (params?: Record<string, unknown>) => [...sentimentKeys.all, 'overview', params] as const,
  mentions: (params?: Record<string, unknown>) => [...sentimentKeys.all, 'mentions', params] as const,
  trends: (params?: Record<string, unknown>) => [...sentimentKeys.all, 'trends', params] as const,
  productSentiment: (productId: string) => [...sentimentKeys.all, 'product', productId] as const,
};

export const analyticsKeys = {
  all: ['analytics'] as const,
  dashboard: () => [...analyticsKeys.all, 'dashboard'] as const,
  productSummaries: (limit?: number) => [...analyticsKeys.all, 'product-summaries', limit] as const,
  recommendationStats: (days?: number) => [...analyticsKeys.all, 'recommendation-stats', days] as const,
  alertAnalytics: (days?: number) => [...analyticsKeys.all, 'alert-analytics', days] as const,
  sentimentTrend: (params?: { product_id?: string; days?: number; bucket?: string }) =>
    [...analyticsKeys.all, 'sentiment-trend', params] as const,
};

export const paymentKeys = {
  all: ['payments'] as const,
  wallet: () => [...paymentKeys.all, 'wallet'] as const,
  balance: (address: string) => [...paymentKeys.all, 'balance', address] as const,
  subscription: () => [...paymentKeys.all, 'subscription'] as const,
  plans: () => [...paymentKeys.all, 'plans'] as const,
  history: (params?: { limit?: number; offset?: number }) =>
    [...paymentKeys.all, 'history', params] as const,
  payment: (id: string) => [...paymentKeys.all, 'payment', id] as const,
};

export const userKeys = {
  all: ['user'] as const,
  profile: () => [...userKeys.all, 'profile'] as const,
  settings: () => [...userKeys.all, 'settings'] as const,
  notifications: () => [...userKeys.all, 'notifications'] as const,
};

export const trendAnalysisKeys = {
  all: ['trend-analysis'] as const,
  quickStats: () => [...trendAnalysisKeys.all, 'quick-stats'] as const,
  analysis: (params?: Record<string, unknown>) => [...trendAnalysisKeys.all, 'analysis', params] as const,
  opportunity: (productId: string) => [...trendAnalysisKeys.all, 'opportunity', productId] as const,
  risks: () => [...trendAnalysisKeys.all, 'risks'] as const,
  insight: (days: number) => [...trendAnalysisKeys.all, 'insight', days] as const,
};



