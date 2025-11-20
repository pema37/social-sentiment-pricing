

//import React from 'react';

import ViewAllLink from '../components/ViewAllLink.js';



const Sidebar = () => (
    <div className="flex flex-col w-64 bg-gray-900 text-white min-h-screen p-4 shadow-lg">
        <div className="text-xl font-extrabold mb-8 flex items-center">
            <span className="text-blue-400 mr-2">SSP</span> Social Sentiment
        </div>
        <nav className="space-y-2">
            {[
                { name: 'Dashboard', icon: '🏠', active: true, href: '/dashboard' },
                { name: 'Products', icon: '📦', href: '/dashboard/products' },
                { name: 'Competitors', icon: '🤝', href: '/competitors' },
                { name: 'Sentiment', icon: '📈', href: '/sentiment' },
                { name: 'Price Suggestions', icon: '$', href: '/price-suggestions' },
                { name: 'Settings', icon: '⚙️', href: '/settings' },
                { name: 'API Keys', icon: '🔑', href: '/api-keys' },
                { name: 'Admin', icon: '👤', href: '/admin' },
            ].map((item) => (
                
                <a 
                    key={item.name}
                    href={item.href}
                    className={`flex items-center p-2 rounded-lg transition-colors duration-200 ${
                        item.active
                            ? 'bg-blue-600 text-white shadow-md'
                            : 'hover:bg-gray-700 text-gray-300'
                    }`}
                >
                    <span className="text-xl mr-3">{item.icon}</span>
                    <span className="font-medium">{item.name}</span>
                </a>
            ))}
        </nav>
    </div>
);

const StatCard = ({ title, value, detail, icon, color }) => (
    <div className="bg-white p-5 rounded-lg shadow-sm flex-grow border border-gray-200">
        <div className="flex justify-between items-start">
            <div>
                <p className="text-sm font-medium text-gray-500">{title}</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
            </div>
            <div className={`p-2 rounded-full ${color} bg-opacity-30`}>
                <span className="text-xl">{icon}</span>
            </div>
        </div>
        {detail && (
            <p className="mt-2 text-xs font-medium text-green-600 flex items-center">
                <span className="mr-1">▲</span> {detail}
            </p>
        )}
    </div>
);

const PriceSuggestionsTable = () => {
    const suggestions = [
        { product: 'Premium Headphones', current: 299, suggested: 279, sentiment: '+12%' },
        { product: 'Wireless Earbuds', current: 129, suggested: 149, sentiment: '+18%' },
        { product: 'Smart Watch Pro', current: 399, suggested: 379, sentiment: '-5%' },
        { product: 'Fitness Tracker', current: 89, suggested: 99, sentiment: '+22%' },
    ];

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-800">Latest Price Suggestions</h2>
                
                {/* 🎯 Using the Client Component wrapper for the Link */}
                <ViewAllLink 
                    href="/price-suggestions" 
                    text="View All" 
                />
                
            </div>
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Product</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Current Price</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Suggested Price</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sentiment</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {suggestions.map((item, index) => (
                            <tr key={index}>
                                <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.product}</td>
                                <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">${item.current}</td>
                                <td className="px-4 py-4 whitespace-nowrap text-sm font-bold text-gray-800">${item.suggested}</td>
                                <td className="px-4 py-4 whitespace-nowrap text-sm">
                                    <span className={item.sentiment.startsWith('+') ? 'text-green-600' : 'text-red-600'}>
                                        {item.sentiment}
                                    </span>
                                </td>
                                <td className="px-4 py-4 whitespace-nowrap text-sm space-x-2">
                                    <button className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-1 px-3 rounded-md transition-colors text-xs">Accept</button>
                                    <button className="bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-1 px-3 rounded-md transition-colors text-xs">Ignore</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

const PlaceholderGraph = ({ title, dataPoints, isBarChart = false, labels = [] }) => {
    // --- Graph rendering logic (simplified) ---
    const maxVal = Math.max(...dataPoints);
    const minVal = Math.min(...dataPoints);
    const range = maxVal - minVal;

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex flex-col h-full">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">{title}</h2>
            <div className="flex-grow relative h-48">
                {/* Y-Axis Labels (simplified) */}
                <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-gray-500 pr-2">
                    <span>{maxVal}</span>
                    <span>{Math.round(maxVal - range / 2)}</span>
                    <span>{minVal}</span>
                </div>
                <div className="absolute left-8 right-0 bottom-0 top-0">
                     {/* X-Axis Labels */}
                    <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-gray-500 pt-2">
                        {labels.map((label, i) => (
                            <span key={i} className="text-[10px] sm:text-xs text-gray-500 mx-1">{label}</span>
                        ))}
                    </div>

                    {isBarChart ? (
                        // Bar Chart Visual
                        <div className="flex items-end h-full w-full justify-around pt-4 pb-6">
                            {dataPoints.map((value, index) => (
                                <div
                                    key={index}
                                    style={{ height: `${((value - minVal) / range) * 90 + 10}%` }}
                                    className="w-8 bg-blue-500 rounded-t-md mx-1 shadow-md hover:bg-blue-600 transition-colors duration-200"
                                    title={`Value: ${value}`}
                                ></div>
                            ))}
                        </div>
                    ) : (
                        // Line Chart Visual
                        <svg className="w-full h-full absolute" viewBox="0 0 100 100" preserveAspectRatio="none">
                            <line x1="0" y1="100" x2="100" y2="100" stroke="#e0e0e0" strokeWidth="0.5"/>
                            <line x1="0" y1="50" x2="100" y2="50" stroke="#e0e0e0" strokeDasharray="2 2" strokeWidth="0.5"/>
                            <polyline
                                fill="none"
                                stroke="#3b82f6"
                                strokeWidth="3"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                points={dataPoints.map((val, i) =>
                                    `${(i / (dataPoints.length - 1)) * 100},${100 - ((val - minVal) / range) * 90 - 5}`
                                ).join(' ')}
                            />
                            {dataPoints.map((val, i) => (
                                <circle
                                    key={i}
                                    cx={`${(i / (dataPoints.length - 1)) * 100}`}
                                    cy={`${100 - ((val - minVal) / range) * 90 - 5}`}
                                    r="2"
                                    fill="#3b82f6"
                                    stroke="white"
                                    strokeWidth="1"
                                />
                            ))}
                        </svg>
                    )}
                </div>
            </div>
        </div>
    );
};

// --- Main Page Component ---
export default function DashboardPage() {
    // Placeholder data
    const sentimentData = [70, 75, 80, 72, 85, 90, 92]; 
    const sentimentLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    const revenueData = [13000, 15000, 14500, 17000, 19000, 22000, 25000];
    const revenueLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']; 

    return (
        <div className="flex bg-gray-100 min-h-screen">
            <Sidebar />
            <main className="flex-1">
                {/* Top Bar (Blue) */}
                <header className="bg-blue-700 text-white p-4 shadow-md flex justify-between items-center px-8">
                    <h1 className="text-2xl font-bold">Dashboard</h1>
                    <button className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow transition-colors duration-200">
                        Refresh Data
                    </button>
                </header>

                <div className="p-8">
                    <p className="text-gray-600 mb-6">Monitor your pricing and sentiment analytics</p>

                    {/* Top Stat Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                        <StatCard title="Products Tracked" value="24" detail="+3 this month" icon="📦" color="text-blue-600"/>
                        <StatCard title="Avg Sentiment" value="88%" detail="+5% from last week" icon="📈" color="text-green-600"/>
                        <StatCard title="Pending Suggestions" value="12" detail="Awaiting review" icon="$" color="text-yellow-600"/>
                        <StatCard title="Competitors" value="8" detail="Actively monitoring" icon="🤝" color="text-purple-600"/>
                    </div>

                    {/* Charts Section */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                        <PlaceholderGraph
                            title="Sentiment Trend"
                            dataPoints={sentimentData}
                            labels={sentimentLabels}
                            isBarChart={false}
                        />
                        <PlaceholderGraph
                            title="Revenue Impact"
                            dataPoints={revenueData}
                            labels={revenueLabels}
                            isBarChart={true}
                        />
                    </div>

                    {/* Price Suggestions Table */}
                    <PriceSuggestionsTable />
                </div>
            </main>
        </div>
    );
}