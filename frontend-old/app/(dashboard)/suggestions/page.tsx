"use client";

import React from "react";
import { DollarSign, TrendingUp, TrendingDown, Clock, CheckCircle, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react';

// --- Data Types ---
type SuggestionAction = 'Accept & Apply' | 'View Details' | 'Dismiss';

interface Suggestion {
    id: number;
    productName: string;
    description: string;
    currentPrice: number;
    suggestedPrice: number;
    priceChange: number; // e.g., 20 or -20
    sentimentScore: number; // 0-100
    confidence: number; // 0-100
    competitorPrice: number;
    revenueImpact: number; // positive or negative
    lowConfidenceWarning: boolean;
}

interface SummaryMetric {
    title: string;
    value: string;
    subtitle: string;
    colorClass: string;
    icon: React.ElementType;
}

// --- Mock Data ---

const MOCK_SUMMARY_METRICS: SummaryMetric[] = [
    {
        title: "Pending Suggestions",
        value: "5",
        subtitle: "Awaiting review",
        colorClass: "text-blue-600",
        icon: Clock,
    },
    {
        title: "Potential Revenue Impact",
        value: "+$35.9K",
        subtitle: "If all accepted",
        colorClass: "text-green-600",
        icon: DollarSign,
    },
    {
        title: "Avg Confidence",
        value: "84.8%",
        subtitle: "High accuracy",
        colorClass: "text-gray-800",
        icon: CheckCircle,
    },
];

const MOCK_SUGGESTIONS: Suggestion[] = [
    {
        id: 1,
        productName: "Premium Headphones",
        description: "High positive sentiment and competitive pricing suggest room for increase",
        currentPrice: 299,
        suggestedPrice: 279,
        priceChange: -20,
        sentimentScore: 88,
        confidence: 92,
        competitorPrice: 289,
        revenueImpact: 12400,
        lowConfidenceWarning: false,
    },
    {
        id: 2,
        productName: "Wireless Earbuds",
        description: "Strong sentiment and higher competitor pricing support increase",
        currentPrice: 129,
        suggestedPrice: 149,
        priceChange: 20,
        sentimentScore: 92,
        confidence: 88,
        competitorPrice: 139,
        revenueImpact: 8200,
        lowConfidenceWarning: false,
    },
    {
        id: 3,
        productName: "Smart Watch Pro",
        description: "Declining sentiment and competitive pressure suggest reduction",
        currentPrice: 399,
        suggestedPrice: 379,
        priceChange: -20,
        sentimentScore: 65,
        confidence: 78,
        competitorPrice: 379,
        revenueImpact: -4100,
        lowConfidenceWarning: false,
    },
    {
        id: 4,
        productName: "Fitness Tracker",
        description: "Exceptional sentiment allows for premium positioning",
        currentPrice: 89,
        suggestedPrice: 99,
        priceChange: 10,
        sentimentScore: 95,
        confidence: 94,
        competitorPrice: 96,
        revenueImpact: 15800,
        lowConfidenceWarning: false,
    },
    {
        id: 5,
        productName: "Bluetooth Speaker",
        description: "Moderate sentiment with competitor parity supports slight increase",
        currentPrice: 159,
        suggestedPrice: 169,
        priceChange: 10,
        sentimentScore: 78,
        confidence: 72,
        competitorPrice: 168,
        revenueImpact: 2800,
        lowConfidenceWarning: true,
    },
];

// --- Utility Components ---

const SummaryCard: React.FC<{ metric: SummaryMetric }> = ({ metric }) => {
    const Icon = metric.icon;
    return (
        <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-200 flex flex-col flex-1 min-w-[200px] transition-shadow duration-300 hover:shadow-xl">
            <div className="flex items-center space-x-3 mb-2">
                <Icon className={`w-6 h-6 ${metric.colorClass}`} />
                <h3 className="text-sm font-medium text-gray-500">{metric.title}</h3>
            </div>
            <p className="text-4xl font-extrabold text-gray-900 mb-1">{metric.value}</p>
            <p className={`text-sm font-semibold ${metric.colorClass}`}>{metric.subtitle}</p>
        </div>
    );
};

const SuggestionCard: React.FC<{ suggestion: Suggestion }> = ({ suggestion }) => {
    const formatCurrency = (amount: number) => {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(amount);
    };

    const changeType = suggestion.priceChange > 0 ? 'increase' : 'decrease';
    const changeColor = suggestion.priceChange > 0 ? 'text-green-600' : suggestion.priceChange < 0 ? 'text-red-600' : 'text-gray-600';
    
    // Assign the icon component itself to ChangeIcon (capitalized for React)
    const ChangeIcon = suggestion.priceChange > 0 ? ChevronUp : suggestion.priceChange < 0 ? ChevronDown : null;

    const handleAction = (action: SuggestionAction) => {
        console.log(`${action} clicked for ${suggestion.productName}`);
        // In a real application, this would trigger an API call or open a modal.
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-200 transition-shadow duration-300 hover:shadow-xl">
            {/* Product Title and Description */}
            <h2 className="text-xl font-bold text-gray-900 mb-1">{suggestion.productName}</h2>
            <p className="text-sm text-gray-500 mb-4">{suggestion.description}</p>

            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 items-center mb-6 border-b pb-4">
                
                {/* Current Price */}
                <div className="flex flex-col">
                    <span className="text-xs font-medium text-gray-500 mb-1">Current Price</span>
                    <span className="text-2xl font-extrabold text-gray-900">{formatCurrency(suggestion.currentPrice)}</span>
                </div>

                {/* Suggested Price & Change */}
                <div className="flex flex-col">
                    <span className="text-xs font-medium text-gray-500 mb-1">Suggested Price</span>
                    <div className="flex items-center space-x-2">
                        <span className={`text-2xl font-extrabold ${changeColor}`}>
                            {formatCurrency(suggestion.suggestedPrice)}
                        </span>
                        <div className={`flex items-center text-sm font-bold ${changeColor}`}>
                            {/* FIX: Render the icon as a JSX component, not a function call */}
                            {ChangeIcon && <ChangeIcon className="w-3 h-3 mr-0.5" />}
                            {suggestion.priceChange !== 0 && `${changeType === 'increase' ? '+' : '-'}${formatCurrency(Math.abs(suggestion.priceChange))}`}
                        </div>
                    </div>
                </div>
                
                {/* Sentiment Score */}
                <div className="flex flex-col">
                    <span className="text-xs font-medium text-gray-500 mb-1">Sentiment Score</span>
                    <div className="flex items-center text-2xl font-extrabold text-gray-900">
                        {suggestion.sentimentScore}%
                        <TrendingUp className="w-5 h-5 ml-1 text-green-500" />
                    </div>
                </div>

                {/* Confidence */}
                <div className="flex flex-col">
                    <span className="text-xs font-medium text-gray-500 mb-1">Confidence</span>
                    <span className="text-2xl font-extrabold text-gray-900">{suggestion.confidence}%</span>
                </div>
            </div>

            {/* Additional Details & Warning */}
            <div className="flex flex-wrap justify-between items-center mb-4 text-sm text-gray-600">
                <span className="mr-4">
                    <span className="font-semibold text-gray-700">Competitor Price:</span> {formatCurrency(suggestion.competitorPrice)}
                </span>
                <span className={suggestion.revenueImpact >= 0 ? 'text-green-600' : 'text-red-600'}>
                    <span className="font-semibold text-gray-700">Revenue Impact:</span> {suggestion.revenueImpact >= 0 ? '+' : ''}{formatCurrency(suggestion.revenueImpact)}
                </span>
            </div>

            {/* Low Confidence Warning */}
            {suggestion.lowConfidenceWarning && (
                <div className="flex items-center p-3 text-sm text-yellow-800 bg-yellow-50 rounded-lg mb-4 border border-yellow-300">
                    <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0 text-yellow-600" />
                    <span>Lower confidence - review market conditions before applying.</span>
                </div>
            )}
            
            {/* Action Buttons */}
            <div className="flex space-x-3 mt-4 justify-end">
                <button
                    onClick={() => handleAction('Accept & Apply')}
                    className="px-4 py-2 text-sm font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition duration-200 shadow-md"
                >
                    Accept & Apply
                </button>
                <button
                    onClick={() => handleAction('View Details')}
                    className="px-4 py-2 text-sm font-bold text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors border border-blue-200"
                >
                    View Details
                </button>
                <button
                    onClick={() => handleAction('Dismiss')}
                    className="px-4 py-2 text-sm font-bold text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors border border-red-200"
                >
                    Dismiss
                </button>
            </div>
        </div>
    );
};

// --- Main Component ---
export default function PriceSuggestionsPage() {
    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">
            
            {/* Header */}
            <header className="mb-8">
                <h1 className="text-3xl font-extrabold text-gray-900">Price Suggestions</h1>
                <p className="text-md text-gray-500 mt-0.5">AI-powered pricing recommendations based on sentiment and market data</p>
            </header>

            {/* Summary Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                {MOCK_SUMMARY_METRICS.map((metric, index) => (
                    <SummaryCard key={index} metric={metric} />
                ))}
            </div>

            {/* Recommendations List */}
            <div className="space-y-6">
                {MOCK_SUGGESTIONS.map(suggestion => (
                    <SuggestionCard key={suggestion.id} suggestion={suggestion} />
                ))}
            </div>

            <footer className="text-center text-xs text-gray-400 mt-10">
                Mock data used for demonstration. Actual calculations would require live market data.
            </footer>
        </div>
    );
}