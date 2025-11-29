import React from 'react';
// import Link from 'next/link'; // REMOVED: Next.js specific import causing build error

// NOTE: We will use standard anchor tags (<a>) instead of Next.js Link components
// to ensure the code compiles and runs in this single-file React environment.

// --- 1. INTERFACE DEFINITIONS ---

// Define the shape of props for the StatCard component
interface StatCardProps {
    title: string;
    // Value can be a string (like "88%") or a number (like 24 or 12)
    value: string | number; 
    detail?: string;
    icon: string;
    color: string;
}

// Define the shape of data for the price suggestions table rows
interface Suggestion {
    product: string;
    current: number;
    suggested: number;
    sentiment: string;
}

// Define the shape of props for the generic graph component
interface GraphProps {
    title: string;
    dataPoints: number[];
    isBarChart?: boolean; // Default is false (line chart)
    labels: string[];
}

// --- 2. CORE HELPER COMPONENTS (Now typed with React.FC) ---

const StatCard: React.FC<StatCardProps> = ({ title, value, detail, icon, color }) => (
    // REFINED: Removed w-full/sm:w-1/2/lg:w-1/4 and mb-* classes. The parent grid now handles sizing and spacing perfectly.
    <div className="bg-white p-5 rounded-lg shadow-sm border border-gray-200"> 
        <div className="flex justify-between items-start">
            <div>
                <p className="text-sm font-medium text-gray-500">{title}</p>
                {/* Value is now correctly typed as string | number */}
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

// Placeholder for ViewAllLink - Replaced Link with <a>
const ViewAllLink: React.FC<{ href: string; text: string }> = ({ href, text }) => (
    <a 
        href={href} 
        className="text-blue-600 hover:text-blue-800 text-sm font-medium transition-colors"
    >
        {text}
    </a>
);


const PriceSuggestionsTable: React.FC = () => {
    // Data is typed as Suggestion[]
    const suggestions: Suggestion[] = [
        { product: 'Premium Headphones', current: 299, suggested: 279, sentiment: '+12%' },
        { product: 'Wireless Earbuds', current: 129, suggested: 149, sentiment: '+18%' },
        { product: 'Smart Watch Pro', current: 399, suggested: 379, sentiment: '-5%' },
        { product: 'Fitness Tracker', current: 89, suggested: 99, sentiment: '+22%' },
    ];

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-gray-800">Latest Price Suggestions</h2>
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

const PlaceholderGraph: React.FC<GraphProps> = ({ title, dataPoints, isBarChart = false, labels }) => {
    // TypeScript ensures dataPoints is number[] and labels is string[]
    const maxVal = Math.max(...dataPoints);
    const minVal = Math.min(...dataPoints);
    const range = maxVal - minVal;

    return (
        // Graph component remains w-full lg:w-1/2 to manage its width within the flex container below
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex flex-col h-full w-full lg:w-1/2">
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
                        </svg>
                    )}
                </div>
            </div>
        </div>
    );
};

// --- 3. MAIN PAGE COMPONENT (Exported by default) ---
// Note: This component assumes a parent layout provides the Sidebar.
export default function DashboardPage(): JSX.Element {
    // Data is now strongly typed (number[])
    const sentimentData: number[] = [70, 75, 80, 72, 85, 90, 92]; 
    const sentimentLabels: string[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    const revenueData: number[] = [13000, 15000, 14500, 17000, 19000, 22000, 25000];
    const revenueLabels: string[] = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']; 

    return (
        <div className="flex flex-col bg-gray-100 min-h-screen"> 
            {/* The primary content will start here. The parent component is responsible for the overall layout (Sidebar + Main Content). */}
            
            <header className="bg-white text-gray-900 p-4 shadow-sm border-b border-gray-200 flex justify-between items-center px-8">
                <h1 className="text-2xl font-bold">Dashboard Overview</h1>
                <button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg shadow-md transition-colors duration-200">
                    Refresh Data
                </button>
            </header>

            <main className="flex-1">
                <div className="p-8">
                    <p className="text-gray-600 mb-6">Monitor your pricing and sentiment analytics</p>

                    {/* Top Stat Cards - REVERTED to grid layout for clean, responsive horizontal distribution (4 columns on desktop) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        <StatCard title="Products Tracked" value={24} detail="+3 this month" icon="📦" color="text-blue-600"/>
                        <StatCard title="Avg Sentiment" value="88%" detail="+5% from last week" icon="📈" color="text-green-600"/>
                        <StatCard title="Pending Suggestions" value={12} detail="Awaiting review" icon="$" color="text-yellow-600"/>
                        <StatCard title="Competitors" value={8} detail="Actively monitoring" icon="🤝" color="text-purple-600"/>
                    </div>

                    {/* Charts Section - Remains responsive flex for side-by-side on desktop */}
                    <div className="flex flex-col lg:flex-row gap-6 mb-8">
                        <PlaceholderGraph
                            title="Sentiment Trend (Last 7 Days)"
                            dataPoints={sentimentData}
                            labels={sentimentLabels}
                            isBarChart={false}
                        />
                        <PlaceholderGraph
                            title="Revenue Impact (Last 7 Months)"
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