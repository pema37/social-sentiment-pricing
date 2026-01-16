// frontend/components/features/trust-scoring/index.ts

/**
 * Trust Scoring / Bot Detection Components
 * 
 * Components for displaying trust scores, risk flags, campaign detection,
 * and sentiment analysis with bot/manipulation filtering.
 */

// Trust Level Components
export { 
  TrustLevelBadge, 
  TrustLevelIcon 
} from './TrustLevelBadge';

// Risk Flag Components
export { 
  RiskFlagBadge, 
  RiskFlagList, 
  SeverityDot 
} from './RiskFlagBadge';

// Trust Score Visualizations
export { 
  TrustScoreGauge, 
  TrustScoreBar, 
  TrustScoreInline 
} from './TrustScoreGauge';

// Sentiment Comparison
export { 
  SentimentComparisonCard, 
  SentimentComparisonMini 
} from './SentimentComparisonCard';

// Campaign Detection
export { 
  CampaignAlertCard, 
  CampaignAlertBanner 
} from './CampaignAlertCard';

// Author Trust
export { 
  AuthorTrustCard, 
  AuthorTrustRow, 
  AuthorTrustInline 
} from './AuthorTrustCard';

// Content Analysis
export { 
  ContentAnalysisCard, 
  ContentAnalysisRow, 
  SpamCheckResult 
} from './ContentAnalysisCard';


