"use client";

import React from "react";
import { PricingRecommendation } from "../types";

interface RecommendationCardProps {
  recommendation: PricingRecommendation;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const isIncrease = recommendation.price_change_percent > 0;
  const isDecrease = recommendation.price_change_percent < 0;

  const riskStyles: Record<string, string> = {
    low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    medium: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
    high: "text-red-400 bg-red-500/10 border-red-500/30",
  };

  const riskStyle = riskStyles[recommendation.risk_level] || riskStyles.medium;

  return (
    <div className="rounded-xl border border-emerald-500/30 bg-linear-to-br from-emerald-500/10 to-transparent p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Pricing Recommendation</h3>
          <p className="text-sm text-gray-400">{recommendation.strategy}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium border ${riskStyle}`}>
          {recommendation.risk_level.toUpperCase()} RISK
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="rounded-lg bg-white/5 p-4 text-center">
          <p className="text-sm text-gray-400 mb-1">Recommended Price</p>
          <p className="text-3xl font-bold text-white">
            ${Number(recommendation.recommended_price).toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <div className="rounded-lg bg-white/5 p-4 text-center">
          <p className="text-sm text-gray-400 mb-1">Price Change</p>
          <p
            className={`text-3xl font-bold ${
              isIncrease ? "text-emerald-400" : isDecrease ? "text-red-400" : "text-gray-400"
            }`}
          >
            {isIncrease ? "+" : ""}
            {Number(recommendation.price_change_percent).toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">Confidence</span>
          <span className="text-sm font-medium text-white">
            {Math.round(Number(recommendation.confidence) * 100)}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-gray-700 overflow-hidden">
          <div
            className="h-full rounded-full bg-linear-to-r from-emerald-500 to-emerald-400 transition-all duration-500"
            style={{ width: `${Number(recommendation.confidence) * 100}%` }}
          />
        </div>
      </div>

      <div className="mb-4">
        <p className="text-sm text-gray-400 mb-2">Reasoning</p>
        <p className="text-sm text-gray-200">{recommendation.reasoning}</p>
      </div>

      {recommendation.key_factors.length > 0 && (
        <div>
          <p className="text-sm text-gray-400 mb-2">Key Factors</p>
          <div className="flex flex-wrap gap-2">
            {recommendation.key_factors.map((factor) => (
              <span
                key={factor}
                className="rounded-full bg-white/5 border border-gray-700 px-3 py-1 text-xs text-gray-300"
              >
                {factor}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


