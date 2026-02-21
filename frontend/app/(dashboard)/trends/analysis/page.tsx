'use client';

import { useState } from 'react';
import Link from 'next/link';
import { RefreshCw, Download, Settings, ArrowLeft, Sparkles } from 'lucide-react';

import {
  QuickStatsGrid,
  MarketSentimentGauge,
  TrendAnalysisCard,
  TrendPredictionChart,
  OpportunityCard,
  RiskAlertCard,
  AIInsightPanel,
} from '@/components/features/trends';

import {
  useQuickStats,
  useRunTrendAnalysis,
  useDetectRisks,
  useGenerateInsight,
} from '@/lib/hooks/use-trend-analysis';

import type { TrendAnalysisResponse, PricingOpportunity, RiskAlert } from '@/types/trend-analysis';

export default function TrendAnalysisPage() {
  const [analysisResult, setAnalysisResult] = useState<TrendAnalysisResponse | null>(null);
  
  // Hooks
  const { data: quickStats, isLoading: statsLoading, refetch: refetchStats } = useQuickStats();
  const runAnalysis = useRunTrendAnalysis();
  const detectRisks = useDetectRisks();
  const generateInsight = useGenerateInsight();

  // Handlers
  const handleRunAnalysis = async (params: { days: number; useModel: 'openai' | 'gemini' }) => {
    const result = await runAnalysis.mutateAsync({
      days: params.days,
      use_model: params.useModel,
    });
    setAnalysisResult(result);
  };

  const handleApplyOpportunity = (opportunity: PricingOpportunity) => {
    console.log('Applying opportunity:', opportunity);
  };

  const handleDismissOpportunity = (opportunity: PricingOpportunity) => {
    console.log('Dismissing opportunity:', opportunity);
  };

  const handleAcknowledgeRisk = (risk: RiskAlert) => {
    console.log('Acknowledging risk:', risk);
  };

  const handleRefreshAll = () => {
    refetchStats();
    if (analysisResult) {
      handleRunAnalysis({ days: 30, useModel: 'openai' });
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link
              href="/trends"
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="h-5 w-5 text-gray-500" />
            </Link>
            <h1 className="text-2xl font-bold text-[#111827] flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-purple-600" />
              AI Trend Analysis
            </h1>
          </div>
          <p className="text-[#6B7280] ml-9">
            AI-powered market insights, predictions, and pricing opportunities
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefreshAll}
            disabled={runAnalysis.isPending}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${runAnalysis.isPending ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            <Download className="h-4 w-4" />
            Export
          </button>
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            <Settings className="h-4 w-4" />
            Configure
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <QuickStatsGrid data={quickStats} isLoading={statsLoading} />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Analysis Control & Sentiment */}
        <div className="space-y-6">
          <TrendAnalysisCard
            analysis={analysisResult ?? undefined}
            isLoading={runAnalysis.isPending}
            onRunAnalysis={handleRunAnalysis}
          />
          
          {analysisResult && (
            <MarketSentimentGauge
              score={analysisResult.market_sentiment_score}
              direction={analysisResult.market_sentiment}
            />
          )}
        </div>

        {/* Center Column - Predictions & Insights */}
        <div className="space-y-6">
          <TrendPredictionChart
            predictions={analysisResult?.predictions ?? []}
          />
          
          <AIInsightPanel
            insight={analysisResult?.insights?.[0]}
            isLoading={generateInsight.isPending}
          />
        </div>

        {/* Right Column - Opportunities & Risks */}
        <div className="space-y-6">
          {/* Opportunities */}
          <div>
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <span className="text-green-500">●</span>
              Pricing Opportunities
              {analysisResult?.opportunities && analysisResult.opportunities.length > 0 && (
                <span className="text-sm font-normal text-gray-500">
                  ({analysisResult.opportunities.length})
                </span>
              )}
            </h3>
            <div className="space-y-3">
              {analysisResult?.opportunities && analysisResult.opportunities.length > 0 ? (
                analysisResult.opportunities.slice(0, 3).map((opportunity, i) => (
                  <OpportunityCard
                    key={i}
                    opportunity={opportunity}
                    onApply={handleApplyOpportunity}
                    onDismiss={handleDismissOpportunity}
                  />
                ))
              ) : (
                <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
                  <p>No opportunities detected</p>
                  <p className="text-sm mt-1">Run AI analysis to find opportunities</p>
                </div>
              )}
            </div>
          </div>

          {/* Risks */}
          <div>
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <span className="text-orange-500">●</span>
              Risk Alerts
              {analysisResult?.risks && analysisResult.risks.length > 0 && (
                <span className="text-sm font-normal text-gray-500">
                  ({analysisResult.risks.length})
                </span>
              )}
            </h3>
            <div className="space-y-3">
              {analysisResult?.risks && analysisResult.risks.length > 0 ? (
                analysisResult.risks.slice(0, 3).map((risk, i) => (
                  <RiskAlertCard
                    key={i}
                    risk={risk}
                    onAcknowledge={handleAcknowledgeRisk}
                  />
                ))
              ) : (
                <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
                  <p>No active risks</p>
                  <p className="text-sm mt-1">All clear! 🎉</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


