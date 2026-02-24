// frontend/types/generated.ts
// ============================================
// TYPE BRIDGE: Generated Types → Domain Layer
// ============================================
//
// This file creates type aliases from api-generated.ts that:
// 1. Provide cleaner import paths
// 2. Enable TypeScript to detect when backend changes
// 3. Document which manual types map to which generated types
//
// WORKFLOW:
// 1. Backend changes a schema
// 2. Run: npm run generate-types
// 3. TypeScript shows errors here if types don't match
// 4. Update domain layer transformers to handle changes
//
// Usage in domain layer:
//   import type { Generated } from '@/types/generated';
//   // TypeScript will error if your transform doesn't match Generated.PricingRuleCreate

import type { components } from './api-generated';

// ============================================
// GENERATED TYPE NAMESPACE
// ============================================

/**
 * All generated schema types in one namespace.
 * Use this for type checking against the backend.
 * 
 * @example
 * import type { Generated } from '@/types/generated';
 * 
 * function transformToApi(form: FormData): Generated.PricingRuleCreate {
 *   // TypeScript ensures this matches the backend schema
 * }
 */
export namespace Generated {
  // ─────────────────────────────────────────
  // PRICING
  // ─────────────────────────────────────────
  export type PricingRuleCreate = components['schemas']['PricingRuleCreate'];
  export type PricingRuleResponse = components['schemas']['PricingRuleResponse'];
  export type PricingRuleUpdate = components['schemas']['PricingRuleUpdate'];
  export type RuleType = components['schemas']['RuleType'];
  export type RuleAction = components['schemas']['RuleAction'];
  export type PriceRecommendationResponse = components['schemas']['PriceRecommendationResponse'];
  export type RecommendationStatus = components['schemas']['RecommendationStatus'];
  export type RecommendationStats = components['schemas']['RecommendationStats'];
  export type RecommendationApprove = components['schemas']['RecommendationApprove'];
  export type RecommendationReject = components['schemas']['RecommendationReject'];
  export type PricingSettingsResponse = components['schemas']['PricingSettingsResponse'];
  export type PricingSettingsUpdate = components['schemas']['PricingSettingsUpdate'];
  export type PriceSuggestion = components['schemas']['PriceSuggestion'];
  export type OutcomeLabel = components['schemas']['OutcomeLabel'];
  export type OutcomeResponse = components['schemas']['OutcomeResponse'];
  export type OutcomeRecordRequest = components['schemas']['OutcomeRecordRequest'];
  export type SimulationRequest = components['schemas']['SimulationRequest'];
  export type SimulationResponse = components['schemas']['SimulationResponse'];
  export type RuleTestRequest = components['schemas']['RuleTestRequest'];
  export type RuleTestResponse = components['schemas']['RuleTestResponse'];
  export type RulePerformanceResponse = components['schemas']['RulePerformanceResponse'];
  export type MockSignals = components['schemas']['MockSignals'];

  // ─────────────────────────────────────────
  // INTELLIGENCE ENVIRONMENT
  // ─────────────────────────────────────────
  export type ExperimentArmStatus = components['schemas']['ExperimentArmStatus'];
  export type ExperimentStatus = components['schemas']['ExperimentStatus'];
  export type CalibrationBand = components['schemas']['CalibrationReport']['confidence_bands'][number];
  export type CalibrationReport = components['schemas']['CalibrationReport'];
  export type DriftAlert = components['schemas']['DriftAlert'];
  export type CategoryPerformance = components['schemas']['CategoryPerformance'];
  export type IEHealthStatus = components['schemas']['IEHealthStatus'];
  export type IEDashboard = components['schemas']['IEDashboard'];
  
  // ─────────────────────────────────────────
  // PRODUCTS
  // ─────────────────────────────────────────
  export type ProductCreate = components['schemas']['ProductCreate'];
  export type ProductRead = components['schemas']['ProductRead'];
  export type ProductUpdate = components['schemas']['ProductUpdate'];
  export type ProductSummary = components['schemas']['ProductSummary'];
  export type ImportProductRow = components['schemas']['ImportProductRow'];
  export type ImportProductsRequest = components['schemas']['ImportProductsRequest'];
  export type ImportProductsResponse = components['schemas']['ImportProductsResponse'];
  export type GenerateDescriptionRequest = components['schemas']['GenerateDescriptionRequest'];
  export type GenerateDescriptionResponse = components['schemas']['GenerateDescriptionResponse'];

  // ─────────────────────────────────────────
  // COMPETITORS
  // ─────────────────────────────────────────
  export type CompetitorCreate = components['schemas']['CompetitorCreate'];
  export type CompetitorResponse = components['schemas']['CompetitorResponse'];
  export type CompetitorUpdate = components['schemas']['CompetitorUpdate'];
  export type CompetitorProductCreate = components['schemas']['CompetitorProductCreate'];
  export type CompetitorProductResponse = components['schemas']['CompetitorProductResponse'];
  export type CompetitorProductUpdate = components['schemas']['CompetitorProductUpdate'];
  export type CompetitorProductWithDetails = components['schemas']['CompetitorProductWithDetails'];
  export type CompetitorPriceComparison = components['schemas']['CompetitorPriceComparison'];
  export type AICompetitorAnalysisResponse = components['schemas']['AICompetitorAnalysisResponse'];

  // ─────────────────────────────────────────
  // INTEGRATIONS
  // ─────────────────────────────────────────
  export type IntegrationResponse = components['schemas']['IntegrationResponse'];
  export type IntegrationUpdate = components['schemas']['IntegrationUpdate'];
  export type IntegrationStatus = components['schemas']['IntegrationStatus'];
  export type IntegrationListResponse = components['schemas']['IntegrationListResponse'];
  export type IntegrationHealthResponse = components['schemas']['IntegrationHealthResponse'];
  export type WooCommerceConnectRequest = components['schemas']['WooCommerceConnectRequest'];
  export type OAuthInitRequest = components['schemas']['OAuthInitRequest'];
  export type OAuthInitResponse = components['schemas']['OAuthInitResponse'];
  export type ProductLinkCreate = components['schemas']['ProductLinkCreate'];
  export type ProductLinkResponse = components['schemas']['ProductLinkResponse'];
  export type ProductLinkListResponse = components['schemas']['ProductLinkListResponse'];
  export type EcommercePlatform = components['schemas']['EcommercePlatform'];
  export type PricePushRequest = components['schemas']['PricePushRequest'];
  export type PricePushResponse = components['schemas']['PricePushResponse'];
  export type SyncStatusResponse = components['schemas']['SyncStatusResponse'];
  export type SyncLogResponse = components['schemas']['SyncLogResponse'];
  export type SyncTriggerRequest = components['schemas']['SyncTriggerRequest'];
  export type WebhookResponse = components['schemas']['WebhookResponse'];

  // ─────────────────────────────────────────
  // ALERTS
  // ─────────────────────────────────────────
  export type AlertRead = components['schemas']['AlertRead'];
  export type AlertConfigurationCreate = components['schemas']['AlertConfigurationCreate'];
  export type AlertConfigurationRead = components['schemas']['AlertConfigurationRead'];
  export type AlertConfigurationUpdate = components['schemas']['AlertConfigurationUpdate'];
  export type AlertType = components['schemas']['AlertType'];
  export type AlertSeverity = components['schemas']['AlertSeverity'];
  export type AlertStatus = components['schemas']['AlertStatus'];
  export type AlertChannel = components['schemas']['AlertChannel'];
  export type AlertStats = components['schemas']['AlertStats'];
  export type AlertAnalytics = components['schemas']['AlertAnalytics'];
  export type CrisisDetectionResponse = components['schemas']['CrisisDetectionResponse'];
  export type CrisisAlert = components['schemas']['CrisisAlert'];
  export type CompetitorAlert = components['schemas']['CompetitorAlert'];

  // ─────────────────────────────────────────
  // SENTIMENT
  // ─────────────────────────────────────────
  export type SentimentResponse = components['schemas']['SentimentResponse'];
  export type SocialMentionResponse = components['schemas']['SocialMentionResponse'];
  export type SentimentSummary = components['schemas']['SentimentSummary'];
  export type SentimentAnalytics = components['schemas']['SentimentAnalytics'];
  export type SentimentDataPoint = components['schemas']['SentimentDataPoint'];
  export type SentimentAnalyzeRequest = components['schemas']['SentimentAnalyzeRequest'];
  export type SentimentBulkRequest = components['schemas']['SentimentBulkRequest'];
  export type SentimentBulkItem = components['schemas']['SentimentBulkItem'];

  // ─────────────────────────────────────────
  // AUTH / USER
  // ─────────────────────────────────────────
  export type UserDetailResponse = components['schemas']['UserDetailResponse'];
  export type UserResponse = components['schemas']['UserResponse'];
  export type UserUpdateRequest = components['schemas']['UserUpdateRequest'];
  export type LoginRequest = components['schemas']['LoginRequest'];
  export type RegisterRequest = components['schemas']['RegisterRequest'];
  export type TokenResponse = components['schemas']['TokenResponse'];
  export type RefreshRequest = components['schemas']['RefreshRequest'];
  export type PasswordChangeRequest = components['schemas']['PasswordChangeRequest'];
  export type ForgotPasswordRequest = components['schemas']['ForgotPasswordRequest'];
  export type ResetPasswordRequest = components['schemas']['ResetPasswordRequest'];

  // ─────────────────────────────────────────
  // PAYMENTS / SUBSCRIPTION
  // ─────────────────────────────────────────
  export type SubscriptionInfo = components['schemas']['SubscriptionInfo'];
  export type SubscribeRequest = components['schemas']['SubscribeRequest'];
  export type PaymentRequest = components['schemas']['PaymentRequest'];
  export type ConfirmPaymentRequest = components['schemas']['ConfirmPaymentRequest'];
  export type ConfirmPaymentResponse = components['schemas']['ConfirmPaymentResponse'];
  export type PaymentInfo = components['schemas']['PaymentInfo'];
  export type PlanInfo = components['schemas']['PlanInfo'];
  export type BalanceInfo = components['schemas']['BalanceInfo'];
  export type WalletInfo = components['schemas']['WalletInfo'];
  export type WalletResponse = components['schemas']['WalletResponse'];
  export type WalletAddressUpdate = components['schemas']['WalletAddressUpdate'];
  export type WalletUpdateRequest = components['schemas']['WalletUpdateRequest'];

  // ─────────────────────────────────────────
  // ANALYTICS / TRENDS
  // ─────────────────────────────────────────
  export type DashboardOverview = components['schemas']['DashboardOverview'];
  export type MarketTrendsRequest = components['schemas']['MarketTrendsRequest'];
  export type MarketTrendsResponse = components['schemas']['MarketTrendsResponse'];
  export type AccuracyStatsResponse = components['schemas']['AccuracyStatsResponse'];
  export type TrendCategoriesResponse = components['schemas']['TrendCategoriesResponse'];
  export type TrendSourcesResponse = components['schemas']['TrendSourcesResponse'];
  export type TrendingProductSchema = components['schemas']['TrendingProductSchema'];

  // ─────────────────────────────────────────
  // SUPPORT / CHAT
  // ─────────────────────────────────────────
  export type SupportChatRequest = components['schemas']['SupportChatRequest'];
  export type SupportChatResponse = components['schemas']['SupportChatResponse'];
  export type SupportHealthResponse = components['schemas']['SupportHealthResponse'];
  export type SupportTopicsResponse = components['schemas']['SupportTopicsResponse'];
  export type ChatMessageSchema = components['schemas']['ChatMessageSchema'];
  export type TopicSuggestion = components['schemas']['TopicSuggestion'];

  // ─────────────────────────────────────────
  // MISC
  // ─────────────────────────────────────────
  export type CategorySchema = components['schemas']['CategorySchema'];
  export type HTTPValidationError = components['schemas']['HTTPValidationError'];
  export type ValidationError = components['schemas']['ValidationError'];
}

// ============================================
// HELPER TYPES
// ============================================

/**
 * Extract the response type for a specific endpoint
 * 
 * @example
 * type ProductsResponse = ApiResponse<'/api/v1/products', 'get'>;
 */
export type ApiResponse<
  Path extends keyof import('./api-generated').paths,
  Method extends keyof import('./api-generated').paths[Path]
> = import('./api-generated').paths[Path][Method] extends {
  responses: { 200: { content: { 'application/json': infer R } } }
}
  ? R
  : never;

/**
 * Extract the request body type for a specific endpoint
 * 
 * @example
 * type CreateProductBody = ApiRequestBody<'/api/v1/products', 'post'>;
 */
export type ApiRequestBody<
  Path extends keyof import('./api-generated').paths,
  Method extends keyof import('./api-generated').paths[Path]
> = import('./api-generated').paths[Path][Method] extends {
  requestBody: { content: { 'application/json': infer B } }
}
  ? B
  : never;

// ============================================
// TYPE COMPATIBILITY CHECKS (Optional)
// ============================================
// 
// Uncomment these to enable compile-time checking that your
// manual types are compatible with generated types.
// 
// If they fail, it means your manual types have drifted
// from the backend schema.

/*
import type { 
  CreatePricingRuleRequest, 
  PricingRule,
} from './pricing';

import type {
  CreateProductRequest,
  Product,
} from './product';

// These will error if types are incompatible:
type _CheckPricingCreate = CreatePricingRuleRequest extends Generated.PricingRuleCreate ? true : false;
type _CheckProductCreate = CreateProductRequest extends Generated.ProductCreate ? true : false;
*/



