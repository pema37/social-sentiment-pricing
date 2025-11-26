"use client";

import React, { useState, useCallback, useMemo } from "react";
import { Search, SlidersHorizontal, RefreshCw, Loader2, Zap } from 'lucide-react';

// --- Data Types ---
type Sentiment = 'positive' | 'neutral' | 'negative';
type Source = 'Twitter' | 'Reddit' | 'Instagram' | 'Facebook';

interface Mention {
    id: string; // Changed type to string for UUID
    source: Source;
    product: string;
    timeAgo: string;
    text: string;
    sentiment: Sentiment;
    confidence: number;
}

interface Metric {
    title: string;
    value: string;
    change: string;
    trend: 'up' | 'down' | 'stable';
    colorClass: string;
}

// --- Mock Data ---

const MOCK_METRICS: Metric[] = [
    {
        title: "Positive Mentions",
        value: "64%",
        change: "+8% from last week",
        trend: 'up',
        colorClass: "text-green-600 bg-green-50",
    },
    {
        title: "Neutral Mentions",
        value: "24%",
        change: "Stable",
        trend: 'stable',
        colorClass: "text-yellow-600 bg-yellow-50",
    },
    {
        title: "Negative Mentions",
        value: "12%",
        change: "-3% from last week",
        trend: 'down',
        colorClass: "text-red-600 bg-red-50",
    },
];

// Base data without IDs
const MOCK_FEED_BASE = [
    {
        source: "Twitter",
        product: "Premium Headphones",
        timeAgo: "2 minutes ago",
        text: "Just got these headphones and they're absolutely amazing! Best sound quality I've ever experienced.",
        sentiment: "positive" as Sentiment,
        confidence: 95,
    },
    {
        source: "Reddit",
        product: "Wireless Earbuds",
        timeAgo: "15 minutes ago",
        text: "Decent earbuds but the battery life could be better. Overall satisfied with the purchase.",
        sentiment: "neutral" as Sentiment,
        confidence: 68,
    },
    {
        source: "Instagram",
        product: "Smart Watch Pro",
        timeAgo: "1 hour ago",
        text: "This watch is a game changer! Love all the fitness tracking features.",
        sentiment: "positive" as Sentiment,
        confidence: 92,
    },
    {
        source: "Twitter",
        product: "Premium Headphones",
        timeAgo: "2 hours ago",
        text: "Overpriced for what you get. There are better options available at this price point.",
        sentiment: "negative" as Sentiment,
        confidence: 32,
    },
    {
        source: "Facebook",
        product: "Fitness Tracker",
        timeAgo: "3 hours ago",
        text: "Perfect for my daily workouts. Accurate tracking and comfortable to wear all day.",
        sentiment: "positive" as Sentiment,
        confidence: 86,
    },
    {
        source: "Reddit",
        product: "Bluetooth Speaker",
        timeAgo: "5 hours ago",
        text: "Sound quality is good but connectivity issues are frustrating.",
        sentiment: "neutral" as Sentiment,
        confidence: 55,
    },
    {
        source: "Twitter",
        product: "Wireless Earbuds",
        timeAgo: "6 hours ago",
        text: "These earbuds keep falling out of my ears. Not recommended.",
        sentiment: "negative" as Sentiment,
        confidence: 28,
    },
    {
        source: "Instagram",
        product: "Smart Watch Pro",
        timeAgo: "1 day ago",
        text: "Loving the sleek design and all the features. Worth every penny!",
        sentiment: "positive" as Sentiment,
        confidence: 94,
    },
];

// Function to generate a unique ID (using crypto.randomUUID for robustness)
const generateId = () => crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9);


// --- Utility Components ---

const SentimentTag: React.FC<{ sentiment: Sentiment, confidence: number }> = ({ sentiment, confidence }) => {
    let colorClass = "";
    if (sentiment === 'positive') colorClass = "bg-green-100 text-green-800";
    else if (sentiment === 'neutral') colorClass = "bg-yellow-100 text-yellow-800";
    else if (sentiment === 'negative') colorClass = "bg-red-100 text-red-800";

    return (
        <div className={`px-3 py-1 text-xs font-semibold rounded-full ${colorClass} flex items-center justify-center min-w-[80px]`}>
            {sentiment}
        </div>
    );
};

const SentimentMetricCard: React.FC<{ metric: Metric }> = ({ metric }) => (
    <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-200 flex flex-col flex-1 min-w-[150px]">
        <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-500">{metric.title}</h3>
            {/* The colored dot next to the title */}
            <span className={`w-3 h-3 rounded-full ${
                metric.title.includes("Positive") ? 'bg-green-500' :
                metric.title.includes("Neutral") ? 'bg-yellow-500' :
                'bg-red-500'
            }`}></span>
        </div>
        <p className="text-4xl font-extrabold text-gray-900 mb-2">{metric.value}</p>
        <p className={`text-sm font-semibold ${metric.colorClass.includes("green") ? 'text-green-600' : metric.colorClass.includes("red") ? 'text-red-600' : 'text-gray-500'}`}>
            {metric.change}
        </p>
    </div>
);

const MentionItem: React.FC<{ mention: Mention }> = ({ mention }) => {
    const getSourceColor = (source: Source) => {
        switch (source) {
            case 'Twitter': return 'text-blue-500';
            case 'Reddit': return 'text-orange-500';
            case 'Instagram': return 'text-pink-500';
            case 'Facebook': return 'text-blue-700';
            default: return 'text-gray-500';
        }
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow duration-300">
            {/* Header: Source, Product, Time */}
            <div className="flex justify-between items-start mb-3">
                <div className="text-sm font-semibold">
                    <span className={`font-extrabold ${getSourceColor(mention.source)}`}>
                        {mention.source}
                    </span>
                    <span className="text-gray-400 mx-2">•</span>
                    <span className="text-gray-700">{mention.product}</span>
                    <span className="text-gray-400 mx-2">•</span>
                    <span className="text-gray-500 font-normal">{mention.timeAgo}</span>
                </div>
                {/* Sentiment Tag and Confidence Score */}
                <div className="flex items-center space-x-3">
                    <SentimentTag sentiment={mention.sentiment} confidence={mention.confidence} />
                    <span className="text-lg font-bold text-gray-900 min-w-[40px] text-right">
                        {mention.confidence}%
                    </span>
                </div>
            </div>

            {/* Content */}
            <p className="text-gray-800 leading-relaxed">
                {mention.text}
            </p>
        </div>
    );
};


// --- Main Component ---
export default function SentimentFeedPage() {
    // 1. Initialize MOCK_FEED with unique IDs ONCE using useMemo
    const initialFeed = useMemo(() => MOCK_FEED_BASE.map(item => ({
        ...item,
        id: generateId() // Ensure every initial item has a unique, stable ID
    })) as Mention[], []);
    
    // We use the generated initialFeed as the state
    const [feed, setFeed] = useState<Mention[]>(initialFeed);
    const [isLoading, setIsLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    
    // Simple filter/search implementation
    const filteredFeed = feed.filter(mention => 
        mention.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
        mention.product.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleRefresh = useCallback(() => {
        if (isLoading) return;
        setIsLoading(true);
        console.log("Refreshing sentiment feed...");
        
        // Simulate fetching new data
        setTimeout(() => {
            // Prepend a new mock item to simulate a fresh feed update
            const newMention: Mention = {
                id: generateId(), // GUARANTEED unique ID
                source: "Facebook",
                product: "Premium Headphones",
                timeAgo: "Just now",
                text: "The noise cancellation feature on these is unbelievable. Highly recommend!",
                sentiment: "positive",
                confidence: 99,
            };
            
            // FIX: Ensure 'updatedFeed' is based on the current 'feed' state, not the static MOCK_FEED
            // Randomly update an existing item (item with original index 4, which is now the item with that specific text/product)
            const updatedFeed = feed.map(item => {
                // We use the product/text as a stable identifier since IDs change on refresh simulation
                if (item.product === "Premium Headphones" && item.text.includes("Overpriced for what you get.")) {
                    return { 
                        ...item, 
                        confidence: 50, 
                        text: "Customer service resolved my issue. Price is fair now.", 
                        // FIX: Use type assertion to satisfy the Sentiment union type requirement
                        sentiment: "neutral" as Sentiment 
                    };
                }
                return item;
            });
            
            // Set the new state: new item first, followed by the first 7 (potentially updated) existing items.
            setFeed([newMention, ...updatedFeed.slice(0, 7)]);
            setIsLoading(false);
            console.log("Feed refreshed.");
        }, 2000);
    }, [isLoading, feed]); // Added 'feed' to dependencies to ensure correct state is accessed

    const handleFilters = () => {
        console.log("Opening filters modal/sidebar...");
        // Placeholder for opening a filter menu
    };
    
    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">
            
            {/* Header */}
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-extrabold text-gray-900">Sentiment Feed</h1>
                    <p className="text-md text-gray-500 mt-0.5">Real-time social media mentions and sentiment analysis</p>
                </div>
                <button
                    onClick={handleRefresh}
                    className="flex items-center space-x-2 px-4 py-2 text-sm font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition duration-200 shadow-md shadow-blue-500/50 disabled:bg-blue-400"
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            <span>Loading...</span>
                        </>
                    ) : (
                        <>
                            <RefreshCw className="w-4 h-4" />
                            <span>Refresh Feed</span>
                        </>
                    )}
                </button>
            </header>

            {/* Search and Filters */}
            <div className="flex space-x-3 mb-8">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search mentions..."
                        className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-blue-500 focus:border-blue-500 transition duration-150 shadow-sm"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <button
                    onClick={handleFilters}
                    className="flex items-center space-x-2 px-4 py-3 text-sm font-semibold text-gray-700 bg-white rounded-xl hover:bg-gray-100 transition-colors border border-gray-300 shadow-sm"
                >
                    <SlidersHorizontal className="w-5 h-5" />
                    <span>Filters</span>
                </button>
            </div>
            
            {/* Sentiment Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8">
                {MOCK_METRICS.map((metric, index) => (
                    <SentimentMetricCard key={index} metric={metric} />
                ))}
            </div>

            {/* Mentions Feed */}
            <div className="space-y-4">
                {filteredFeed.length > 0 ? (
                    filteredFeed.map(mention => (
                        <MentionItem key={mention.id} mention={mention} />
                    ))
                ) : (
                    <div className="text-center py-10 text-gray-500 border border-dashed border-gray-300 rounded-xl bg-white">
                        <Zap className="w-8 h-8 mx-auto mb-3 text-gray-400" />
                        <p className="font-semibold text-lg">No mentions match your search query.</p>
                        <p className="text-sm">Try adjusting your search or clearing the filters.</p>
                    </div>
                )}
            </div>

            <footer className="text-center text-xs text-gray-400 mt-10">
                Data is static and dynamically filtered/simulated for demonstration purposes.
            </footer>
        </div>
    );
}