// Dashboard components barrel export

export { StatCard } from './StatCard';
export { RecentAlerts } from './RecentAlerts';
export { ProductSummaryCard } from './ProductSummaryCard';
// AP-014: Was exporting as SentimentTrendChart from ./SentimentOverview — wrong name.
// The component defined in SentimentOverview.tsx is SentimentOverview, not SentimentTrendChart.
// Importing SentimentTrendChart from this barrel would resolve to undefined at runtime.
export { SentimentOverview } from './SentimentOverview';
export { QuickActions } from './QuickActions';
export { PendingRecommendations } from './PendingRecommendations';
export { AIFeaturesCard } from './AIFeaturesCard';

