"use client";

import React, { useState } from "react";
import { 
    Plus, 
    Search, 
    TrendingUp, 
    TrendingDown, 
    AlertTriangle,
    RefreshCw, 
    ArrowLeft, // Used for back navigation
    ExternalLink,
    CheckCircle,
} from 'lucide-react';

// --- Data Types ---
interface Competitor {
    id: string;
    competitor: string;
    productName: string;
    theirPrice: number;
    ourPrice: number;
    difference: number; // calculated field
    lastSync: string; // e.g., "5 min ago"
    sentiment: number; // e.g., 0.05
    url: string;
}

type Page = 'list' | 'add' | 'details';

// --- Mock Data Set (Static Data for pure Frontend) ---
const MOCK_COMPETITORS_DATA: Competitor[] = [
    // Pre-calculate difference for simplicity
    { id: '1', competitor: "AudioTech Pro", productName: "Premium Headphones", theirPrice: 399, ourPrice: 380, difference: -4.76, lastSync: "5 min ago", sentiment: 0.05, url: "https://www.audiotechpro.com/headphones" },
    { id: '2', competitor: "SoundWave", productName: "Wireless Earbuds", theirPrice: 139, ourPrice: 129, difference: -7.19, lastSync: "10 min ago", sentiment: -0.07, url: "https://www.soundwave.net/earbuds" },
    { id: '3', competitor: "TechGear Inc.", productName: "Smart Watch", theirPrice: 379, ourPrice: 390, difference: 2.90, lastSync: "10 min ago", sentiment: 0.03, url: "https://www.techgearinc.com/watch" },
    { id: '4', competitor: "FitnessPro", productName: "Fitness Tracker", theirPrice: 89, ourPrice: 79, difference: -11.24, lastSync: "15 min ago", sentiment: -0.10, url: "https://www.fitnesspro.io/tracker" },
    { id: '5', competitor: "AudioMax", productName: "Bluetooth Speaker", theirPrice: 169, ourPrice: 159, difference: -5.92, lastSync: "20 min ago", sentiment: -0.05, url: "https://www.audiomax.co/speaker" },
];

// --- Utility Components ---

// Displays an error message banner
const AlertBanner: React.FC<{ message: string; type?: 'error' | 'success' }> = ({ message, type = 'error' }) => {
    const isError = type === 'error';
    const colorClass = isError ? 'text-red-800 bg-red-100 border-red-300' : 'text-green-800 bg-green-100 border-green-300';
    const Icon = isError ? AlertTriangle : CheckCircle;

    return (
        <div className={`flex items-center p-3 mb-4 text-sm font-medium rounded-lg shadow-md border ${colorClass}`}>
            <Icon className={`w-5 h-5 mr-2 ${isError ? 'text-red-600' : 'text-green-600'}`} />
            <span>{message}</span>
        </div>
    );
};

// Displays the percentage difference visually
const PriceDifference: React.FC<{ value: number }> = ({ value }) => {
    // Difference is (Our Price - Their Price) / Their Price. 
    // Positive means our price is higher (bad), Negative means our price is lower (good)
    const isPositive = value > 0;
    const colorClass = isPositive ? "text-red-600 bg-red-50" : "text-green-600 bg-green-50";
    const Icon = isPositive ? TrendingUp : TrendingDown;

    return (
        <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${colorClass}`}>
            <Icon className="w-3 h-3 mr-1" />
            {Math.abs(value).toFixed(2)}%
        </span>
    );
};

// --- Page Components ---

const AddCompetitorPage: React.FC<{ onBack: () => void }> = ({ onBack }) => {
    const [status, setStatus] = useState<'initial' | 'saving' | 'success'>('initial');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setStatus('saving');
        // Simulate API delay
        setTimeout(() => {
            setStatus('success');
            // In a real app, this would send data to the backend
            console.log("Competitor added successfully (simulated)");
        }, 1500);
    };

    return (
        <div className="max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-lg">
            <button onClick={onBack} className="flex items-center text-blue-600 hover:text-blue-800 mb-6 font-medium">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Competitors List
            </button>
            <h2 className="text-2xl font-bold text-gray-900 mb-6 border-b pb-2">Add New Competitor Source</h2>

            {status === 'success' && (
                <AlertBanner 
                    message="Competitor successfully simulated and tracked! Return to the list to see data updates." 
                    type="success" 
                />
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="compName" className="block text-sm font-medium text-gray-700">Competitor Name</label>
                    <input 
                        type="text" 
                        id="compName" 
                        required 
                        placeholder="e.g., TechGiant Co."
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                    />
                </div>
                <div>
                    <label htmlFor="productUrl" className="block text-sm font-medium text-gray-700">Product URL to Track</label>
                    <input 
                        type="url" 
                        id="productUrl" 
                        required 
                        placeholder="e.g., https://www.techgiant.com/product-x"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                    />
                </div>
                <div>
                    <label htmlFor="ourProduct" className="block text-sm font-medium text-gray-700">Our Matching Product</label>
                    <select 
                        id="ourProduct" 
                        required
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border bg-white"
                    >
                        <option value="">Select our product...</option>
                        <option value="headphones">Premium Headphones</option>
                        <option value="earbuds">Wireless Earbuds</option>
                        <option value="watch">Smart Watch</option>
                    </select>
                </div>

                <div className="pt-4 flex justify-end">
                    <button
                        type="submit"
                        disabled={status === 'saving'}
                        className="flex items-center space-x-2 px-6 py-2 text-sm font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition duration-200 shadow-md disabled:bg-blue-400"
                    >
                        {status === 'saving' ? (
                            <>
                                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                                <span>Adding...</span>
                            </>
                        ) : (
                            <>
                                <Plus className="w-4 h-4" />
                                <span>Submit for Tracking</span>
                            </>
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
};

const ViewCompetitorDetails: React.FC<{ competitor: Competitor, onBack: () => void }> = ({ competitor, onBack }) => {
    const formatCurrency = (amount: number) => 
        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(amount);

    const formatSentiment = (value: number) => {
        if (value > 0.03) return { text: "Positive Trend", color: "text-green-600", icon: TrendingUp };
        if (value < -0.03) return { text: "Negative Trend", color: "text-red-600", icon: TrendingDown };
        return { text: "Neutral Trend", color: "text-gray-500", icon: ExternalLink }; // Use ExternalLink as a neutral icon placeholder
    };

    const sentimentData = formatSentiment(competitor.sentiment);
    const SentimentIcon = sentimentData.icon;

    return (
        <div className="max-w-4xl mx-auto p-8 bg-white rounded-xl shadow-2xl border border-gray-100">
            <button onClick={onBack} className="flex items-center text-blue-600 hover:text-blue-800 mb-6 font-medium">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Competitors List
            </button>
            
            <header className="border-b pb-4 mb-6">
                <h2 className="text-3xl font-extrabold text-gray-900">{competitor.competitor}</h2>
                <p className="text-xl text-gray-600 mt-1">{competitor.productName} Match</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                {/* Price Card */}
                <div className="bg-blue-50 p-6 rounded-lg shadow-inner border-l-4 border-blue-400">
                    <h3 className="text-lg font-semibold text-blue-800 mb-3">Pricing Overview</h3>
                    <div className="space-y-3">
                        <p className="flex justify-between text-gray-700">
                            <span>Competitor Price:</span>
                            <span className="font-bold text-xl">{formatCurrency(competitor.theirPrice)}</span>
                        </p>
                        <p className="flex justify-between text-gray-700">
                            <span>Our Current Price:</span>
                            <span className="font-bold text-xl">{formatCurrency(competitor.ourPrice)}</span>
                        </p>
                        <p className="flex justify-between items-center pt-2 border-t border-blue-200">
                            <span className="font-semibold text-gray-900">Price Difference:</span>
                            <PriceDifference value={competitor.difference} />
                        </p>
                    </div>
                </div>

                {/* Tracking Card */}
                <div className="bg-gray-50 p-6 rounded-lg shadow-inner border-l-4 border-gray-400">
                    <h3 className="text-lg font-semibold text-gray-800 mb-3">Tracking & Sentiment</h3>
                    <div className="space-y-3">
                        <p className="flex justify-between text-gray-700">
                            <span>Last Synchronized:</span>
                            <span className="font-medium text-gray-900">{competitor.lastSync}</span>
                        </p>
                        <p className="flex justify-between items-center text-gray-700">
                            <span>Market Sentiment:</span>
                            <span className={`flex items-center font-bold ${sentimentData.color}`}>
                                <SentimentIcon className="w-4 h-4 mr-1" />
                                {sentimentData.text} ({competitor.sentiment.toFixed(2)})
                            </span>
                        </p>
                        <p className="pt-2 border-t border-gray-200">
                             <a 
                                href={competitor.url} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="inline-flex items-center text-sm font-semibold text-blue-600 hover:text-blue-800 transition-colors"
                            >
                                <ExternalLink className="w-4 h-4 mr-1" />
                                View Competitor's Product Page
                            </a>
                        </p>
                    </div>
                </div>
            </div>

            <div className="mt-8 pt-4 border-t text-sm text-gray-500">
                This section would normally contain historical pricing charts, detailed sentiment analysis, and action logs for this specific competitor.
            </div>
        </div>
    );
};


// --- Competitors List Screen (Original logic, refactored) ---
const CompetitorsListScreen: React.FC<{ 
    competitors: Competitor[];
    onAddCompetitor: () => void;
    onViewDetails: (competitor: Competitor) => void;
}> = ({ competitors, onAddCompetitor, onViewDetails }) => {
    
    const [searchTerm, setSearchTerm] = useState<string>("");
    const [pageError, setPageError] = useState<string | null>(null);
    const isLoading = false; 

    // 1. Filtering Logic (Client-side)
    const filteredCompetitors = competitors.filter(c =>
        c.competitor.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.productName.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Handles the "Sync All" button click
    const handleSyncAll = () => {
        setPageError("The 'Sync All' feature requires a backend integration and is not implemented.");
        console.log("Simulating Sync All action.");
    };

    return (
        <div className="p-4 md:p-8 bg-gray-50 min-h-screen">
            <header className="mb-8">
                <h1 className="text-3xl font-extrabold text-gray-900">Competitor Price Tracking</h1>
                <p className="text-gray-500 mt-1">Track competitor pricing and stay competitive.</p>
            </header>

            {pageError && <AlertBanner message={pageError} />}

            {/* Controls Bar */}
            <div className="flex flex-col md:flex-row justify-between items-center mb-6 space-y-4 md:space-y-0">
                {/* Search Bar */}
                <div className="relative w-full md:w-80">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search competitors..."
                        className="w-full py-2 pl-10 pr-4 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition duration-150"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                {/* Actions */}
                <div className="flex space-x-3">
                    <button
                        onClick={handleSyncAll}
                        className="flex items-center space-x-2 px-4 py-2 text-sm font-semibold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors border border-gray-300 shadow-sm"
                        disabled={isLoading}
                    >
                        <RefreshCw className="w-4 h-4" />
                        <span>Sync All</span>
                    </button>
                    <button
                        onClick={onAddCompetitor}
                        className="flex items-center space-x-2 px-4 py-2 text-sm font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition duration-200 shadow-md shadow-blue-500/50"
                    >
                        <Plus className="w-4 h-4" />
                        <span>Add Competitor</span>
                    </button>
                </div>
            </div>

            {/* Competitors Table */}
            <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-100">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Competitor
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Product Name
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Their Price
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Our Price
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Difference
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Sentiment
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Last Sync
                                </th>
                                <th className="px-6 py-3 text-center text-xs font-semibold text-gray-600 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {filteredCompetitors.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="py-10 text-center text-gray-500">
                                        No competitors found matching "{searchTerm}".
                                    </td>
                                </tr>
                            ) : (
                                filteredCompetitors.map((item) => (
                                    <tr key={item.id} className="hover:bg-blue-50 transition-colors">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                            {item.competitor}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                            {item.productName}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-700 text-right">
                                            ${item.theirPrice.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-700 text-right">
                                            ${item.ourPrice.toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                                            <PriceDifference value={item.difference} />
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-700 text-right">
                                            <span className={`font-semibold ${item.sentiment > 0 ? 'text-green-600' : item.sentiment < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                                                {item.sentiment.toFixed(2)}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-right">
                                            {item.lastSync}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-center font-medium">
                                            {/* ACTION BUTTON: VIEW DETAILS */}
                                            <button
                                                onClick={() => onViewDetails(item)}
                                                className="text-blue-600 hover:text-blue-800 transition-colors inline-flex items-center space-x-1 font-semibold p-2 rounded-lg bg-blue-100 hover:bg-blue-200"
                                            >
                                                <span className="mr-1">👁️</span> View
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <footer className="text-center text-xs text-gray-400 mt-6">
                Data is static (mock data) for this front-end only view.
            </footer>
        </div>
    );
};

// --- Main App Component (Client-side Router) ---
export default function App() {
    // State to manage the current view/page
    const [currentPage, setCurrentPage] = useState<Page>('list');
    // State to hold data for the competitor whose details are being viewed
    const [selectedCompetitor, setSelectedCompetitor] = useState<Competitor | null>(null);

    const handleViewDetails = (competitor: Competitor) => {
        setSelectedCompetitor(competitor);
        setCurrentPage('details');
    };

    const handleBack = () => {
        setCurrentPage('list');
        setSelectedCompetitor(null);
    };

    switch (currentPage) {
        case 'add':
            return <AddCompetitorPage onBack={handleBack} />;
        case 'details':
            // Render details page only if a competitor is selected
            if (selectedCompetitor) {
                return <ViewCompetitorDetails competitor={selectedCompetitor} onBack={handleBack} />;
            }
            // Fallback to list if details view is somehow entered without selection
            return <CompetitorsListScreen 
                competitors={MOCK_COMPETITORS_DATA}
                onAddCompetitor={() => setCurrentPage('add')}
                onViewDetails={handleViewDetails}
            />;
        case 'list':
        default:
            return <CompetitorsListScreen 
                competitors={MOCK_COMPETITORS_DATA}
                onAddCompetitor={() => setCurrentPage('add')}
                onViewDetails={handleViewDetails}
            />;
    }
}