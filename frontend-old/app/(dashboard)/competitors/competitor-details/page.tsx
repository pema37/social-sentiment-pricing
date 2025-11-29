"use client";

import React, { useState } from "react";
import { 
    // Icons required for the entire app
    Link, Clock, Plus, AlertTriangle, X, CheckCircle, RefreshCw, 
    Search, TrendingUp, TrendingDown, ArrowLeft, ExternalLink, 
} from 'lucide-react';

// --- Data Types ---

// Data structure for an item in the main competitor list
interface Competitor {
    id: string;
    competitor: string;
    productName: string;
    theirPrice: number;
    ourPrice: number;
    difference: number; // calculated field
    lastSync: string; // e.g., "5 min ago"
    sentiment: number; // e.g., 0.05
}

// Data structure for the ADD competitor form
interface CompetitorFormData {
    name: string;
    product: string;
    url: string; 
    frequency: string;
}

// Data structure for the page router
type Page = 'list' | 'add' | 'details';

// --- Mock Data Set (Static Data for pure Frontend) ---
const MOCK_COMPETITORS_DATA: Competitor[] = [
    { id: '1', competitor: "AudioTech Pro", productName: "Premium Headphones", theirPrice: 399, ourPrice: 380, difference: -4.76, lastSync: "5 min ago", sentiment: 0.05 },
    { id: '2', competitor: "SoundWave", productName: "Wireless Earbuds", theirPrice: 139, ourPrice: 129, difference: -7.19, lastSync: "10 min ago", sentiment: -0.07 },
    { id: '3', competitor: "TechGear Inc.", productName: "Smart Watch", theirPrice: 379, ourPrice: 390, difference: 2.90, lastSync: "10 min ago", sentiment: 0.03 },
    { id: '4', competitor: "FitnessPro", productName: "Fitness Tracker", theirPrice: 89, ourPrice: 79, difference: -11.24, lastSync: "15 min ago", sentiment: -0.10 },
    { id: '5', competitor: "AudioMax", productName: "Bluetooth Speaker", theirPrice: 169, ourPrice: 159, difference: -5.92, lastSync: "20 min ago", sentiment: -0.05 },
];

// --- Utility Components ---

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

const ErrorMessage: React.FC<{ message: string; onClose: () => void }> = ({ message, onClose }) => (
    <div className="flex items-center justify-between p-3 mb-4 text-sm font-medium text-red-800 bg-red-100 rounded-lg shadow-md border border-red-300">
        <div className="flex items-center">
            <AlertTriangle className="w-5 h-5 mr-2 text-red-600" />
            <span>{message}</span>
        </div>
        <button
            onClick={onClose}
            className="p-1 rounded-full text-red-600 hover:bg-red-200 transition-colors"
            aria-label="Close alert"
        >
            <X className="w-4 h-4" />
        </button>
    </div>
);

const PriceDifference: React.FC<{ value: number }> = ({ value }) => {
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

// 1. ADD COMPETITOR PAGE
const AddCompetitorPage: React.FC<{ onBack: () => void }> = ({ onBack }) => {
    const [formData, setFormData] = useState<CompetitorFormData>({
        name: "",
        product: "",
        url: "",
        frequency: "Daily", 
    });
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submissionSuccess, setSubmissionSuccess] = useState(false);

    const SYNC_FREQUENCIES = ["Hourly", "Daily", "Weekly", "Monthly"];
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
        setErrorMessage(null); 
    };

    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMessage(null);
        setSubmissionSuccess(false);

        const urlRegex = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
        if (!urlRegex.test(formData.url)) {
            setErrorMessage("Please enter a valid URL (starting with http:// or https:// is recommended).");
            return;
        }

        if (formData.frequency === "") {
             setErrorMessage("Please select a sync frequency.");
             return;
        }

        setIsSubmitting(true);
        console.log("Submitting Competitor Data:", formData);

        setTimeout(() => {
            setIsSubmitting(false);
            setSubmissionSuccess(true);
            
            setFormData({
                name: "",
                product: "",
                url: "",
                frequency: "Daily",
            });
            console.log("Competitor added successfully!");
        }, 1500);
    };

    const handleCancel = () => {
        console.log("Competitor creation cancelled.");
        onBack();
    };
    
    return (
        <div className="min-h-screen bg-gray-100 flex items-start justify-center p-4 md:p-10 font-sans">
            <div className="bg-white shadow-2xl rounded-xl p-6 sm:p-8 w-full max-w-lg border border-gray-200 mt-10">

                <h2 className="text-3xl font-extrabold text-gray-900 mb-6">
                    Add Competitor
                </h2>

                {errorMessage && (
                    <ErrorMessage 
                        message={errorMessage} 
                        onClose={() => setErrorMessage(null)} 
                    />
                )}

                {submissionSuccess && (
                    <div className="flex items-center justify-between p-3 mb-4 text-sm font-medium text-green-800 bg-green-100 rounded-lg shadow-md border border-green-300">
                        <div className="flex items-center">
                            <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
                            <span>Competitor successfully added and monitoring has started!</span>
                        </div>
                        <button
                            onClick={onBack}
                            className="text-sm font-semibold text-blue-600 hover:text-blue-800 transition-colors"
                        >
                            Go to List
                        </button>
                    </div>
                )}

                <form onSubmit={handleFormSubmit} className="space-y-6">

                    {/* Competitor Name */}
                    <div>
                        <label htmlFor="name" className="block text-sm text-gray-700 font-bold mb-1">
                            Competitor Name
                        </label>
                        <input
                            id="name"
                            name="name"
                            type="text"
                            required
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition duration-150 placeholder-gray-400"
                            placeholder="Enter competitor name"
                            value={formData.name}
                            onChange={handleChange}
                        />
                    </div>

                    {/* Product to Track */}
                    <div>
                        <label htmlFor="product" className="block text-sm text-gray-700 font-bold mb-1">
                            Product to Track
                        </label>
                        <input
                            id="product"
                            name="product"
                            type="text"
                            required
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 transition duration-150 placeholder-gray-400"
                            placeholder="Which product to compare"
                            value={formData.product}
                            onChange={handleChange}
                        />
                    </div>

                    {/* Competitor URL */}
                    <div className="relative">
                        <label htmlFor="url" className="block text-sm text-gray-700 font-bold mb-1">
                            Competitor URL (Required for tracking)
                        </label>
                        <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
                            <Link className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
                            <input
                                id="url"
                                name="url"
                                type="url"
                                required
                                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                                placeholder="https://..."
                                value={formData.url}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Sync Frequency */}
                    <div className="relative">
                        <label htmlFor="frequency" className="block text-sm text-gray-700 font-bold mb-1">
                            Sync Frequency
                        </label>
                        <div className="relative">
                            <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                            <select
                                id="frequency"
                                name="frequency"
                                required
                                className="w-full px-4 py-3 pl-10 border border-gray-300 rounded-lg appearance-none bg-white focus:ring-blue-500 focus:border-blue-500 transition duration-150"
                                value={formData.frequency}
                                onChange={handleChange}
                            >
                                {SYNC_FREQUENCIES.map(freq => (
                                    <option key={freq} value={freq}>
                                        {freq}
                                    </option>
                                ))}
                            </select>
                            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
                                <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                                    <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                                </svg>
                            </div>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end space-x-3 pt-4">
                        <button
                            type="button"
                            onClick={handleCancel}
                            disabled={isSubmitting}
                            className="px-6 py-3 text-sm font-bold text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors border border-gray-300 shadow-sm disabled:opacity-50"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="flex items-center space-x-2 px-6 py-3 text-sm font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition duration-200 shadow-lg shadow-blue-500/50 disabled:opacity-50"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? (
                                <>
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                    <span>Adding...</span>
                                </>
                            ) : (
                                <>
                                    <Plus className="w-4 h-4" />
                                    <span>Add Competitor</span>
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};


// 2. VIEW COMPETITOR DETAILS PAGE (Simulates the /competitor/competitor-details.tsx page)
const ViewCompetitorDetails: React.FC<{ 
    competitor: Competitor, 
    onBack: () => void,
}> = ({ competitor, onBack }) => {
    const formatCurrency = (amount: number) => 
        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }).format(amount);

    const formatSentiment = (value: number) => {
        if (value > 0.03) return { text: "Positive Trend", color: "text-green-600", icon: TrendingUp };
        if (value < -0.03) return { text: "Negative Trend", color: "text-red-600", icon: TrendingDown };
        return { text: "Neutral Trend", color: "text-gray-500", icon: ExternalLink };
    };

    const sentimentData = formatSentiment(competitor.sentiment);
    const SentimentIcon = sentimentData.icon;

    return (
        <div className="max-w-4xl mx-auto p-8 bg-white rounded-xl shadow-2xl border border-gray-100 mt-4">
            <div className="flex justify-between items-center mb-6">
                <button onClick={onBack} className="flex items-center text-blue-600 hover:text-blue-800 font-medium">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Competitors List
                </button>
            </div>
            
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
                            <span>Competitor ID:</span>
                            <span className="font-medium text-gray-900">{competitor.id}</span>
                        </p>
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
                    </div>
                </div>
            </div>

            <div className="mt-8 pt-4 border-t text-sm text-gray-500">
                This simulated page path is <code className="bg-gray-100 p-1 rounded text-red-500">/competitor/competitor-details.tsx</code>.
            </div>
        </div>
    );
};


// 3. COMPETITORS LIST SCREEN (The main landing page)
const CompetitorsListScreen: React.FC<{ 
    competitors: Competitor[];
    onAddCompetitor: () => void;
    onViewDetails: (competitor: Competitor) => void;
}> = ({ competitors, onAddCompetitor, onViewDetails }) => {
    
    const [searchTerm, setSearchTerm] = useState<string>("");
    const [pageError, setPageError] = useState<string | null>(null);
    const isLoading = false; 

    // Filtering Logic (Client-side)
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
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-extrabold text-gray-900">Competitor Price Tracking</h1>
                    <p className="text-gray-500 mt-1">Track competitor pricing and stay competitive.</p>
                </div>
                {/* No extra button here */}
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
                                    Action
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
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                            {/* Clicking the competitor name takes you to details */}
                                            <button
                                                onClick={() => onViewDetails(item)}
                                                className="text-blue-600 hover:text-blue-800 transition-colors font-bold text-base hover:underline"
                                            >
                                                {item.competitor}
                                            </button>
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
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                                            {/* Clicking 'View Products' takes you to details */}
                                            <button
                                                onClick={() => onViewDetails(item)}
                                                className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                                            >
                                                View Products
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
    const [currentPage, setCurrentPage] = useState<Page>('list');
    const [selectedCompetitor, setSelectedCompetitor] = useState<Competitor | null>(null);

    // Function to handle internal navigation to the details view
    const handleViewDetails = (competitor: Competitor) => {
        setSelectedCompetitor(competitor);
        setCurrentPage('details');
        // This simulates navigating to /competitor/competitor-details.tsx
        console.log(`Navigating to full details page for Competitor ID: ${competitor.id}`);
    };

    const handleBack = () => {
        setCurrentPage('list'); // Only two steps now: list or details
        setSelectedCompetitor(null);
    };

    switch (currentPage) {
        case 'add':
            return <AddCompetitorPage onBack={handleBack} />;
            
        case 'details':
            if (selectedCompetitor) {
                return <ViewCompetitorDetails 
                    competitor={selectedCompetitor} 
                    onBack={handleBack}
                />;
            }
            // Fallthrough if selectedCompetitor is null
            break; 
            
        case 'list':
        default:
            return <CompetitorsListScreen 
                competitors={MOCK_COMPETITORS_DATA}
                onAddCompetitor={() => setCurrentPage('add')}
                onViewDetails={handleViewDetails}
            />;
    }
    // Default render for fallbacks
    return <CompetitorsListScreen 
        competitors={MOCK_COMPETITORS_DATA}
        onAddCompetitor={() => setCurrentPage('add')}
        onViewDetails={handleViewDetails}
    />;
}